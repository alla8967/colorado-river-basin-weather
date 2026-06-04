import csv
import sys

import config
from common.csv_utils import read_csv_rows
from common.geo_utils import calculate_distance_km
from common.number_utils import to_float

TARGET_FILE = config.TARGET_CANDIDATE_FILE
HUB_FILE = config.HUB_CANDIDATE_FILE
TARGET_DAILY_FILE = config.TARGET_DAILY_FILE
HUB_DAILY_FILE = config.HUB_DAILY_FILE

def find_station_by_id(stations, station_id):
    for station in stations:
        if station["station_id"] == station_id:
            return station

    return None

def summarize_daily_temperature_file(file_path, sample_station_id):
    total_rows = 0
    sample_rows = []
    station_metadata = {}

    with file_path.open("r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            total_rows += 1
            station_id = row["station_id"]

            if station_id not in station_metadata:
                station_metadata[station_id] = {
                    "station_name": row["station_name"],
                    "elevation": row["elevation"],
                }

            if station_id == sample_station_id and len(sample_rows) < 5:
                sample_rows.append(row)

    return total_rows, sample_rows, station_metadata

def print_daily_samples(rows):
    for row in rows:
        tmax = to_float(row["tmax"])
        tmin = to_float(row["tmin"])
        tavg = (tmax + tmin) / 2

        print(
            f"{row['station_id']} | {row['station_name']} | {row['date']} | "
            f"TMAX {tmax:.2f} | TMIN {tmin:.2f} | TAVG {tavg:.2f}"
        )

def print_nearest_hubs(target_station, hubs, hub_metadata, count=10):
    target_latitude = to_float(target_station["latitude"])
    target_longitude = to_float(target_station["longitude"])

    ranked_hubs = []

    for hub in hubs:
        hub_latitude = to_float(hub["latitude"])
        hub_longitude = to_float(hub["longitude"])
        metadata = hub_metadata.get(hub["station_id"], {})

        ranked_hubs.append({
            "station_id": hub["station_id"],
            "station_name": metadata.get("station_name", "Unknown station"),
            "distance_km": calculate_distance_km(
                target_latitude,
                target_longitude,
                hub_latitude,
                hub_longitude,
            ),
            "latitude": hub_latitude,
            "longitude": hub_longitude,
            "elevation": metadata.get("elevation", "N/A"),
            "usable_years": hub["usable_temp_years"],
            "usable_period": f"{hub['usable_temp_start']}-{hub['usable_temp_end']}",
        })

    ranked_hubs.sort(key=lambda hub: hub["distance_km"])

    print()
    print("Nearest hub stations for selected target")
    print("----------------------------------------")
    print(f"Target: {target_station['station_id']}")
    print(f"Target coordinates: {target_latitude:.4f}, {target_longitude:.4f}")
    print()
    print(f"{'Rank':<5} {'Station ID':<12} {'Distance km':>12} {'Record':>12}  Station name")

    for index, hub in enumerate(ranked_hubs[:count], start=1):
        print(
            f"{index:<5} {hub['station_id']:<12} "
            f"{hub['distance_km']:>12.2f} {hub['usable_period']:>12}  "
            f"{hub['station_name']}"
        )

def main():
    targets = read_csv_rows(TARGET_FILE)
    hubs = read_csv_rows(HUB_FILE)
    selected_target_station_id = sys.argv[1] if len(sys.argv) > 1 else "USC00052223"
    selected_target = find_station_by_id(targets, selected_target_station_id)

    if selected_target is None:
        print(f"Target station {selected_target_station_id} was not found. Using the first target station instead.")
        selected_target = targets[0]

    print("Target stations:", len(targets))
    print("Hub stations:", len(hubs))

    first_target_station_id = selected_target["station_id"]
    first_hub_station_id = hubs[0]["station_id"]

    target_daily_count, target_daily_sample, target_metadata = summarize_daily_temperature_file(
        TARGET_DAILY_FILE,
        first_target_station_id
    )
    hub_daily_count, hub_daily_sample, hub_metadata = summarize_daily_temperature_file(
        HUB_DAILY_FILE,
        first_hub_station_id
    )

    print()
    print("Target daily temperature rows:", target_daily_count)
    print("Sample daily temperatures for target station", first_target_station_id)
    print_daily_samples(target_daily_sample)

    print()
    print("Hub daily temperature rows:", hub_daily_count)
    print("Sample daily temperatures for hub station", first_hub_station_id)
    print_daily_samples(hub_daily_sample)

    print_nearest_hubs(selected_target, hubs, hub_metadata, count=10)


if __name__ == "__main__":
    main()
