"""Split station-holdout work into chunk CSVs for array jobs.

This lets Alpine jobs process validation stations in parallel without hand-curating station lists."""

from __future__ import annotations

import argparse
from pathlib import Path

import config
from common.csv_utils import read_csv_rows, write_csv_rows
from common.weather_cache import TEMPERATURE_VARIABLES, validate_temperature_variable


DEFAULT_OUTPUT_ROOT = config.OUTPUT_DIR / "paloma" / "station_holdout_chunks"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split Paloma station-holdout targets into chunk CSVs."
    )
    parser.add_argument(
        "general_table",
        type=Path,
        help="Full general training table whose target stations should be held out.",
    )
    parser.add_argument(
        "--variable",
        choices=sorted(TEMPERATURE_VARIABLES),
        default="tavg",
        help="Temperature variable represented by the general table.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=30,
        help="Number of target stations per chunk.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Root output directory. A variable subdirectory is created inside it.",
    )
    return parser.parse_args()


def unique_target_stations(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    stations_by_id: dict[str, dict[str, str]] = {}

    for row in rows:
        station_id = row["target_station_id"]

        if station_id not in stations_by_id:
            stations_by_id[station_id] = {
                "station_id": station_id,
                "station_name": row.get("target_name", ""),
            }

    return sorted(
        stations_by_id.values(),
        key=lambda row: (row["station_name"], row["station_id"]),
    )


def chunks(items: list[dict[str, str]], chunk_size: int) -> list[list[dict[str, str]]]:
    return [
        items[index:index + chunk_size]
        for index in range(0, len(items), chunk_size)
    ]


def main() -> None:
    arguments = parse_arguments()
    variable = validate_temperature_variable(arguments.variable)

    if arguments.chunk_size <= 0:
        raise ValueError("--chunk-size must be positive.")

    rows = read_csv_rows(arguments.general_table)

    if not rows:
        raise ValueError(f"General table is empty: {arguments.general_table}")

    target_column = f"target_{variable}"
    if target_column not in rows[0]:
        raise ValueError(
            f"General table is missing {target_column}. "
            f"Use the matching --variable for this table."
        )

    stations = unique_target_stations(rows)
    output_dir = arguments.output_dir / variable
    output_dir.mkdir(parents=True, exist_ok=True)

    chunk_rows = chunks(stations, arguments.chunk_size)

    for index, station_chunk in enumerate(chunk_rows, start=1):
        output_file = output_dir / f"chunk_{index:03d}.csv"
        write_csv_rows(
            output_file,
            station_chunk,
            ["station_id", "station_name"],
        )

    print("Station holdout chunks created")
    print("==============================")
    print(f"General table: {arguments.general_table}")
    print(f"Temperature variable: {variable}")
    print(f"Target stations: {len(stations)}")
    print(f"Chunk size: {arguments.chunk_size}")
    print(f"Chunks: {len(chunk_rows)}")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
