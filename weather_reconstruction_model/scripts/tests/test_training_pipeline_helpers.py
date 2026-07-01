"""Test shared training-data and station-holdout helper functions.

The coverage protects feature/label extraction and leakage-prevention filters."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from pipeline.station_holdouts import (
    row_uses_any_station,
    row_uses_station,
    training_rows_for_station_holdout,
)
from pipeline.training_data import (
    actual_temperature_values,
    add_baseline_to_offsets,
    build_temperature_prediction_rows,
    build_unscaled_features_and_labels,
    calculate_prediction_bias,
    temperature_prediction_fieldnames,
)


def sample_rows() -> list[dict[str, str]]:
    return [
        {
            "date": "2020-01-01",
            "year": "2020",
            "target_station_id": "T1",
            "target_name": "Target One",
            "target_tmin": "20.0",
            "regional_baseline_tmin": "15.0",
            "feature_a": "1.5",
            "feature_b": "2.5",
            "hub_1_station_id": "H1",
            "target_neighbor_1_station_id": "N1",
        },
        {
            "date": "2021-01-01",
            "year": "2021",
            "target_station_id": "T2",
            "target_name": "Target Two",
            "target_tmin": "25.0",
            "regional_baseline_tmin": "20.0",
            "feature_a": "3.0",
            "feature_b": "4.0",
            "hub_1_station_id": "H2",
            "target_neighbor_1_station_id": "N2",
        },
    ]


def test_training_data_helpers_build_numeric_arrays_and_prediction_rows() -> None:
    rows = sample_rows()

    features, labels = build_unscaled_features_and_labels(
        rows,
        ["feature_a", "feature_b"],
        "target_tmin",
    )
    predictions = add_baseline_to_offsets(
        rows,
        [1.0, -2.0],
        baseline_column="regional_baseline_tmin",
    )
    prediction_rows = build_temperature_prediction_rows(
        rows,
        actual_temperature_values(rows, "tmin"),
        predictions,
        "tmin",
        {"holdout_group_id": "group_001", "holdout_group_size": 2},
    )

    assert features == [[1.5, 2.5], [3.0, 4.0]]
    assert labels == [20.0, 25.0]
    assert predictions == [16.0, 18.0]
    assert calculate_prediction_bias([20.0, 25.0], predictions) == 5.5
    assert temperature_prediction_fieldnames(
        "tmin",
        ["holdout_group_id", "holdout_group_size"],
    ) == [
        "date",
        "target_station_id",
        "target_name",
        "holdout_group_id",
        "holdout_group_size",
        "actual_tmin",
        "predicted_tmin",
        "error",
    ]
    assert prediction_rows[0] == {
        "date": "2020-01-01",
        "target_station_id": "T1",
        "target_name": "Target One",
        "holdout_group_id": "group_001",
        "holdout_group_size": 2,
        "actual_tmin": "20.00",
        "predicted_tmin": "16.00",
        "error": "4.00",
    }


def test_station_holdout_helpers_filter_target_hubs_neighbors_and_years() -> None:
    rows = sample_rows()

    assert row_uses_station(rows[0], "T1", hub_count=1, target_neighbor_count=1)
    assert row_uses_station(rows[0], "H1", hub_count=1, target_neighbor_count=1)
    assert row_uses_station(rows[0], "N1", hub_count=1, target_neighbor_count=1)
    assert not row_uses_station(rows[0], "OTHER", hub_count=1, target_neighbor_count=1)
    assert row_uses_any_station(
        rows[0],
        {"N1", "OTHER"},
        hub_count=1,
        target_neighbor_count=1,
    )
    assert training_rows_for_station_holdout(
        rows,
        {"H1"},
        train_end_year=2020,
        hub_count=1,
        target_neighbor_count=1,
    ) == []
    assert training_rows_for_station_holdout(
        rows,
        {"T1"},
        train_end_year=2021,
        hub_count=1,
        target_neighbor_count=1,
    ) == [rows[1]]


def test_training_data_helpers_reject_misaligned_predictions() -> None:
    rows = sample_rows()

    for callback in (
        lambda: add_baseline_to_offsets(
            rows,
            [1.0],
            baseline_column="regional_baseline_tmin",
        ),
        lambda: calculate_prediction_bias([20.0], []),
        lambda: build_temperature_prediction_rows(
            rows,
            [20.0],
            [19.0],
            "tmin",
        ),
    ):
        try:
            callback()
        except ValueError:
            continue

        raise AssertionError("Expected a ValueError for misaligned predictions.")


def main() -> None:
    test_training_data_helpers_build_numeric_arrays_and_prediction_rows()
    test_station_holdout_helpers_filter_target_hubs_neighbors_and_years()
    test_training_data_helpers_reject_misaligned_predictions()
    print("training pipeline helper tests passed")


if __name__ == "__main__":
    main()
