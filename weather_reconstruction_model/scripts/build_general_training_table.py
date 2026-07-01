"""Build wide training tables for general temperature reconstruction models.

It assembles target, hub, terrain, offset, and optional pairwise-skill features into model-ready CSV rows."""

import argparse
from pathlib import Path

import batch_validate_models as batch_tools
import config
from common.csv_utils import read_csv_rows
from common.geo_utils import calculate_distance_km
from common.number_utils import to_float
from common.weather_cache import (
    HUB_SOURCE,
    TARGET_SOURCE,
    TEMPERATURE_VARIABLES,
    load_daily_for_station_ids,
    load_date_sets_for_station_ids,
    load_metadata_for_station_ids,
    load_year_coverage_for_station_ids,
    validate_temperature_variable,
)
from pipeline.station_selection import find_training_eligible_hubs
from pipeline.training_tables import (
    build_general_rows_for_target,
    open_streaming_general_table_writer,
)

GENERAL_TABLE_DIR = config.GENERAL_TABLE_DIR
TARGET_CANDIDATE_FILE = config.TARGET_CANDIDATE_FILE
HUB_CANDIDATE_FILE = config.HUB_CANDIDATE_FILE
TARGET_DAILY_FILE = config.TARGET_DAILY_FILE
HUB_DAILY_FILE = config.HUB_DAILY_FILE
TERRAIN_FEATURE_FILE = config.TERRAIN_FEATURE_FILE
WEATHER_CACHE_FILE = config.WEATHER_CACHE_FILE
DEFAULT_PAIRWISE_SKILL_FILE = config.CACHE_DIR / "pairwise_station_skill_features.csv"
DEFAULT_TARGET_LIMIT = 100
DEFAULT_HUB_COUNT = config.DEFAULT_HUB_COUNT
DEFAULT_TARGET_NEIGHBOR_COUNT = 0
DEFAULT_TARGET_NEIGHBOR_PREFILTER_COUNT = 100
DEFAULT_TARGET_NEIGHBOR_MAX_DISTANCE_KM = 300.0
MIN_OVERLAP_PERCENT = config.MIN_OVERLAP_PERCENT
MIN_OVERLAP_DAYS = config.MIN_OVERLAP_DAYS
MIN_SHARED_DAYS = config.MIN_SHARED_DAYS
MAX_ELEVATION_DIFFERENCE_M = config.MAX_ELEVATION_DIFFERENCE_M


def attach_coordinates(selected_stations, source_stations_by_id):
    stations_with_coordinates = []

    for selected_station in selected_stations:
        source_station = source_stations_by_id.get(selected_station["station_id"])

        if source_station is None:
            continue

        station_with_coordinates = dict(selected_station)
        station_with_coordinates["latitude"] = source_station["latitude"]
        station_with_coordinates["longitude"] = source_station["longitude"]
        stations_with_coordinates.append(station_with_coordinates)

    return stations_with_coordinates


def prefilter_target_neighbors(
    target_station,
    target_neighbor_pool,
    prefilter_count,
    max_distance_km,
):
    if prefilter_count <= 0 and max_distance_km <= 0:
        return [
            station
            for station in target_neighbor_pool
            if station["station_id"] != target_station["station_id"]
        ]

    target_latitude = to_float(target_station["latitude"])
    target_longitude = to_float(target_station["longitude"])
    candidates = []

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


def build_prefiltered_target_neighbor_pool_by_target(
    targets,
    target_neighbor_pool,
    target_neighbor_count,
    prefilter_count,
    max_distance_km,
):
    if target_neighbor_count <= 0:
        return {}, []

    pool_by_target = {}
    station_ids = set()

    for target_station in targets:
        candidates = prefilter_target_neighbors(
            target_station,
            target_neighbor_pool,
            prefilter_count,
            max_distance_km,
        )
        pool_by_target[target_station["station_id"]] = candidates
        station_ids.update(station["station_id"] for station in candidates)

    return pool_by_target, sorted(station_ids)


def years_for_dates(dates):
    return sorted({int(date_text[:4]) for date_text in dates})


def approximate_overlap_days(target_dates, candidate_year_coverage):
    return sum(
        candidate_year_coverage.get(year, 0)
        for year in years_for_dates(target_dates)
    )


