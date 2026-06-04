from __future__ import annotations

import json
import math
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from common.csv_utils import CsvRow, read_csv_rows
from common.geo_utils import calculate_distance_km
from common.number_utils import to_optional_float


VARIABLE_LAYERS = ("tavg", "tmin", "tmax")
HELPFULNESS_LAYER = "helpfulness"
RELIABILITY_LAYERS = (HELPFULNESS_LAYER, "overall", *VARIABLE_LAYERS)
SURFACE_SCHEMA_VERSION = "reliability-surface-v1"
SUMMARY_SCHEMA_VERSION = "reliability-summary-v1"
SCORE_VERSION = "holdout-mae-spatial-reliability-v1"
HELPFULNESS_SCORE_VERSION = "model-helpfulness-v1"

MAE_FIELDS = ("mae", "test_mae", "mean_absolute_error", "observed_mae_f")
RMSE_FIELDS = ("rmse", "test_rmse", "observed_rmse_f")
CORRELATION_FIELDS = ("correlation", "r", "test_correlation", "observed_correlation")
TEST_ROWS_FIELDS = ("test_rows", "paired_days", "paired_count")
STATION_ID_FIELDS = ("target_station_id", "station_id", "validation_station_id")
STATION_NAME_FIELDS = ("target_name", "station_name", "name")


@dataclass(frozen=True)
class Bounds:
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float

    def as_dict(self) -> dict[str, float]:
        return {
            "latMin": round(self.lat_min, 6),
            "latMax": round(self.lat_max, 6),
            "lonMin": round(self.lon_min, 6),
            "lonMax": round(self.lon_max, 6),
        }


@dataclass(frozen=True)
class GridCell:
    row: int
    column: int
    latitude: float
    longitude: float


@dataclass(frozen=True)
class StationAnchor:
    station_id: str
    station_name: str
    latitude: float
    longitude: float
    mae_f: float
    rmse_f: float | None = None
    correlation: float | None = None
    test_rows: int | None = None
    elevation_m: float | None = None
    terrain: Mapping[str, float] | None = None


@dataclass(frozen=True)
class StationCoordinate:
    station_id: str
    latitude: float
    longitude: float
    source_file: str


def normalize_layer(layer: str) -> str:
    normalized = layer.strip().lower()
    if normalized not in RELIABILITY_LAYERS:
        allowed = ", ".join(RELIABILITY_LAYERS)
        raise ValueError(f"Unknown reliability layer {layer!r}. Expected one of: {allowed}.")
    return normalized


def first_present(row: Mapping[str, object], fields: Iterable[str]) -> str | None:
    for field in fields:
        value = row.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def first_present_float(row: Mapping[str, object], fields: Iterable[str]) -> float | None:
    value = first_present(row, fields)
    if value is None:
        return None
    return to_optional_float(value)


def first_present_int(row: Mapping[str, object], fields: Iterable[str]) -> int | None:
    value = first_present_float(row, fields)
    if value is None:
        return None
    return int(value)


