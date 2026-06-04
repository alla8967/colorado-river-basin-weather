from pathlib import Path
import csv
import sys

import config
from common.csv_utils import read_csv_rows, write_csv_rows
from common.geo_utils import calculate_distance_km
from common.number_utils import to_float
from pipeline.station_selection import find_training_eligible_hubs
from pipeline.training_tables import build_shared_date_rows

PROJECT_DIR = config.PROJECT_DIR
TRAINING_TABLE_DIR = config.TRAINING_TABLE_DIR
TARGET_CANDIDATE_FILE = config.TARGET_CANDIDATE_FILE
HUB_CANDIDATE_FILE = config.HUB_CANDIDATE_FILE
TARGET_DAILY_FILE = config.TARGET_DAILY_FILE
HUB_DAILY_FILE = config.HUB_DAILY_FILE
DEFAULT_TARGET_STATION_ID = config.DEFAULT_TARGET_STATION_ID
DEFAULT_HUB_COUNT = config.DEFAULT_HUB_COUNT
MIN_OVERLAP_PERCENT = config.MIN_OVERLAP_PERCENT
MIN_OVERLAP_DAYS = config.MIN_OVERLAP_DAYS
MAX_ELEVATION_DIFFERENCE_M = config.MAX_ELEVATION_DIFFERENCE_M


def calculate_tavg(row):
    return (to_float(row["tmax"]) + to_float(row["tmin"])) / 2


def find_station_by_id(stations, station_id):
    for station in stations:
        if station["station_id"] == station_id:
            return station

    return None


def find_nearest_hubs(target_station, hubs, count):
    target_latitude = to_float(target_station["latitude"])
    target_longitude = to_float(target_station["longitude"])
    ranked_hubs = []

    for hub in hubs:
        hub_latitude = to_float(hub["latitude"])
        hub_longitude = to_float(hub["longitude"])
        distance_km = calculate_distance_km(
            target_latitude,
            target_longitude,
            hub_latitude,
            hub_longitude,
        )

        ranked_hubs.append({
            "station_id": hub["station_id"],
            "distance_km": distance_km,
            "usable_period": f"{hub['usable_temp_start']}-{hub['usable_temp_end']}",
        })

    ranked_hubs.sort(key=lambda hub: hub["distance_km"])
    return ranked_hubs[:count]


