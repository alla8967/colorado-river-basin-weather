"""Convert training-table rows into model features, labels, and prediction rows.

This shared layer keeps trainers consistent about scaling, variables, offsets, and output shape."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from common.metrics import validate_paired_values
from common.number_utils import to_float
from common.weather_cache import validate_temperature_variable


def build_unscaled_features_and_labels(
    rows: Sequence[Mapping[str, str]],
    feature_columns: Sequence[str],
    label_column: str = "target_tavg",
) -> tuple[list[list[float]], list[float]]:
    """Build numeric feature and label arrays for tree-style estimators."""
    features = []
    labels = []

    for row in rows:
        features.append([
            to_float(row.get(column, ""))
            for column in feature_columns
        ])
        labels.append(to_float(row[label_column]))

    return features, labels


def actual_temperature_values(
    rows: Sequence[Mapping[str, str]],
    variable: str,
) -> list[float]:
    variable = validate_temperature_variable(variable)
    target_column = f"target_{variable}"
    return [
        to_float(row[target_column])
        for row in rows
    ]


def add_baseline_to_offsets(
    rows: Sequence[Mapping[str, str]],
    offset_predictions: Sequence[float],
    baseline_column: str = "regional_baseline_tavg",
) -> list[float]:
    if len(rows) != len(offset_predictions):
        raise ValueError("Rows and offset predictions must have the same length.")

    return [
        to_float(row[baseline_column]) + offset
        for row, offset in zip(rows, offset_predictions)
    ]


def calculate_prediction_bias(
    actual_values: Sequence[float],
    predicted_values: Sequence[float],
) -> float:
    validate_paired_values(actual_values, predicted_values)
    return sum(
        actual - predicted
        for actual, predicted in zip(actual_values, predicted_values)
    ) / len(actual_values)


def temperature_prediction_fieldnames(
    variable: str,
    extra_fieldnames: Sequence[str] | None = None,
) -> list[str]:
    variable = validate_temperature_variable(variable)
    return [
        "date",
        "target_station_id",
        "target_name",
        *(extra_fieldnames or []),
        f"actual_{variable}",
        f"predicted_{variable}",
        "error",
    ]


def build_temperature_prediction_rows(
    source_rows: Sequence[Mapping[str, str]],
    actual_values: Sequence[float],
    predicted_values: Sequence[float],
    variable: str,
    extra_fields: Mapping[str, object] | None = None,
) -> list[dict[str, object]]:
    variable = validate_temperature_variable(variable)
    validate_paired_values(actual_values, predicted_values)
    if len(source_rows) != len(actual_values):
        raise ValueError("Source rows and prediction values must have the same length.")

    actual_column = f"actual_{variable}"
    predicted_column = f"predicted_{variable}"
    rows: list[dict[str, object]] = []

    for row, actual, predicted in zip(source_rows, actual_values, predicted_values):
        output_row = {
            "date": row["date"],
            "target_station_id": row["target_station_id"],
            "target_name": row["target_name"],
        }
        if extra_fields is not None:
            output_row.update(extra_fields)
        output_row.update({
            actual_column: f"{actual:.2f}",
            predicted_column: f"{predicted:.2f}",
            "error": f"{actual - predicted:.2f}",
        })
        rows.append(output_row)

    return rows
