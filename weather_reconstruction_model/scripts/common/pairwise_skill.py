"""Calculate station-pair skill metrics used as training features.

The shared implementation prevents training-table builders and tests from drifting on pairwise evidence definitions."""

from __future__ import annotations

import math
from collections.abc import Mapping

from common.metrics import calculate_correlation, calculate_mae, calculate_rmse
from common.number_utils import to_optional_float

PAIRWISE_SKILL_COLUMNS = [
    "pair_overlap_days",
    "pair_corr",
    "pair_mae",
    "pair_rmse",
    "pair_mean_bias",
    "pair_abs_mean_bias",
    "pair_winter_mae",
    "pair_summer_mae",
    "pair_winter_bias",
    "pair_summer_bias",
    "pair_skill_score",
]


def month_from_date(date_text: str) -> int:
    return int(date_text[5:7])


def decay_score(value: float, scale: float) -> float:
    return 100.0 * math.exp(-abs(value) / scale)


def calculate_bias(target_values: list[float], predictor_values: list[float]) -> float:
    if not target_values:
        raise ValueError("Cannot calculate bias for empty values.")

    return sum(
        predictor - target
        for target, predictor in zip(target_values, predictor_values)
    ) / len(target_values)


def calculate_optional_mae(
    target_values: list[float],
    predictor_values: list[float],
) -> float | None:
    if not target_values:
        return None

    return calculate_mae(target_values, predictor_values)


def calculate_optional_bias(
    target_values: list[float],
    predictor_values: list[float],
) -> float | None:
    if not target_values:
        return None

    return calculate_bias(target_values, predictor_values)


def calculate_pair_skill_score(
    overlap_days: int,
    correlation: float,
    mae: float,
    rmse: float,
    abs_mean_bias: float,
    winter_mae: float | None,
    summer_mae: float | None,
    min_reliable_overlap_days: int = 1000,
) -> float:
    corr_score = max(0.0, min(100.0, correlation * 100.0))
    mae_score = decay_score(mae, 5.0)
    rmse_score = decay_score(rmse, 7.0)
    bias_score = decay_score(abs_mean_bias, 5.0)
    seasonal_scores = [
        decay_score(value, 5.0)
        for value in (winter_mae, summer_mae)
        if value is not None
    ]
    seasonal_score = (
        sum(seasonal_scores) / len(seasonal_scores)
        if seasonal_scores
        else mae_score
    )
    overlap_score = min(100.0, overlap_days / min_reliable_overlap_days * 100.0)

    return (
        0.35 * corr_score
        + 0.25 * mae_score
        + 0.15 * rmse_score
        + 0.10 * bias_score
        + 0.10 * seasonal_score
        + 0.05 * overlap_score
    )


def calculate_pairwise_skill(
    target_daily: Mapping[str, float],
    predictor_daily: Mapping[str, float],
    train_end_year: int,
) -> dict[str, float | int | None]:
    shared_dates = sorted(
        date_text
        for date_text in target_daily.keys() & predictor_daily.keys()
        if int(date_text[:4]) <= train_end_year
    )
    target_values = [target_daily[date_text] for date_text in shared_dates]
    predictor_values = [predictor_daily[date_text] for date_text in shared_dates]
    winter_target_values: list[float] = []
    winter_predictor_values: list[float] = []
    summer_target_values: list[float] = []
    summer_predictor_values: list[float] = []

    for date_text in shared_dates:
        month = month_from_date(date_text)

        if month in (12, 1, 2):
            winter_target_values.append(target_daily[date_text])
            winter_predictor_values.append(predictor_daily[date_text])
        elif month in (6, 7, 8):
            summer_target_values.append(target_daily[date_text])
            summer_predictor_values.append(predictor_daily[date_text])

    overlap_days = len(shared_dates)

    if overlap_days == 0:
        return empty_pairwise_skill()

    correlation = calculate_correlation(target_values, predictor_values)
    mae = calculate_mae(target_values, predictor_values)
    rmse = calculate_rmse(target_values, predictor_values)
    mean_bias = calculate_bias(target_values, predictor_values)
    winter_mae = calculate_optional_mae(winter_target_values, winter_predictor_values)
    summer_mae = calculate_optional_mae(summer_target_values, summer_predictor_values)
    winter_bias = calculate_optional_bias(winter_target_values, winter_predictor_values)
    summer_bias = calculate_optional_bias(summer_target_values, summer_predictor_values)

    return {
        "pair_overlap_days": overlap_days,
        "pair_corr": correlation,
        "pair_mae": mae,
        "pair_rmse": rmse,
        "pair_mean_bias": mean_bias,
        "pair_abs_mean_bias": abs(mean_bias),
        "pair_winter_mae": winter_mae,
        "pair_summer_mae": summer_mae,
        "pair_winter_bias": winter_bias,
        "pair_summer_bias": summer_bias,
        "pair_skill_score": calculate_pair_skill_score(
            overlap_days,
            correlation,
            mae,
            rmse,
            abs(mean_bias),
            winter_mae,
            summer_mae,
        ),
    }


def empty_pairwise_skill() -> dict[str, float | int | None]:
    return {
        "pair_overlap_days": 0,
        "pair_corr": None,
        "pair_mae": None,
        "pair_rmse": None,
        "pair_mean_bias": None,
        "pair_abs_mean_bias": None,
        "pair_winter_mae": None,
        "pair_summer_mae": None,
        "pair_winter_bias": None,
        "pair_summer_bias": None,
        "pair_skill_score": None,
    }


def format_optional_float(value: object, digits: int = 6) -> str:
    numeric_value = to_optional_float(value)

    if numeric_value is None:
        return ""

    return f"{numeric_value:.{digits}f}"


def format_pairwise_skill_row(row: Mapping[str, object]) -> dict[str, object]:
    formatted = dict(row)

    for column in PAIRWISE_SKILL_COLUMNS:
        if column == "pair_overlap_days":
            formatted[column] = str(int(to_optional_float(row.get(column)) or 0))
        else:
            formatted[column] = format_optional_float(row.get(column))

    return formatted