def prefilter_candidates_by_year_coverage(
    candidates,
    target_dates,
    year_coverage_by_station,
    min_overlap_percent,
    min_overlap_days,
):
    if not year_coverage_by_station:
        return candidates

    minimum_days_from_percent = len(target_dates) * min_overlap_percent / 100
    required_days = max(min_overlap_days, minimum_days_from_percent)
    filtered_candidates = []

    for candidate in candidates:
        station_id = candidate["station_id"]
        approximate_days = approximate_overlap_days(
            target_dates,
            year_coverage_by_station.get(station_id, {}),
        )

        if approximate_days >= required_days:
            filtered_candidates.append(candidate)

    return filtered_candidates


def load_terrain_features(file_path):
    if not file_path.exists():
        print(f"Terrain feature file not found, continuing without terrain values: {file_path}")
        return {}

    terrain_by_station = {}

    for row in read_csv_rows(file_path):
        if row.get("terrain_status") != "ok":
            continue

        station_id = row["station_id"]
        terrain_by_station[station_id] = row

    return terrain_by_station


def load_pairwise_skill_features(file_path):
    if file_path is None:
        return {}

    if not file_path.exists():
        print(f"Pairwise skill file not found, continuing without pairwise values: {file_path}")
        return {}

    pairwise_by_target = {}

    for row in read_csv_rows(file_path):
        target_id = row["target_station_id"]
        source_type = row["predictor_source_type"]
        predictor_id = row["predictor_station_id"]
        pairwise_by_target.setdefault(target_id, {}).setdefault(source_type, {})[
            predictor_id
        ] = row

    return pairwise_by_target


def pairwise_skill_for_target(pairwise_by_target, target_station_id, predictor_source_type):
    return pairwise_by_target.get(target_station_id, {}).get(predictor_source_type, {})


def count_pairwise_skill_rows(pairwise_by_target):
    return sum(
        len(rows_by_predictor)
        for rows_by_source in pairwise_by_target.values()
        for rows_by_predictor in rows_by_source.values()
    )


