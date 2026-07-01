"""Build map-ready confidence points from validation, terrain, and station metadata.

The resulting JSON feeds the frontend confidence layer and location-level support analysis."""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import config
from common.confidence_data import ConfidenceSupportInputs, load_confidence_support_inputs
from common.confidence_support import (
    ConfidenceSupportConfig,
    SupportPoint,
    SupportStation,
    calculate_confidence_support,
)
from score_confidence_point import (
    DEFAULT_VALIDATION_METRICS_FILE,
    parse_component_weights,
)

DEFAULT_OUTPUT_FILE = config.PROJECT_DIR / "station-proxy-backend" / "assets" / "confidence-points.json"


@dataclass(frozen=True)
class Bounds:
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float

    def as_dict(self) -> dict[str, float]:
        return {
            "latMin": self.lat_min,
            "latMax": self.lat_max,
            "lonMin": self.lon_min,
            "lonMax": self.lon_max,
        }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build sparse confidence/support sample points for map visualization. "
            "The output is intended for dot/marker layers, not rectangular overlays."
        )
    )
    parser.add_argument(
        "--target-candidates",
        type=Path,
        default=config.TARGET_CANDIDATE_FILE,
        help="Target station candidate CSV.",
    )
    parser.add_argument(
        "--hub-candidates",
        type=Path,
        default=config.HUB_CANDIDATE_FILE,
        help="Hub station candidate CSV.",
    )
    parser.add_argument(
        "--terrain-features",
        type=Path,
        default=config.TERRAIN_FEATURE_FILE,
        help="Station terrain features CSV.",
    )
    parser.add_argument(
        "--validation-metrics",
        type=Path,
        default=DEFAULT_VALIDATION_METRICS_FILE,
        help="Optional station metrics CSV from a model run.",
    )
    parser.add_argument(
        "--no-validation",
        action="store_true",
        help="Do not load model-validation metrics.",
    )
    parser.add_argument(
        "--model-reference",
        default=None,
        help="Model/run identifier attached to generated confidence results.",
    )
    parser.add_argument(
        "--score-version",
        default=None,
        help="Override the default scoreVersion in the output.",
    )
    parser.add_argument(
        "--component-weight",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Override a component weight. May be repeated.",
    )
    parser.add_argument(
        "--spacing-km",
        type=float,
        default=50.0,
        help="Approximate spacing between sample points in kilometers.",
    )
    parser.add_argument("--lat-min", type=float, default=None, help="Minimum latitude.")
    parser.add_argument("--lat-max", type=float, default=None, help="Maximum latitude.")
    parser.add_argument("--lon-min", type=float, default=None, help="Minimum longitude.")
    parser.add_argument("--lon-max", type=float, default=None, help="Maximum longitude.")
    parser.add_argument(
        "--bounds-padding-degrees",
        type=float,
        default=0.25,
        help="Padding applied to station-derived bounds when explicit bounds are omitted.",
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=2500,
        help="Safety limit for generated sample points.",
    )
    parser.add_argument(
        "--nearest-station-limit",
        type=int,
        default=3,
        help="Nearest stations to include for each sample point.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="JSON output file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned point count without writing JSON.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Write compact JSON instead of pretty JSON.",
    )
    return parser.parse_args()


def build_config(arguments: argparse.Namespace) -> ConfidenceSupportConfig:
    config_kwargs = {
        "model_reference": arguments.model_reference,
        "component_weights": parse_component_weights(arguments.component_weight),
    }

    if arguments.score_version is not None:
        config_kwargs["score_version"] = arguments.score_version

    return ConfidenceSupportConfig(**config_kwargs)


def explicit_bounds(arguments: argparse.Namespace) -> Bounds | None:
    values = [
        arguments.lat_min,
        arguments.lat_max,
        arguments.lon_min,
        arguments.lon_max,
    ]

    if all(value is None for value in values):
        return None

    if any(value is None for value in values):
        raise ValueError("Provide all explicit bounds: --lat-min, --lat-max, --lon-min, and --lon-max.")

    bounds = Bounds(
        lat_min=arguments.lat_min,
        lat_max=arguments.lat_max,
        lon_min=arguments.lon_min,
        lon_max=arguments.lon_max,
    )
    validate_bounds(bounds)
    return bounds


def station_derived_bounds(
    stations: Sequence[SupportStation],
    padding_degrees: float,
) -> Bounds:
    if not stations:
        raise ValueError("Cannot derive confidence point bounds without stations.")

    bounds = Bounds(
        lat_min=min(station.latitude for station in stations) - padding_degrees,
        lat_max=max(station.latitude for station in stations) + padding_degrees,
        lon_min=min(station.longitude for station in stations) - padding_degrees,
        lon_max=max(station.longitude for station in stations) + padding_degrees,
    )
    validate_bounds(bounds)
    return bounds


def validate_bounds(bounds: Bounds) -> None:
    if bounds.lat_min >= bounds.lat_max:
        raise ValueError("lat-min must be less than lat-max.")

    if bounds.lon_min >= bounds.lon_max:
        raise ValueError("lon-min must be less than lon-max.")


def resolve_bounds(
    arguments: argparse.Namespace,
    inputs: ConfidenceSupportInputs,
) -> Bounds:
    bounds = explicit_bounds(arguments)
    if bounds is not None:
        return bounds

    return station_derived_bounds(
        [*inputs.target_stations, *inputs.hub_stations],
        padding_degrees=arguments.bounds_padding_degrees,
    )


