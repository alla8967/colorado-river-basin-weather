"""Test model-run artifact loading and required-file validation.

These checks protect backend/report consumers from malformed generated run folders."""

from pathlib import Path
import json
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from common.csv_utils import write_csv_rows
from common.model_runs import (
    load_model_run,
    missing_model_run_files,
    resolve_model_run,
)


MODEL_RUN_ID = "example_model_run"


def write_json(file_path: Path, data: dict[str, object]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, indent=2) + "\n")


def build_model_run(root: Path):
    paths = resolve_model_run(root, MODEL_RUN_ID)

    write_json(
        paths.manifest,
        {
            "modelRunId": MODEL_RUN_ID,
            "modelFamily": "random_forest",
            "predictionTarget": "daily_tavg_f",
            "trainingMode": "station_holdout",
            "validationMode": "out_of_sample_station_holdout",
            "sourceFiles": {},
            "summaryMetrics": {
                "validationStationCount": 1,
                "testRows": 2,
                "meanMaeF": 1.2,
                "meanRmseF": 1.8,
            },
        },
    )
    write_json(
        paths.feature_schema,
        {
            "featureSchemaVersion": "feature-schema-v1",
            "targetColumn": "target_tavg",
            "features": [
                {
                    "name": "hub_1_tavg",
                    "type": "float",
                    "unit": "F",
                    "required": True,
                }
            ],
        },
    )
    write_csv_rows(
        paths.station_metrics,
        [
            {
                "target_station_id": "T1",
                "target_name": "Target One",
                "test_rows": 2,
                "mae": 1.2,
                "rmse": 1.8,
                "correlation": 0.99,
            }
        ],
        ["target_station_id", "target_name", "test_rows", "mae", "rmse", "correlation"],
    )
    write_csv_rows(
        paths.validation_predictions,
        [
            {
                "date": "2024-01-01",
                "target_station_id": "T1",
                "target_name": "Target One",
                "actual_tavg": 30.0,
                "predicted_tavg": 29.0,
                "error": 1.0,
            }
        ],
        [
            "date",
            "target_station_id",
            "target_name",
            "actual_tavg",
            "predicted_tavg",
            "error",
        ],
    )
    write_csv_rows(
        paths.calibration_points,
        [
            {
                "latitude": 39.75,
                "longitude": -105.0,
                "target_station_id": "T1",
                "observed_mae_f": 1.2,
                "observed_rmse_f": 1.8,
                "observed_correlation": 0.99,
                "support_score": 82.0,
            }
        ],
        [
            "latitude",
            "longitude",
            "target_station_id",
            "observed_mae_f",
            "observed_rmse_f",
            "observed_correlation",
            "support_score",
        ],
    )
    write_json(
        paths.confidence_grid,
        {
            "modelRunId": MODEL_RUN_ID,
            "scoreVersion": "calibrated-confidence-v1",
            "bounds": {
                "latMin": 39.0,
                "latMax": 40.0,
                "lonMin": -106.0,
                "lonMax": -104.0,
            },
            "points": [
                {
                    "latitude": 39.75,
                    "longitude": -105.0,
                    "confidence": 82.0,
                    "expectedMaeF": 1.8,
                    "label": "High confidence",
                }
            ],
        },
    )

    return paths


def assert_raises(expected_error: type[Exception], callback) -> None:
    try:
        callback()
    except expected_error:
        return

    raise AssertionError(f"Expected {expected_error.__name__} to be raised.")


def test_load_model_run_contract() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        paths = build_model_run(Path(temp_dir))
        model_run = load_model_run(paths)

        assert model_run["manifest"]["modelRunId"] == MODEL_RUN_ID
        assert model_run["feature_schema"]["features"][0]["name"] == "hub_1_tavg"
        assert model_run["station_metrics"][0]["target_station_id"] == "T1"
        assert model_run["validation_predictions"][0]["error"] == "1.0"
        assert model_run["calibration_points"][0]["support_score"] == "82.0"
        assert model_run["confidence_grid"]["points"][0]["confidence"] == 82.0


def test_missing_model_run_files_are_reported() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        paths = resolve_model_run(Path(temp_dir), MODEL_RUN_ID)
        missing = missing_model_run_files(paths)

        assert len(missing) == 6
        assert paths.manifest in missing
        assert_raises(FileNotFoundError, lambda: load_model_run(paths))


def main() -> None:
    test_load_model_run_contract()
    test_missing_model_run_files_are_reported()
    print("model run tests passed")


if __name__ == "__main__":
    main()
