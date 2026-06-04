from pathlib import Path
import math
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from common.csv_utils import (
    count_csv_rows,
    read_csv_fieldnames,
    read_csv_rows,
    write_csv_rows,
    write_csv_rows_inferred,
)
from common.geo_utils import calculate_distance_km
from common.json_utils import write_json_file
from common.model_artifacts import (
    NO_SERIALIZED_ESTIMATOR_NOTE,
    SERIALIZED_ESTIMATOR_NOTE,
    build_production_model_run_manifest,
    build_feature_schema_payload,
    build_serialized_model_artifact_manifest,
    build_validation_model_run_manifest,
    infer_feature_unit,
    merge_serialized_model_run_manifest,
    project_relative_path,
)
from common.metrics import (
    calculate_correlation,
    calculate_mae,
    calculate_metrics,
    calculate_rmse,
    mean,
)
from common.number_utils import to_float, to_optional_float
from common.reporting import (
    escape_html,
    render_html_table,
    render_html_value,
    render_metric_card,
    trusted_html,
)


def assert_close(actual: float, expected: float, tolerance: float = 1e-9) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"Expected {expected}, got {actual}")


def assert_raises(expected_error: type[Exception], callback) -> None:
    try:
        callback()
    except expected_error:
        return

    raise AssertionError(f"Expected {expected_error.__name__} to be raised.")


def test_number_utils() -> None:
    assert_close(to_float("12.5"), 12.5)
    assert_close(to_float(7), 7.0)
    assert_close(to_float(4.75), 4.75)
    assert_close(to_float("bad"), 0.0)
    assert_close(to_float(""), 0.0)
    assert_close(to_float(None, default=-1.0), -1.0)
    assert_close(to_float("bad", default=99.0), 99.0)
    assert_close(to_optional_float("3.25"), 3.25)
    assert_close(to_optional_float(8), 8.0)
    assert to_optional_float("") is None
    assert to_optional_float(None) is None
    assert to_optional_float("not-a-number") is None


def test_geo_utils() -> None:
    denver_to_boulder_km = calculate_distance_km(
        39.7392,
        -104.9903,
        40.01499,
        -105.27055,
    )
    assert_close(denver_to_boulder_km, 38.9, tolerance=0.5)
    assert_close(calculate_distance_km(39.0, -105.0, 39.0, -105.0), 0.0)
    assert_close(
        calculate_distance_km(40.01499, -105.27055, 39.7392, -104.9903),
        denver_to_boulder_km,
    )


def test_metrics_happy_path() -> None:
    actual = [1.0, 3.0]
    predicted = [2.0, 1.0]
    assert_close(mean(actual), 2.0)
    assert_close(calculate_mae(actual, predicted), 1.5)
    assert_close(calculate_rmse(actual, predicted), math.sqrt(2.5))
    assert_close(calculate_correlation([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]), 1.0)

    metrics = calculate_metrics(actual, predicted)
    assert_close(metrics["mae"], 1.5)
    assert_close(metrics["rmse"], math.sqrt(2.5))
    assert_close(metrics["correlation"], calculate_correlation(actual, predicted))


def test_metrics_edge_cases() -> None:
    assert_close(calculate_correlation([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]), -1.0)
    assert_close(calculate_correlation([5.0, 5.0, 5.0], [1.0, 2.0, 3.0]), 0.0)
    assert_raises(ValueError, lambda: mean([]))
    assert_raises(ValueError, lambda: calculate_mae([], []))
    assert_raises(ValueError, lambda: calculate_rmse([1.0], [1.0, 2.0]))
    assert_raises(ValueError, lambda: calculate_correlation([1.0], []))


def test_csv_utils() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        csv_file = Path(temp_dir) / "nested" / "sample.csv"
        write_csv_rows(
            csv_file,
            [
                {"station_id": "A", "value": 1},
                {"station_id": "B", "value": 2},
            ],
            ["station_id", "value"],
        )
        rows = read_csv_rows(csv_file)
        fieldnames = read_csv_fieldnames(csv_file)
        row_count = count_csv_rows(csv_file)

        inferred_csv_file = Path(temp_dir) / "inferred" / "sample.csv"
        write_csv_rows_inferred(
            inferred_csv_file,
            [
                {"first": "A", "second": 1},
                {"first": "B", "second": 2},
            ],
        )
        inferred_rows = read_csv_rows(inferred_csv_file)

        header = inferred_csv_file.read_text().splitlines()[0]
        assert header == "first,second"
        assert_raises(ValueError, lambda: write_csv_rows_inferred(
            Path(temp_dir) / "empty.csv",
            [],
        ))

    assert rows == [
        {"station_id": "A", "value": "1"},
        {"station_id": "B", "value": "2"},
    ]
    assert fieldnames == ["station_id", "value"]
    assert row_count == 2
    assert inferred_rows == [
        {"first": "A", "second": "1"},
        {"first": "B", "second": "2"},
    ]


