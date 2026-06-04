from pathlib import Path
import argparse
import os
import subprocess
import sys

import config
from common.csv_utils import read_csv_rows
from common.metrics import calculate_metrics as calculate_standard_metrics


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = config.PROJECT_DIR
PREDICTION_DIR = config.PREDICTION_DIR

REFERENCE_CASES = [
    {
        "station_id": "USC00052223",
        "name": "DENVER WATER DEPT",
        "kind": "strong baseline case",
        "hub_count": 5,
        "expected_mae": 1.48,
        "expected_rmse": 1.88,
        "expected_correlation": 0.995,
        "mae_warning_limit": 1.75,
        "rmse_warning_limit": 2.20,
        "correlation_warning_floor": 0.990,
        "note": "This should remain a strong reconstruction if the baseline pipeline is healthy.",
    },
    {
        "station_id": "USC00025494",
        "name": "METEOR CRATER",
        "kind": "known weak geography case",
        "hub_count": 5,
        "expected_mae": 3.60,
        "expected_rmse": 4.54,
        "expected_correlation": 0.970,
        "mae_warning_limit": 3.85,
        "rmse_warning_limit": 4.80,
        "correlation_warning_floor": 0.960,
        "note": "This should remain a useful failure case until terrain/geography features improve it.",
    },
]


def run_command(command):
    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"

    completed_process = subprocess.run(
        command,
        cwd=PROJECT_DIR,
        env=environment,
        check=False,
    )

    if completed_process.returncode != 0:
        raise SystemExit(completed_process.returncode)


def read_prediction_rows(station_id, hub_count):
    prediction_file = PREDICTION_DIR / f"{station_id}_{hub_count}_hubs_predictions.csv"
    return prediction_file, read_csv_rows(prediction_file)


def calculate_prediction_metrics(rows):
    actual_values = [float(row["actual_tavg"]) for row in rows]
    predicted_values = [float(row["predicted_tavg"]) for row in rows]
    metrics = calculate_standard_metrics(actual_values, predicted_values)
    metrics.update({
        "days": len(rows),
    })
    return metrics


def classify_case(reference_case, metrics):
    if (
        metrics["mae"] <= reference_case["mae_warning_limit"]
        and metrics["rmse"] <= reference_case["rmse_warning_limit"]
        and metrics["correlation"] >= reference_case["correlation_warning_floor"]
    ):
        return "OK"

    return "REVIEW"


def print_case_summary(reference_case, metrics, prediction_file):
    status = classify_case(reference_case, metrics)

    print()
    print(f"{status}: {reference_case['station_id']} - {reference_case['name']}")
    print("-" * 72)
    print(f"Case type: {reference_case['kind']}")
    print(f"Prediction file: {prediction_file}")
    print(f"Test days: {metrics['days']}")
    print()
    print("Current result:")
    print(f"  MAE:         {metrics['mae']:.4f} F")
    print(f"  RMSE:        {metrics['rmse']:.4f} F")
    print(f"  Correlation: {metrics['correlation']:.5f}")
    print()
    print("Reference result:")
    print(f"  MAE:         {reference_case['expected_mae']:.2f} F")
    print(f"  RMSE:        {reference_case['expected_rmse']:.2f} F")
    print(f"  Correlation: {reference_case['expected_correlation']:.3f}")
    print()
    print(reference_case["note"])


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Rerun known reference stations and compare them against expected baseline behavior."
    )
    parser.add_argument(
        "--skip-rerun",
        action="store_true",
        help="Only read existing prediction files instead of rerunning the validation pipeline.",
    )
    parser.add_argument(
        "--with-cpp",
        action="store_true",
        help="Also run the independent C++ validator for each reference case.",
    )
    return parser.parse_args()


def main():
    arguments = parse_arguments()

    print("Reference reconstruction cases")
    print("==============================")
    print("These are not final scientific proof. They are sanity checks for known behavior.")

    review_count = 0

    for reference_case in REFERENCE_CASES:
        station_id = reference_case["station_id"]
        hub_count = reference_case["hub_count"]

        if not arguments.skip_rerun:
            command = [
                sys.executable,
                str(SCRIPT_DIR / "run_station_validation.py"),
                station_id,
                "--hub-count",
                str(hub_count),
            ]

            if not arguments.with_cpp:
                command.append("--skip-cpp")

            run_command(command)

        prediction_file, prediction_rows = read_prediction_rows(station_id, hub_count)
        metrics = calculate_prediction_metrics(prediction_rows)
        print_case_summary(reference_case, metrics, prediction_file)

        if classify_case(reference_case, metrics) == "REVIEW":
            review_count += 1

    print()
    print("Reference case summary")
    print("----------------------")
    print(f"Cases checked: {len(REFERENCE_CASES)}")
    print(f"Cases needing review: {review_count}")

    if review_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
