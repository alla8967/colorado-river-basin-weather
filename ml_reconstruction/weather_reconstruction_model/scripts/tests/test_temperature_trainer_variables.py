from __future__ import annotations

from pathlib import Path
import csv
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import train_general_temperature_model as general_model
import train_tree_temperature_model as tree_model
from pipeline.model_features import (
    add_offset_feature_columns,
    is_pairwise_feature_column,
    require_training_columns,
    resolve_model_feature_selection,
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


def sample_rows() -> list[dict[str, str]]:
    return [
        {
            "date": "2023-01-01",
            "year": "2023",
            "target_station_id": "T1",
            "target_name": "TARGET ONE",
            "season_sin": "0.1",
            "season_cos": "0.9",
            "target_latitude": "40.0",
            "target_longitude": "-105.0",
            "target_elevation_m": "1600",
            "target_tmin": "20.0",
            "regional_baseline_tmin": "15.0",
            "target_tmin_offset_from_baseline": "5.0",
            "hub_1_tmin": "14.0",
            "hub_1_tmin_offset_from_baseline": "-1.0",
            "hub_1_distance_km": "10.0",
            "hub_1_elevation_difference_m": "25.0",
            "hub_1_latitude_offset": "0.1",
            "hub_1_longitude_offset": "-0.1",
            "hub_1_overlap_percent": "99.0",
            "target_neighbor_1_tmin": "16.0",
            "target_neighbor_1_tmin_offset_from_baseline": "1.0",
            "target_neighbor_1_distance_km": "15.0",
            "target_neighbor_1_elevation_difference_m": "35.0",
            "target_neighbor_1_latitude_offset": "0.2",
            "target_neighbor_1_longitude_offset": "-0.2",
            "target_neighbor_1_overlap_percent": "98.0",
        },
        {
            "date": "2024-01-01",
            "year": "2024",
            "target_station_id": "T1",
            "target_name": "TARGET ONE",
            "season_sin": "0.2",
            "season_cos": "0.8",
            "target_latitude": "40.0",
            "target_longitude": "-105.0",
            "target_elevation_m": "1600",
            "target_tmin": "22.0",
            "regional_baseline_tmin": "17.0",
            "target_tmin_offset_from_baseline": "5.0",
            "hub_1_tmin": "18.0",
            "hub_1_tmin_offset_from_baseline": "1.0",
            "hub_1_distance_km": "10.0",
            "hub_1_elevation_difference_m": "25.0",
            "hub_1_latitude_offset": "0.1",
            "hub_1_longitude_offset": "-0.1",
            "hub_1_overlap_percent": "99.0",
            "target_neighbor_1_tmin": "20.0",
            "target_neighbor_1_tmin_offset_from_baseline": "3.0",
            "target_neighbor_1_distance_km": "15.0",
            "target_neighbor_1_elevation_difference_m": "35.0",
            "target_neighbor_1_latitude_offset": "0.2",
            "target_neighbor_1_longitude_offset": "-0.2",
            "target_neighbor_1_overlap_percent": "98.0",
        },
    ]


def test_general_model_helpers_are_variable_aware() -> None:
    rows = sample_rows()
    fieldnames = rows[0].keys()

    hub_count = general_model.get_hub_count(fieldnames, variable="tmin")
    target_neighbor_count = general_model.get_target_neighbor_count(
        fieldnames,
        variable="tmin",
    )
    feature_columns = general_model.build_feature_columns(
        hub_count,
        fieldnames,
        include_terrain=False,
        variable="tmin",
    )

    assert hub_count == 1
    assert target_neighbor_count == 1
    assert "hub_1_tmin" in feature_columns
    assert "target_neighbor_1_tmin" in feature_columns
    assert "hub_1_tavg" not in feature_columns
    assert general_model.get_hub_count(fieldnames) == 0
    assert general_model.average_hub_predictions(rows, hub_count, variable="tmin") == [
        14.0,
        18.0,
    ]

    feature_stats = general_model.calculate_feature_stats(rows, feature_columns)
    features, labels = general_model.build_features_and_labels(
        rows,
        feature_columns,
        feature_stats,
        label_column="target_tmin",
    )

    assert len(features) == 2
    assert labels == [20.0, 22.0]


def test_tree_offset_helpers_are_variable_aware() -> None:
    rows = sample_rows()
    feature_columns = []

    add_offset_feature_columns(
        feature_columns,
        rows[0].keys(),
        hub_count=1,
        target_neighbor_count=1,
        variable="tmin",
    )

    assert feature_columns == [
        "regional_baseline_tmin",
        "hub_1_tmin_offset_from_baseline",
        "target_neighbor_1_tmin_offset_from_baseline",
    ]
    predictions = tree_model.add_baseline_to_offsets(
        rows,
        [2.0, 3.0],
        baseline_column="regional_baseline_tmin",
    )
    assert predictions == [17.0, 20.0]


def test_model_feature_selection_resolves_paloma_columns() -> None:
    fieldnames = list(sample_rows()[0].keys()) + [
        "hub_1_pair_skill_score",
        "target_neighbor_1_pair_rmse",
    ]

    feature_selection = resolve_model_feature_selection(
        fieldnames,
        variable="tmin",
        include_terrain=False,
    )
    no_pairwise_selection = resolve_model_feature_selection(
        fieldnames,
        variable="tmin",
        include_terrain=False,
        exclude_pairwise_features=True,
    )

    assert feature_selection.target_column == "target_tmin"
    assert feature_selection.baseline_column == "regional_baseline_tmin"
    assert feature_selection.label_column == "target_tmin_offset_from_baseline"
    assert feature_selection.prediction_output == "daily_tmin_f"
    assert (
        feature_selection.prediction_transform
        == "regional_baseline_tmin + predicted_offset"
    )
    assert feature_selection.hub_count == 1
    assert feature_selection.target_neighbor_count == 1
    assert "hub_1_tmin" in feature_selection.feature_columns
    assert "hub_1_tmin_offset_from_baseline" in feature_selection.feature_columns
    assert "target_neighbor_1_tmin" in feature_selection.feature_columns
    assert "target_neighbor_1_tmin_offset_from_baseline" in feature_selection.feature_columns
    assert "hub_1_pair_skill_score" in feature_selection.feature_columns
    assert "target_neighbor_1_pair_rmse" in feature_selection.feature_columns
    assert is_pairwise_feature_column("hub_1_pair_skill_score")
    assert "hub_1_pair_skill_score" not in no_pairwise_selection.feature_columns
    assert "target_neighbor_1_pair_rmse" not in no_pairwise_selection.feature_columns

    require_training_columns(
        fieldnames,
        feature_selection,
        "test fixture requires columns",
    )
    assert_raises(
        ValueError,
        lambda: require_training_columns(
            [
                fieldname
                for fieldname in fieldnames
                if fieldname != "target_tmin_offset_from_baseline"
            ],
            feature_selection,
            "test fixture requires columns",
        ),
    )


def test_tree_prediction_file_uses_variable_columns() -> None:
    rows = sample_rows()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        table_path = temp_path / "fixture_table.csv"
        original_prediction_dir = tree_model.PREDICTION_DIR
        tree_model.PREDICTION_DIR = temp_path

        try:
            prediction_file = tree_model.write_prediction_file(
                table_path,
                "tmin_direct_test_model",
                rows,
                [20.0, 22.0],
                [19.5, 22.5],
                variable="tmin",
            )
        finally:
            tree_model.PREDICTION_DIR = original_prediction_dir

        with prediction_file.open("r", newline="") as file:
            reader = csv.DictReader(file)
            output_rows = list(reader)
            fieldnames = reader.fieldnames

    assert fieldnames == [
        "date",
        "target_station_id",
        "target_name",
        "actual_tmin",
        "predicted_tmin",
        "error",
    ]
    assert output_rows[0]["actual_tmin"] == "20.00"
    assert output_rows[0]["predicted_tmin"] == "19.50"
    assert_close(float(output_rows[0]["error"]), 0.5)


def main() -> None:
    test_general_model_helpers_are_variable_aware()
    test_tree_offset_helpers_are_variable_aware()
    test_model_feature_selection_resolves_paloma_columns()
    test_tree_prediction_file_uses_variable_columns()
    print("temperature trainer variable tests passed")


if __name__ == "__main__":
    main()