def merge_loaded_daily(
    cache_file,
    source_type,
    station_ids,
    daily_by_station,
    metadata_by_station,
    variable="tavg",
):
    missing_station_ids = [
        station_id
        for station_id in station_ids
        if station_id not in daily_by_station
    ]

    if not missing_station_ids:
        return 0

    loaded_daily, loaded_metadata, total_rows, rows_kept = load_daily_for_station_ids(
        cache_file,
        source_type,
        missing_station_ids,
        variable=variable,
    )
    daily_by_station.update(loaded_daily)
    metadata_by_station.update(loaded_metadata)
    return rows_kept


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Build a many-station training table with target, date, hub temperature, and hub geography features."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_TARGET_LIMIT,
        help="Number of target stations to include. Use 0 or a negative value for all targets.",
    )
    parser.add_argument(
        "--hub-count",
        type=int,
        default=DEFAULT_HUB_COUNT,
        help="Number of selected hubs to include per target.",
    )
    parser.add_argument(
        "--target-neighbor-count",
        type=int,
        default=DEFAULT_TARGET_NEIGHBOR_COUNT,
        help="Number of non-hub target stations to include as extra predictors per target.",
    )
    parser.add_argument(
        "--target-neighbor-prefilter-count",
        type=int,
        default=DEFAULT_TARGET_NEIGHBOR_PREFILTER_COUNT,
        help="Number of geographically nearest target-neighbor candidates to overlap-check. Use 0 to disable this limit.",
    )
    parser.add_argument(
        "--target-neighbor-max-distance-km",
        type=float,
        default=DEFAULT_TARGET_NEIGHBOR_MAX_DISTANCE_KM,
        help="Maximum target-neighbor candidate distance before overlap checks. Use 0 to disable this limit.",
    )
    parser.add_argument(
        "--min-shared-days",
        type=int,
        default=MIN_SHARED_DAYS,
        help="Minimum all-hub shared dates required for a target to be included.",
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Load daily temperature data from the SQLite cache instead of scanning CSVs.",
    )
    parser.add_argument(
        "--variable",
        choices=sorted(TEMPERATURE_VARIABLES),
        default="tavg",
        help="Daily temperature variable to use for target and predictor values.",
    )
    parser.add_argument(
        "--cache-file",
        type=Path,
        default=WEATHER_CACHE_FILE,
        help="SQLite weather cache file used with --use-cache.",
    )
    parser.add_argument(
        "--terrain-file",
        type=Path,
        default=TERRAIN_FEATURE_FILE,
        help="DEM-derived terrain feature CSV to merge into the general table.",
    )
    parser.add_argument(
        "--pairwise-skill-file",
        type=Path,
        default=DEFAULT_PAIRWISE_SKILL_FILE,
        help=(
            "Same-date pairwise historical skill CSV to merge into selection and "
            "training features. Missing files are treated as neutral/no pairwise skill."
        ),
    )
    parser.add_argument(
        "--disable-pairwise-skill",
        action="store_true",
        help="Do not load or use pairwise historical skill features.",
    )
    parser.add_argument(
        "--output-stem",
        default=None,
        help="Optional stable output filename stem. The .csv extension is added automatically.",
    )
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    variable = validate_temperature_variable(arguments.variable)
    all_targets = read_csv_rows(TARGET_CANDIDATE_FILE)
    targets = all_targets if arguments.limit <= 0 else all_targets[:arguments.limit]
    target_neighbor_pool = read_csv_rows(TARGET_CANDIDATE_FILE)
    hubs = read_csv_rows(HUB_CANDIDATE_FILE)
    hubs_by_id = {
        hub["station_id"]: hub
        for hub in hubs
    }
    target_neighbor_pool_by_id = {
        station["station_id"]: station
        for station in target_neighbor_pool
    }
    target_ids = [target["station_id"] for target in targets]
    target_neighbor_pool_by_target, target_neighbor_ids = build_prefiltered_target_neighbor_pool_by_target(
        targets,
        target_neighbor_pool,
        arguments.target_neighbor_count,
        arguments.target_neighbor_prefilter_count,
        arguments.target_neighbor_max_distance_km,
    )

    print("Build general many-station training table")
    print("=========================================")
    print(f"Target limit: {'all' if arguments.limit <= 0 else arguments.limit}")
    print(f"Hubs per target: {arguments.hub_count}")
    print(f"Target-neighbor stations per target: {arguments.target_neighbor_count}")
    if arguments.target_neighbor_count > 0:
        print(f"Target-neighbor prefilter count: {arguments.target_neighbor_prefilter_count}")
        print(f"Target-neighbor max distance km: {arguments.target_neighbor_max_distance_km:g}")
        print(f"Target-neighbor candidate union: {len(target_neighbor_ids)}")
    print(f"Minimum shared days: {arguments.min_shared_days}")
    print(f"Temperature variable: {variable}")
    print(f"Daily data source: {'SQLite cache' if arguments.use_cache else 'CSV files'}")
    print()
    print("Loading terrain features...")

    terrain_by_station = load_terrain_features(arguments.terrain_file)
    print(f"Terrain feature rows loaded: {len(terrain_by_station)}")
    print("Loading pairwise historical skill features...")
    pairwise_skill_file = None if arguments.disable_pairwise_skill else arguments.pairwise_skill_file
    pairwise_skill_by_key = load_pairwise_skill_features(pairwise_skill_file)
    print(f"Pairwise skill rows loaded: {count_pairwise_skill_rows(pairwise_skill_by_key)}")
    print()
    print("Loading target daily data...")

    requested_target_ids = sorted(set(target_ids + target_neighbor_ids))
    if arguments.use_cache and arguments.target_neighbor_count > 0:
        target_daily_by_station, target_metadata_by_station, target_rows_read, target_rows_kept = load_daily_for_station_ids(
            arguments.cache_file,
            TARGET_SOURCE,
            target_ids,
            variable=variable,
        )
        target_neighbor_metadata_by_station = load_metadata_for_station_ids(
            arguments.cache_file,
            TARGET_SOURCE,
            target_neighbor_ids,
        )
        target_neighbor_year_coverage_by_station = load_year_coverage_for_station_ids(
            arguments.cache_file,
            TARGET_SOURCE,
            target_neighbor_ids,
        )
        target_dates_by_station = {
            station_id: set(daily_rows.keys())
            for station_id, daily_rows in target_daily_by_station.items()
        }
        target_metadata_by_station.update(target_neighbor_metadata_by_station)
        target_rows_read = len(target_neighbor_ids)
        target_rows_kept = len(target_neighbor_year_coverage_by_station)
    elif arguments.use_cache:
        target_daily_by_station, target_metadata_by_station, target_rows_read, target_rows_kept = load_daily_for_station_ids(
            arguments.cache_file,
            TARGET_SOURCE,
            requested_target_ids,
            variable=variable,
        )
        target_dates_by_station = {
            station_id: set(daily_rows.keys())
            for station_id, daily_rows in target_daily_by_station.items()
        }
        target_neighbor_year_coverage_by_station = {}
    else:
        target_daily_by_station, target_metadata_by_station, target_rows_read, target_rows_kept = batch_tools.load_target_daily_for_batch(
            TARGET_DAILY_FILE,
            requested_target_ids,
            variable=variable,
        )
        target_dates_by_station = {
            station_id: set(daily_rows.keys())
            for station_id, daily_rows in target_daily_by_station.items()
        }
        target_neighbor_year_coverage_by_station = {}

    print(f"Target rows scanned: {target_rows_read}")
    print(f"Target rows kept: {target_rows_kept}")
    print("Loading hub daily data...")

    if arguments.use_cache:
        hub_metadata_by_station = load_metadata_for_station_ids(
            arguments.cache_file,
            HUB_SOURCE,
        )
        hub_year_coverage_by_station = load_year_coverage_for_station_ids(
            arguments.cache_file,
            HUB_SOURCE,
        )
        hub_dates_by_station = {}
        hub_rows_read = len(hubs)
        hub_rows_kept = len(hub_year_coverage_by_station)
    else:
        hub_daily_by_station, hub_metadata_by_station, hub_rows_read = batch_tools.load_hub_daily_for_batch(
            HUB_DAILY_FILE,
            variable=variable,
        )
        hub_rows_kept = hub_rows_read
        hub_dates_by_station = {
            station_id: set(daily_rows.keys())
            for station_id, daily_rows in hub_daily_by_station.items()
        }
        hub_year_coverage_by_station = {}

    if arguments.use_cache:
        hub_daily_by_station = {}

    print(f"Hub rows scanned: {hub_rows_read}")
    print(f"Hub rows kept: {hub_rows_kept}")
    print()

    included_targets = 0
    skipped_targets = 0
    total_rows = 0
    output_stem = arguments.output_stem
    default_output_stem = output_stem is None

    if output_stem is None:
        output_stem = f"general_pending_{arguments.limit}_targets_{arguments.hub_count}_hubs"
        if arguments.target_neighbor_count > 0:
            output_stem += f"_{arguments.target_neighbor_count}_target_neighbors"
        if variable != "tavg":
            output_stem += f"_{variable}"

    output_file = GENERAL_TABLE_DIR / f"{output_stem}.csv"
    temp_output_file = output_file.with_suffix(output_file.suffix + ".tmp")
    output_handle, output_writer = open_streaming_general_table_writer(
        temp_output_file,
        arguments.hub_count,
        arguments.target_neighbor_count,
        variable,
    )

    try:
        for index, target_station in enumerate(targets, start=1):
            target_id = target_station["station_id"]
            target_daily = target_daily_by_station.get(target_id, {})
            target_metadata = target_metadata_by_station.get(target_id, {})

            print(f"[{index}/{len(targets)}] {target_id}", end=" ")

            if not target_daily:
                skipped_targets += 1
                print("SKIP: no target daily data")
                continue

            target_dates = set(target_daily.keys())
            hub_candidates = prefilter_candidates_by_year_coverage(
                hubs,
                target_dates,
                hub_year_coverage_by_station,
                MIN_OVERLAP_PERCENT,
                MIN_OVERLAP_DAYS,
            )

            if arguments.use_cache:
                hub_candidate_dates, hub_candidate_metadata, hub_candidate_rows_read, hub_candidate_rows_kept = load_date_sets_for_station_ids(
                    arguments.cache_file,
                    HUB_SOURCE,
                    [hub["station_id"] for hub in hub_candidates],
                )
                hub_dates_by_station.update(hub_candidate_dates)
                hub_metadata_by_station.update(hub_candidate_metadata)

            selected_hubs, eligible_hubs, rejected_hubs = find_training_eligible_hubs(
                target_station,
                hub_candidates,
                target_dates,
                target_metadata,
                hub_dates_by_station,
                hub_metadata_by_station,
                arguments.hub_count,
                MIN_OVERLAP_PERCENT,
                MIN_OVERLAP_DAYS,
                MAX_ELEVATION_DIFFERENCE_M,
                terrain_by_station.get(target_id, {}),
                terrain_by_station,
                pairwise_skill_for_target(pairwise_skill_by_key, target_id, HUB_SOURCE),
            )

            if len(selected_hubs) < arguments.hub_count:
                skipped_targets += 1
                print(f"SKIP: only {len(selected_hubs)} eligible hubs")
                continue

            selected_hubs_with_coordinates = attach_coordinates(selected_hubs, hubs_by_id)
            selected_target_neighbors_with_coordinates = []

            if arguments.target_neighbor_count > 0:
                target_neighbor_candidates = target_neighbor_pool_by_target[target_id]
                target_neighbor_candidates = prefilter_candidates_by_year_coverage(
                    target_neighbor_candidates,
                    target_dates,
                    target_neighbor_year_coverage_by_station,
                    MIN_OVERLAP_PERCENT,
                    MIN_OVERLAP_DAYS,
                )

                if arguments.use_cache:
                    target_neighbor_candidate_dates, target_neighbor_candidate_metadata, target_neighbor_candidate_rows_read, target_neighbor_candidate_rows_kept = load_date_sets_for_station_ids(
                        arguments.cache_file,
                        TARGET_SOURCE,
                        [station["station_id"] for station in target_neighbor_candidates],
                    )
                    target_dates_by_station.update(target_neighbor_candidate_dates)
                    target_metadata_by_station.update(target_neighbor_candidate_metadata)

                selected_target_neighbors, eligible_target_neighbors, rejected_target_neighbors = find_training_eligible_hubs(
                    target_station,
                    target_neighbor_candidates,
                    target_dates,
                    target_metadata,
                    target_dates_by_station,
                    target_metadata_by_station,
                    arguments.target_neighbor_count,
                    MIN_OVERLAP_PERCENT,
                    MIN_OVERLAP_DAYS,
                    MAX_ELEVATION_DIFFERENCE_M,
                    terrain_by_station.get(target_id, {}),
                    terrain_by_station,
                    pairwise_skill_for_target(pairwise_skill_by_key, target_id, TARGET_SOURCE),
                )

                if len(selected_target_neighbors) < arguments.target_neighbor_count:
                    skipped_targets += 1
                    print(
                        f"SKIP: only {len(selected_target_neighbors)} eligible target-neighbors"
                    )
                    continue

                selected_target_neighbors_with_coordinates = attach_coordinates(
                    selected_target_neighbors,
                    target_neighbor_pool_by_id,
                )

            if arguments.use_cache:
                merge_loaded_daily(
                    arguments.cache_file,
                    HUB_SOURCE,
                    [hub["station_id"] for hub in selected_hubs],
                    hub_daily_by_station,
                    hub_metadata_by_station,
                    variable,
                )
                merge_loaded_daily(
                    arguments.cache_file,
                    TARGET_SOURCE,
                    [neighbor["station_id"] for neighbor in selected_target_neighbors_with_coordinates],
                    target_daily_by_station,
                    target_metadata_by_station,
                    variable,
                )

            rows = build_general_rows_for_target(
                target_station,
                target_metadata,
                target_daily,
                selected_hubs_with_coordinates,
                selected_target_neighbors_with_coordinates,
                hub_daily_by_station,
                hub_metadata_by_station,
                target_daily_by_station,
                target_metadata_by_station,
                terrain_by_station,
                variable,
            )

            if len(rows) < arguments.min_shared_days:
                skipped_targets += 1
                print(f"SKIP: only {len(rows)} shared rows")
                continue

            output_writer.writerows(rows)
            output_handle.flush()
            total_rows += len(rows)
            included_targets += 1
            print(
                f"INCLUDE: {len(rows)} rows, {len(eligible_hubs)} eligible hubs"
            )
    finally:
        output_handle.close()

    if default_output_stem:
        output_stem = f"general_{included_targets}_targets_{arguments.hub_count}_hubs"
        if arguments.target_neighbor_count > 0:
            output_stem += f"_{arguments.target_neighbor_count}_target_neighbors"
            if (
                arguments.target_neighbor_prefilter_count > 0
                or arguments.target_neighbor_max_distance_km > 0
            ):
                output_stem += (
                    f"_prefilter_{arguments.target_neighbor_prefilter_count}"
                    f"_{arguments.target_neighbor_max_distance_km:g}km"
                )
        if variable != "tavg":
            output_stem += f"_{variable}"
        output_file = GENERAL_TABLE_DIR / f"{output_stem}.csv"

    temp_output_file.replace(output_file)

    print()
    print("General training table complete")
    print("-------------------------------")
    print(f"Included targets: {included_targets}")
    print(f"Skipped targets: {skipped_targets}")
    print(f"Total rows: {total_rows}")
    print(f"Output file: {output_file}")


if __name__ == "__main__":
    main()
