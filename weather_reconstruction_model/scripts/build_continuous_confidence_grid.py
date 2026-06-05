"""Interpolate station confidence evidence into a continuous map grid.

This creates the gridded confidence layer used by the browser map to show spatial support between stations."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Mapping

import config
from build_calibrated_confidence_comparison import (
    SCORE_VERSION as ANCHOR_SCORE_VERSION,
    confidence_label,
    fit_expected_mae_model,
    pearson_correlation,
    score_pairs,
)
from build_confidence_points import (
    build_confidence_points_payload,
    resolve_bounds,
)
from common.confidence_data import load_confidence_support_inputs
from common.confidence_support import ConfidenceSupportConfig
from common.csv_utils import read_csv_rows
from common.json_utils import write_json_file
from common.model_runs import load_confidence_grid, resolve_model_run
from common.number_utils import to_optional_float


DEFAULT_MODEL_RUN_ID = (
    "option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain_"
    "offset_terrain_standard_random_forest"
)

CONTINUOUS_SCORE_VERSION = "calibrated-confidence-continuous-support-v1"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a full-region model-run confidence grid from the current support "
            "surface and held-out station calibration evidence."
        )
    )
    parser.add_argument("--model-run-id", default=DEFAULT_MODEL_RUN_ID)
    parser.add_argument("--model-run-root", type=Path, default=config.MODEL_RUN_DIR)
    parser.add_argument("--target-candidates", type=Path, default=config.TARGET_CANDIDATE_FILE)
    parser.add_argument("--hub-candidates", type=Path, default=config.HUB_CANDIDATE_FILE)
    parser.add_argument("--terrain-features", type=Path, default=config.TERRAIN_FEATURE_FILE)
    parser.add_argument("--spacing-km", type=float, default=50.0)
    parser.add_argument("--lat-min", type=float, default=None)
    parser.add_argument("--lat-max", type=float, default=None)
    parser.add_argument("--lon-min", type=float, default=None)
    parser.add_argument("--lon-max", type=float, default=None)
    parser.add_argument("--max-points", type=int, default=5000)
    parser.add_argument("--nearest-station-limit", type=int, default=3)
    parser.add_argument("--bounds-padding-degrees", type=float, default=0.25)
    parser.add_argument("--output-grid", type=Path, default=None)
    parser.add_argument("--anchor-backup", type=Path, default=None)
    return parser.parse_args()


def backup_anchor_grid(paths, backup_path: Path) -> None:
    if not paths.confidence_grid.exists() or backup_path.exists():
        return

    grid = load_confidence_grid(paths)
    if grid.get("pointType") == "validation_station_anchor":
        write_json_file(backup_path, grid)


def grid_point_from_support_point(
    point: Mapping[str, object],
    expected_mae_model,
) -> dict[str, object]:
    confidence = to_optional_float(point.get("score")) or 0.0
    expected_mae = expected_mae_model.predict(confidence)

    return {
        "latitude": point["latitude"],
        "longitude": point["longitude"],
        "confidence": round(confidence, 2),
        "expectedMaeF": round(expected_mae, 3),
        "label": confidence_label(confidence),
        "supportScore": round(confidence, 2),
        "components": point.get("components", {}),
        "warnings": point.get("warnings", []),
        "nearestStations": point.get("nearestStations", []),
        "physicalRiskReasons": [],
    }


def build_payload(
    model_run_id: str,
    support_payload: Mapping[str, object],
    expected_mae_model,
    calibration_rows: list[Mapping[str, object]],
) -> dict[str, object]:
    support_pairs = score_pairs(calibration_rows, "support_confidence")
    physical_pairs = score_pairs(calibration_rows, "physical_adjusted_confidence")
    points = [
        grid_point_from_support_point(point, expected_mae_model)
        for point in support_payload["points"]
    ]

    return {
        "schemaVersion": "confidence-grid-v1",
        "modelRunId": model_run_id,
        "scoreVersion": CONTINUOUS_SCORE_VERSION,
        "status": "ok",
        "calibrationStatus": "expected_mae_calibrated_from_out_of_sample_station_holdout",
        "pointType": "continuous_support_surface",
        "pointCount": len(points),
        "spacingKm": support_payload["spacingKm"],
        "bounds": support_payload["bounds"],
        "expectedMaeModel": expected_mae_model.as_dict(),
        "calibrationSummary": {
            "validationStationCount": len(calibration_rows),
            "anchorScoreVersion": ANCHOR_SCORE_VERSION,
            "supportPearsonRVsMae": round(pearson_correlation(support_pairs), 6),
            "physicalAdjustedPearsonRVsMae": round(pearson_correlation(physical_pairs), 6),
            "surfaceScoreColumn": "support_confidence",
            "surfaceReason": (
                "This continuous surface covers the full station catalog extent. "
                "Physical-risk adjustment is retained in validation-anchor artifacts "
                "but is not yet available for arbitrary grid cells."
            ),
        },
        "points": points,
        "notes": [
            "This replaces the validation-anchor-only map with a full-region support surface.",
            "Expected MAE is calibrated from held-out validation stations.",
            "The production model artifact can be trained separately from this confidence surface.",
            "Physical risk reasons are blank for non-station grid cells until terrain features are calculated at arbitrary map points.",
        ],
    }


def main() -> None:
    arguments = parse_arguments()
    paths = resolve_model_run(arguments.model_run_root, arguments.model_run_id)
    calibration_candidate_file = paths.root / "calibrated_confidence_candidates.csv"
    if not calibration_candidate_file.exists():
        raise FileNotFoundError(
            "Missing calibrated confidence candidates. Run "
            "build_calibrated_confidence_comparison.py first."
        )

    calibration_rows = read_csv_rows(calibration_candidate_file)
    expected_mae_model = fit_expected_mae_model(
        calibration_rows,
        "support_confidence",
    )
    inputs = load_confidence_support_inputs(
        target_candidate_file=arguments.target_candidates,
        hub_candidate_file=arguments.hub_candidates,
        terrain_file=arguments.terrain_features,
        validation_metrics_file=paths.station_metrics,
        model_reference=arguments.model_run_id,
    )
    bounds = resolve_bounds(arguments, inputs)
    support_payload = build_confidence_points_payload(
        inputs=inputs,
        scorer_config=ConfidenceSupportConfig(
            score_version=CONTINUOUS_SCORE_VERSION,
            model_reference=arguments.model_run_id,
        ),
        bounds=bounds,
        spacing_km=arguments.spacing_km,
        nearest_station_limit=arguments.nearest_station_limit,
        max_points=arguments.max_points,
    )
    output_grid = arguments.output_grid or paths.confidence_grid
    anchor_backup = arguments.anchor_backup or paths.root / "confidence_grid_validation_anchors.json"

    backup_anchor_grid(paths, anchor_backup)
    write_json_file(
        output_grid,
        build_payload(
            arguments.model_run_id,
            support_payload,
            expected_mae_model,
            calibration_rows,
        ),
    )

    print(f"Continuous confidence grid: {output_grid}")
    print(f"Validation anchor backup: {anchor_backup}")
    print(f"Points: {support_payload['pointCount']}")
    print(f"Bounds: {support_payload['bounds']}")
    print(
        "Support score expected-MAE model: "
        f"MAE = {expected_mae_model.intercept:.4f} "
        f"+ ({expected_mae_model.slope:.4f} * confidence)"
    )


if __name__ == "__main__":
    main()