def quantile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]

    position = (len(sorted_values) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[int(position)]

    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def empirical_percentile(sorted_values: list[float], value: float) -> float:
    """Return a 0-1 percentile where lower values are better for MAE."""
    if not sorted_values:
        return 1.0
    if len(sorted_values) == 1:
        return 0.5
    if value <= sorted_values[0]:
        return 0.0
    if value >= sorted_values[-1]:
        return 1.0

    for index in range(1, len(sorted_values)):
        lower = sorted_values[index - 1]
        upper = sorted_values[index]
        if value <= upper:
            fraction = 0.0 if upper == lower else (value - lower) / (upper - lower)
            return (index - 1 + fraction) / (len(sorted_values) - 1)

    return 1.0


def reliability_from_expected_mae(sorted_maes: list[float], expected_mae_f: float) -> float:
    percentile = empirical_percentile(sorted_maes, expected_mae_f)
    return clamp(100.0 * (1.0 - percentile), 0.0, 100.0)


def expected_mae_usefulness_score(expected_mae_f: float) -> float:
    """Map expected daily temperature MAE in F to a decision-support usefulness score."""
    stops = [
        (0.0, 100.0),
        (1.5, 95.0),
        (2.5, 80.0),
        (3.5, 60.0),
        (4.5, 40.0),
        (6.0, 20.0),
        (8.0, 5.0),
    ]
    value = max(0.0, expected_mae_f)
    if value <= stops[0][0]:
        return stops[0][1]

    for index in range(1, len(stops)):
        lower_value, lower_score = stops[index - 1]
        upper_value, upper_score = stops[index]
        if value <= upper_value:
            fraction = (
                0.0
                if upper_value == lower_value
                else (value - lower_value) / (upper_value - lower_value)
            )
            return clamp(lower_score * (1.0 - fraction) + upper_score * fraction, 0.0, 100.0)

    return stops[-1][1]


def model_helpfulness_components(
    expected_mae_f: float,
    generalization_reliability: float,
    evidence: float,
) -> dict[str, float]:
    accuracy_score = expected_mae_usefulness_score(expected_mae_f)
    low_evidence_penalty = clamp(((45.0 - evidence) / 45.0) * 20.0, 0.0, 20.0)
    score = clamp(
        accuracy_score * 0.5
        + generalization_reliability * 0.3
        + evidence * 0.2
        - low_evidence_penalty,
        0.0,
        100.0,
    )
    return {
        "modelHelpfulness": round(score, 2),
        "expectedMaeUsefulness": round(accuracy_score, 2),
        "generalizationReliability": round(generalization_reliability, 2),
        "evidenceStrength": round(evidence, 2),
        "lowEvidencePenalty": round(low_evidence_penalty, 2),
    }


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def summarize_values(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "p25": None,
            "median": None,
            "mean": None,
            "p75": None,
            "p90": None,
            "max": None,
        }

    sorted_values = sorted(values)
    return {
        "count": len(sorted_values),
        "min": round(sorted_values[0], 4),
        "p25": round(quantile(sorted_values, 0.25), 4),
        "median": round(quantile(sorted_values, 0.5), 4),
        "mean": round(sum(sorted_values) / len(sorted_values), 4),
        "p75": round(quantile(sorted_values, 0.75), 4),
        "p90": round(quantile(sorted_values, 0.9), 4),
        "max": round(sorted_values[-1], 4),
    }


def load_station_coordinate_lookup(files: Iterable[Path]) -> dict[str, dict[str, object]]:
    lookup: dict[str, dict[str, object]] = {}
    for file_path in files:
        if file_path is None or not file_path.exists():
            continue
        for row in read_csv_rows(file_path):
            station_id = first_present(row, STATION_ID_FIELDS)
            latitude = first_present_float(row, ("latitude", "lat"))
            longitude = first_present_float(row, ("longitude", "lon", "lng"))
            if station_id is None or latitude is None or longitude is None:
                continue

            lookup.setdefault(station_id, {})
            lookup[station_id].update({
                "latitude": latitude,
                "longitude": longitude,
                "station_name": first_present(row, STATION_NAME_FIELDS) or station_id,
            })

            elevation = first_present_float(
                row,
                ("elevation_m", "noaa_elevation_m", "dem_elevation_m", "elevation"),
            )
            if elevation is not None:
                lookup[station_id]["elevation_m"] = elevation

    return lookup


def load_station_coordinates(files: Iterable[Path]) -> list[StationCoordinate]:
    coordinates_by_station_id: dict[str, StationCoordinate] = {}
    anonymous_index = 0

    for file_path in files:
        if file_path is None or not file_path.exists():
            continue

        for row in read_csv_rows(file_path):
            latitude = first_present_float(row, ("latitude", "lat"))
            longitude = first_present_float(row, ("longitude", "lon", "lng"))
            if latitude is None or longitude is None:
                continue

            station_id = first_present(row, STATION_ID_FIELDS)
            if station_id is None:
                anonymous_index += 1
                station_id = f"{file_path.name}:{anonymous_index}"

            coordinates_by_station_id.setdefault(
                station_id,
                StationCoordinate(
                    station_id=station_id,
                    latitude=latitude,
                    longitude=longitude,
                    source_file=str(file_path),
                ),
            )

    return list(coordinates_by_station_id.values())


def build_station_extent_boundary_geojson(
    coordinate_files: Iterable[Path],
    padding_km: float = 30.0,
) -> dict[str, object]:
    coordinates = load_station_coordinates(coordinate_files)
    if not coordinates:
        raise ValueError("Cannot build station-extent boundary without station coordinates.")

    latitudes = [coordinate.latitude for coordinate in coordinates]
    longitudes = [coordinate.longitude for coordinate in coordinates]
    raw_lat_min = min(latitudes)
    raw_lat_max = max(latitudes)
    raw_lon_min = min(longitudes)
    raw_lon_max = max(longitudes)
    center_latitude = (raw_lat_min + raw_lat_max) / 2.0
    latitude_padding_degrees = padding_km / 111.32
    longitude_padding_degrees = padding_km / (
        111.32 * max(0.25, math.cos(math.radians(center_latitude)))
    )
    bounds = Bounds(
        lat_min=raw_lat_min - latitude_padding_degrees,
        lat_max=raw_lat_max + latitude_padding_degrees,
        lon_min=raw_lon_min - longitude_padding_degrees,
        lon_max=raw_lon_max + longitude_padding_degrees,
    )
    ring = [
        [round(bounds.lon_min, 6), round(bounds.lat_min, 6)],
        [round(bounds.lon_max, 6), round(bounds.lat_min, 6)],
        [round(bounds.lon_max, 6), round(bounds.lat_max, 6)],
        [round(bounds.lon_min, 6), round(bounds.lat_max, 6)],
        [round(bounds.lon_min, 6), round(bounds.lat_min, 6)],
    ]

    return {
        "type": "Feature",
        "properties": {
            "name": "Station extent reliability boundary",
            "boundaryType": "station_extent_rectangle",
            "paddingKm": padding_km,
            "stationCount": len(coordinates),
            "rawStationBounds": Bounds(
                lat_min=raw_lat_min,
                lat_max=raw_lat_max,
                lon_min=raw_lon_min,
                lon_max=raw_lon_max,
            ).as_dict(),
            "paddedBounds": bounds.as_dict(),
            "sourceFiles": sorted({
                coordinate.source_file
                for coordinate in coordinates
            }),
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [ring],
        },
    }


def load_station_terrain_lookup(terrain_file: Path | None) -> dict[str, dict[str, float]]:
    if terrain_file is None or not terrain_file.exists():
        return {}

    terrain_columns = (
        "dem_elevation_m",
        "slope_degrees",
        "local_relief_m",
        "local_relief_m_r990m",
        "local_relief_m_r3000m",
        "terrain_position_index_m",
        "terrain_position_index_m_r990m",
        "terrain_position_index_m_r3000m",
    )
    lookup: dict[str, dict[str, float]] = {}
    for row in read_csv_rows(terrain_file):
        station_id = first_present(row, STATION_ID_FIELDS)
        if station_id is None:
            continue
        values = {
            column: numeric_value
            for column in terrain_columns
            if (numeric_value := to_optional_float(row.get(column))) is not None
        }
        if values:
            lookup[station_id] = values
    return lookup


def normalize_holdout_anchors(
    station_metrics_file: Path,
    coordinate_files: Iterable[Path],
    calibration_points_file: Path | None = None,
    terrain_file: Path | None = None,
) -> list[StationAnchor]:
    coordinate_lookup = load_station_coordinate_lookup([
        *(coordinate_files or []),
        *([calibration_points_file] if calibration_points_file is not None else []),
        *([terrain_file] if terrain_file is not None else []),
    ])
    terrain_lookup = load_station_terrain_lookup(terrain_file)
    anchors = []

    for row in read_csv_rows(station_metrics_file):
        station_id = first_present(row, STATION_ID_FIELDS)
        mae_f = first_present_float(row, MAE_FIELDS)
        if station_id is None or mae_f is None:
            continue

        coordinates = coordinate_lookup.get(station_id)
        if coordinates is None:
            continue

        latitude = to_optional_float(coordinates.get("latitude"))
        longitude = to_optional_float(coordinates.get("longitude"))
        if latitude is None or longitude is None:
            continue

        anchor_terrain = terrain_lookup.get(station_id, {})
        elevation_m = to_optional_float(coordinates.get("elevation_m"))
        if elevation_m is None:
            elevation_m = anchor_terrain.get("dem_elevation_m")

        anchors.append(
            StationAnchor(
                station_id=station_id,
                station_name=first_present(row, STATION_NAME_FIELDS)
                or str(coordinates.get("station_name") or station_id),
                latitude=latitude,
                longitude=longitude,
                mae_f=mae_f,
                rmse_f=first_present_float(row, RMSE_FIELDS),
                correlation=first_present_float(row, CORRELATION_FIELDS),
                test_rows=first_present_int(row, TEST_ROWS_FIELDS),
                elevation_m=elevation_m,
                terrain=anchor_terrain or None,
            )
        )

    if not anchors:
        raise ValueError(f"No holdout anchors with coordinates were loaded from {station_metrics_file}.")

    return anchors


def load_boundary_geojson(boundary_file: Path) -> dict[str, Any]:
    with boundary_file.open("r") as file:
        payload = json.load(file)

    if not isinstance(payload, dict):
        raise ValueError(f"Expected GeoJSON object in {boundary_file}.")
    return payload


def extract_polygon_rings(geojson: Mapping[str, Any]) -> list[list[list[list[float]]]]:
    geometry_type = geojson.get("type")
    if geometry_type == "FeatureCollection":
        polygons: list[list[list[list[float]]]] = []
        for feature in geojson.get("features", []):
            polygons.extend(extract_polygon_rings(feature))
        return polygons
    if geometry_type == "Feature":
        geometry = geojson.get("geometry")
        if not isinstance(geometry, Mapping):
            return []
        return extract_polygon_rings(geometry)
    if geometry_type == "Polygon":
        coordinates = geojson.get("coordinates")
        if isinstance(coordinates, list):
            return [coordinates]
    if geometry_type == "MultiPolygon":
        coordinates = geojson.get("coordinates")
        if isinstance(coordinates, list):
            return [polygon for polygon in coordinates if isinstance(polygon, list)]
    return []


def boundary_bounds(polygons: list[list[list[list[float]]]]) -> Bounds:
    coordinates = [
        coordinate
        for polygon in polygons
        for ring in polygon
        for coordinate in ring
        if len(coordinate) >= 2
    ]
    if not coordinates:
        raise ValueError("Boundary GeoJSON did not include polygon coordinates.")

    longitudes = [float(coordinate[0]) for coordinate in coordinates]
    latitudes = [float(coordinate[1]) for coordinate in coordinates]
    return Bounds(
        lat_min=min(latitudes),
        lat_max=max(latitudes),
        lon_min=min(longitudes),
        lon_max=max(longitudes),
    )


def point_in_ring(latitude: float, longitude: float, ring: list[list[float]]) -> bool:
    inside = False
    point_count = len(ring)
    if point_count < 3:
        return False

    previous_lon = float(ring[-1][0])
    previous_lat = float(ring[-1][1])
    for coordinate in ring:
        current_lon = float(coordinate[0])
        current_lat = float(coordinate[1])
        crosses = (current_lat > latitude) != (previous_lat > latitude)
        if crosses:
            slope_lon = (
                (previous_lon - current_lon)
                * (latitude - current_lat)
                / (previous_lat - current_lat)
                + current_lon
            )
            if longitude < slope_lon:
                inside = not inside
        previous_lon = current_lon
        previous_lat = current_lat

    return inside


def point_in_boundary(
    latitude: float,
    longitude: float,
    polygons: list[list[list[list[float]]]],
) -> bool:
    for polygon in polygons:
        if not polygon or not point_in_ring(latitude, longitude, polygon[0]):
            continue
        if any(point_in_ring(latitude, longitude, hole) for hole in polygon[1:]):
            continue
        return True
    return False


def build_grid_cells(
    polygons: list[list[list[list[float]]]],
    spacing_km: float,
    max_points: int,
) -> tuple[Bounds, dict[str, float | int], list[GridCell]]:
    bounds = boundary_bounds(polygons)
    center_latitude = (bounds.lat_min + bounds.lat_max) / 2.0
    latitude_step = spacing_km / 111.32
    longitude_step = spacing_km / (111.32 * max(0.25, math.cos(math.radians(center_latitude))))
    width = max(1, int(math.floor((bounds.lon_max - bounds.lon_min) / longitude_step)) + 1)
    height = max(1, int(math.floor((bounds.lat_max - bounds.lat_min) / latitude_step)) + 1)
    cells: list[GridCell] = []

    for row in range(height):
        latitude = bounds.lat_max - row * latitude_step
        for column in range(width):
            longitude = bounds.lon_min + column * longitude_step
            if point_in_boundary(latitude, longitude, polygons):
                cells.append(
                    GridCell(
                        row=row,
                        column=column,
                        latitude=latitude,
                        longitude=longitude,
                    )
                )

    if len(cells) > max_points:
        raise ValueError(
            f"Reliability grid point count {len(cells)} exceeds --max-points {max_points}."
        )

    return bounds, {
        "width": width,
        "height": height,
        "spacingKm": spacing_km,
        "latitudeStepDegrees": latitude_step,
        "longitudeStepDegrees": longitude_step,
        "maskedPointCount": len(cells),
    }, cells


def anchor_as_dict(anchor: StationAnchor, distance_km: float | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "stationId": anchor.station_id,
        "stationName": anchor.station_name,
        "latitude": round(anchor.latitude, 6),
        "longitude": round(anchor.longitude, 6),
        "observedMaeF": round(anchor.mae_f, 4),
    }
    if distance_km is not None:
        payload["distanceKm"] = round(distance_km, 3)
    if anchor.rmse_f is not None:
        payload["observedRmseF"] = round(anchor.rmse_f, 4)
    if anchor.correlation is not None:
        payload["observedCorrelation"] = round(anchor.correlation, 6)
    if anchor.test_rows is not None:
        payload["testRows"] = anchor.test_rows
    if anchor.elevation_m is not None:
        payload["elevationM"] = round(anchor.elevation_m, 2)
    return payload


def sorted_anchor_distances(
    latitude: float,
    longitude: float,
    anchors: list[StationAnchor],
) -> list[tuple[StationAnchor, float]]:
    return sorted(
        (
            (
                anchor,
                calculate_distance_km(latitude, longitude, anchor.latitude, anchor.longitude),
            )
            for anchor in anchors
        ),
        key=lambda item: item[1],
    )


def weighted_mean(values: list[tuple[float, float]]) -> float:
    weight_sum = sum(weight for _, weight in values)
    if weight_sum <= 0:
        return 0.0
    return sum(value * weight for value, weight in values) / weight_sum


def weighted_std(values: list[tuple[float, float]], mean_value: float) -> float:
    weight_sum = sum(weight for _, weight in values)
    if weight_sum <= 0:
        return 0.0
    variance = sum(((value - mean_value) ** 2) * weight for value, weight in values) / weight_sum
    return math.sqrt(max(0.0, variance))


def evidence_strength(nearest_km: float, counts: Mapping[str, int]) -> float:
    distance_component = clamp(50.0 * (1.0 - nearest_km / 180.0), 0.0, 50.0)
    density_component = min(
        50.0,
        counts.get("within50Km", 0) * 8.0
        + counts.get("within100Km", 0) * 4.0
        + counts.get("within200Km", 0) * 1.5,
    )
    return clamp(distance_component + density_component, 0.0, 100.0)


def predict_variable_cell(
    cell: GridCell,
    anchors: list[StationAnchor],
    sorted_maes: list[float],
) -> dict[str, object]:
    distances = sorted_anchor_distances(cell.latitude, cell.longitude, anchors)
    if not distances:
        raise ValueError("Cannot predict reliability without holdout anchors.")

    nearest_anchor, nearest_km = distances[0]
    counts = {
        "within50Km": sum(1 for _, distance in distances if distance <= 50.0),
        "within100Km": sum(1 for _, distance in distances if distance <= 100.0),
        "within200Km": sum(1 for _, distance in distances if distance <= 200.0),
    }
    evidence = evidence_strength(nearest_km, counts)
    local_pairs = [
        (anchor.mae_f, 1.0 / (max(distance, 8.0) ** 1.6))
        for anchor, distance in distances
        if distance <= 450.0
    ]
    if not local_pairs:
        local_pairs = [(nearest_anchor.mae_f, 1.0)]

    local_mae = weighted_mean(local_pairs)
    local_std = weighted_std(local_pairs, local_mae)
    median_mae = quantile(sorted_maes, 0.5)
    p25_mae = quantile(sorted_maes, 0.25)
    p75_mae = quantile(sorted_maes, 0.75)
    iqr = max(0.1, p75_mae - p25_mae)
    blend = clamp(evidence / 65.0, 0.0, 1.0)
    expected_mae = local_mae * blend + p75_mae * (1.0 - blend)
    expected_mae += min(local_std * 0.15, iqr * 0.3)
    if nearest_km > 120.0:
        expected_mae += min(iqr, ((nearest_km - 120.0) / 180.0) * iqr)

    mae_percentile = empirical_percentile(sorted_maes, expected_mae)
    reliability = 100.0 * (1.0 - mae_percentile)
    helpfulness = model_helpfulness_components(expected_mae, reliability, evidence)
    nearest_high = next((item for item in distances if item[0].mae_f >= p75_mae), None)
    nearest_low = next((item for item in distances if item[0].mae_f <= p25_mae), None)

    return {
        "row": cell.row,
        "column": cell.column,
        "latitude": round(cell.latitude, 6),
        "longitude": round(cell.longitude, 6),
        "reliability": round(clamp(reliability, 0.0, 100.0), 2),
        "expectedMaeF": round(max(0.0, expected_mae), 4),
        "maePercentile": round(mae_percentile, 4),
        "evidenceStrength": round(evidence, 2),
        "nearestHoldoutDistanceKm": round(nearest_km, 3),
        "localHoldoutMaeF": round(local_mae, 4),
        "localHoldoutStdF": round(local_std, 4),
        "modelHelpfulness": helpfulness["modelHelpfulness"],
        "expectedMaeUsefulness": helpfulness["expectedMaeUsefulness"],
        "generalizationReliability": helpfulness["generalizationReliability"],
        "lowEvidencePenalty": helpfulness["lowEvidencePenalty"],
        "holdoutCounts": counts,
        "nearestHoldoutStations": [
            anchor_as_dict(anchor, distance)
            for anchor, distance in distances[:5]
        ],
        "nearestHighMaeStation": (
            anchor_as_dict(nearest_high[0], nearest_high[1])
            if nearest_high is not None
            else None
        ),
        "nearestLowMaeStation": (
            anchor_as_dict(nearest_low[0], nearest_low[1])
            if nearest_low is not None
            else None
        ),
    }


def holdout_station_payload(anchors: list[StationAnchor], sorted_maes: list[float]) -> list[dict[str, object]]:
    stations = []
    for anchor in anchors:
        reliability = reliability_from_expected_mae(sorted_maes, anchor.mae_f)
        payload = anchor_as_dict(anchor)
        payload["observedReliability"] = round(reliability, 2)
        payload["maePercentile"] = round(empirical_percentile(sorted_maes, anchor.mae_f), 4)
        stations.append(payload)
    return stations


def build_variable_surface_payload(
    reliability_run_id: str,
    source_model_run_id: str,
    variable: str,
    anchors: list[StationAnchor],
    boundary_geojson: Mapping[str, object],
    bounds: Bounds,
    grid: Mapping[str, float | int],
    cells: list[GridCell],
    image_file_name: str,
) -> tuple[dict[str, object], list[list[float | None]]]:
    sorted_maes = sorted(anchor.mae_f for anchor in anchors)
    raster = [[None for _ in range(int(grid["width"]))] for _ in range(int(grid["height"]))]
    points = []

    for cell in cells:
        point = predict_variable_cell(cell, anchors, sorted_maes)
        raster[cell.row][cell.column] = float(point["reliability"])
        points.append(point)

    values = [float(point["reliability"]) for point in points]
    visual_scale = surface_relative_visual_scale(values)
    terrain_status = (
        "station_terrain_proxy"
        if any(anchor.terrain for anchor in anchors)
        else "not_available"
    )
    payload: dict[str, object] = {
        "schemaVersion": SURFACE_SCHEMA_VERSION,
        "modelRunId": reliability_run_id,
        "sourceModelRunId": source_model_run_id,
        "scoreVersion": SCORE_VERSION,
        "layer": variable,
        "variable": variable,
        "status": "ok",
        "bounds": bounds.as_dict(),
        "grid": dict(grid),
        "imageArtifact": image_file_name,
        "legend": legend_payload(),
        "visualization": visual_scale,
        "surfaceSummary": summarize_values(values),
        "stationHoldoutSummary": summarize_values(sorted_maes),
        "calibration": {
            "method": "inverse_distance_holdout_mae_neighborhood",
            "maeToReliability": "100 * (1 - empirical_cdf(expectedMaeF))",
            "lowMaeMeaning": "Higher reliability",
            "highMaeMeaning": "Lower reliability",
            "terrainFeatureStatus": terrain_status,
            "notes": [
                "Expected MAE is driven by nearby station holdout MAE, local holdout variance, station density, and sparse-evidence penalties.",
                "Dense regions with high holdout MAE remain low reliability because density does not reduce expected MAE.",
            ],
        },
        "boundaryGeoJson": boundary_geojson,
        "holdoutStations": holdout_station_payload(anchors, sorted_maes),
        "points": points,
    }
    return payload, raster


def build_overall_surface_payload(
    reliability_run_id: str,
    source_model_run_ids: Mapping[str, str],
    variable_payloads: Mapping[str, Mapping[str, object]],
    boundary_geojson: Mapping[str, object],
    bounds: Bounds,
    grid: Mapping[str, float | int],
    cells: list[GridCell],
    image_file_name: str,
) -> tuple[dict[str, object], list[list[float | None]]]:
    variable_points = {
        variable: {
            (int(point["row"]), int(point["column"])): point
            for point in payload.get("points", [])
        }
        for variable, payload in variable_payloads.items()
    }
    raster = [[None for _ in range(int(grid["width"]))] for _ in range(int(grid["height"]))]
    points = []

    for cell in cells:
        cell_key = (cell.row, cell.column)
        breakdown = {
            variable: variable_points[variable][cell_key]
            for variable in VARIABLE_LAYERS
            if cell_key in variable_points.get(variable, {})
        }
        if not breakdown:
            continue

        reliabilities = [float(point["reliability"]) for point in breakdown.values()]
        evidence_values = [float(point["evidenceStrength"]) for point in breakdown.values()]
        min_evidence = min(evidence_values)
        low_evidence_penalty = clamp(((45.0 - min_evidence) / 45.0) * 20.0, 0.0, 20.0)
        reliability = clamp(sum(reliabilities) / len(reliabilities) - low_evidence_penalty, 0.0, 100.0)
        worst_variable = min(breakdown.items(), key=lambda item: float(item[1]["reliability"]))[0]
        expected_maes = [float(point["expectedMaeF"]) for point in breakdown.values()]
        point_payload = {
            "row": cell.row,
            "column": cell.column,
            "latitude": round(cell.latitude, 6),
            "longitude": round(cell.longitude, 6),
            "reliability": round(reliability, 2),
            "expectedMaeF": round(sum(expected_maes) / len(expected_maes), 4),
            "evidenceStrength": round(min_evidence, 2),
            "lowEvidencePenalty": round(low_evidence_penalty, 2),
            "worstVariable": worst_variable,
            "variables": {
                variable: {
                    "reliability": point["reliability"],
                    "expectedMaeF": point["expectedMaeF"],
                    "maePercentile": point["maePercentile"],
                    "evidenceStrength": point["evidenceStrength"],
                    "nearestHoldoutDistanceKm": point["nearestHoldoutDistanceKm"],
                }
                for variable, point in breakdown.items()
            },
        }
        raster[cell.row][cell.column] = float(point_payload["reliability"])
        points.append(point_payload)

    values = [float(point["reliability"]) for point in points]
    payload = {
        "schemaVersion": SURFACE_SCHEMA_VERSION,
        "modelRunId": reliability_run_id,
        "sourceModelRunIds": dict(source_model_run_ids),
        "scoreVersion": SCORE_VERSION,
        "layer": "overall",
        "status": "ok",
        "bounds": bounds.as_dict(),
        "grid": dict(grid),
        "imageArtifact": image_file_name,
        "legend": legend_payload(),
        "visualization": surface_relative_visual_scale(values),
        "surfaceSummary": summarize_values(values),
        "calibration": {
            "method": "equal_weight_variable_reliability_with_low_evidence_penalty",
            "formula": "clamp(mean(tavg,tmin,tmax reliability) - lowEvidencePenalty, 0, 100)",
            "lowEvidencePenalty": "Only applied where station holdout evidence is weak.",
        },
        "boundaryGeoJson": boundary_geojson,
        "variableDiagnostics": {
            variable: {
                "surfaceSummary": variable_payloads[variable].get("surfaceSummary"),
                "stationHoldoutSummary": variable_payloads[variable].get("stationHoldoutSummary"),
            }
            for variable in VARIABLE_LAYERS
        },
        "points": points,
    }
    return payload, raster


def merge_holdout_station_payloads(
    variable_payloads: Mapping[str, Mapping[str, object]],
    source_variables: Iterable[str],
) -> list[dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    for variable in source_variables:
        for station in variable_payloads.get(variable, {}).get("holdoutStations", []):
            station_id = station.get("stationId")
            if not station_id:
                continue
            payload = dict(station)
            payload["sourceVariable"] = variable
            merged.setdefault(str(station_id), payload)
    return sorted(merged.values(), key=lambda station: str(station.get("stationId", "")))


def build_helpfulness_surface_payload(
    reliability_run_id: str,
    source_model_run_ids: Mapping[str, str],
    variable_payloads: Mapping[str, Mapping[str, object]],
    boundary_geojson: Mapping[str, object],
    bounds: Bounds,
    grid: Mapping[str, float | int],
    cells: list[GridCell],
    image_file_name: str,
) -> tuple[dict[str, object], list[list[float | None]]]:
    variable_points = {
        variable: {
            (int(point["row"]), int(point["column"])): point
            for point in payload.get("points", [])
        }
        for variable, payload in variable_payloads.items()
    }
    raster = [[None for _ in range(int(grid["width"]))] for _ in range(int(grid["height"]))]
    points = []
    source_variables = [
        variable
        for variable in VARIABLE_LAYERS
        if variable in variable_payloads
    ]

    for cell in cells:
        cell_key = (cell.row, cell.column)
        breakdown = {
            variable: variable_points[variable][cell_key]
            for variable in source_variables
            if cell_key in variable_points.get(variable, {})
        }
        if not breakdown:
            continue

        expected_maes = [float(point["expectedMaeF"]) for point in breakdown.values()]
        evidence_values = [float(point["evidenceStrength"]) for point in breakdown.values()]
        generalization_values = [float(point["reliability"]) for point in breakdown.values()]
        variable_helpfulness = []
        variables = {}
        for variable, point in breakdown.items():
            components = model_helpfulness_components(
                expected_mae_f=float(point["expectedMaeF"]),
                generalization_reliability=float(point["reliability"]),
                evidence=float(point["evidenceStrength"]),
            )
            variable_helpfulness.append(components["modelHelpfulness"])
            variables[variable] = {
                "reliability": components["modelHelpfulness"],
                "modelHelpfulness": components["modelHelpfulness"],
                "expectedMaeF": point["expectedMaeF"],
                "expectedMaeUsefulness": components["expectedMaeUsefulness"],
                "generalizationReliability": components["generalizationReliability"],
                "evidenceStrength": components["evidenceStrength"],
                "lowEvidencePenalty": components["lowEvidencePenalty"],
                "maePercentile": point["maePercentile"],
                "nearestHoldoutDistanceKm": point["nearestHoldoutDistanceKm"],
        }

        helpfulness = clamp(
            sum(variable_helpfulness) / len(variable_helpfulness),
            0.0,
            100.0,
        )
        worst_variable = min(variables.items(), key=lambda item: float(item[1]["modelHelpfulness"]))[0]
        worst_point = breakdown[worst_variable]
        point_payload = {
            "row": cell.row,
            "column": cell.column,
            "latitude": round(cell.latitude, 6),
            "longitude": round(cell.longitude, 6),
            "reliability": round(helpfulness, 2),
            "modelHelpfulness": round(helpfulness, 2),
            "expectedMaeF": round(sum(expected_maes) / len(expected_maes), 4),
            "expectedMaeUsefulness": round(
                sum(float(item["expectedMaeUsefulness"]) for item in variables.values()) / len(variables),
                2,
            ),
            "generalizationReliability": round(sum(generalization_values) / len(generalization_values), 2),
            "evidenceStrength": round(min(evidence_values), 2),
            "lowEvidencePenalty": round(
                max(float(item["lowEvidencePenalty"]) for item in variables.values()),
                2,
            ),
            "worstVariable": worst_variable,
            "nearestHoldoutStations": worst_point.get("nearestHoldoutStations", []),
            "nearestHighMaeStation": worst_point.get("nearestHighMaeStation"),
            "nearestLowMaeStation": worst_point.get("nearestLowMaeStation"),
            "variables": variables,
        }
        raster[cell.row][cell.column] = float(point_payload["modelHelpfulness"])
        points.append(point_payload)

    values = [float(point["modelHelpfulness"]) for point in points]
    payload = {
        "schemaVersion": SURFACE_SCHEMA_VERSION,
        "modelRunId": reliability_run_id,
        "sourceModelRunIds": {
            variable: source_model_run_ids[variable]
            for variable in source_variables
        },
        "scoreVersion": HELPFULNESS_SCORE_VERSION,
        "layer": HELPFULNESS_LAYER,
        "status": "ok" if set(VARIABLE_LAYERS).issubset(source_variables) else "partial",
        "sourceVariableLayers": source_variables,
        "missingVariableLayers": [
            variable
            for variable in VARIABLE_LAYERS
            if variable not in source_variables
        ],
        "bounds": bounds.as_dict(),
        "grid": dict(grid),
        "imageArtifact": image_file_name,
        "legend": legend_payload(),
        "visualization": surface_relative_visual_scale(values),
        "surfaceSummary": summarize_values(values),
        "calibration": {
            "method": "weighted_decision_support_score",
            "formula": (
                "0.50 * expectedMaeUsefulness + 0.30 * stationHoldoutGeneralizationReliability "
                "+ 0.20 * evidenceStrength - lowEvidencePenalty"
            ),
            "interpretation": (
                "Higher scores mean the model is more likely to be useful for regional exploration. "
                "This is a decision-support score, not a direct validation error estimate."
            ),
            "componentWeights": {
                "expectedMaeUsefulness": 0.5,
                "stationHoldoutGeneralizationReliability": 0.3,
                "evidenceStrength": 0.2,
            },
            "lowEvidencePenalty": "Applied only where station support evidence is weak.",
        },
        "boundaryGeoJson": boundary_geojson,
        "holdoutStations": merge_holdout_station_payloads(variable_payloads, source_variables),
        "variableDiagnostics": {
            variable: {
                "surfaceSummary": variable_payloads[variable].get("surfaceSummary"),
                "stationHoldoutSummary": variable_payloads[variable].get("stationHoldoutSummary"),
            }
            for variable in source_variables
        },
        "points": points,
    }
    return payload, raster


def legend_payload() -> list[dict[str, object]]:
    return [
        {"percentileMin": 80, "label": "Top 20% trend", "color": "#16a34a"},
        {"percentileMin": 60, "percentileMax": 80, "label": "60-80% trend", "color": "#14b8a6"},
        {"percentileMin": 35, "percentileMax": 60, "label": "35-60% trend", "color": "#facc15"},
        {"percentileMin": 15, "percentileMax": 35, "label": "15-35% trend", "color": "#f97316"},
        {"percentileMax": 15, "label": "Bottom 15% trend", "color": "#b91c1c"},
    ]


def surface_relative_visual_scale(values: list[float]) -> dict[str, object]:
    sorted_values = sorted(value for value in values if math.isfinite(value))
    if not sorted_values:
        return {
            "scaleVersion": "surface-relative-quantile-v1",
            "method": "surface_relative_quantile_bins",
            "note": "Map colors are relative to available grid cells; inspector scores remain absolute holdout-MAE percentile reliability.",
            "thresholds": {},
        }

    thresholds = {
        "p15": quantile(sorted_values, 0.15),
        "p35": quantile(sorted_values, 0.35),
        "p60": quantile(sorted_values, 0.60),
        "p80": quantile(sorted_values, 0.80),
    }
    return {
        "scaleVersion": "surface-relative-quantile-v1",
        "method": "surface_relative_quantile_bins",
        "note": "Map colors are relative to available grid cells; inspector scores remain absolute holdout-MAE percentile reliability.",
        "thresholds": {
            key: round(value, 4)
            for key, value in thresholds.items()
        },
    }


def color_for_reliability(
    value: float | None,
    visual_scale: Mapping[str, object] | None = None,
) -> tuple[int, int, int, int]:
    if value is None:
        return 0, 0, 0, 0

    thresholds = (
        visual_scale.get("thresholds", {})
        if isinstance(visual_scale, Mapping)
        else {}
    )
    p15 = to_optional_float(thresholds.get("p15"))
    p35 = to_optional_float(thresholds.get("p35"))
    p60 = to_optional_float(thresholds.get("p60"))
    p80 = to_optional_float(thresholds.get("p80"))

    if p15 is None or p35 is None or p60 is None or p80 is None:
        p15, p35, p60, p80 = 15.0, 35.0, 60.0, 80.0

    if value <= p15:
        return 185, 28, 28, 185
    if value <= p35:
        return 249, 115, 22, 185
    if value <= p60:
        return 250, 204, 21, 185
    if value <= p80:
        return 20, 184, 166, 185
    return 22, 163, 74, 185


def png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + chunk_type
        + payload
        + struct.pack(">I", zlib.crc32(chunk_type + payload) & 0xFFFFFFFF)
    )


def write_reliability_png(file_path: Path, raster: list[list[float | None]]) -> None:
    height = len(raster)
    width = len(raster[0]) if height else 0
    if width <= 0 or height <= 0:
        raise ValueError("Cannot write reliability PNG for an empty raster.")

    values = [
        float(value)
        for row in raster
        for value in row
        if value is not None
    ]
    visual_scale = surface_relative_visual_scale(values)
    raw_rows = []
    for row in raster:
        pixels = bytearray()
        for value in row:
            pixels.extend(color_for_reliability(value, visual_scale))
        raw_rows.append(b"\x00" + bytes(pixels))

    png = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(b"".join(raw_rows), level=9))
        + png_chunk(b"IEND", b"")
    )
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(png)


