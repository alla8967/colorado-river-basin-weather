"""Score one latitude/longitude against confidence-support evidence.

Use this CLI to inspect the same confidence logic that the backend exposes to the browser."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import config
from common.confidence_data import load_confidence_support_inputs
from common.confidence_support import (
    ConfidenceSupportConfig,
    DEFAULT_COMPONENT_WEIGHTS,
    SupportPoint,
    calculate_confidence_support,
)


DEFAULT_VALIDATION_METRICS_FILE = (
    config.REPORT_DIR
    / "option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain_offset_terrain_standard_random_forest_station_metrics.csv"
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Score confidence/support for one latitude/longitude using station, "
            "terrain, and optional model-validation data."
        )
    )
    parser.add_argument("latitude", type=float, help="Point latitude.")
    parser.add_argument("longitude", type=float, help="Point longitude.")
    parser.add_argument(
        "--elevation-m",
        type=float,
        default=None,
        help="Optional point elevation in meters. Terrain sampling comes in a later step.",
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
        help=(
            "Optional station metrics CSV from a model run. Use --no-validation "
            "to score without model-validation evidence."
        ),
    )
    parser.add_argument(
        "--no-validation",
        action="store_true",
        help="Do not load model-validation metrics.",
    )
    parser.add_argument(
        "--model-reference",
        default=None,
        help="Model/run identifier attached to the confidence result.",
    )
    parser.add_argument(
        "--score-version",
        default=None,
        help="Override the default scoreVersion in the result.",
    )
    parser.add_argument(
        "--component-weight",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help=(
            "Override a component weight. May be repeated, for example "
            "--component-weight stationCoverage=0.5."
        ),
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Write compact JSON instead of pretty JSON.",
    )
    return parser.parse_args()


def parse_component_weights(
    weight_overrides: list[str],
) -> dict[str, float]:
    weights = dict(DEFAULT_COMPONENT_WEIGHTS)

    for override in weight_overrides:
        if "=" not in override:
            raise ValueError(f"Invalid component weight override: {override}")

        name, value = override.split("=", 1)
        name = name.strip()
        if name not in DEFAULT_COMPONENT_WEIGHTS:
            valid_names = ", ".join(sorted(DEFAULT_COMPONENT_WEIGHTS))
            raise ValueError(
                f"Unknown component weight '{name}'. Valid names: {valid_names}"
            )

        weights[name] = float(value)

    return weights


def build_config(arguments: argparse.Namespace) -> ConfidenceSupportConfig:
    config_kwargs = {
        "model_reference": arguments.model_reference,
        "component_weights": parse_component_weights(arguments.component_weight),
    }

    if arguments.score_version is not None:
        config_kwargs["score_version"] = arguments.score_version

    return ConfidenceSupportConfig(**config_kwargs)


def print_text_result(result_dict: dict[str, object]) -> None:
    print("Confidence Support Result")
    print("=========================")
    print(f"Point: {result_dict['latitude']}, {result_dict['longitude']}")
    print(f"Score: {result_dict['score']} ({result_dict['label']})")
    print(f"Score version: {result_dict['scoreVersion']}")

    if result_dict.get("modelReference"):
        print(f"Model reference: {result_dict['modelReference']}")

    print()
    print("Components")
    print("----------")
    for name, score in sorted(result_dict["components"].items()):
        print(f"{name:<22} {score:>7}")

    if result_dict["reasons"]:
        print()
        print("Reasons")
        print("-------")
        for reason in result_dict["reasons"]:
            print(f"- {reason}")

    if result_dict["warnings"]:
        print()
        print("Warnings")
        print("--------")
        for warning in result_dict["warnings"]:
            print(f"- {warning}")

    if result_dict["nearestStations"]:
        print()
        print("Nearest Stations")
        print("----------------")
        for station in result_dict["nearestStations"]:
            elevation_difference = station["elevationDifferenceM"]
            elevation_text = (
                "N/A"
                if elevation_difference is None
                else f"{elevation_difference:.1f} m"
            )
            print(
                f"- {station['stationId']} ({station['stationRole']}): "
                f"{station['distanceKm']:.1f} km, elevation diff {elevation_text}"
            )


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

    result = calculate_confidence_support(
        SupportPoint(
            latitude=arguments.latitude,
            longitude=arguments.longitude,
            elevation_m=arguments.elevation_m,
        ),
        target_stations=inputs.target_stations,
        hub_stations=inputs.hub_stations,
        validation_by_station_id=inputs.validation_by_station_id,
        config=scorer_config,
    )
    result_dict = result.as_dict()

    if arguments.format == "text":
        print_text_result(result_dict)
        return

    if arguments.compact:
        print(json.dumps(result_dict, separators=(",", ":")))
    else:
        print(json.dumps(result_dict, indent=2))


if __name__ == "__main__":
    main()
