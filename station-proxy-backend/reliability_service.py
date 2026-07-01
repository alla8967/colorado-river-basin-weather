"""Serve reliability raster images, station overlays, and map metadata to the frontend.

It turns generated Paloma reliability artifacts into lightweight FastAPI responses and fallback test fixtures."""

from __future__ import annotations

import csv
import struct
import zlib
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.responses import FileResponse

from settings import BackendSettings

# settings configures imports for weather_reconstruction_model/scripts.
from common.csv_utils import read_csv_rows
from common.geo_utils import calculate_distance_km
from common.model_runs import load_json_file, resolve_model_run
from common.reliability_surface import (
    RELIABILITY_LAYERS,
    SURFACE_SCHEMA_VERSION,
    SUMMARY_SCHEMA_VERSION,
    normalize_layer,
)


MAX_PREDICTION_SERIES_POINTS = 800


class ReliabilitySurfaceService:
    """Loads model reliability surfaces from model_runs/paloma_v1_reliability."""

    def __init__(self, settings: BackendSettings) -> None:
        self.settings = settings
        self._holdout_master_rows: dict[str, dict[str, dict[str, str]]] = {}
        self._final_model_station_metric_rows: dict[str, dict[str, dict[str, str]]] = {}
        self._station_candidate_rows: dict[str, dict[str, dict[str, str]]] = {}
        self._terrain_feature_rows: dict[str, dict[str, str]] | None = None

    @property
    def root(self) -> Path:
        return self.settings.model_run_root / self.settings.reliability_model_run_id

    def summary_path(self) -> Path:
        return self.root / "reliability_summary.json"

    def surface_path(self, layer: str) -> Path:
        return self.root / f"reliability_surface_{normalize_layer(layer)}.json"

    def image_path(self, layer: str) -> Path:
        return self.root / f"reliability_surface_{normalize_layer(layer)}.png"

    def station_overlay_image_path(self, layer: str, mode: str) -> Path:
        normalized_mode = self.normalize_station_overlay_mode(mode)
        return self.root / f"reliability_station_overlay_{normalize_layer(layer)}_{normalized_mode}.png"

    def summary(self) -> dict[str, Any]:
        path = self.summary_path()
        if not path.exists():
            raise self.not_found_error("Reliability summary is unavailable.", path)

        payload = load_json_file(path)
        if payload.get("schemaVersion") != SUMMARY_SCHEMA_VERSION:
            raise self.validation_error("Reliability summary failed schema validation.")
        if payload.get("modelRunId") != self.settings.reliability_model_run_id:
            raise self.validation_error("Reliability summary modelRunId does not match settings.")

        payload["surfaceBaseUrl"] = "/model-runs/reliability/surface"
        payload["imageBaseUrl"] = "/model-runs/reliability/surface.png"
        return payload

    def surface(self, layer: str) -> dict[str, Any]:
        normalized_layer = normalize_layer(layer)
        path = self.surface_path(normalized_layer)
        if not path.exists():
            raise self.not_found_error(f"Reliability surface is unavailable: {normalized_layer}.", path)

        payload = load_json_file(path)
        if payload.get("schemaVersion") != SURFACE_SCHEMA_VERSION:
            raise self.validation_error(f"Reliability surface failed schema validation: {normalized_layer}.")
        if payload.get("layer") != normalized_layer:
            raise self.validation_error(f"Reliability surface layer mismatch: {normalized_layer}.")
        if payload.get("modelRunId") != self.settings.reliability_model_run_id:
            raise self.validation_error(f"Reliability surface modelRunId mismatch: {normalized_layer}.")
        if not isinstance(payload.get("points"), list):
            raise self.validation_error(f"Reliability surface must include points: {normalized_layer}.")

        image_path = self.image_path(normalized_layer)
        if not image_path.exists():
            raise self.not_found_error(f"Reliability PNG is unavailable: {normalized_layer}.", image_path)

        visualization = payload.get("visualization") or {}
        visual_version = visualization.get("scaleVersion") or payload.get("scoreVersion") or "1"
        payload["imageUrl"] = (
            f"/model-runs/reliability/surface.png?layer={normalized_layer}"
            f"&visual={visual_version}"
        )
        payload["sampleUrl"] = f"/model-runs/reliability/sample?layer={normalized_layer}"
        payload["stationOverlayUrls"] = {
            "bias": f"/model-runs/reliability/station-overlay.png?layer={normalized_layer}&mode=bias",
            "correlation": f"/model-runs/reliability/station-overlay.png?layer={normalized_layer}&mode=correlation",
            "mae": f"/model-runs/reliability/station-overlay.png?layer={normalized_layer}&mode=mae",
            "rmse": f"/model-runs/reliability/station-overlay.png?layer={normalized_layer}&mode=rmse",
            "final-correlation": (
                f"/model-runs/reliability/station-overlay.png?layer={normalized_layer}"
                "&mode=final-correlation"
            ),
            "final-mae": f"/model-runs/reliability/station-overlay.png?layer={normalized_layer}&mode=final-mae",
            "final-rmse": f"/model-runs/reliability/station-overlay.png?layer={normalized_layer}&mode=final-rmse",
            "final-bias": f"/model-runs/reliability/station-overlay.png?layer={normalized_layer}&mode=final-bias",
        }
        self.enrich_holdout_stations(payload, normalized_layer)
        return payload

    def image_response(self, layer: str) -> FileResponse:
        normalized_layer = normalize_layer(layer)
        path = self.image_path(normalized_layer)
        if not path.exists():
            raise self.not_found_error(f"Reliability PNG is unavailable: {normalized_layer}.", path)

        return FileResponse(path, media_type="image/png")

    def station_overlay_image_response(self, layer: str, mode: str) -> FileResponse:
        normalized_layer = normalize_layer(layer)
        normalized_mode = self.normalize_station_overlay_mode(mode)
        path = self.station_overlay_image_path(normalized_layer, normalized_mode)
        if self.station_overlay_is_stale(normalized_layer, normalized_mode, path):
            self.write_station_overlay_image(normalized_layer, normalized_mode, path)

        return FileResponse(path, media_type="image/png")

    def station(self, layer: str, station_id: str) -> dict[str, Any]:
        normalized_layer = normalize_layer(layer)
        requested_station_id = station_id.strip()
        if not requested_station_id:
            raise self.validation_error("Station id is required.")

        payload = self.surface(normalized_layer)
        station = self.find_holdout_station(payload, requested_station_id)
        if station is None:
            raise self.not_found_error(
                f"Station is not available in reliability layer: {requested_station_id}.",
                self.surface_path(normalized_layer),
            )

        source_variable = self.station_source_variable(payload, station, normalized_layer)
        paloma_metrics = (
            self.paloma_station_metrics(source_variable, requested_station_id)
            if source_variable
            else None
        )
        fully_trained_metrics = (
            self.fully_trained_model_metrics(source_variable, requested_station_id)
            if source_variable
            else None
        )
        holdout_run = (
            self.station_holdout_master_metrics(source_variable, requested_station_id)
            if source_variable
            else None
        )
        station_profile = self.station_record_profile(requested_station_id)
        terrain_features = self.station_terrain_features(requested_station_id)

        return {
            "status": "ok",
            "layer": normalized_layer,
            "station": {
                "stationId": station.get("stationId") or requested_station_id,
                "stationName": station.get("stationName") or station.get("stationId") or requested_station_id,
                "latitude": station.get("latitude"),
                "longitude": station.get("longitude"),
                "sourceVariable": source_variable,
                "profile": station_profile,
                "terrainFeatures": terrain_features,
            },
            "fullyTrainedModelVsObserved": fully_trained_metrics,
            "preparedPalomaStationMetrics": paloma_metrics,
            "palomaFullV1": paloma_metrics,
            "stationHoldoutTest": self.station_holdout_metrics(station, normalized_layer),
            "holdoutRun": holdout_run,
            "temperaturePredictionSeries": (
                self.temperature_prediction_series(
                    source_variable,
                    requested_station_id,
                    holdout_run,
                )
                if source_variable
                else None
            ),
            "context": {
                "reliabilityModelRunId": self.settings.reliability_model_run_id,
                "sourceModelRunId": self.source_model_run_id(payload, source_variable),
                "surfaceArtifact": self.surface_path(normalized_layer).name,
                "surfaceLayer": normalized_layer,
                "fullyTrainedMetricStatus": (
                    "available"
                    if fully_trained_metrics
                    else "missing_final_model_station_vs_observed_artifact"
                ),
                "terrainFeatureStatus": (
                    "available"
                    if terrain_features
                    else "missing_station_terrain_features_artifact"
                ),
                "preparedStationMetricsSource": (
                    paloma_metrics.get("source") if paloma_metrics else None
                ),
            },
        }

    def temperature_prediction_series(
        self,
        variable: str,
        station_id: str,
        holdout_run: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "variable": variable,
            "maxPoints": MAX_PREDICTION_SERIES_POINTS,
            "finalModel": self.prediction_series_from_candidates(
                self.final_model_prediction_path_candidates(variable),
                variable,
                station_id,
                "final_model_vs_observed",
                (
                    "Daily final-model prediction rows were not found. "
                    "Station-level final metrics are still available above."
                ),
            ),
            "holdout": self.prediction_series_from_candidates(
                self.holdout_prediction_path_candidates(variable, holdout_run),
                variable,
                station_id,
                "station_holdout_reconstruction",
                (
                    "Daily holdout prediction rows were not found for this station. "
                    "Station-level holdout metrics are still available above."
                ),
            ),
        }

    def final_model_prediction_path_candidates(self, variable: str) -> list[Path]:
        normalized_variable = variable.strip().lower()
        run_root = resolve_model_run(
            self.settings.model_run_root,
            f"paloma_v1_{normalized_variable}",
        ).root
        return [
            run_root / "final_model_predictions.csv",
            run_root / "final_model_station_predictions.csv",
            run_root / f"paloma_v1_{normalized_variable}_final_model_predictions.csv",
            run_root / f"paloma_v1_{normalized_variable}_final_predictions.csv",
        ]

    def holdout_prediction_path_candidates(
        self,
        variable: str,
        holdout_run: dict[str, Any] | None,
    ) -> list[Path]:
        normalized_variable = variable.strip().lower()
        candidates = []
        group_id = str((holdout_run or {}).get("holdoutGroupId") or "").strip()
        if group_id:
            candidates.append(
                self.settings.project_dir
                / "alpine_outputs"
                / "predictions"
                / (
                    f"paloma_v1_{normalized_variable}_group_holdout_"
                    f"{group_id}_predictions.csv"
                )
            )

        candidates.append(
            resolve_model_run(
                self.settings.model_run_root,
                f"paloma_v1_{normalized_variable}",
            ).root
            / "validation_predictions.csv"
        )
        return candidates

    def prediction_series_from_candidates(
        self,
        candidates: list[Path],
        variable: str,
        station_id: str,
        series_type: str,
        missing_message: str,
    ) -> dict[str, Any]:
        station_missing_payload = None

        for path in candidates:
            if not path.exists():
                continue

            points, total_rows = self.read_station_prediction_points(
                path,
                variable,
                station_id,
            )
            if not points:
                station_missing_payload = {
                    "status": "station_not_found",
                    "seriesType": series_type,
                    "sourceFile": str(path),
                    "message": "Prediction artifact exists, but this station has no rows in it.",
                    "totalRows": 0,
                    "points": [],
                }
                continue

            sampled_points = self.downsample_prediction_points(points)
            return {
                "status": "available",
                "seriesType": series_type,
                "sourceFile": str(path),
                "totalRows": total_rows,
                "returnedRows": len(sampled_points),
                "downsampled": len(sampled_points) < total_rows,
                "points": sampled_points,
            }

        if station_missing_payload is not None:
            return station_missing_payload

        return {
            "status": "missing_artifact",
            "seriesType": series_type,
            "sourceFile": None,
            "expectedFiles": [str(path) for path in candidates],
            "message": missing_message,
            "totalRows": 0,
            "points": [],
        }

    def read_station_prediction_points(
        self,
        path: Path,
        variable: str,
        station_id: str,
    ) -> tuple[list[dict[str, Any]], int]:
        requested_station_id = station_id.strip().upper()
        normalized_variable = variable.strip().lower()
        points: list[dict[str, Any]] = []

        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            fieldnames = reader.fieldnames or []
            actual_field = self.first_available_field(
                fieldnames,
                [
                    f"actual_{normalized_variable}",
                    "actual_tavg",
                    "actual_temperature_f",
                    "actual",
                ],
            )
            predicted_field = self.first_available_field(
                fieldnames,
                [
                    f"predicted_{normalized_variable}",
                    f"model_predicted_{normalized_variable}",
                    f"final_predicted_{normalized_variable}",
                    "predicted_tavg",
                    "model_predicted_tavg",
                    "prediction",
                    "predicted",
                ],
            )
            if actual_field is None or predicted_field is None:
                return [], 0

            for row in reader:
                candidate_station_id = str(
                    row.get("target_station_id")
                    or row.get("station_id")
                    or row.get("validation_station_id")
                    or ""
                ).strip().upper()
                if candidate_station_id != requested_station_id:
                    continue

                actual = self.optional_float(row.get(actual_field))
                predicted = self.optional_float(row.get(predicted_field))
                date = str(row.get("date") or "").strip()
                if actual is None or predicted is None or not date:
                    continue

                points.append({
                    "date": date,
                    "actualF": round(actual, 3),
                    "predictedF": round(predicted, 3),
                    "errorF": round(actual - predicted, 3),
                })

        points.sort(key=lambda point: str(point["date"]))
        return points, len(points)

    def first_available_field(
        self,
        fieldnames: list[str],
        candidates: list[str],
    ) -> str | None:
        fields = set(fieldnames)
        for candidate in candidates:
            if candidate in fields:
                return candidate
        return None

    def downsample_prediction_points(
        self,
        points: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if len(points) <= MAX_PREDICTION_SERIES_POINTS:
            return points

        if MAX_PREDICTION_SERIES_POINTS <= 1:
            return points[:1]

        last_index = len(points) - 1
        sampled_points = []
        previous_index = -1
        for index in range(MAX_PREDICTION_SERIES_POINTS):
            source_index = round(index * last_index / (MAX_PREDICTION_SERIES_POINTS - 1))
            if source_index == previous_index:
                continue
            sampled_points.append(points[source_index])
            previous_index = source_index
        return sampled_points

    def sample(self, layer: str, latitude: float, longitude: float) -> dict[str, Any]:
        normalized_layer = normalize_layer(layer)
        payload = self.surface(normalized_layer)
        points = payload.get("points") or []
        if not points:
            raise self.not_found_error(f"Reliability surface has no sample points: {normalized_layer}.", self.surface_path(normalized_layer))

        nearest = min(
            points,
            key=lambda point: calculate_distance_km(
                latitude,
                longitude,
                float(point["latitude"]),
                float(point["longitude"]),
            ),
        )
        nearest_distance = calculate_distance_km(
            latitude,
            longitude,
            float(nearest["latitude"]),
            float(nearest["longitude"]),
        )
        spacing_km = float((payload.get("grid") or {}).get("spacingKm") or 25.0)
        if nearest_distance > spacing_km * 1.75:
            raise HTTPException(
                status_code=404,
                detail={
                    "status": "error",
                    "message": "Clicked point is outside the reliability surface mask.",
                    "layer": normalized_layer,
                    "nearestSurfaceDistanceKm": round(nearest_distance, 3),
                },
            )

        return {
            "status": "ok",
            "layer": normalized_layer,
            "query": {
                "latitude": round(latitude, 6),
                "longitude": round(longitude, 6),
            },
            "nearestSurfaceDistanceKm": round(nearest_distance, 3),
            "sample": nearest,
        }

    def find_holdout_station(
        self,
        payload: dict[str, Any],
        station_id: str,
    ) -> dict[str, Any] | None:
        requested_station_id = station_id.strip().upper()
        for station in payload.get("holdoutStations") or []:
            candidate_station_id = str(station.get("stationId") or "").strip().upper()
            if candidate_station_id == requested_station_id:
                return station
        return None

    def station_source_variable(
        self,
        payload: dict[str, Any],
        station: dict[str, Any],
        layer: str,
    ) -> str | None:
        station_variable = str(station.get("sourceVariable") or "").strip().lower()
        if station_variable:
            return station_variable

        payload_variable = str(payload.get("variable") or "").strip().lower()
        if payload_variable:
            return payload_variable

        if layer in {"tavg", "tmin", "tmax"}:
            return layer

        source_layers = payload.get("sourceVariableLayers") or []
        if len(source_layers) == 1:
            return str(source_layers[0]).strip().lower()

        return None

    def source_model_run_id(
        self,
        payload: dict[str, Any],
        source_variable: str | None,
    ) -> str | None:
        source_model_run_id = payload.get("sourceModelRunId")
        if source_model_run_id:
            return str(source_model_run_id)

        source_model_run_ids = payload.get("sourceModelRunIds") or {}
        if source_variable and isinstance(source_model_run_ids, dict):
            value = source_model_run_ids.get(source_variable)
            if value:
                return str(value)

        return f"paloma_v1_{source_variable}" if source_variable else None

    def station_holdout_metrics(
        self,
        station: dict[str, Any],
        layer: str,
    ) -> dict[str, Any]:
        return {
            "source": "reliability_surface",
            "surfaceLayer": layer,
            "maeF": station.get("observedMaeF"),
            "rmseF": station.get("observedRmseF"),
            "correlation": station.get("observedCorrelation"),
            "testRows": station.get("testRows"),
            "observedReliability": station.get("observedReliability"),
            "maePercentile": station.get("maePercentile"),
        }

    def normalize_station_overlay_mode(self, mode: str) -> str:
        normalized = mode.strip().lower()
        allowed_modes = {
            "bias",
            "correlation",
            "mae",
            "rmse",
            "final-correlation",
            "final-mae",
            "final-rmse",
            "final-bias",
        }
        if normalized not in allowed_modes:
            raise self.validation_error(
                "Station overlay mode must be one of: bias, correlation, mae, rmse, "
                "final-correlation, final-mae, final-rmse, final-bias."
            )
        return normalized

    def station_overlay_is_stale(self, layer: str, mode: str, path: Path) -> bool:
        if not path.exists():
            return True

        source_variable = self.station_source_variable_for_layer(layer) or ""
        source_paths = [
            self.surface_path(layer),
            self.station_holdout_master_path(source_variable),
        ]
        if mode.startswith("final-"):
            source_paths.append(self.final_model_station_metrics_path(source_variable))
        existing_mtime = path.stat().st_mtime
        return any(
            source_path.exists() and source_path.stat().st_mtime > existing_mtime
            for source_path in source_paths
        )

    def station_source_variable_for_layer(self, layer: str) -> str | None:
        if layer in {"tavg", "tmin", "tmax"}:
            return layer

        try:
            payload = load_json_file(self.surface_path(layer))
        except FileNotFoundError:
            return None

        payload_variable = str(payload.get("variable") or "").strip().lower()
        if payload_variable:
            return payload_variable

        source_layers = payload.get("sourceVariableLayers") or []
        if len(source_layers) == 1:
            return str(source_layers[0]).strip().lower()

        return None

    def write_station_overlay_image(self, layer: str, mode: str, path: Path) -> None:
        payload = self.surface(layer)
        grid = payload.get("grid") or {}
        width = int(grid.get("width") or 0)
        height = int(grid.get("height") or 0)
        if width <= 0 or height <= 0:
            raise self.validation_error(f"Reliability surface grid is invalid: {layer}.")

        stations = self.station_overlay_value_points(payload, mode)
        if not stations:
            raise self.not_found_error(
                f"No station metrics are available for {mode} overlay: {layer}.",
                self.surface_path(layer),
            )

        raster: list[list[tuple[int, int, int, int] | None]] = [
            [None for _ in range(width)]
            for _ in range(height)
        ]
        for point in payload.get("points") or []:
            row = int(point["row"])
            column = int(point["column"])
            if row < 0 or row >= height or column < 0 or column >= width:
                continue

            value = self.interpolate_station_overlay_value(
                float(point["latitude"]),
                float(point["longitude"]),
                stations,
            )
            raster[row][column] = self.station_overlay_color(mode, value)

        self.write_rgba_png(path, raster)

    def station_overlay_value_points(
        self,
        payload: dict[str, Any],
        mode: str,
    ) -> list[dict[str, float]]:
        value_fields = {
            "bias": "holdoutBiasF",
            "correlation": "observedCorrelation",
            "mae": "observedMaeF",
            "rmse": "observedRmseF",
            "final-correlation": "finalModelCorrelation",
            "final-mae": "finalModelMaeF",
            "final-rmse": "finalModelRmseF",
            "final-bias": "finalModelBiasF",
        }
        value_field = value_fields.get(mode)
        if not value_field:
            return []

        points = []

        for station in payload.get("holdoutStations") or []:
            latitude = self.optional_float(station.get("latitude"))
            longitude = self.optional_float(station.get("longitude"))
            value = self.optional_float(station.get(value_field))
            if latitude is None or longitude is None or value is None:
                continue
            points.append({
                "latitude": latitude,
                "longitude": longitude,
                "value": value,
            })

        return points

    def interpolate_station_overlay_value(
        self,
        latitude: float,
        longitude: float,
        stations: list[dict[str, float]],
    ) -> float:
        weighted_values = []
        nearest: tuple[dict[str, float], float] | None = None

        for station in stations:
            distance_km = calculate_distance_km(
                latitude,
                longitude,
                station["latitude"],
                station["longitude"],
            )
            if nearest is None or distance_km < nearest[1]:
                nearest = (station, distance_km)
            if distance_km <= 500.0:
                weighted_values.append((
                    station["value"],
                    1.0 / (max(distance_km, 8.0) ** 1.8),
                ))

        if not weighted_values:
            if nearest is None:
                return 0.0
            return nearest[0]["value"]

        weight_sum = sum(weight for _, weight in weighted_values)
        return sum(value * weight for value, weight in weighted_values) / weight_sum

    def station_overlay_color(self, mode: str, value: float) -> tuple[int, int, int, int]:
        if mode in {"bias", "final-bias"}:
            return self.bias_overlay_color(value)
        if mode in {"correlation", "final-correlation"}:
            return self.correlation_overlay_color(value)
        if mode in {"mae", "final-mae"}:
            return self.mae_overlay_color(value)
        if mode in {"rmse", "final-rmse"}:
            return self.rmse_overlay_color(value)
        return self.correlation_overlay_color(value)

    def bias_overlay_color(self, value: float) -> tuple[int, int, int, int]:
        if value <= -4.0:
            return 185, 28, 28, 170
        if value <= -2.0:
            return 239, 68, 68, 166
        if value <= -1.0:
            return 251, 146, 60, 162
        if value < 1.0:
            return 22, 163, 74, 150
        if value < 2.0:
            return 56, 189, 248, 160
        if value < 4.0:
            return 2, 132, 199, 166
        return 29, 78, 216, 170

    def correlation_overlay_color(self, value: float) -> tuple[int, int, int, int]:
        if value >= 0.995:
            return 22, 163, 74, 168
        if value >= 0.990:
            return 20, 184, 166, 166
        if value >= 0.980:
            return 132, 204, 22, 162
        if value >= 0.950:
            return 250, 204, 21, 164
        if value >= 0.900:
            return 249, 115, 22, 166
        return 185, 28, 28, 170

    def mae_overlay_color(self, value: float) -> tuple[int, int, int, int]:
        if value <= 1.25:
            return 22, 163, 74, 168
        if value <= 2.0:
            return 20, 184, 166, 166
        if value <= 2.5:
            return 250, 204, 21, 164
        if value <= 4.0:
            return 249, 115, 22, 166
        return 185, 28, 28, 170

    def rmse_overlay_color(self, value: float) -> tuple[int, int, int, int]:
        if value <= 2.0:
            return 22, 163, 74, 168
        if value <= 3.0:
            return 20, 184, 166, 166
        if value <= 3.5:
            return 250, 204, 21, 164
        if value <= 5.0:
            return 249, 115, 22, 166
        return 185, 28, 28, 170

    def write_rgba_png(
        self,
        path: Path,
        raster: list[list[tuple[int, int, int, int] | None]],
    ) -> None:
        height = len(raster)
        width = len(raster[0]) if height else 0
        if width <= 0 or height <= 0:
            raise self.validation_error("Cannot write an empty station overlay PNG.")

        raw_rows = []
        for row in raster:
            pixels = bytearray()
            for color in row:
                pixels.extend(color or (0, 0, 0, 0))
            raw_rows.append(b"\x00" + bytes(pixels))

        png = (
            b"\x89PNG\r\n\x1a\n"
            + self.png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + self.png_chunk(b"IDAT", zlib.compress(b"".join(raw_rows), level=9))
            + self.png_chunk(b"IEND", b"")
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png)

    def png_chunk(self, chunk_type: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + chunk_type
            + payload
            + struct.pack(">I", zlib.crc32(chunk_type + payload) & 0xFFFFFFFF)
        )

    def enrich_holdout_stations(self, payload: dict[str, Any], layer: str) -> None:
        stations = payload.get("holdoutStations")
        if not isinstance(stations, list):
            return

        for station in stations:
            if not isinstance(station, dict):
                continue

            source_variable = self.station_source_variable(payload, station, layer)
            if source_variable and not station.get("sourceVariable"):
                station["sourceVariable"] = source_variable

            station_id = str(station.get("stationId") or "").strip()
            if not source_variable or not station_id:
                continue

            row = self.station_holdout_master_row(source_variable, station_id)
            if row is not None:
                station["holdoutBiasF"] = self.optional_float(row.get("bias"))
                station["holdoutStrictPass"] = self.optional_bool(row.get("strict_pass"))
                station["holdoutGroupId"] = row.get("holdout_group_id") or None
                station["holdoutGroupSize"] = self.optional_int(row.get("holdout_group_size"))
                station["holdoutTrainRows"] = self.optional_int(row.get("train_rows"))

            final_row = self.final_model_station_metric_row(source_variable, station_id)
            if final_row is None:
                station["finalModelMetricStatus"] = "missing"
                continue

            station["finalModelMetricStatus"] = "available"
            station["finalModelMaeF"] = self.optional_float(final_row.get("mae"))
            station["finalModelRmseF"] = self.optional_float(final_row.get("rmse"))
            station["finalModelCorrelation"] = self.optional_float(final_row.get("correlation"))
            station["finalModelBiasF"] = self.optional_float(final_row.get("bias"))
            station["finalModelRowCount"] = self.optional_int(final_row.get("row_count"))
            station["finalModelStartDate"] = final_row.get("start_date") or None
            station["finalModelEndDate"] = final_row.get("end_date") or None

    def fully_trained_model_metrics(
        self,
        variable: str,
        station_id: str,
    ) -> dict[str, Any] | None:
        run_id = f"paloma_v1_{variable}"
        path = self.final_model_station_metrics_path(variable)
        row = self.final_model_station_metric_row(variable, station_id)
        if row is None:
            return None

        return {
            "source": "final_model_station_metrics",
            "modelRunId": row.get("model_run_id") or run_id,
            "variable": row.get("variable") or variable,
            "stationMetricsFile": str(path),
            "evaluationMode": row.get("evaluation_mode") or "final_model_in_sample_fit",
            "maeF": self.optional_float(row.get("mae")),
            "rmseF": self.optional_float(row.get("rmse")),
            "correlation": self.optional_float(row.get("correlation")),
            "rowCount": self.optional_int(row.get("row_count")),
            "testRows": self.optional_int(row.get("row_count")),
            "startDate": row.get("start_date") or None,
            "endDate": row.get("end_date") or None,
            "biasF": self.optional_float(row.get("bias")),
            "actualMeanF": self.optional_float(row.get("actual_mean")),
            "predictedMeanF": self.optional_float(row.get("predicted_mean")),
        }

    def final_model_station_metrics_path(self, variable: str) -> Path:
        normalized_variable = variable.strip().lower()
        return (
            resolve_model_run(
                self.settings.model_run_root,
                f"paloma_v1_{normalized_variable}",
            ).root
            / "final_model_station_metrics.csv"
        )

    def final_model_station_metric_row(
        self,
        variable: str,
        station_id: str,
    ) -> dict[str, str] | None:
        lookup = self.final_model_station_metrics_lookup(variable)
        return lookup.get(station_id.strip().upper())

    def final_model_station_metrics_lookup(self, variable: str) -> dict[str, dict[str, str]]:
        normalized_variable = variable.strip().lower()
        if normalized_variable in self._final_model_station_metric_rows:
            return self._final_model_station_metric_rows[normalized_variable]

        path = self.final_model_station_metrics_path(normalized_variable)
        if not path.exists():
            self._final_model_station_metric_rows[normalized_variable] = {}
            return self._final_model_station_metric_rows[normalized_variable]

        rows: dict[str, dict[str, str]] = {}
        for row in read_csv_rows(path):
            station_id = str(
                row.get("target_station_id")
                or row.get("station_id")
                or row.get("validation_station_id")
                or ""
            ).strip().upper()
            if station_id:
                rows[station_id] = row

        self._final_model_station_metric_rows[normalized_variable] = rows
        return rows

    def paloma_station_metrics(
        self,
        variable: str,
        station_id: str,
    ) -> dict[str, Any] | None:
        run_id = f"paloma_v1_{variable}"
        paths = resolve_model_run(self.settings.model_run_root, run_id)
        if not paths.station_metrics.exists():
            return None

        row = self.find_csv_station_row(paths.station_metrics, station_id)
        if row is None:
            return None

        return {
            "source": "station_metrics",
            "modelRunId": run_id,
            "stationMetricsFile": str(paths.station_metrics),
            "maeF": self.optional_float(row.get("mae")),
            "rmseF": self.optional_float(row.get("rmse")),
            "correlation": self.optional_float(row.get("correlation")),
            "testRows": self.optional_int(row.get("test_rows")),
        }

    def station_holdout_master_metrics(
        self,
        variable: str,
        station_id: str,
    ) -> dict[str, Any] | None:
        row = self.station_holdout_master_row(variable, station_id)
        if row is None:
            return None

        return {
            "source": "station_holdout_master",
            "modelId": row.get("model_id") or f"paloma_v1_{variable}",
            "variable": row.get("variable") or variable,
            "sourceFile": str(self.station_holdout_master_path(variable)),
            "trainRows": self.optional_int(row.get("train_rows")),
            "testRows": self.optional_int(row.get("test_rows")),
            "maeF": self.optional_float(row.get("mae")),
            "rmseF": self.optional_float(row.get("rmse")),
            "correlation": self.optional_float(row.get("correlation")),
            "biasF": self.optional_float(row.get("bias")),
            "strictPass": self.optional_bool(row.get("strict_pass")),
            "holdoutGroupId": row.get("holdout_group_id") or None,
            "holdoutGroupSize": self.optional_int(row.get("holdout_group_size")),
            "elapsedSeconds": self.optional_float(row.get("elapsed_seconds")),
        }

    def station_holdout_master_path(self, variable: str) -> Path:
        return (
            self.settings.project_dir
            / "alpine_outputs"
            / "paloma"
            / f"paloma_v1_{variable}_station_holdout_master.csv"
        )

    def station_holdout_master_row(
        self,
        variable: str,
        station_id: str,
    ) -> dict[str, str] | None:
        lookup = self.station_holdout_master_lookup(variable)
        return lookup.get(station_id.strip().upper())

    def station_holdout_master_lookup(self, variable: str) -> dict[str, dict[str, str]]:
        normalized_variable = variable.strip().lower()
        if normalized_variable in self._holdout_master_rows:
            return self._holdout_master_rows[normalized_variable]

        path = self.station_holdout_master_path(normalized_variable)
        if not path.exists():
            self._holdout_master_rows[normalized_variable] = {}
            return self._holdout_master_rows[normalized_variable]

        rows: dict[str, dict[str, str]] = {}
        for row in read_csv_rows(path):
            station_id = str(row.get("target_station_id") or "").strip().upper()
            if station_id:
                rows[station_id] = row

        self._holdout_master_rows[normalized_variable] = rows
        return rows

    def station_record_profile(self, station_id: str) -> dict[str, Any] | None:
        target_row = self.station_candidate_row(
            self.settings.confidence_target_candidate_file,
            station_id,
        )
        hub_row = self.station_candidate_row(
            self.settings.confidence_hub_candidate_file,
            station_id,
        )
        if target_row is None and hub_row is None:
            return None

        merged_row: dict[str, str] = {}
        if target_row is not None:
            merged_row.update(target_row)
        if hub_row is not None:
            merged_row.update({key: value for key, value in hub_row.items() if value != ""})

        is_target_candidate = (
            self.optional_bool(merged_row.get("is_target_candidate"))
            if target_row is None
            else True
        )
        is_hub_candidate = (
            self.optional_bool(merged_row.get("is_hub_candidate"))
            if hub_row is None
            else True
        )

        return {
            "source": "station_candidate_inventory",
            "isTargetCandidate": is_target_candidate,
            "isHubCandidate": is_hub_candidate,
            "hasTmax": self.optional_bool(merged_row.get("has_tmax")),
            "hasTmin": self.optional_bool(merged_row.get("has_tmin")),
            "tmaxStartYear": self.optional_int(merged_row.get("tmax_start")),
            "tmaxEndYear": self.optional_int(merged_row.get("tmax_end")),
            "tminStartYear": self.optional_int(merged_row.get("tmin_start")),
            "tminEndYear": self.optional_int(merged_row.get("tmin_end")),
            "usableTempStartYear": self.optional_int(merged_row.get("usable_temp_start")),
            "usableTempEndYear": self.optional_int(merged_row.get("usable_temp_end")),
            "usableTempYears": self.optional_int(merged_row.get("usable_temp_years")),
        }

    def station_candidate_row(self, path: Path, station_id: str) -> dict[str, str] | None:
        lookup = self.station_candidate_lookup(path)
        return lookup.get(station_id.strip().upper())

    def station_candidate_lookup(self, path: Path) -> dict[str, dict[str, str]]:
        cache_key = str(path)
        if cache_key in self._station_candidate_rows:
            return self._station_candidate_rows[cache_key]

        if not path.exists():
            self._station_candidate_rows[cache_key] = {}
            return self._station_candidate_rows[cache_key]

        rows: dict[str, dict[str, str]] = {}
        for row in read_csv_rows(path):
            station_id = str(row.get("station_id") or "").strip().upper()
            if station_id:
                rows[station_id] = row

        self._station_candidate_rows[cache_key] = rows
        return rows

    def station_terrain_features(self, station_id: str) -> dict[str, Any] | None:
        lookup = self.terrain_feature_lookup()
        row = lookup.get(station_id.strip().upper())
        if row is None:
            return None

        features = {
            "source": "station_terrain_features",
            "noaaElevationM": self.optional_float(row.get("noaa_elevation_m")),
            "demElevationM": self.optional_float(row.get("dem_elevation_m")),
            "demMinusNoaaElevationM": self.optional_float(row.get("dem_minus_noaa_elevation_m")),
            "slopeDegrees": self.optional_float(row.get("slope_degrees")),
            "localReliefM": self.optional_float(row.get("local_relief_m")),
            "terrainPositionIndexM": self.optional_float(row.get("terrain_position_index_m")),
            "slopeDegreesR300m": self.optional_float(row.get("slope_degrees_r300m")),
            "localReliefMR300m": self.optional_float(row.get("local_relief_m_r300m")),
            "terrainPositionIndexMR300m": self.optional_float(
                row.get("terrain_position_index_m_r300m")
            ),
            "slopeDegreesR990m": self.optional_float(row.get("slope_degrees_r990m")),
            "localReliefMR990m": self.optional_float(row.get("local_relief_m_r990m")),
            "terrainPositionIndexMR990m": self.optional_float(
                row.get("terrain_position_index_m_r990m")
            ),
            "slopeDegreesR3000m": self.optional_float(row.get("slope_degrees_r3000m")),
            "localReliefMR3000m": self.optional_float(row.get("local_relief_m_r3000m")),
            "terrainPositionIndexMR3000m": self.optional_float(
                row.get("terrain_position_index_m_r3000m")
            ),
        }
        available_features = {
            key: value
            for key, value in features.items()
            if key == "source" or value is not None
        }
        return available_features if len(available_features) > 1 else None

    def terrain_feature_lookup(self) -> dict[str, dict[str, str]]:
        if self._terrain_feature_rows is not None:
            return self._terrain_feature_rows

        path = self.settings.confidence_terrain_feature_file
        if not path.exists():
            self._terrain_feature_rows = {}
            return self._terrain_feature_rows

        rows: dict[str, dict[str, str]] = {}
        for row in read_csv_rows(path):
            station_id = str(row.get("station_id") or "").strip().upper()
            if station_id:
                rows[station_id] = row

        self._terrain_feature_rows = rows
        return rows

    def find_csv_station_row(self, path: Path, station_id: str) -> dict[str, str] | None:
        requested_station_id = station_id.strip().upper()
        for row in read_csv_rows(path):
            candidate_station_id = str(
                row.get("target_station_id")
                or row.get("station_id")
                or row.get("validation_station_id")
                or ""
            ).strip().upper()
            if candidate_station_id == requested_station_id:
                return row
        return None

    def optional_float(self, value: object) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def optional_int(self, value: object) -> int | None:
        number = self.optional_float(value)
        return int(number) if number is not None else None

    def optional_bool(self, value: object) -> bool | None:
        if value is None or value == "":
            return None
        normalized = str(value).strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
        return None

    def not_found_error(self, message: str, path: Path) -> HTTPException:
        return HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "message": message,
                "details": str(path),
                "modelRunRoot": str(self.settings.model_run_root),
                "reliabilityModelRunId": self.settings.reliability_model_run_id,
            },
        )

    def validation_error(self, message: str) -> HTTPException:
        return HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": message,
                "allowedLayers": list(RELIABILITY_LAYERS),
                "reliabilityModelRunId": self.settings.reliability_model_run_id,
            },
        )