def test_json_utils() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        json_file = Path(temp_dir) / "nested" / "artifact.json"
        write_json_file(json_file, {"status": "ok", "count": 2})

        assert json_file.read_text() == '{\n  "status": "ok",\n  "count": 2\n}\n'


def test_model_artifact_helpers() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        project_dir = Path(temp_dir) / "project"
        table_file = project_dir / "outputs" / "training.csv"
        external_file = Path(temp_dir) / "external.csv"

        assert project_relative_path(table_file, project_dir) == "outputs/training.csv"
        assert project_relative_path(external_file, project_dir) == str(external_file.resolve())

    assert infer_feature_unit("hub_1_distance_km") == "km"
    assert infer_feature_unit("hub_1_elevation_m") == "m"
    assert infer_feature_unit("local_relief_m_r990m") == "m"
    assert infer_feature_unit("slope_degrees") == "degrees"
    assert infer_feature_unit("hub_1_tavg") == "F"
    assert infer_feature_unit("hub_1_tmax", variable="tmax") == "F"
    assert infer_feature_unit("station_coverage_percent") == "percent"
    assert infer_feature_unit("aspect_sin") is None

    with tempfile.TemporaryDirectory() as temp_dir:
        project_dir = Path(temp_dir)
        table_file = project_dir / "tables" / "training.csv"
        schema = build_feature_schema_payload(
            model_run_id="model-v1",
            source_training_table=table_file,
            project_dir=project_dir,
            target_column="target_tavg_offset_from_baseline",
            prediction_output="daily_tavg_f",
            prediction_transform="regional_baseline_tavg + predicted_offset",
            hub_count=2,
            target_neighbor_count=1,
            feature_columns=["hub_1_tavg", "hub_1_distance_km"],
            variable="tavg",
        )

    assert schema["featureSchemaVersion"] == "feature-schema-v1"
    assert schema["modelRunId"] == "model-v1"
    assert schema["sourceTrainingTable"] == "tables/training.csv"
    assert schema["targetColumn"] == "target_tavg_offset_from_baseline"
    assert schema["predictionOutput"] == "daily_tavg_f"
    assert schema["predictionTransform"] == "regional_baseline_tavg + predicted_offset"
    assert schema["hubCount"] == 2
    assert schema["targetNeighborCount"] == 1
    assert schema["featureCount"] == 2
    assert schema["features"] == [
        {
            "name": "hub_1_tavg",
            "type": "float",
            "unit": "F",
            "required": True,
        },
        {
            "name": "hub_1_distance_km",
            "type": "float",
            "unit": "km",
            "required": True,
        },
    ]


