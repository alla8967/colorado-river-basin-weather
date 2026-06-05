"""Run one station validation scenario through training and prediction scripts.

This is a lower-level helper for targeted debugging outside the larger batch runner."""

from pathlib import Path
import argparse
import os
import subprocess
import sys

import config

PROJECT_DIR = config.PROJECT_DIR
SCRIPT_DIR = Path(__file__).resolve().parent
TRAINING_TABLE_DIR = config.TRAINING_TABLE_DIR
VALIDATION_DIR = config.VALIDATION_DIR
DEFAULT_TARGET_STATION_ID = config.DEFAULT_TARGET_STATION_ID
DEFAULT_HUB_COUNT = config.DEFAULT_HUB_COUNT
DEFAULT_TRAIN_END_YEAR = config.DEFAULT_TRAIN_END_YEAR
DEFAULT_TEST_START_YEAR = config.DEFAULT_TEST_START_YEAR
DEFAULT_ALPHA = config.DEFAULT_ALPHA


def run_command(command, description):
    print()
    print(description, flush=True)
    print("-" * len(description), flush=True)
    print(" ".join(str(part) for part in command), flush=True)
    child_environment = os.environ.copy()
    child_environment["PYTHONUNBUFFERED"] = "1"

    completed_process = subprocess.run(
        command,
        cwd=PROJECT_DIR,
        env=child_environment,
        check=False,
    )

    if completed_process.returncode != 0:
        raise SystemExit(completed_process.returncode)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Run the full one-station reconstruction validation pipeline."
    )
    parser.add_argument(
        "target_station_id",
        nargs="?",
        default=DEFAULT_TARGET_STATION_ID,
        help="Target station ID to validate.",
    )
    parser.add_argument(
        "--hub-count",
        type=int,
        default=DEFAULT_HUB_COUNT,
        help="Number of hub stations to use.",
    )
    parser.add_argument(
        "--train-end",
        type=int,
        default=DEFAULT_TRAIN_END_YEAR,
        help="Last year used for model training.",
    )
    parser.add_argument(
        "--test-start",
        type=int,
        default=DEFAULT_TEST_START_YEAR,
        help="First year used for model testing.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=DEFAULT_ALPHA,
        help="Regression regularization. Use 0 for ordinary linear regression.",
    )
    parser.add_argument(
        "--skip-cpp",
        action="store_true",
        help="Skip the independent C++ similarity validation step.",
    )
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    target_station_id = arguments.target_station_id
    hub_count = arguments.hub_count
    training_table = TRAINING_TABLE_DIR / f"{target_station_id}_{hub_count}_hubs.csv"
    actual_validation_csv = VALIDATION_DIR / f"{training_table.stem}_actual.csv"
    predicted_validation_csv = VALIDATION_DIR / f"{training_table.stem}_predicted.csv"

    print("One-station reconstruction validation", flush=True)
    print("=====================================", flush=True)
    print(f"Target station: {target_station_id}", flush=True)
    print(f"Hub count: {hub_count}", flush=True)
    print(f"Train through: {arguments.train_end}", flush=True)
    print(f"Test from: {arguments.test_start}", flush=True)
    print(f"Alpha: {arguments.alpha}", flush=True)

    run_command(
        [
            sys.executable,
            str(SCRIPT_DIR / "build_training_table.py"),
            target_station_id,
            str(hub_count),
        ],
        "1. Build shared-date training table",
    )

    run_command(
        [
            sys.executable,
            str(SCRIPT_DIR / "train_temperature_model.py"),
            str(training_table),
            "--train-end",
            str(arguments.train_end),
            "--test-start",
            str(arguments.test_start),
            "--alpha",
            str(arguments.alpha),
        ],
        "2. Train regression model and export prediction CSVs",
    )

    if arguments.skip_cpp:
        print()
        print("Skipped C++ validation.")
        return

    run_command(
        ["make", "validate-prediction"],
        "3. Build C++ prediction validator",
    )

    run_command(
        [
            str(PROJECT_DIR / "validate_prediction_similarity"),
            str(actual_validation_csv),
            str(predicted_validation_csv),
        ],
        "4. Validate predicted station against actual station in C++",
    )

    print()
    print("Pipeline complete.")
    print(f"Training table: {training_table}")
    print(f"Actual validation CSV: {actual_validation_csv}")
    print(f"Predicted validation CSV: {predicted_validation_csv}")


if __name__ == "__main__":
    main()
