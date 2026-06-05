"""Calculate historical pairwise skill features between target and hub stations.

These features let training-table builders use past station agreement as model input without leaking test-period evidence."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import config
from common.csv_utils import read_csv_rows
from common.geo_utils import calculate_distance_km
from common.pairwise_skill import (
    PAIRWISE_SKILL_COLUMNS,
    calculate_pairwise_skill,
    format_pairwise_skill_row,
)
from common.number_utils import to_float
from common.weather_cache import (
    HUB_SOURCE,
    TARGET_SOURCE,
    TEMPERATURE_VARIABLES,
    load_daily_for_station_ids,
    validate_temperature_variable,
)


DEFAULT_OUTPUT_FILE = config.CACHE_DIR / "pairwise_station_skill_features.csv"
IDENTITY_COLUMNS = [
    "target_station_id",
    "predictor_source_type",
    "predictor_station_id",
]
FIELDNAMES = IDENTITY_COLUMNS + PAIRWISE_SKILL_COLUMNS


def prefilter_target_neighbor_candidates(
    target_station: dict[str, str],
    target_neighbor_pool: list[dict[str, str]],
    prefilter_count: int,
    max_distance_km: float,
) -> list[dict[str, str]]:
    target_latitude = to_float(target_station["latitude"])
    target_longitude = to_float(target_station["longitude"])
    candidates: list[tuple[float, dict[str, str]]] = []

    for station in target_neighbor_pool:
        if station["station_id"] == target_station["station_id"]:
            continue

        distance_km = calculate_distance_km(
            target_latitude,
            target_longitude,
            to_float(station["latitude"]),
            to_float(station["longitude"]),
        )

        if max_distance_km > 0 and distance_km > max_distance_km:
            continue

        candidates.append((distance_km, station))

    candidates.sort(key=lambda item: item[0])

    if prefilter_count > 0:
        candidates = candidates[:prefilter_count]

    return [
        station
        for distance_km, station in candidates
    ]


def write_pairwise_row(
    writer: csv.DictWriter,
    target_station_id: str,
    predictor_source_type: str,
    predictor_station_id: str,
    target_daily: dict[str, float],
    predictor_daily: dict[str, float],
    train_end_year: int,
) -> None:
    skill_row = calculate_pairwise_skill(
        target_daily,
        predictor_daily,
        train_end_year,
    )
    writer.writerow(format_pairwise_skill_row({
        "target_station_id": target_station_id,
        "predictor_source_type": predictor_source_type,
        "predictor_station_id": predictor_station_id,
        **skill_row,
    }))


def build_pairwise_skill_file(
    target_limit: int,
    target_neighbor_prefilter_count: int,
    target_neighbor_max_distance_km: float,
    train_end_year: int,
    cache_file: Path,
    output_file: Path,
    variable: str = "tavg",
) -> None:
    variable = validate_temperature_variable(variable)
    targets = read_csv_rows(config.TARGET_CANDIDATE_FILE)[:target_limit]
    target_neighbor_pool = read_csv_rows(config.TARGET_CANDIDATE_FILE)
    hubs = read_csv_rows(config.HUB_CANDIDATE_FILE)
    target_ids = [target["station_id"] for target in targets]
    target_neighbor_ids = set(target_ids)

    for index, target in enumerate(targets, start=1):
        candidates = prefilter_target_neighbor_candidates(
            target,
            target_neighbor_pool,
            target_neighbor_prefilter_count,
            target_neighbor_max_distance_km,
        )
        target_neighbor_ids.update(station["station_id"] for station in candidates)

        if index % 100 == 0:
            print(
                f"Target-neighbor candidate scan: {index}/{len(targets)} targets, "
                f"{len(target_neighbor_ids)} unique target stations"
            )

    print(f"Loading target daily {variable} temperatures from cache...")
    target_daily_by_station, target_metadata, target_rows_read, target_rows_kept = load_daily_for_station_ids(
        cache_file,
        TARGET_SOURCE,
        target_neighbor_ids,
        variable=variable,
    )
    print(f"Target stations loaded: {len(target_daily_by_station)}")
    print(f"Target daily rows loaded: {target_rows_kept} of {target_rows_read}")

    print(f"Loading hub daily {variable} temperatures from cache...")
    hub_daily_by_station, hub_metadata, hub_rows_read, hub_rows_kept = load_daily_for_station_ids(
        cache_file,
        HUB_SOURCE,
        [hub["station_id"] for hub in hubs],
        variable=variable,
    )
    print(f"Hub stations loaded: {len(hub_daily_by_station)}")
    print(f"Hub daily rows loaded: {hub_rows_kept} of {hub_rows_read}")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    temp_output_file = output_file.with_suffix(output_file.suffix + ".tmp")
    pair_count = 0

    with temp_output_file.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()

        for target_index, target in enumerate(targets, start=1):
            target_station_id = target["station_id"]
            target_daily = target_daily_by_station.get(target_station_id, {})

            for hub in hubs:
                hub_station_id = hub["station_id"]
                hub_daily = hub_daily_by_station.get(hub_station_id, {})
                write_pairwise_row(
                    writer,
                    target_station_id,
                    HUB_SOURCE,
                    hub_station_id,
                    target_daily,
                    hub_daily,
                    train_end_year,
                )
                pair_count += 1

            target_neighbor_candidates = prefilter_target_neighbor_candidates(
                target,
                target_neighbor_pool,
                target_neighbor_prefilter_count,
                target_neighbor_max_distance_km,
            )

            for neighbor in target_neighbor_candidates:
                neighbor_station_id = neighbor["station_id"]
                neighbor_daily = target_daily_by_station.get(neighbor_station_id, {})
                write_pairwise_row(
                    writer,
                    target_station_id,
                    TARGET_SOURCE,
                    neighbor_station_id,
                    target_daily,
                    neighbor_daily,
                    train_end_year,
                )
                pair_count += 1

            if target_index % 25 == 0 or target_index == len(targets):
                print(
                    f"Pairwise skill rows: {pair_count} "
                    f"after {target_index}/{len(targets)} targets"
                )

    temp_output_file.replace(output_file)
    print()
    print("Pairwise station skill features complete")
    print("----------------------------------------")
    print(f"Targets: {len(targets)}")
    print(f"Hubs: {len(hubs)}")
    print(f"Temperature variable: {variable}")
    print(f"Pair rows: {pair_count}")
    print(f"Training evidence through year: {train_end_year}")
    print(f"Output file: {output_file}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build same-date pairwise historical skill features for target/predictor "
            "station relationships."
        )
    )
    parser.add_argument(
        "--target-limit",
        type=int,
        default=config.DEFAULT_TARGET_LIMIT,
        help="Number of target stations to include.",
    )
    parser.add_argument(
        "--target-neighbor-prefilter-count",
        type=int,
        default=100,
        help="Number of geographically nearest target-neighbor candidates per target.",
    )
    parser.add_argument(
        "--target-neighbor-max-distance-km",
        type=float,
        default=300.0,
        help="Maximum target-neighbor distance. Use 0 to disable the distance limit.",
    )
    parser.add_argument(
        "--train-end-year",
        type=int,
        default=config.DEFAULT_TRAIN_END_YEAR,
        help="Last year allowed when computing historical skill.",
    )
    parser.add_argument(
        "--cache-file",
        type=Path,
        default=config.WEATHER_CACHE_FILE,
        help="SQLite weather cache file.",
    )
    parser.add_argument(
        "--variable",
        choices=sorted(TEMPERATURE_VARIABLES),
        default="tavg",
        help="Daily temperature variable used for same-date pairwise skill.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="Output CSV file.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    build_pairwise_skill_file(
        arguments.target_limit,
        arguments.target_neighbor_prefilter_count,
        arguments.target_neighbor_max_distance_km,
        arguments.train_end_year,
        arguments.cache_file,
        arguments.output_file,
        arguments.variable,
    )


if __name__ == "__main__":
    main()
