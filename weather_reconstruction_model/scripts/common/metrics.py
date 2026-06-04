import math
from typing import Sequence


NumericSequence = Sequence[float]
MetricResults = dict[str, float]


def mean(values: NumericSequence) -> float:
    """Calculate arithmetic mean for a non-empty sequence."""
    if not values:
        raise ValueError("Cannot calculate mean of an empty sequence.")

    return sum(values) / len(values)


def calculate_mae(
    actual_values: NumericSequence,
    predicted_values: NumericSequence,
) -> float:
    """Calculate mean absolute error."""
    validate_paired_values(actual_values, predicted_values)
    errors = [
        abs(actual - predicted)
        for actual, predicted in zip(actual_values, predicted_values)
    ]
    return mean(errors)


def calculate_rmse(
    actual_values: NumericSequence,
    predicted_values: NumericSequence,
) -> float:
    """Calculate root mean squared error."""
    validate_paired_values(actual_values, predicted_values)
    squared_errors = [
        (actual - predicted) ** 2
        for actual, predicted in zip(actual_values, predicted_values)
    ]
    return math.sqrt(mean(squared_errors))


def calculate_correlation(
    actual_values: NumericSequence,
    predicted_values: NumericSequence,
) -> float:
    """Calculate Pearson correlation for paired values."""
    validate_paired_values(actual_values, predicted_values)
    actual_mean = mean(actual_values)
    predicted_mean = mean(predicted_values)
    numerator = sum(
        (actual - actual_mean) * (predicted - predicted_mean)
        for actual, predicted in zip(actual_values, predicted_values)
    )
    actual_variance = sum((actual - actual_mean) ** 2 for actual in actual_values)
    predicted_variance = sum(
        (predicted - predicted_mean) ** 2 for predicted in predicted_values
    )
    denominator = math.sqrt(actual_variance * predicted_variance)

    if denominator == 0:
        return 0.0

    return numerator / denominator


def calculate_metrics(
    actual_values: NumericSequence,
    predicted_values: NumericSequence,
) -> MetricResults:
    """Calculate the standard reconstruction metrics used by the project."""
    return {
        "mae": calculate_mae(actual_values, predicted_values),
        "rmse": calculate_rmse(actual_values, predicted_values),
        "correlation": calculate_correlation(actual_values, predicted_values),
    }


def validate_paired_values(
    actual_values: NumericSequence,
    predicted_values: NumericSequence,
) -> None:
    """Raise a clear error if paired metric inputs are unusable."""
    if len(actual_values) != len(predicted_values):
        raise ValueError("Actual and predicted sequences must have the same length.")

    if not actual_values:
        raise ValueError("Metric inputs cannot be empty.")
