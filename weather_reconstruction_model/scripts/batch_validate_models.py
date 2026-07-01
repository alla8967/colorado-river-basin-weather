"""Run station-validation experiments across many targets and write aggregate metrics.

This script is the baseline batch evaluator for comparing reconstruction model choices."""

import argparse
import csv
from pathlib import Path

import config
import train_temperature_model as model_trainer
from common.csv_utils import read_csv_rows, write_csv_rows
from common.geo_utils import calculate_distance_km
from common.number_utils import to_float
from common.weather_cache import (
    HUB_SOURCE,
    TARGET_SOURCE,
    load_daily_for_station_ids,
    load_date_sets_for_station_ids,
    validate_temperature_variable,
)
from pipeline.station_selection import find_training_eligible_hubs
from pipeline.training_tables import build_shared_date_rows

PROJECT_DIR = config.PROJECT_DIR
REPORT_DIR = config.REPORT_DIR
TARGET_CANDIDATE_FILE = config.TARGET_CANDIDATE_FILE
HUB_CANDIDATE_FILE = config.HUB_CANDIDATE_FILE
TARGET_DAILY_FILE = config.TARGET_DAILY_FILE
HUB_DAILY_FILE = config.HUB_DAILY_FILE
WEATHER_CACHE_FILE = config.WEATHER_CACHE_FILE
DEFAULT_TARGET_LIMIT = config.DEFAULT_TARGET_LIMIT
DEFAULT_HUB_COUNT = config.DEFAULT_HUB_COUNT
DEFAULT_HUB_PREFILTER_COUNT = 0
DEFAULT_HUB_MAX_DISTANCE_KM = 0.0
DEFAULT_TRAIN_END_YEAR = config.DEFAULT_TRAIN_END_YEAR
DEFAULT_TEST_START_YEAR = config.DEFAULT_TEST_START_YEAR
DEFAULT_ALPHA = config.DEFAULT_ALPHA
MIN_OVERLAP_PERCENT = config.MIN_OVERLAP_PERCENT
MIN_OVERLAP_DAYS = config.MIN_OVERLAP_DAYS
MIN_SHARED_DAYS = config.MIN_SHARED_DAYS
MIN_TEST_DAYS = config.MIN_TEST_DAYS
MAX_ELEVATION_DIFFERENCE_M = config.MAX_ELEVATION_DIFFERENCE_M
PASS_MAX_MAE = config.PASS_MAX_MAE
PASS_MAX_RMSE = config.PASS_MAX_RMSE
PASS_MIN_CORRELATION = config.PASS_MIN_CORRELATION
BORDERLINE_MAX_MAE = config.BORDERLINE_MAX_MAE
BORDERLINE_MAX_RMSE = config.BORDERLINE_MAX_RMSE
BORDERLINE_MIN_CORRELATION = config.BORDERLINE_MIN_CORRELATION


def calculate_tavg(row):
    return (to_float(row["tmax"]) + to_float(row["tmin"])) / 2


def calculate_temperature_value(row, variable="tavg"):
    variable = validate_temperature_variable(variable)

    if variable == "tavg":
        return calculate_tavg(row)

    return to_float(row[variable])