def test_model_manifest_helpers() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        project_dir = Path(temp_dir) / "project"
        training_table = project_dir / "outputs" / "general.csv"
        station_metrics = project_dir / "reports" / "station_metrics.csv"
        validation_predictions = project_dir / "predictions" / "validation.csv"

        validation_manifest = build_validation_model_run_manifest(
            model_run_id="model-v1",
            model_variant="offset_rf",
            training_table=training_table,
            station_metrics=station_metrics,
            validation_predictions=validation_predictions,
            project_dir=project_dir,
            summary_metrics={
                "validationStationCount": 2,
                "testRows": 100,
                "validationPredictionRows": 100,
                "meanMaeF": 1.2,
            },
        )

    assert validation_manifest["modelRunId"] == "model-v1"
    assert validation_manifest["modelVariant"] == "offset_rf"
    assert validation_manifest["sourceFiles"] == {
        "trainingTable": "outputs/general.csv",
        "stationMetrics": "reports/station_metrics.csv",
        "validationPredictions": "predictions/validation.csv",
    }
    assert validation_manifest["summaryMetrics"]["validationStationCount"] == 2
    assert NO_SERIALIZED_ESTIMATOR_NOTE in validation_manifest["notes"]
    assert "createdAt" in validation_manifest

    with tempfile.TemporaryDirectory() as temp_dir:
        project_dir = Path(temp_dir) / "project"
        training_table = project_dir / "outputs" / "production.csv"
        model_file = project_dir / "model_runs" / "model-v1" / "model.joblib"
        artifact = {
            "variable": "tmax",
            "trainingMode": "all_eligible_rows_no_holdout_production",
            "modelFamily": "random_forest",
            "predictionTarget": "daily_tmax_f",
            "predictionMode": "offset_from_regional_baseline",
            "predictionTransform": "baseline + predicted_offset",
            "rowCount": 50,
            "targetStationCount": 4,
            "featureColumns": ["hub_1_tmax", "hub_1_distance_km"],
            "labelColumn": "target_tmax_offset_from_baseline",
            "baselineColumn": "regional_baseline_tmax",
            "includeTerrain": True,
            "hubCount": 1,
            "targetNeighborCount": 2,
            "trainingStrategy": "chunked-forest",
            "chunkRows": 100000,
            "chunkCount": 1,
            "hyperparameters": {"n_estimators": 200},
        }

        artifact_manifest = build_serialized_model_artifact_manifest(
            artifact=artifact,
            model_path=model_file,
            source_training_table=training_table,
            project_dir=project_dir,
        )
        base_manifest = build_production_model_run_manifest(
            model_run_id="model-v1",
            source_table=training_table,
            variable="tmax",
            row_count=50,
            station_count=4,
            project_dir=project_dir,
        )
        merged_manifest = merge_serialized_model_run_manifest(
            existing_manifest={
                **base_manifest,
                "notes": [
                    NO_SERIALIZED_ESTIMATOR_NOTE,
                    "Reviewer note to preserve.",
                ],
                "summaryMetrics": {"existingMetric": 7},
            },
            artifact_manifest=artifact_manifest,
            model_run_id="model-v1",
            variable="tmax",
            source_table=training_table,
            row_count=50,
            station_count=4,
            project_dir=project_dir,
        )

    assert artifact_manifest["artifactVersion"] == "model-artifact-v1"
    assert artifact_manifest["modelPath"] == "model_runs/model-v1/model.joblib"
    assert artifact_manifest["sourceTrainingTable"] == "outputs/production.csv"
    assert artifact_manifest["featureCount"] == 2
    assert artifact_manifest["importantCaveat"].startswith("This production estimator")

    assert merged_manifest["serializedModel"] == artifact_manifest
    assert merged_manifest["predictionTarget"] == "daily_tmax_f"
    assert merged_manifest["sourceFiles"]["trainingTable"] == "outputs/production.csv"
    assert merged_manifest["summaryMetrics"]["existingMetric"] == 7
    assert merged_manifest["summaryMetrics"]["trainingRows"] == 50
    assert NO_SERIALIZED_ESTIMATOR_NOTE not in merged_manifest["notes"]
    assert "Reviewer note to preserve." in merged_manifest["notes"]
    assert SERIALIZED_ESTIMATOR_NOTE in merged_manifest["notes"]


def test_reporting_helpers() -> None:
    assert escape_html("<station>") == "&lt;station&gt;"
    assert render_html_value("<raw>") == "&lt;raw&gt;"
    assert render_html_value(trusted_html("<code>trusted</code>")) == "<code>trusted</code>"

    escaped_table = render_html_table(["Name"], [["<b>raw</b>"]])
    assert "<td>&lt;b&gt;raw&lt;/b&gt;</td>" in escaped_table

    trusted_table = render_html_table(
        ["Station"],
        [[trusted_html("<code>USC00000001</code>")]],
    )
    assert "<td><code>USC00000001</code></td>" in trusted_table

    metric_card = render_metric_card(
        "Mean <MAE>",
        trusted_html("<strong>1.25 F</strong>"),
        "holdout only",
    )
    assert '<div class="label">Mean &lt;MAE&gt;</div>' in metric_card
    assert '<div class="value"><strong>1.25 F</strong></div>' in metric_card
    assert '<div class="note">holdout only</div>' in metric_card

    custom_metric_card = render_metric_card(
        "RMSE",
        "1.8 F",
        "lower is better",
        label_class="card-label",
        value_class="card-value",
        note_class="card-note",
    )
    assert '<div class="card-label">RMSE</div>' in custom_metric_card
    assert '<div class="card-value">1.8 F</div>' in custom_metric_card
    assert '<div class="card-note">lower is better</div>' in custom_metric_card


def main() -> None:
    test_number_utils()
    test_geo_utils()
    test_metrics_happy_path()
    test_metrics_edge_cases()
    test_csv_utils()
    test_json_utils()
    test_model_artifact_helpers()
    test_model_manifest_helpers()
    test_reporting_helpers()
    print("common utility tests passed")


if __name__ == "__main__":
    main()
