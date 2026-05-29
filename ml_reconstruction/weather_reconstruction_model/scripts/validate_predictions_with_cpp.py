from __future__ import annotations

import argparse
import csv
import subprocess
from pathlib import Path

import config
from common.csv_utils import write_csv_rows


PROJECT_DIR = config.PROJECT_DIR
VALIDATION_DIR = config.VALIDATION_DIR
REPORT_DIR = config.REPORT_DIR
DEFAULT_EXECUTABLE = PROJECT_DIR / "validate_prediction_similarity"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export Python model predictions as station-style CSVs and validate "
            "them station-by-station with the C++ prediction similarity engine."
        )
    )
    parser.add_argument(
        "prediction_file",
        type=Path,
        help="Prediction CSV with date,target_station_id,actual_tavg,predicted_tavg columns.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for generated station-style validation CSVs.",
    )
    parser.add_argument(
        "--summary-file",
        type=Path,
        default=None,
        help="CSV summary of C++ validation results.",
    )
    parser.add_argument(
        "--executable",
        type=Path,
        default=DEFAULT_EXECUTABLE,
        help="C++ validate_prediction_similarity executable.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Use the existing C++ executable without rebuilding it first.",
    )
    return parser.parse_args()


def read_predictions(prediction_file: Path) -> dict[str, list[dict[str, str]]]:
    rows_by_station: dict[str, list[dict[str, str]]] = {}

    with prediction_file.open("r", newline="") as file:
        for row in csv.DictReader(file):
            rows_by_station.setdefault(row["target_station_id"], []).append(row)

    return rows_by_station


def build_cpp_validator(executable: Path, skip_build: bool) -> None:
    if skip_build and executable.exists():
        return

    subprocess.run(
        ["make", "validate-prediction"],
        cwd=PROJECT_DIR,
        check=True,
    )


def write_station_validation_files(
    station_id: str,
    rows: list[dict[str, str]],
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    actual_file = output_dir / f"{station_id}_actual.csv"
    predicted_file = output_dir / f"{station_id}_predicted.csv"
    fieldnames = [
        "station_id",
        "station_name",
        "latitude",
        "longitude",
        "elevation",
        "date",
        "tmax",
        "tmin",
    ]
    target_name = rows[0].get("target_name", station_id)

    with actual_file.open("w", newline="") as actual_output:
        writer = csv.DictWriter(actual_output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "station_id": station_id,
                "station_name": target_name,
                "latitude": "0",
                "longitude": "0",
                "elevation": "0",
                "date": row["date"],
                "tmax": row["actual_tavg"],
                "tmin": row["actual_tavg"],
            })

    with predicted_file.open("w", newline="") as predicted_output:
        writer = csv.DictWriter(predicted_output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "station_id": f"{station_id}_PREDICTED",
                "station_name": f"{target_name} predicted",
                "latitude": "0",
                "longitude": "0",
                "elevation": "0",
                "date": row["date"],
                "tmax": row["predicted_tavg"],
                "tmin": row["predicted_tavg"],
            })

    return actual_file, predicted_file


def parse_cpp_output(output: str) -> dict[str, str]:
    parsed: dict[str, str] = {}

    for line in output.splitlines():
        if ":" not in line:
            continue

        label, value = line.split(":", 1)
        parsed[label.strip()] = value.strip()

    return parsed


def run_cpp_validation(
    executable: Path,
    actual_file: Path,
    predicted_file: Path,
) -> dict[str, str]:
    completed = subprocess.run(
        [
            str(executable),
            str(actual_file),
            str(predicted_file),
        ],
        cwd=PROJECT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_cpp_output(completed.stdout)


def summary_row(
    station_id: str,
    rows: list[dict[str, str]],
    cpp_metrics: dict[str, str],
    actual_file: Path,
    predicted_file: Path,
) -> dict[str, str]:
    return {
        "target_station_id": station_id,
        "target_name": rows[0].get("target_name", station_id),
        "prediction_rows": str(len(rows)),
        "cpp_paired_days": cpp_metrics.get("Paired days compared", ""),
        "cpp_correlation": cpp_metrics.get("Daily correlation", ""),
        "cpp_mae_f": cpp_metrics.get("Daily MAD / MAE", "").replace(" F", ""),
        "cpp_rmse_f": cpp_metrics.get("Daily RMSE", "").replace(" F", ""),
        "actual_csv": str(actual_file),
        "predicted_csv": str(predicted_file),
    }


def main() -> None:
    arguments = parse_arguments()
    prediction_file = arguments.prediction_file
    output_dir = arguments.output_dir or (
        VALIDATION_DIR / f"{prediction_file.stem}_cpp_station_files"
    )
    summary_file = arguments.summary_file or (
        REPORT_DIR / f"{prediction_file.stem}_cpp_validation.csv"
    )

    rows_by_station = read_predictions(prediction_file)
    build_cpp_validator(arguments.executable, arguments.skip_build)

    results = []
    for index, (station_id, rows) in enumerate(sorted(rows_by_station.items()), start=1):
        print(f"[{index}/{len(rows_by_station)}] {station_id}", end=" ")
        actual_file, predicted_file = write_station_validation_files(
            station_id,
            rows,
            output_dir,
        )
        cpp_metrics = run_cpp_validation(
            arguments.executable,
            actual_file,
            predicted_file,
        )
        row = summary_row(
            station_id,
            rows,
            cpp_metrics,
            actual_file,
            predicted_file,
        )
        results.append(row)
        print(
            f"MAE {row['cpp_mae_f']} F, "
            f"RMSE {row['cpp_rmse_f']} F, "
            f"r {row['cpp_correlation']}"
        )

    write_csv_rows(
        summary_file,
        results,
        [
            "target_station_id",
            "target_name",
            "prediction_rows",
            "cpp_paired_days",
            "cpp_correlation",
            "cpp_mae_f",
            "cpp_rmse_f",
            "actual_csv",
            "predicted_csv",
        ],
    )

    print()
    print("C++ validation complete")
    print("-----------------------")
    print(f"Stations validated: {len(results)}")
    print(f"Station CSV directory: {output_dir}")
    print(f"Summary file: {summary_file}")


if __name__ == "__main__":
    main()
