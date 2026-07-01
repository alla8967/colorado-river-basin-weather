"""Test row-locked holdout baseline comparisons.

These checks protect the no-leakage and same-row comparison assumptions used by
the Paloma baseline report."""

import csv
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import build_holdout_baseline_comparison as baseline


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def base_fixture(temp_path: Path, include_second_hub_day: bool = True) -> SimpleNamespace:
    prediction_dir = temp_path / "predictions"
    output_dir = temp_path / "reports"
    prediction_fields = [
        "date",
        "target_station_id",
        "target_name",
        "holdout_group_id",
        "holdout_group_size",
        "actual_tavg",
        "predicted_tavg",
        "error",
    ]
    write_csv(
        prediction_dir / "paloma_v1_tavg_group_holdout_group_001_predictions.csv",
        [
            {
                "date": "2024-01-01",
                "target_station_id": "T1",
                "target_name": "Target One",
                "holdout_group_id": "G1",
                "holdout_group_size": "2",
                "actual_tavg": "10",
                "predicted_tavg": "11",
                "error": "-1",
            },
            {
                "date": "2024-01-02",
                "target_station_id": "T1",
                "target_name": "Target One",
                "holdout_group_id": "G1",
                "holdout_group_size": "2",
                "actual_tavg": "20",
                "predicted_tavg": "18",
                "error": "2",
            },
        ],
        prediction_fields,
    )
    metrics_fields = [
        "model_id",
        "variable",
        "target_station_id",
        "target_name",
        "train_rows",
        "test_rows",
        "mae",
        "rmse",
        "correlation",
        "bias",
        "strict_pass",
        "elapsed_seconds",
        "holdout_group_id",
        "holdout_group_size",
    ]
    model_metrics = temp_path / "station_holdout_master.csv"
    write_csv(
        model_metrics,
        [
            {
                "model_id": "paloma",
                "variable": "tavg",
                "target_station_id": "T1",
                "target_name": "Target One",
                "train_rows": "10",
                "test_rows": "2",
                "mae": "1.5",
                "rmse": "1.5811",
                "correlation": "1.0",
                "bias": "0.5",
                "strict_pass": "False",
                "elapsed_seconds": "1",
                "holdout_group_id": "G1",
                "holdout_group_size": "2",
            },
            {
                "model_id": "paloma",
                "variable": "tavg",
                "target_station_id": "H_LEAK",
                "target_name": "Leaky Heldout Hub",
                "train_rows": "10",
                "test_rows": "2",
                "mae": "0",
                "rmse": "0",
                "correlation": "1.0",
                "bias": "0",
                "strict_pass": "True",
                "elapsed_seconds": "1",
                "holdout_group_id": "G1",
                "holdout_group_size": "2",
            },
        ],
        metrics_fields,
    )
    candidate_fields = [
        "station_id",
        "latitude",
        "longitude",
        "has_tmax",
        "has_tmin",
        "tmax_start",
        "tmax_end",
        "tmin_start",
        "tmin_end",
        "usable_temp_start",
        "usable_temp_end",
        "usable_temp_years",
        "is_target_candidate",
        "is_hub_candidate",
    ]
    target_candidates = temp_path / "target_station_candidates.csv"
    write_csv(
        target_candidates,
        [
            {
                "station_id": "T1",
                "latitude": "0",
                "longitude": "0",
                "has_tmax": "1",
                "has_tmin": "1",
                "tmax_start": "2024",
                "tmax_end": "2024",
                "tmin_start": "2024",
                "tmin_end": "2024",
                "usable_temp_start": "2024",
                "usable_temp_end": "2024",
                "usable_temp_years": "1",
                "is_target_candidate": "1",
                "is_hub_candidate": "0",
            },
        ],
        candidate_fields,
    )
    hub_candidates = temp_path / "hub_station_candidates.csv"
    hub_rows = []
    for station_id, longitude in [
        ("H_LEAK", "0"),
        ("H_NEAR", "1"),
        ("H_FAR", "10"),
    ]:
        hub_rows.append({
            "station_id": station_id,
            "latitude": "0",
            "longitude": longitude,
            "has_tmax": "1",
            "has_tmin": "1",
            "tmax_start": "2024",
            "tmax_end": "2024",
            "tmin_start": "2024",
            "tmin_end": "2024",
            "usable_temp_start": "2024",
            "usable_temp_end": "2024",
            "usable_temp_years": "1",
            "is_target_candidate": "1",
            "is_hub_candidate": "1",
        })
    write_csv(hub_candidates, hub_rows, candidate_fields)
    daily_fields = [
        "station_id",
        "station_name",
        "latitude",
        "longitude",
        "elevation",
        "date",
        "tmax",
        "tmin",
    ]
    target_daily = temp_path / "target_daily_app_ready.csv"
    write_csv(
        target_daily,
        [
            {
                "station_id": "T1",
                "station_name": "Target One",
                "latitude": "0",
                "longitude": "0",
                "elevation": "1500",
                "date": "2024-01-01",
                "tmax": "12",
                "tmin": "8",
            },
        ],
        daily_fields,
    )
    hub_daily = temp_path / "hub_daily_app_ready.csv"
    hub_daily_rows = [
        {
            "station_id": "H_LEAK",
            "station_name": "Leaky Heldout Hub",
            "latitude": "0",
            "longitude": "0",
            "elevation": "1500",
            "date": "2024-01-01",
            "tmax": "12",
            "tmin": "8",
        },
        {
            "station_id": "H_LEAK",
            "station_name": "Leaky Heldout Hub",
            "latitude": "0",
            "longitude": "0",
            "elevation": "1500",
            "date": "2024-01-02",
            "tmax": "22",
            "tmin": "18",
        },
        {
            "station_id": "H_NEAR",
            "station_name": "Near Hub",
            "latitude": "0",
            "longitude": "1",
            "elevation": "1500",
            "date": "2024-01-01",
            "tmax": "10",
            "tmin": "6",
        },
        {
            "station_id": "H_FAR",
            "station_name": "Far Hub",
            "latitude": "0",
            "longitude": "10",
            "elevation": "1500",
            "date": "2024-01-01",
            "tmax": "30",
            "tmin": "26",
        },
    ]
    if include_second_hub_day:
        hub_daily_rows.extend([
            {
                "station_id": "H_NEAR",
                "station_name": "Near Hub",
                "latitude": "0",
                "longitude": "1",
                "elevation": "1500",
                "date": "2024-01-02",
                "tmax": "18",
                "tmin": "16",
            },
            {
                "station_id": "H_FAR",
                "station_name": "Far Hub",
                "latitude": "0",
                "longitude": "10",
                "elevation": "1500",
                "date": "2024-01-02",
                "tmax": "26",
                "tmin": "22",
            },
        ])
    write_csv(hub_daily, hub_daily_rows, daily_fields)
    terrain_file = temp_path / "terrain.csv"
    write_csv(
        terrain_file,
        [
            {
                "station_id": "T1",
                "local_relief_m": "500",
                "slope_degrees": "8",
            },
        ],
        ["station_id", "local_relief_m", "slope_degrees"],
    )
    return SimpleNamespace(
        model_metrics=model_metrics,
        prediction_dir=prediction_dir,
        prediction_pattern="*_predictions.csv",
        hub_daily=hub_daily,
        target_daily=target_daily,
        hub_candidates=hub_candidates,
        target_candidates=target_candidates,
        terrain_features=terrain_file,
        variable="tavg",
        idw_hub_count=2,
        idw_power=2.0,
        output_stem="comparison",
        output_dir=output_dir,
        allow_incomplete_baseline=False,
    )