def load_target_daily_dates(file_path, target_station_id):
    dates = set()
    metadata = {}
    rows_read = 0
    rows_kept = 0

    with file_path.open("r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            rows_read += 1

            if row["station_id"] != target_station_id:
                continue

            rows_kept += 1
            dates.add(row["date"])
            metadata = {
                "station_name": row["station_name"],
                "elevation": row["elevation"],
            }

    return dates, metadata, rows_read, rows_kept


def load_hub_dates_for_candidates(file_path):
    dates_by_hub = {}
    metadata_by_hub = {}
    rows_read = 0

    with file_path.open("r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            rows_read += 1
            station_id = row["station_id"]

            if station_id not in dates_by_hub:
                dates_by_hub[station_id] = set()
                metadata_by_hub[station_id] = {
                    "station_name": row["station_name"],
                    "elevation": row["elevation"],
                }

            dates_by_hub[station_id].add(row["date"])

    return dates_by_hub, metadata_by_hub, rows_read


def load_daily_tavg_by_station(file_path, station_ids):
    station_id_set = set(station_ids)
    daily_by_station = {station_id: {} for station_id in station_ids}
    names_by_station = {}
    rows_read = 0
    rows_kept = 0

    with file_path.open("r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            rows_read += 1
            station_id = row["station_id"]

            if station_id not in station_id_set:
                continue

            rows_kept += 1
            names_by_station[station_id] = row["station_name"]
            daily_by_station[station_id][row["date"]] = calculate_tavg(row)

    return daily_by_station, names_by_station, rows_read, rows_kept


def print_coverage_report(target_station_id, hub_ids, target_daily, hub_daily, nearest_hubs, hub_names):
    target_dates = set(target_daily[target_station_id].keys())
    running_shared_dates = set(target_dates)
    nearest_hub_by_id = {
        hub["station_id"]: hub
        for hub in nearest_hubs
    }

    print()
    print("Coverage report")
    print("---------------")
    print(f"Target observed days: {len(target_dates)}")
    print()
    print(
        f"{'Rank':<5} {'Station ID':<12} {'Distance':>10} {'Hub days':>9} "
        f"{'Overlap':>9} {'Overlap %':>10} {'Elev diff':>11} {'All-hub shared':>15}  Station name"
    )

    for index, hub_id in enumerate(hub_ids, start=1):
        hub_dates = set(hub_daily[hub_id].keys())
        overlap_with_target = target_dates.intersection(hub_dates)
        running_shared_dates = running_shared_dates.intersection(hub_dates)
        overlap_percent = 0.0

        if target_dates:
            overlap_percent = len(overlap_with_target) / len(target_dates) * 100

        hub = nearest_hub_by_id[hub_id]

        print(
            f"{index:<5} {hub_id:<12} "
            f"{hub['distance_km']:>8.2f}km "
            f"{len(hub_dates):>9} "
            f"{len(overlap_with_target):>9} "
            f"{overlap_percent:>9.1f}% "
            f"{hub.get('elevation_difference_m', 0.0):>9.1f}m "
            f"{len(running_shared_dates):>15}  "
            f"{hub_names.get(hub_id, 'Unknown station')}"
        )


def write_training_table(output_file, rows, hub_count):
    fieldnames = [
        "date",
        "target_station_id",
        "target_tavg",
    ]

    for index in range(1, hub_count + 1):
        fieldnames.append(f"hub_{index}_station_id")
        fieldnames.append(f"hub_{index}_tavg")

    write_csv_rows(output_file, rows, fieldnames)


def print_training_table_preview(rows, count=5):
    print()
    print("Shared-date training rows preview")
    print("---------------------------------")

    for row in rows[:count]:
        print(row)


def main():
    target_station_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET_STATION_ID
    hub_count = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_HUB_COUNT

    targets = read_csv_rows(TARGET_CANDIDATE_FILE)
    hubs = read_csv_rows(HUB_CANDIDATE_FILE)
    target_station = find_station_by_id(targets, target_station_id)

    if target_station is None:
        print(f"Could not find target station: {target_station_id}")
        print("Try a target station ID from target_station_candidates.csv.")
        return

    print("Step 5: Build shared-date training table")
    print("========================================")
    print(f"Target station: {target_station_id}")
    print(f"Hub count: {hub_count}")
    print(f"Minimum target overlap: {MIN_OVERLAP_PERCENT:.1f}%")
    print(f"Minimum overlap days: {MIN_OVERLAP_DAYS}")
    print(f"Maximum elevation difference: {MAX_ELEVATION_DIFFERENCE_M:.0f} m")

    target_dates, target_metadata, target_date_rows_read, target_date_rows_kept = load_target_daily_dates(
        TARGET_DAILY_FILE,
        target_station_id,
    )
    hub_dates_by_station, hub_metadata_for_selection, hub_date_rows_read = load_hub_dates_for_candidates(
        HUB_DAILY_FILE
    )
    nearest_hubs, eligible_hubs, rejected_hubs = find_training_eligible_hubs(
        target_station,
        hubs,
        target_dates,
        target_metadata,
        hub_dates_by_station,
        hub_metadata_for_selection,
        hub_count,
        MIN_OVERLAP_PERCENT,
        MIN_OVERLAP_DAYS,
        MAX_ELEVATION_DIFFERENCE_M,
    )
    hub_ids = [hub["station_id"] for hub in nearest_hubs]

    print()
    print("Coverage pre-scan:")
    print(f"Target date rows scanned: {target_date_rows_read}")
    print(f"Target observed days: {len(target_dates)}")
    print(f"Hub date rows scanned: {hub_date_rows_read}")
    print(f"Eligible hubs: {len(eligible_hubs)}")
    print(f"Rejected hubs: {len(rejected_hubs)}")

    print()
    print("Selected training hubs:")
    for index, hub in enumerate(nearest_hubs, start=1):
        print(
            f"{index}. {hub['station_id']} | "
            f"{hub['distance_km']:.2f} km | "
            f"{hub['elevation_difference_m']:.1f} m elev diff | "
            f"{hub['overlap_days']} days | "
            f"{hub['overlap_percent']:.1f}% overlap | "
            f"{hub['usable_period']} | "
            f"{hub['station_name']}"
        )

    target_daily, target_names, target_rows_read, target_rows_kept = load_daily_tavg_by_station(
        TARGET_DAILY_FILE,
        [target_station_id],
    )
    hub_daily, hub_names, hub_rows_read, hub_rows_kept = load_daily_tavg_by_station(
        HUB_DAILY_FILE,
        hub_ids,
    )

    print_coverage_report(
        target_station_id,
        hub_ids,
        target_daily,
        hub_daily,
        nearest_hubs,
        hub_names,
    )

    rows = build_shared_date_rows(
        target_station_id,
        hub_ids,
        target_daily,
        hub_daily,
    )

    output_file = TRAINING_TABLE_DIR / f"{target_station_id}_{hub_count}_hubs.csv"
    write_training_table(output_file, rows, hub_count)

    print()
    print("Daily rows scanned/kept:")
    print(f"Target file: {target_rows_read} scanned, {target_rows_kept} kept")
    print(f"Hub file: {hub_rows_read} scanned, {hub_rows_kept} kept")
    print()
    print(f"Shared dates found: {len(rows)}")
    print(f"Output file: {output_file}")

    print_training_table_preview(rows)


if __name__ == "__main__":
    main()
