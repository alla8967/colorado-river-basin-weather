"""Filter NOAA GHCN-Daily yearly bulk files into app-ready station CSVs.

This prepares the target and hub daily temperature inputs consumed by the C++ proxy engine and FastAPI app."""

import csv
import gzip
from pathlib import Path

# This script filters NOAA GHCN-Daily yearly bulk files into app-ready CSVs.
#
# Input:
#   - hub_station_candidates.csv
#   - target_station_candidates.csv
#   - ghcnd-stations.txt
#   - NOAA_GHCN_ByYear/*.csv.gz, such as 2025.csv.gz
#
# Output:
#   - hub_daily_app_ready.csv
#   - target_daily_app_ready.csv
#
# Output columns:
#   station_id,station_name,latitude,longitude,elevation,date,tmax,tmin
#
# Notes:
#   - GHCN-Daily TMAX/TMIN values are stored in tenths of degrees Celsius.
#   - This script converts them to Fahrenheit.
#   - ghcnd-stations.txt supplies elevation metadata.

BASE_DIR = Path(__file__).resolve().parent
GHCN_FOLDER = BASE_DIR / "NOAA_GHCN_ByYear"

STATIONS_METADATA_FILE = BASE_DIR / "ghcnd-stations.txt"
HUB_CANDIDATE_FILE = BASE_DIR / "hub_station_candidates.csv"
TARGET_CANDIDATE_FILE = BASE_DIR / "target_station_candidates.csv"

HUB_OUTPUT_FILE = BASE_DIR / "hub_daily_app_ready.csv"
TARGET_OUTPUT_FILE = BASE_DIR / "target_daily_app_ready.csv"

START_YEAR = 2016
END_YEAR = 2026
KEEP_ELEMENTS = {"TMAX", "TMIN"}


def celsius_tenths_to_fahrenheit(value_text: str) -> float:
    celsius = int(value_text) / 10.0
    return (celsius * 9.0 / 5.0) + 32.0


def format_noaa_date(date_text: str) -> str:
    # NOAA date format is YYYYMMDD. Convert to YYYY-MM-DD.
    return f"{date_text[0:4]}-{date_text[4:6]}-{date_text[6:8]}"


def get_available_year_files() -> list[Path]:
    year_files = []

    if not GHCN_FOLDER.exists():
        return year_files

    for file_path in GHCN_FOLDER.glob("*.csv.gz"):
        year_text = file_path.stem.replace(".csv", "")

        try:
            year = int(year_text)
        except ValueError:
            continue

        if START_YEAR <= year <= END_YEAR:
            year_files.append(file_path)

    year_files.sort()
    return year_files


def load_ghcnd_station_metadata(stations_file: Path) -> dict[str, dict[str, str]]:
    metadata_by_station_id = {}

    if not stations_file.exists():
        print(f"WARNING: Could not find station metadata file: {stations_file}")
        print("Elevation will be left blank unless it exists in the candidate CSVs.")
        return metadata_by_station_id

    with stations_file.open("r", encoding="utf-8", errors="replace") as file:
        for line in file:
            if len(line) < 37:
                continue

            station_id = line[0:11].strip()
            latitude = line[12:20].strip()
            longitude = line[21:30].strip()
            elevation = line[31:37].strip()
            station_name = line[41:71].strip() if len(line) >= 71 else ""

            if not station_id:
                continue

            metadata_by_station_id[station_id] = {
                "latitude": latitude,
                "longitude": longitude,
                "elevation": elevation,
                "station_name": station_name,
            }

    print(f"Loaded station metadata records: {len(metadata_by_station_id)}")
    return metadata_by_station_id


def load_candidate_station_metadata(
    candidate_file: Path,
    ghcnd_metadata: dict[str, dict[str, str]]
) -> dict[str, dict[str, str]]:
    metadata_by_station_id = {}

    if not candidate_file.exists():
        raise FileNotFoundError(f"Could not find candidate file: {candidate_file}")

    with candidate_file.open("r", newline="") as file:
        reader = csv.DictReader(file)

        required_columns = {"station_id", "latitude", "longitude"}
        missing_columns = required_columns - set(reader.fieldnames or [])

        if missing_columns:
            raise ValueError(
                f"Candidate file {candidate_file} is missing columns: {sorted(missing_columns)}. "
                f"Found columns: {reader.fieldnames}"
            )

        for row in reader:
            station_id = row["station_id"].strip()

            if not station_id:
                continue

            ghcnd_row = ghcnd_metadata.get(station_id, {})

            station_name = row.get("station_name", "").strip() or ghcnd_row.get("station_name", "") or station_id
            latitude = row.get("latitude", "").strip() or ghcnd_row.get("latitude", "")
            longitude = row.get("longitude", "").strip() or ghcnd_row.get("longitude", "")
            elevation = row.get("elevation", "").strip() or ghcnd_row.get("elevation", "")

            metadata_by_station_id[station_id] = {
                "station_name": station_name,
                "latitude": latitude,
                "longitude": longitude,
                "elevation": elevation,
            }

    return metadata_by_station_id


