from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from common.pairwise_skill import (
    calculate_pair_skill_score,
    calculate_pairwise_skill,
    format_pairwise_skill_row,
)


def assert_close(actual: float, expected: float, tolerance: float = 1e-9) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"Expected {expected}, got {actual}")


def test_calculate_pairwise_skill_uses_same_dates_and_training_window() -> None:
    target_daily = {
        "2022-01-01": 10.0,
        "2022-07-01": 20.0,
        "2023-01-01": 12.0,
        "2024-01-01": 100.0,
    }
    predictor_daily = {
        "2022-01-01": 11.0,
        "2022-07-01": 21.0,
        "2023-01-01": 13.0,
        "2024-01-01": -100.0,
        "2022-02-01": 99.0,
    }

    row = calculate_pairwise_skill(target_daily, predictor_daily, train_end_year=2023)

    assert row["pair_overlap_days"] == 3
    assert_close(row["pair_corr"], 1.0)
    assert_close(row["pair_mae"], 1.0)
    assert_close(row["pair_rmse"], 1.0)
    assert_close(row["pair_mean_bias"], 1.0)
    assert_close(row["pair_abs_mean_bias"], 1.0)
    assert_close(row["pair_winter_mae"], 1.0)
    assert_close(row["pair_summer_mae"], 1.0)


def test_calculate_pair_skill_score_rewards_good_pairs() -> None:
    strong_score = calculate_pair_skill_score(
        overlap_days=1500,
        correlation=0.98,
        mae=1.0,
        rmse=1.4,
        abs_mean_bias=0.4,
        winter_mae=1.1,
        summer_mae=0.9,
    )
    weak_score = calculate_pair_skill_score(
        overlap_days=200,
        correlation=0.3,
        mae=8.0,
        rmse=10.0,
        abs_mean_bias=5.0,
        winter_mae=9.0,
        summer_mae=7.5,
    )

    assert strong_score > 80.0
    assert weak_score < 35.0


def test_format_pairwise_skill_row_preserves_blank_optional_values() -> None:
    formatted = format_pairwise_skill_row({
        "target_station_id": "T1",
        "predictor_source_type": "hub",
        "predictor_station_id": "H1",
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
    })

    assert formatted["pair_overlap_days"] == "0"
    assert formatted["pair_corr"] == ""
    assert formatted["pair_skill_score"] == ""


def main() -> None:
    test_calculate_pairwise_skill_uses_same_dates_and_training_window()
    test_calculate_pair_skill_score_rewards_good_pairs()
    test_format_pairwise_skill_row_preserves_blank_optional_values()
    print("pairwise skill tests passed")


if __name__ == "__main__":
    main()