def load_target_daily_for_batch(file_path, target_ids, variable="tavg"):
    variable = validate_temperature_variable(variable)
    target_id_set = set(target_ids)
    daily_by_station = {station_id: {} for station_id in target_ids}
    metadata_by_station = {}
    rows_read = 0
    rows_kept = 0

    with file_path.open("r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            rows_read += 1
            station_id = row["station_id"]

            if station_id not in target_id_set:
                continue

            rows_kept += 1
            daily_by_station[station_id][row["date"]] = calculate_temperature_value(
                row,
                variable,
            )
            metadata_by_station[station_id] = {
                "station_name": row["station_name"],
                "elevation": row["elevation"],
            }

    return daily_by_station, metadata_by_station, rows_read, rows_kept


def load_hub_daily_for_batch(file_path, variable="tavg"):
    variable = validate_temperature_variable(variable)
    daily_by_station = {}
    metadata_by_station = {}
    rows_read = 0

    with file_path.open("r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            rows_read += 1
            station_id = row["station_id"]

            if station_id not in daily_by_station:
                daily_by_station[station_id] = {}
                metadata_by_station[station_id] = {
                    "station_name": row["station_name"],
                    "elevation": row["elevation"],
                }

            daily_by_station[station_id][row["date"]] = calculate_temperature_value(
                row,
                variable,
            )

    return daily_by_station, metadata_by_station, rows_read


def merge_cached_daily_for_station_ids(
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

    loaded_daily, loaded_metadata, rows_read, rows_kept = load_daily_for_station_ids(
        cache_file,
        source_type,
        missing_station_ids,
        variable=variable,
    )
    daily_by_station.update(loaded_daily)
    metadata_by_station.update(loaded_metadata)
    return rows_kept


def merge_cached_date_sets_for_hubs(
    cache_file,
    hub_candidates,
    hub_dates_by_station,
    hub_metadata_by_station,
):
    missing_station_ids = [
        hub["station_id"]
        for hub in hub_candidates
        if hub["station_id"] not in hub_dates_by_station
    ]

    if not missing_station_ids:
        return 0, 0

    candidate_dates, candidate_metadata, rows_read, rows_kept = load_date_sets_for_station_ids(
        cache_file,
        HUB_SOURCE,
        missing_station_ids,
    )
    hub_dates_by_station.update(candidate_dates)
    hub_metadata_by_station.update(candidate_metadata)
    return len(missing_station_ids), rows_kept


def hub_prefilter_enabled(prefilter_count, max_distance_km):
    return prefilter_count > 0 or max_distance_km > 0


def prefilter_hubs_for_target(
    target_station,
    hubs,
    prefilter_count,
    max_distance_km,
):
    if prefilter_count <= 0 and max_distance_km <= 0:
        return hubs

    target_latitude = to_float(target_station["latitude"])
    target_longitude = to_float(target_station["longitude"])
    candidates = []

    for hub in hubs:
        distance_km = calculate_distance_km(
            target_latitude,
            target_longitude,
            to_float(hub["latitude"]),
            to_float(hub["longitude"]),
        )

        if max_distance_km > 0 and distance_km > max_distance_km:
            continue

        candidates.append((distance_km, hub))

    candidates.sort(key=lambda item: item[0])

    if prefilter_count > 0:
        candidates = candidates[:prefilter_count]

    return [
        hub
        for distance_km, hub in candidates
    ]


def train_and_score_rows(rows, train_end_year, test_start_year, alpha):
    hub_temperature_columns = model_trainer.get_hub_temperature_columns(rows[0].keys())
    train_rows, test_rows = model_trainer.split_rows_by_year(
        rows,
        train_end_year,
        test_start_year,
    )

    if len(test_rows) < MIN_TEST_DAYS:
        raise ValueError(f"Only {len(test_rows)} test rows found")

    train_features, train_labels = model_trainer.build_features_and_labels(
        train_rows,
        hub_temperature_columns,
    )
    test_features, test_labels = model_trainer.build_features_and_labels(
        test_rows,
        hub_temperature_columns,
    )
    coefficients = model_trainer.train_linear_regression(
        train_features,
        train_labels,
        alpha,
    )
    train_predictions = model_trainer.predict(train_features, coefficients)
    test_predictions = model_trainer.predict(test_features, coefficients)

    average_train_predictions = model_trainer.average_hub_predictions(
        train_rows,
        hub_temperature_columns,
    )
    average_test_predictions = model_trainer.average_hub_predictions(
        test_rows,
        hub_temperature_columns,
    )

    return {
        "train_rows": len(train_rows),
        "test_rows": len(test_rows),
        "train_metrics": model_trainer.calculate_metrics(train_labels, train_predictions),
        "test_metrics": model_trainer.calculate_metrics(test_labels, test_predictions),
        "average_train_metrics": model_trainer.calculate_metrics(train_labels, average_train_predictions),
        "average_test_metrics": model_trainer.calculate_metrics(test_labels, average_test_predictions),
        "coefficients": coefficients,
    }


def classify_result(test_metrics, test_days):
    if test_days < MIN_TEST_DAYS:
        return "FAIL"

    if (
        test_metrics["mae"] <= PASS_MAX_MAE
        and test_metrics["rmse"] <= PASS_MAX_RMSE
        and test_metrics["correlation"] >= PASS_MIN_CORRELATION
    ):
        return "PASS"

    if (
        test_metrics["mae"] <= BORDERLINE_MAX_MAE
        and test_metrics["rmse"] <= BORDERLINE_MAX_RMSE
        and test_metrics["correlation"] >= BORDERLINE_MIN_CORRELATION
    ):
        return "BORDERLINE"

    return "FAIL"


def blank_summary_row(target_station, target_metadata, status, reason):
    return {
        "target_station_id": target_station["station_id"],
        "target_name": target_metadata.get("station_name", "Unknown station"),
        "target_latitude": target_station["latitude"],
        "target_longitude": target_station["longitude"],
        "target_elevation_m": target_metadata.get("elevation", ""),
        "status": status,
        "reason": reason,
    }


def build_summary_row(
    target_station,
    target_metadata,
    target_daily,
    selected_hubs,
    eligible_hub_count,
    rejected_hub_count,
    shared_rows,
    score,
):
    test_metrics = score["test_metrics"]
    average_test_metrics = score["average_test_metrics"]
    distances = [hub["distance_km"] for hub in selected_hubs]
    elevation_differences = [hub["elevation_difference_m"] for hub in selected_hubs]
    overlap_percents = [hub["overlap_percent"] for hub in selected_hubs]
    status = classify_result(test_metrics, score["test_rows"])

    return {
        "target_station_id": target_station["station_id"],
        "target_name": target_metadata.get("station_name", "Unknown station"),
        "target_latitude": target_station["latitude"],
        "target_longitude": target_station["longitude"],
        "target_elevation_m": target_metadata.get("elevation", ""),
        "status": status,
        "reason": "",
        "target_observed_days": len(target_daily),
        "eligible_hubs": eligible_hub_count,
        "rejected_hubs": rejected_hub_count,
        "selected_hubs": ";".join(hub["station_id"] for hub in selected_hubs),
        "shared_days": len(shared_rows),
        "train_days": score["train_rows"],
        "test_days": score["test_rows"],
        "test_mae_f": f"{test_metrics['mae']:.4f}",
        "test_rmse_f": f"{test_metrics['rmse']:.4f}",
        "test_correlation": f"{test_metrics['correlation']:.5f}",
        "average_hub_test_mae_f": f"{average_test_metrics['mae']:.4f}",
        "average_hub_test_rmse_f": f"{average_test_metrics['rmse']:.4f}",
        "average_hub_test_correlation": f"{average_test_metrics['correlation']:.5f}",
        "nearest_hub_km": f"{min(distances):.2f}",
        "farthest_hub_km": f"{max(distances):.2f}",
        "average_hub_distance_km": f"{sum(distances) / len(distances):.2f}",
        "average_elevation_difference_m": f"{sum(elevation_differences) / len(elevation_differences):.1f}",
        "minimum_selected_overlap_percent": f"{min(overlap_percents):.1f}",
    }


def write_summary(output_file, rows):
    fieldnames = [
        "target_station_id",
        "target_name",
        "target_latitude",
        "target_longitude",
        "target_elevation_m",
        "status",
        "reason",
        "target_observed_days",
        "eligible_hubs",
        "rejected_hubs",
        "selected_hubs",
        "shared_days",
        "train_days",
        "test_days",
        "test_mae_f",
        "test_rmse_f",
        "test_correlation",
        "average_hub_test_mae_f",
        "average_hub_test_rmse_f",
        "average_hub_test_correlation",
        "nearest_hub_km",
        "farthest_hub_km",
        "average_hub_distance_km",
        "average_elevation_difference_m",
        "minimum_selected_overlap_percent",
    ]

    write_csv_rows(output_file, rows, fieldnames)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Run regression validation across many target stations."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_TARGET_LIMIT,
        help="Number of target stations to validate.",
    )
    parser.add_argument(
        "--hub-count",
        type=int,
        default=DEFAULT_HUB_COUNT,
        help="Number of hub stations to use per target.",
    )
    parser.add_argument(
        "--hub-prefilter-count",
        type=int,
        default=DEFAULT_HUB_PREFILTER_COUNT,
        help="Number of geographically nearest hub candidates to date-check in cache mode. Defaults to 0 so cache mode matches CSV selection.",
    )
    parser.add_argument(
        "--hub-max-distance-km",
        type=float,
        default=DEFAULT_HUB_MAX_DISTANCE_KM,
        help="Maximum hub candidate distance in cache mode before date checks. Defaults to 0 so cache mode matches CSV selection.",
    )
    parser.add_argument(
        "--train-end",
        type=int,
        default=DEFAULT_TRAIN_END_YEAR,
        help="Last year used for training.",
    )
    parser.add_argument(
        "--test-start",
        type=int,
        default=DEFAULT_TEST_START_YEAR,
        help="First year used for testing.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=DEFAULT_ALPHA,
        help="Regression regularization. Use 0 for ordinary linear regression.",
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Load daily temperature data from the SQLite cache instead of scanning CSVs.",
    )
    parser.add_argument(
        "--cache-file",
        type=Path,
        default=WEATHER_CACHE_FILE,
        help="SQLite weather cache file used with --use-cache.",
    )
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    targets = read_csv_rows(TARGET_CANDIDATE_FILE)[:arguments.limit]
    hubs = read_csv_rows(HUB_CANDIDATE_FILE)
    target_ids = [target["station_id"] for target in targets]

    print("Batch temperature reconstruction validation")
    print("===========================================")
    print(f"Targets: {len(targets)}")
    print(f"Hubs per target: {arguments.hub_count}")
    print(f"Train through: {arguments.train_end}")
    print(f"Test from: {arguments.test_start}")
    print(f"Alpha: {arguments.alpha}")
    print(f"Daily data source: {'SQLite cache' if arguments.use_cache else 'CSV files'}")
    print()
    print("Loading daily target data...")

    if arguments.use_cache:
        target_daily_by_station, target_metadata_by_station, target_rows_read, target_rows_kept = load_daily_for_station_ids(
            arguments.cache_file,
            TARGET_SOURCE,
            target_ids,
        )
    else:
        target_daily_by_station, target_metadata_by_station, target_rows_read, target_rows_kept = load_target_daily_for_batch(
            TARGET_DAILY_FILE,
            target_ids,
        )

    print(f"Target rows scanned: {target_rows_read}")
    print(f"Target rows kept: {target_rows_kept}")
    print("Loading daily hub data...")

    if arguments.use_cache:
        hub_dates_by_station = {}
        hub_metadata_by_station = {}
        hub_daily_by_station = {}
        hub_rows_read = 0
        hub_rows_kept = 0
    else:
        hub_daily_by_station, hub_metadata_by_station, hub_rows_read = load_hub_daily_for_batch(
            HUB_DAILY_FILE
        )
        hub_rows_kept = hub_rows_read
        hub_dates_by_station = {
            station_id: set(daily_rows.keys())
            for station_id, daily_rows in hub_daily_by_station.items()
        }

    if arguments.use_cache:
        print("Hub date loading: deferred by target")
        print(f"Hub prefilter count: {arguments.hub_prefilter_count}")
        print(f"Hub max distance km: {arguments.hub_max_distance_km:g}")
        if not hub_prefilter_enabled(
            arguments.hub_prefilter_count,
            arguments.hub_max_distance_km,
        ):
            print("Hub prefilter: disabled; cache mode will preserve CSV selection behavior")
    else:
        print(f"Hub rows scanned: {hub_rows_read}")
        print(f"Hub rows kept: {hub_rows_kept}")
    print()

    summary_rows = []

    for index, target_station in enumerate(targets, start=1):
        target_id = target_station["station_id"]
        target_daily = target_daily_by_station.get(target_id, {})
        target_metadata = target_metadata_by_station.get(target_id, {})

        print(f"[{index}/{len(targets)}] {target_id}", end=" ")

        if not target_daily:
            print("SKIP: no target daily data")
            summary_rows.append(blank_summary_row(
                target_station,
                target_metadata,
                "FAIL",
                "No target daily data",
            ))
            continue

        hub_candidates = hubs
        used_prefilter = False

        if arguments.use_cache:
            used_prefilter = hub_prefilter_enabled(
                arguments.hub_prefilter_count,
                arguments.hub_max_distance_km,
            )
            if used_prefilter:
                hub_candidates = prefilter_hubs_for_target(
                    target_station,
                    hubs,
                    arguments.hub_prefilter_count,
                    arguments.hub_max_distance_km,
                )

            candidate_count, rows_kept = merge_cached_date_sets_for_hubs(
                arguments.cache_file,
                hub_candidates,
                hub_dates_by_station,
                hub_metadata_by_station,
            )
            hub_rows_read += candidate_count
            hub_rows_kept += rows_kept

        selected_hubs, eligible_hubs, rejected_hubs = find_training_eligible_hubs(
            target_station,
            hub_candidates,
            set(target_daily.keys()),
            target_metadata,
            hub_dates_by_station,
            hub_metadata_by_station,
            arguments.hub_count,
            MIN_OVERLAP_PERCENT,
            MIN_OVERLAP_DAYS,
            MAX_ELEVATION_DIFFERENCE_M,
        )

        if len(selected_hubs) < arguments.hub_count and arguments.use_cache and used_prefilter:
            fallback_count, rows_kept = merge_cached_date_sets_for_hubs(
                arguments.cache_file,
                hubs,
                hub_dates_by_station,
                hub_metadata_by_station,
            )
            hub_rows_read += fallback_count
            hub_rows_kept += rows_kept

            selected_hubs, eligible_hubs, rejected_hubs = find_training_eligible_hubs(
                target_station,
                hubs,
                set(target_daily.keys()),
                target_metadata,
                hub_dates_by_station,
                hub_metadata_by_station,
                arguments.hub_count,
                MIN_OVERLAP_PERCENT,
                MIN_OVERLAP_DAYS,
                MAX_ELEVATION_DIFFERENCE_M,
            )

        if len(selected_hubs) < arguments.hub_count:
            print(f"SKIP: only {len(selected_hubs)} eligible hubs")
            summary_rows.append(blank_summary_row(
                target_station,
                target_metadata,
                "FAIL",
                f"Only {len(selected_hubs)} eligible hubs",
            ))
            continue

        selected_hub_ids = [hub["station_id"] for hub in selected_hubs]

        if arguments.use_cache:
            merge_cached_daily_for_station_ids(
                arguments.cache_file,
                HUB_SOURCE,
                selected_hub_ids,
                hub_daily_by_station,
                hub_metadata_by_station,
            )

        shared_rows = build_shared_date_rows(
            target_id,
            selected_hub_ids,
            target_daily,
            hub_daily_by_station,
        )

        if len(shared_rows) < MIN_SHARED_DAYS:
            print(f"SKIP: only {len(shared_rows)} shared days")
            summary_rows.append(blank_summary_row(
                target_station,
                target_metadata,
                "FAIL",
                f"Only {len(shared_rows)} shared days",
            ))
            continue

        try:
            score = train_and_score_rows(
                shared_rows,
                arguments.train_end,
                arguments.test_start,
                arguments.alpha,
            )
        except ValueError as error:
            print(f"SKIP: {error}")
            summary_rows.append(blank_summary_row(
                target_station,
                target_metadata,
                "FAIL",
                str(error),
            ))
            continue

        summary_row = build_summary_row(
            target_station,
            target_metadata,
            target_daily,
            selected_hubs,
            len(eligible_hubs),
            len(rejected_hubs),
            shared_rows,
            score,
        )
        summary_rows.append(summary_row)

        print(
            f"{summary_row['status']}: "
            f"MAE {summary_row['test_mae_f']} F, "
            f"RMSE {summary_row['test_rmse_f']} F, "
            f"r {summary_row['test_correlation']}"
        )

    output_file = REPORT_DIR / f"batch_{len(targets)}_targets_{arguments.hub_count}_hubs.csv"
    write_summary(output_file, summary_rows)

    pass_count = sum(1 for row in summary_rows if row["status"] == "PASS")
    borderline_count = sum(1 for row in summary_rows if row["status"] == "BORDERLINE")
    fail_count = sum(1 for row in summary_rows if row["status"] == "FAIL")

    print()
    print("Batch complete")
    print("--------------")
    print(f"PASS: {pass_count}")
    print(f"BORDERLINE: {borderline_count}")
    print(f"FAIL: {fail_count}")
    if arguments.use_cache:
        print(f"Hub candidate stations date-checked: {hub_rows_read}")
        print(f"Hub candidate date rows loaded: {hub_rows_kept}")
    print(f"Summary file: {output_file}")


if __name__ == "__main__":
    main()
