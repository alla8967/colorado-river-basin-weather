"""Merge station-holdout chunk outputs into consolidated validation metrics.

Run this after array jobs finish so reports and reliability surfaces can use one station-level table."""

from __future__ import annotations

import argparse
from pathlib import Path
from statistics import median

import config
from common.csv_utils import read_csv_rows, write_csv_rows
from common.number_utils import to_float
from common.weather_cache import TEMPERATURE_VARIABLES, validate_temperature_variable

DEFAULT_INPUT_DIR = config.REPORT_DIR
DEFAULT_OUTPUT = config.OUTPUT_DIR / "paloma" / "paloma_v1_tavg_station_holdout_master.csv"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge Paloma station-holdout chunk metrics into one CSV."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument(
        "--pattern",
        default="paloma_v1_tavg_holdout_chunk_*_station_metrics.csv",
        help="Glob pattern, relative to --input-dir, for chunk metric files.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--station-list", type=Path, default=None)
    parser.add_argument("--model-id", default=None)
    parser.add_argument(
        "--variable",
        choices=sorted(TEMPERATURE_VARIABLES),
        default=None,
        help="Optional variable filter/annotation for merged rows.",
    )
    return parser.parse_args()


def station_id(row: dict[str, str]) -> str:
    return row.get("STATION_ID") or row.get("target_station_id", "")


def station_name(row: dict[str, str]) -> str:
    return row.get("STATION_NAME") or row.get("target_name", "")


def variable_value(row: dict[str, str]) -> str:
    return row.get("variable") or row.get("VARIABLE", "")


def mae_value(row: dict[str, str]) -> float:
    return to_float(row.get("STATION_HOLDOUT_MAE") or row.get("mae", ""))


def rmse_value(row: dict[str, str]) -> float:
    return to_float(row.get("STATION_HOLDOUT_RMSE") or row.get("rmse", ""))


def strict_pass_value(row: dict[str, str]) -> bool:
    value = row.get("STRICT_PASS") or row.get("strict_pass", "")
    return value.strip().lower() == "true"


def read_station_list(file_path: Path) -> set[str]:
    rows = read_csv_rows(file_path)
    return {
        row.get("station_id") or row.get("STATION_ID", "")
        for row in rows
        if row.get("station_id") or row.get("STATION_ID")
    }


def merged_fieldnames(rows: list[dict[str, str]]) -> list[str]:
    preferred_order = [
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
        "MODEL_ID",
        "VARIABLE",
        "STATION_ID",
        "STATION_NAME",
        "TRAIN_ROWS",
        "TEST_ROWS",
        "STATION_HOLDOUT_MAE",
        "STATION_HOLDOUT_RMSE",
        "STATION_HOLDOUT_CORRELATION",
        "STATION_HOLDOUT_BIAS",
        "STRICT_PASS",
        "ELAPSED_SECONDS",
    ]
    fieldnames = [
        fieldname
        for fieldname in preferred_order
        if any(fieldname in row for row in rows)
    ]

    for row in rows:
        for fieldname in row:
            if fieldname not in fieldnames:
                fieldnames.append(fieldname)

    return fieldnames


def collect_rows(
    input_dir: Path,
    pattern: str,
    model_id: str | None,
    variable: str | None,
) -> tuple[list[dict[str, str]], list[Path]]:
    files = sorted(input_dir.glob(pattern))
    rows: list[dict[str, str]] = []

    for file_path in files:
        for row in read_csv_rows(file_path):
            output_row = dict(row)
            if model_id and not output_row.get("model_id") and not output_row.get("MODEL_ID"):
                output_row["model_id"] = model_id
            if variable and not output_row.get("variable") and not output_row.get("VARIABLE"):
                output_row["variable"] = variable
            rows.append(output_row)

    return rows, files


def duplicate_station_ids(rows: list[dict[str, str]]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()

    for row in rows:
        current_station_id = station_id(row)
        if current_station_id in seen:
            duplicates.add(current_station_id)
        seen.add(current_station_id)

    return sorted(duplicates)


def print_summary(rows: list[dict[str, str]], files: list[Path]) -> None:
    maes = [mae_value(row) for row in rows]
    rmses = [rmse_value(row) for row in rows]
    strict_count = sum(1 for row in rows if strict_pass_value(row))
    worst_rows = sorted(rows, key=mae_value, reverse=True)[:20]

    print("Merged station-holdout results")
    print("==============================")
    print(f"Input files: {len(files)}")
    print(f"Station count: {len(rows)}")
    print(f"Mean MAE: {sum(maes) / len(maes):.4f} F")
    print(f"Median MAE: {median(maes):.4f} F")
    print(f"Mean RMSE: {sum(rmses) / len(rmses):.4f} F")
    print(f"Strict passes: {strict_count}/{len(rows)} ({strict_count / len(rows) * 100:.1f}%)")
    print()
    print("Worst 20 stations by MAE")
    print("------------------------")
    for row in worst_rows:
        print(
            f"{station_id(row):<12} {mae_value(row):>7.4f} F  "
            f"{station_name(row)}"
        )


def warn_missing_stations(rows: list[dict[str, str]], station_list: Path | None) -> None:
    if station_list is None:
        return

    expected_station_ids = read_station_list(station_list)
    present_station_ids = {station_id(row) for row in rows}
    missing_station_ids = sorted(expected_station_ids - present_station_ids)

    if missing_station_ids:
        print()
        print(f"WARNING: {len(missing_station_ids)} station-list IDs are missing from merged results.")
        for current_station_id in missing_station_ids[:40]:
            print(f"  {current_station_id}")
        if len(missing_station_ids) > 40:
            print(f"  ... {len(missing_station_ids) - 40} more")


def main() -> None:
    arguments = parse_arguments()
    variable = (
        validate_temperature_variable(arguments.variable)
        if arguments.variable is not None
        else None
    )
    rows, files = collect_rows(
        arguments.input_dir,
        arguments.pattern,
        arguments.model_id,
        variable,
    )

    if not files:
        raise FileNotFoundError(
            f"No station metric files matched {arguments.input_dir / arguments.pattern}"
        )
    if not rows:
        raise ValueError("Matched station metric files, but no rows were found.")

    duplicates = duplicate_station_ids(rows)
    if duplicates:
        raise ValueError(
            "Duplicate station IDs found in chunk metrics: " + ", ".join(duplicates)
        )

    rows.sort(key=lambda row: (variable_value(row), station_name(row), station_id(row)))
    write_csv_rows(arguments.output, rows, merged_fieldnames(rows))
    warn_missing_stations(rows, arguments.station_list)
    print_summary(rows, files)
    print()
    print(f"Merged CSV: {arguments.output}")


if __name__ == "__main__":
    main()