def test_baseline_comparison_excludes_heldout_group_and_keeps_rows_locked() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        arguments = base_fixture(Path(temp_dir))
        summary = baseline.build_holdout_baseline_comparison(arguments)
        row_file = arguments.output_dir / "comparison_row_locked_predictions.csv"
        station_file = arguments.output_dir / "comparison_station_comparison.csv"

        with row_file.open("r", newline="") as file:
            row_locked = list(csv.DictReader(file))
        with station_file.open("r", newline="") as file:
            station_rows = list(csv.DictReader(file))

    assert summary["source_prediction_rows"] == 2
    assert summary["row_locked_prediction_rows"] == 2
    assert summary["missing_baseline_rows"] == 0
    assert {row["nearest_hub_id"] for row in row_locked} == {"H_NEAR"}
    assert row_locked[0]["nearest_hub_id"] != "H_LEAK"
    assert len(station_rows) == 1
    assert station_rows[0]["test_rows"] == "2"
    assert float(station_rows[0]["model_mae"]) == 1.5


def test_baseline_comparison_fails_when_rows_are_not_identical() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        arguments = base_fixture(Path(temp_dir), include_second_hub_day=False)
        try:
            baseline.build_holdout_baseline_comparison(arguments)
        except ValueError as error:
            message = str(error)
        else:
            raise AssertionError("Expected missing baseline rows to fail.")

    assert "Baseline predictions are missing" in message
    assert "T1:2024-01-02" in message


if __name__ == "__main__":
    test_baseline_comparison_excludes_heldout_group_and_keeps_rows_locked()
    test_baseline_comparison_fails_when_rows_are_not_identical()
    print("holdout baseline comparison tests passed")