def latitude_step_degrees(spacing_km: float) -> float:
    validate_spacing(spacing_km)
    return spacing_km / 111.32


def longitude_step_degrees(
    spacing_km: float,
    latitude: float,
) -> float:
    validate_spacing(spacing_km)
    cosine = abs(math.cos(math.radians(latitude)))
    cosine = max(cosine, 0.10)
    return spacing_km / (111.32 * cosine)


def validate_spacing(spacing_km: float) -> None:
    if spacing_km <= 0:
        raise ValueError("spacing-km must be greater than zero.")


def inclusive_float_range(
    start: float,
    stop: float,
    step: float,
) -> list[float]:
    values = []
    value = start
    epsilon = step * 0.001

    while value <= stop + epsilon:
        values.append(round(value, 6))
        value += step

    return values


def generate_sample_coordinates(
    bounds: Bounds,
    spacing_km: float,
) -> list[tuple[float, float]]:
    latitudes = inclusive_float_range(
        bounds.lat_min,
        bounds.lat_max,
        latitude_step_degrees(spacing_km),
    )
    coordinates = []

    for latitude in latitudes:
        longitudes = inclusive_float_range(
            bounds.lon_min,
            bounds.lon_max,
            longitude_step_degrees(spacing_km, latitude),
        )
        for longitude in longitudes:
            coordinates.append((latitude, longitude))

    return coordinates


def nearest_station_summary(
    nearest_stations: list[dict[str, object]],
    limit: int,
) -> list[dict[str, object]]:
    return nearest_stations[:max(0, limit)]


def confidence_point_from_result(
    result_dict: dict[str, object],
    nearest_station_limit: int,
) -> dict[str, object]:
    return {
        "latitude": result_dict["latitude"],
        "longitude": result_dict["longitude"],
        "score": result_dict["score"],
        "label": result_dict["label"],
        "components": result_dict["components"],
        "warnings": result_dict["warnings"],
        "nearestStations": nearest_station_summary(
            result_dict["nearestStations"],
            nearest_station_limit,
        ),
    }


def build_confidence_points_payload(
    inputs: ConfidenceSupportInputs,
    scorer_config: ConfidenceSupportConfig,
    bounds: Bounds,
    spacing_km: float,
    nearest_station_limit: int,
    max_points: int,
) -> dict[str, object]:
    coordinates = generate_sample_coordinates(bounds, spacing_km)

    if len(coordinates) > max_points:
        raise ValueError(
            f"Requested confidence surface would create {len(coordinates)} points, "
            f"which exceeds --max-points {max_points}."
        )

    points = []
    for latitude, longitude in coordinates:
        result = calculate_confidence_support(
            SupportPoint(latitude=latitude, longitude=longitude),
            target_stations=inputs.target_stations,
            hub_stations=inputs.hub_stations,
            validation_by_station_id=inputs.validation_by_station_id,
            config=scorer_config,
        )
        points.append(
            confidence_point_from_result(
                result.as_dict(),
                nearest_station_limit=nearest_station_limit,
            )
        )

    return {
        "schemaVersion": "confidence-points-v1",
        "scoreVersion": scorer_config.score_version,
        "modelReference": scorer_config.model_reference,
        "spacingKm": spacing_km,
        "bounds": bounds.as_dict(),
        "pointCount": len(points),
        "points": points,
    }


def write_payload(
    output_file: Path,
    payload: dict[str, object],
    compact: bool,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        output_file.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    else:
        output_file.write_text(json.dumps(payload, indent=2) + "\n")


def main() -> None:
    arguments = parse_arguments()
    validation_metrics_file = None

    if not arguments.no_validation:
        validation_metrics_file = arguments.validation_metrics

    inputs = load_confidence_support_inputs(
        target_candidate_file=arguments.target_candidates,
        hub_candidate_file=arguments.hub_candidates,
        terrain_file=arguments.terrain_features,
        validation_metrics_file=validation_metrics_file,
        model_reference=arguments.model_reference,
    )
    scorer_config = build_config(arguments)
    bounds = resolve_bounds(arguments, inputs)
    coordinates = generate_sample_coordinates(bounds, arguments.spacing_km)

    if len(coordinates) > arguments.max_points:
        raise ValueError(
            f"Requested confidence surface would create {len(coordinates)} points, "
            f"which exceeds --max-points {arguments.max_points}."
        )

    if arguments.dry_run:
        print("Confidence point generation dry run")
        print("===================================")
        print(f"Bounds: {bounds.as_dict()}")
        print(f"Spacing km: {arguments.spacing_km}")
        print(f"Point count: {len(coordinates)}")
        print(f"Output file: {arguments.output_file}")
        return

    payload = build_confidence_points_payload(
        inputs=inputs,
        scorer_config=scorer_config,
        bounds=bounds,
        spacing_km=arguments.spacing_km,
        nearest_station_limit=arguments.nearest_station_limit,
        max_points=arguments.max_points,
    )
    write_payload(arguments.output_file, payload, arguments.compact)
    print(f"Wrote {payload['pointCount']} confidence points to {arguments.output_file}")


if __name__ == "__main__":
    main()
