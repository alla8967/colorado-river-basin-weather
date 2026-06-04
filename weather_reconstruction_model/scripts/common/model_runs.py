from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from common.csv_utils import CsvRow, read_csv_rows


REQUIRED_MODEL_RUN_FILES = {
    "manifest": "model_manifest.json",
    "feature_schema": "feature_schema.json",
    "station_metrics": "station_metrics.csv",
    "validation_predictions": "validation_predictions.csv",
    "calibration_points": "calibration_points.csv",
    "confidence_grid": "confidence_grid.json",
}

STATION_METRIC_COLUMNS = {
    "target_station_id",
    "target_name",
    "test_rows",
    "mae",
    "rmse",
    "correlation",
}

VALIDATION_PREDICTION_COLUMNS = {
    "date",
    "target_station_id",
    "target_name",
    "actual_tavg",
    "predicted_tavg",
    "error",
}

CALIBRATION_POINT_COLUMNS = {
    "latitude",
    "longitude",
    "target_station_id",
    "observed_mae_f",
    "observed_rmse_f",
    "observed_correlation",
    "support_score",
}


@dataclass(frozen=True)
class ModelRunPaths:
    model_run_id: str
    root: Path
    manifest: Path
    feature_schema: Path
    station_metrics: Path
    validation_predictions: Path
    calibration_points: Path
    confidence_grid: Path


def resolve_model_run(model_run_root: Path, model_run_id: str) -> ModelRunPaths:
    """Return canonical paths for a model run id."""
    root = model_run_root / model_run_id

    return ModelRunPaths(
        model_run_id=model_run_id,
        root=root,
        manifest=root / REQUIRED_MODEL_RUN_FILES["manifest"],
        feature_schema=root / REQUIRED_MODEL_RUN_FILES["feature_schema"],
        station_metrics=root / REQUIRED_MODEL_RUN_FILES["station_metrics"],
        validation_predictions=root / REQUIRED_MODEL_RUN_FILES["validation_predictions"],
        calibration_points=root / REQUIRED_MODEL_RUN_FILES["calibration_points"],
        confidence_grid=root / REQUIRED_MODEL_RUN_FILES["confidence_grid"],
    )


def load_json_file(file_path: Path) -> dict[str, Any]:
    with file_path.open("r") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {file_path}.")

    return data


def missing_model_run_files(paths: ModelRunPaths) -> list[Path]:
    expected_paths = [
        paths.manifest,
        paths.feature_schema,
        paths.station_metrics,
        paths.validation_predictions,
        paths.calibration_points,
        paths.confidence_grid,
    ]
    return [file_path for file_path in expected_paths if not file_path.exists()]


def require_model_run_files(paths: ModelRunPaths) -> None:
    missing = missing_model_run_files(paths)

    if missing:
        missing_list = ", ".join(str(file_path) for file_path in missing)
        raise FileNotFoundError(f"Missing model run artifact file(s): {missing_list}")


def validate_required_columns(rows: list[CsvRow], required_columns: set[str], file_path: Path) -> None:
    if not rows:
        raise ValueError(f"Expected at least one row in {file_path}.")

    present_columns = set(rows[0].keys())
    missing_columns = sorted(required_columns - present_columns)

    if missing_columns:
        missing_text = ", ".join(missing_columns)
        raise ValueError(f"Missing required column(s) in {file_path}: {missing_text}")


def load_model_manifest(paths: ModelRunPaths) -> dict[str, Any]:
    manifest = load_json_file(paths.manifest)
    manifest_id = manifest.get("modelRunId")

    if manifest_id != paths.model_run_id:
        raise ValueError(
            "model_manifest.json modelRunId does not match folder id: "
            f"{manifest_id!r} != {paths.model_run_id!r}"
        )

    return manifest


def load_feature_schema(paths: ModelRunPaths) -> dict[str, Any]:
    schema = load_json_file(paths.feature_schema)

    if not isinstance(schema.get("features"), list):
        raise ValueError("feature_schema.json must include a features list.")

    return schema


def load_station_metrics(paths: ModelRunPaths) -> list[CsvRow]:
    rows = read_csv_rows(paths.station_metrics)
    validate_required_columns(rows, STATION_METRIC_COLUMNS, paths.station_metrics)
    return rows


def load_validation_predictions(paths: ModelRunPaths) -> list[CsvRow]:
    rows = read_csv_rows(paths.validation_predictions)
    validate_required_columns(
        rows,
        VALIDATION_PREDICTION_COLUMNS,
        paths.validation_predictions,
    )
    return rows


def load_calibration_points(paths: ModelRunPaths) -> list[CsvRow]:
    rows = read_csv_rows(paths.calibration_points)
    validate_required_columns(rows, CALIBRATION_POINT_COLUMNS, paths.calibration_points)
    return rows


def load_confidence_grid(paths: ModelRunPaths) -> dict[str, Any]:
    grid = load_json_file(paths.confidence_grid)
    grid_id = grid.get("modelRunId")

    if grid_id != paths.model_run_id:
        raise ValueError(
            "confidence_grid.json modelRunId does not match folder id: "
            f"{grid_id!r} != {paths.model_run_id!r}"
        )

    if not isinstance(grid.get("points"), list):
        raise ValueError("confidence_grid.json must include a points list.")

    return grid


def load_model_run(paths: ModelRunPaths) -> dict[str, Any]:
    require_model_run_files(paths)

    return {
        "paths": paths,
        "manifest": load_model_manifest(paths),
        "feature_schema": load_feature_schema(paths),
        "station_metrics": load_station_metrics(paths),
        "validation_predictions": load_validation_predictions(paths),
        "calibration_points": load_calibration_points(paths),
        "confidence_grid": load_confidence_grid(paths),
    }
