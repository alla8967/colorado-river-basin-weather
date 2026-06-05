"""Test calibrated confidence scoring helpers and physical risk labels.

These checks keep confidence-map calibration behavior stable across refactors."""

from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from build_calibrated_confidence_comparison import (
    confidence_label,
    fit_expected_mae_model,
    physical_adjusted_confidence,
    physical_risk_details,
    support_representativeness_blend,
)


def test_physical_adjustment_lowers_risky_high_support_station() -> None:
    low_risk_row = {
        "support_score": "90",
        "representativeness_score": "90",
        "cold_pool_index": "0.1",
        "monsoon_region_flag": "no",
        "arid_plateau_flag": "no",
        "elevation_mismatch_risk": "no",
        "terrain_mismatch_risk": "no",
        "seasonal_confidence_warning": "",
    }
    risky_row = {
        **low_risk_row,
        "elevation_mismatch_risk": "yes",
        "terrain_mismatch_risk": "yes",
        "arid_plateau_flag": "yes",
        "cold_pool_index": "0.7",
    }

    low_risk_score = physical_adjusted_confidence(low_risk_row)
    risky_score = physical_adjusted_confidence(risky_row)
    penalty, reasons = physical_risk_details(risky_row)

    assert support_representativeness_blend(low_risk_row) == 90.0
    assert low_risk_score == 90.0
    assert risky_score < 75.0
    assert penalty > 15.0
    assert "elevation mismatch" in reasons


def test_confidence_label_thresholds() -> None:
    assert confidence_label(90.0) == "Very high confidence"
    assert confidence_label(80.0) == "High confidence"
    assert confidence_label(70.0) == "Moderate confidence"
    assert confidence_label(55.0) == "Low confidence"
    assert confidence_label(40.0) == "Very low confidence"


def test_expected_mae_model_slope_is_negative_when_errors_fall_with_confidence() -> None:
    rows = [
        {"physical_adjusted_confidence": "90", "observed_mae_f": "1.0"},
        {"physical_adjusted_confidence": "70", "observed_mae_f": "2.0"},
        {"physical_adjusted_confidence": "50", "observed_mae_f": "3.0"},
    ]

    model = fit_expected_mae_model(rows, "physical_adjusted_confidence")

    assert model.slope < 0
    assert model.predict(90) < model.predict(50)


def main() -> None:
    test_physical_adjustment_lowers_risky_high_support_station()
    test_confidence_label_thresholds()
    test_expected_mae_model_slope_is_negative_when_errors_fall_with_confidence()
    print("calibrated confidence comparison tests passed")


if __name__ == "__main__":
    main()