def collect_daily_temperature_rows(
    station_metadata: dict[str, dict[str, str]],
    label: str
) -> dict[tuple[str, str], dict[str, float]]:
    station_ids = set(station_metadata.keys())
    daily_values = {}
    year_files = get_available_year_files()

    print(f"\nCollecting {label} daily temperature data")
    print("----------------------------------------")
    print(f"Station IDs loaded: {len(station_ids)}")
    print(f"Year files found: {len(year_files)}")

    if not year_files:
        print("No matching .csv.gz year files were found. Nothing to filter.")
        return daily_values

    for input_file in year_files:
        year_rows_kept = 0
        print(f"Reading {input_file.name}...")

        with gzip.open(input_file, "rt", newline="") as input_data:
            reader = csv.reader(input_data)

            for row in reader:
                if len(row) < 4:
                    continue

                station_id = row[0]
                date_text = row[1]
                element = row[2]
                value_text = row[3]

                if station_id not in station_ids:
                    continue

                if element not in KEEP_ELEMENTS:
                    continue

                try:
                    temperature_f = celsius_tenths_to_fahrenheit(value_text)
                except ValueError:
                    continue

                formatted_date = format_noaa_date(date_text)
                key = (station_id, formatted_date)

                if key not in daily_values:
                    daily_values[key] = {}

                if element == "TMAX":
                    daily_values[key]["tmax"] = temperature_f
                elif element == "TMIN":
                    daily_values[key]["tmin"] = temperature_f

                year_rows_kept += 1

        print(f"  TMAX/TMIN rows kept from {input_file.name}: {year_rows_kept}")
        print(f"  Station-date pairs collected so far: {len(daily_values)}")

    return daily_values


def write_app_ready_csv(
    output_file: Path,
    station_metadata: dict[str, dict[str, str]],
    daily_values: dict[tuple[str, str], dict[str, float]]
) -> int:
    rows_written = 0
    rows_skipped_missing_pair = 0

    with output_file.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            "station_id",
            "station_name",
            "latitude",
            "longitude",
            "elevation",
            "date",
            "tmax",
            "tmin",
        ])

        for key in sorted(daily_values.keys()):
            station_id, date = key
            values = daily_values[key]

            if "tmax" not in values or "tmin" not in values:
                rows_skipped_missing_pair += 1
                continue

            metadata = station_metadata[station_id]

            writer.writerow([
                station_id,
                metadata["station_name"],
                metadata["latitude"],
                metadata["longitude"],
                metadata["elevation"],
                date,
                f"{values['tmax']:.2f}",
                f"{values['tmin']:.2f}",
            ])

            rows_written += 1

    print(f"\nWrote app-ready file: {output_file.name}")
    print(f"Rows written: {rows_written}")
    print(f"Rows skipped because TMAX or TMIN was missing: {rows_skipped_missing_pair}")

    return rows_written


def build_app_ready_file(
    candidate_file: Path,
    output_file: Path,
    label: str,
    ghcnd_metadata: dict[str, dict[str, str]]
) -> int:
    station_metadata = load_candidate_station_metadata(candidate_file, ghcnd_metadata)
    daily_values = collect_daily_temperature_rows(station_metadata, label)
    return write_app_ready_csv(output_file, station_metadata, daily_values)


def main():
    print("GHCN DAILY APP-READY CSV BUILDER")
    print("========================================")
    print(f"Base folder: {BASE_DIR}")
    print(f"GHCN yearly folder: {GHCN_FOLDER}")
    print(f"Year range: {START_YEAR}-{END_YEAR}")
    print(f"Elements kept: {', '.join(sorted(KEEP_ELEMENTS))}")

    if not GHCN_FOLDER.exists():
        GHCN_FOLDER.mkdir(parents=True, exist_ok=True)
        print("\nCreated NOAA_GHCN_ByYear folder.")
        print("Download yearly files like 2025.csv.gz into this folder, then run this script again.")
        print(f"Folder created at: {GHCN_FOLDER}")
        return

    ghcnd_metadata = load_ghcnd_station_metadata(STATIONS_METADATA_FILE)

    hub_rows = build_app_ready_file(
        candidate_file=HUB_CANDIDATE_FILE,
        output_file=HUB_OUTPUT_FILE,
        label="hub",
        ghcnd_metadata=ghcnd_metadata
    )

    target_rows = build_app_ready_file(
        candidate_file=TARGET_CANDIDATE_FILE,
        output_file=TARGET_OUTPUT_FILE,
        label="target",
        ghcnd_metadata=ghcnd_metadata
    )

    print("\nSUMMARY")
    print("========================================")
    print(f"Hub rows written: {hub_rows}")
    print(f"Target rows written: {target_rows}")
    print(f"Hub output: {HUB_OUTPUT_FILE}")
    print(f"Target output: {TARGET_OUTPUT_FILE}")
    print("\nDone.")


if __name__ == "__main__":
    main()