def build_summary_payload(
    reliability_run_id: str,
    surfaces: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    available_layers = [
        layer
        for layer in RELIABILITY_LAYERS
        if layer in surfaces
    ]
    if not available_layers:
        raise ValueError("Cannot build reliability summary without at least one surface.")

    notes = ["Lower station holdout MAE maps to higher reliability."]
    if HELPFULNESS_LAYER in surfaces:
        notes.append(
            "The model helpfulness layer combines expected MAE usefulness, station-holdout generalization, and evidence strength into one decision-support score."
        )
    if "overall" in surfaces:
        notes.append(
            "The overall layer combines TAVG, TMIN, and TMAX reliability and penalizes only weak evidence."
        )
    elif not set(VARIABLE_LAYERS).issubset(surfaces):
        notes.append(
            "The overall layer becomes available after TAVG, TMIN, and TMAX holdout metrics are all present."
        )

    return {
        "schemaVersion": SUMMARY_SCHEMA_VERSION,
        "modelRunId": reliability_run_id,
        "scoreVersion": SCORE_VERSION,
        "status": "ok",
        "defaultLayer": (
            HELPFULNESS_LAYER
            if HELPFULNESS_LAYER in surfaces
            else "overall"
                if "overall" in surfaces
                else available_layers[0]
        ),
        "availableLayers": available_layers,
        "layers": {
            layer: {
                "surfaceArtifact": f"reliability_surface_{layer}.json",
                "imageArtifact": surface.get("imageArtifact"),
                "surfaceSummary": surface.get("surfaceSummary"),
                "stationHoldoutSummary": surface.get("stationHoldoutSummary"),
                "bounds": surface.get("bounds"),
            }
            for layer, surface in surfaces.items()
        },
        "notes": notes,
    }
