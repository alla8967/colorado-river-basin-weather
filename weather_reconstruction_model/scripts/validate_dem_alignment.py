"""Validate DEM tile alignment and sampled terrain metadata.

Use it when rebuilding terrain products to catch coordinate or raster mismatch issues."""

from pathlib import Path
import argparse
import csv
import math
import re
import sys

import config
from common.csv_utils import read_csv_rows, write_csv_rows
from common.number_utils import to_optional_float as to_float


PROJECT_DIR = config.PROJECT_DIR
RAW_DEM_DIR = PROJECT_DIR / "Raw_DEM"
TARGET_CANDIDATE_FILE = config.TARGET_CANDIDATE_FILE
HUB_CANDIDATE_FILE = config.HUB_CANDIDATE_FILE
TARGET_DAILY_FILE = config.TARGET_DAILY_FILE
HUB_DAILY_FILE = config.HUB_DAILY_FILE
REPORT_DIR = PROJECT_DIR / "terrain_data" / "processed"
DEFAULT_OUTPUT_FILE = REPORT_DIR / "dem_alignment_validation.csv"
TILE_NAME_PATTERN = re.compile(r"_n(\d+)w(\d+)_", re.IGNORECASE)
NO_DATA_THRESHOLD = -100000
EARTH_RADIUS_M = 6_371_000.0


try:
    import numpy as np
    from PIL import Image
except ModuleNotFoundError as error:
    print()
    print("Missing DEM validation dependency.")
    print("----------------------------------")
    print("This script needs Pillow and NumPy to read GeoTIFF DEM tiles.")
    print()
    print("Install the project dependencies and rerun this script with the project Python environment.")
    print("For example: .venv/bin/python weather_reconstruction_model/scripts/validate_dem_alignment.py")
    print()
    print(f"Original error: {error}")
    sys.exit(1)


class DemTile:
    def __init__(self, path):
        self.path = path
        self.image = Image.open(path)
        self.width, self.height = self.image.size
        self.pixel_scale = self.image.tag_v2[33550]
        self.tiepoint = self.image.tag_v2[33922]
        self.no_data_value = self.image.tag_v2.get(42113, None)
        self.array = None
        self.bounds = self.calculate_bounds()

    def calculate_bounds(self):
        scale_x, scale_y, _ = self.pixel_scale
        tie_col, tie_row, _, tie_x, tie_y, _ = self.tiepoint
        min_longitude = tie_x - (tie_col * scale_x)
        max_latitude = tie_y + (tie_row * scale_y)
        max_longitude = min_longitude + ((self.width - 1) * scale_x)
        min_latitude = max_latitude - ((self.height - 1) * scale_y)

        return {
            "min_latitude": min(min_latitude, max_latitude),
            "max_latitude": max(min_latitude, max_latitude),
            "min_longitude": min(min_longitude, max_longitude),
            "max_longitude": max(min_longitude, max_longitude),
        }

    def load_array(self):
        if self.array is None:
            self.array = np.array(self.image, dtype=float)

            if self.no_data_value is not None:
                self.array[self.array == float(self.no_data_value)] = np.nan

            self.array[self.array <= NO_DATA_THRESHOLD] = np.nan

        return self.array

    def row_col_for_coordinate(self, latitude, longitude):
        scale_x, scale_y, _ = self.pixel_scale
        tie_col, tie_row, _, tie_x, tie_y, _ = self.tiepoint
        column_float = tie_col + ((longitude - tie_x) / scale_x)
        row_float = tie_row + ((tie_y - latitude) / scale_y)
        column = int(round(column_float))
        row = int(round(row_float))

        return {
            "row": row,
            "column": column,
            "row_float": row_float,
            "column_float": column_float,
            "inside_pixel_grid": (
                row >= 0
                and row < self.height
                and column >= 0
                and column < self.width
            ),
        }

    def coordinate_for_row_col(self, row, column):
        scale_x, scale_y, _ = self.pixel_scale
        tie_col, tie_row, _, tie_x, tie_y, _ = self.tiepoint
        longitude = tie_x + ((column - tie_col) * scale_x)
        latitude = tie_y - ((row - tie_row) * scale_y)

        return latitude, longitude

    def value_at_row_col(self, row, column):
        if row < 0 or row >= self.height or column < 0 or column >= self.width:
            return None

        value = self.load_array()[row, column]

        if np.isnan(value):
            return None

        return float(value)


def tile_key_for_coordinate(latitude, longitude):
    # USGS 1-degree DEM filenames use the tile's north edge.
    # Example: n34w112 covers roughly 33-34 N and 112-111 W.
    north_latitude = math.ceil(latitude)
    west_longitude = abs(math.floor(longitude))
    return f"n{north_latitude:02d}w{west_longitude:03d}"


def tile_key_from_path(path):
    match = TILE_NAME_PATTERN.search(path.name)

    if match is None:
        return None

    return f"n{int(match.group(1)):02d}w{int(match.group(2)):03d}"


def nominal_bounds_for_tile_key(tile_key):
    match = re.match(r"n(\d+)w(\d+)", tile_key)

    if match is None:
        return None

    north_latitude = int(match.group(1))
    west_longitude = -int(match.group(2))

    return {
        "min_latitude": north_latitude - 1,
        "max_latitude": north_latitude,
        "min_longitude": west_longitude,
        "max_longitude": west_longitude + 1,
    }


def build_dem_tile_index(raw_dem_dir):
    tile_index = {}

    for path in sorted(raw_dem_dir.glob("*.tif")):
        tile_key = tile_key_from_path(path)

        if tile_key is not None:
            tile_index[tile_key] = path

    return tile_index


def load_station_metadata(file_paths):
    metadata = {}

    for file_path in file_paths:
        if not file_path.exists():
            continue

        with file_path.open("r", newline="") as file:
            reader = csv.DictReader(file)

            for row in reader:
                station_id = row["station_id"]

                if station_id in metadata:
                    continue

                metadata[station_id] = {
                    "station_name": row.get("station_name", ""),
                    "noaa_elevation_m": row.get("elevation", ""),
                }

    return metadata


def load_station_candidates(target_file, hub_file):
    stations = {}

    for role, file_path in [("target", target_file), ("hub", hub_file)]:
        for row in read_csv_rows(file_path):
            station_id = row["station_id"]

            if station_id not in stations:
                stations[station_id] = {
                    "station_id": station_id,
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "roles": set(),
                }

            stations[station_id]["roles"].add(role)

    return stations


def distance_meters(lat1, lon1, lat2, lon2):
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )

    return EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


def bounds_difference_m(tile_bounds, nominal_bounds):
    checks = [
        ("min_latitude", "latitude"),
        ("max_latitude", "latitude"),
        ("min_longitude", "longitude"),
        ("max_longitude", "longitude"),
    ]
    differences = []
    center_latitude = (
        nominal_bounds["min_latitude"] + nominal_bounds["max_latitude"]
    ) / 2

    for key, coordinate_type in checks:
        difference_degrees = abs(tile_bounds[key] - nominal_bounds[key])

        if coordinate_type == "latitude":
            differences.append(difference_degrees * 111_320.0)
        else:
            differences.append(difference_degrees * 111_320.0 * math.cos(math.radians(center_latitude)))

    return max(differences)


def validate_station(station, metadata, tile_index, loaded_tiles):
    station_id = station["station_id"]
    latitude = to_float(station["latitude"])
    longitude = to_float(station["longitude"])
    noaa_elevation = to_float(metadata.get(station_id, {}).get("noaa_elevation_m", ""))

    row = {
        "station_id": station_id,
        "station_role": "+".join(sorted(station["roles"])),
        "station_name": metadata.get(station_id, {}).get("station_name", ""),
        "latitude": station["latitude"],
        "longitude": station["longitude"],
        "noaa_elevation_m": metadata.get(station_id, {}).get("noaa_elevation_m", ""),
        "expected_tile": "",
        "tile_file": "",
        "tile_width": "",
        "tile_height": "",
        "tile_min_latitude": "",
        "tile_max_latitude": "",
        "tile_min_longitude": "",
        "tile_max_longitude": "",
        "nominal_bounds_difference_m": "",
        "station_inside_tile_bounds": "",
        "pixel_row": "",
        "pixel_column": "",
        "pixel_row_float": "",
        "pixel_column_float": "",
        "inside_pixel_grid": "",
        "roundtrip_latitude": "",
        "roundtrip_longitude": "",
        "roundtrip_error_m": "",
        "dem_elevation_m": "",
        "dem_minus_noaa_elevation_m": "",
        "alignment_status": "missing_coordinate",
    }

    if latitude is None or longitude is None:
        return row

    expected_tile = tile_key_for_coordinate(latitude, longitude)
    tile_path = tile_index.get(expected_tile)
    row["expected_tile"] = expected_tile

    if tile_path is None:
        row["alignment_status"] = "missing_dem_tile"
        return row

    if expected_tile not in loaded_tiles:
        loaded_tiles.clear()
        loaded_tiles[expected_tile] = DemTile(tile_path)

    tile = loaded_tiles[expected_tile]
    nominal_bounds = nominal_bounds_for_tile_key(expected_tile)
    tile_bounds = tile.bounds
    pixel = tile.row_col_for_coordinate(latitude, longitude)
    roundtrip_latitude, roundtrip_longitude = tile.coordinate_for_row_col(
        pixel["row"],
        pixel["column"],
    )
    roundtrip_error = distance_meters(
        latitude,
        longitude,
        roundtrip_latitude,
        roundtrip_longitude,
    )
    dem_elevation = tile.value_at_row_col(pixel["row"], pixel["column"])
    station_inside_tile_bounds = (
        latitude >= tile_bounds["min_latitude"]
        and latitude <= tile_bounds["max_latitude"]
        and longitude >= tile_bounds["min_longitude"]
        and longitude <= tile_bounds["max_longitude"]
    )
    nominal_bounds_difference = bounds_difference_m(tile_bounds, nominal_bounds)

    row.update({
        "tile_file": tile.path.name,
        "tile_width": tile.width,
        "tile_height": tile.height,
        "tile_min_latitude": f"{tile_bounds['min_latitude']:.8f}",
        "tile_max_latitude": f"{tile_bounds['max_latitude']:.8f}",
        "tile_min_longitude": f"{tile_bounds['min_longitude']:.8f}",
        "tile_max_longitude": f"{tile_bounds['max_longitude']:.8f}",
        "nominal_bounds_difference_m": f"{nominal_bounds_difference:.2f}",
        "station_inside_tile_bounds": int(station_inside_tile_bounds),
        "pixel_row": pixel["row"],
        "pixel_column": pixel["column"],
        "pixel_row_float": f"{pixel['row_float']:.3f}",
        "pixel_column_float": f"{pixel['column_float']:.3f}",
        "inside_pixel_grid": int(pixel["inside_pixel_grid"]),
        "roundtrip_latitude": f"{roundtrip_latitude:.8f}",
        "roundtrip_longitude": f"{roundtrip_longitude:.8f}",
        "roundtrip_error_m": f"{roundtrip_error:.3f}",
    })

    if dem_elevation is not None:
        row["dem_elevation_m"] = f"{dem_elevation:.2f}"

        if noaa_elevation is not None:
            row["dem_minus_noaa_elevation_m"] = f"{dem_elevation - noaa_elevation:.2f}"

    if not station_inside_tile_bounds:
        row["alignment_status"] = "station_outside_tile_bounds"
    elif not pixel["inside_pixel_grid"]:
        row["alignment_status"] = "outside_pixel_grid"
    elif roundtrip_error > 30:
        row["alignment_status"] = "large_roundtrip_error"
    elif dem_elevation is None:
        row["alignment_status"] = "missing_dem_value"
    else:
        row["alignment_status"] = "ok"

    return row


def write_rows(output_file, rows):
    fieldnames = [
        "station_id",
        "station_role",
        "station_name",
        "latitude",
        "longitude",
        "noaa_elevation_m",
        "expected_tile",
        "tile_file",
        "tile_width",
        "tile_height",
        "tile_min_latitude",
        "tile_max_latitude",
        "tile_min_longitude",
        "tile_max_longitude",
        "nominal_bounds_difference_m",
        "station_inside_tile_bounds",
        "pixel_row",
        "pixel_column",
        "pixel_row_float",
        "pixel_column_float",
        "inside_pixel_grid",
        "roundtrip_latitude",
        "roundtrip_longitude",
        "roundtrip_error_m",
        "dem_elevation_m",
        "dem_minus_noaa_elevation_m",
        "alignment_status",
    ]

    write_csv_rows(output_file, rows, fieldnames)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Validate DEM tile selection, bounds, and coordinate-to-pixel alignment for station coordinates."
    )
    parser.add_argument(
        "--raw-dem-dir",
        type=Path,
        default=RAW_DEM_DIR,
        help="Folder containing DEM GeoTIFF tiles.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="Output validation CSV.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only validate the first N stations. Useful for testing.",
    )
    return parser.parse_args()


def main():
    arguments = parse_arguments()

    if not arguments.raw_dem_dir.exists():
        raise FileNotFoundError(f"DEM folder was not found: {arguments.raw_dem_dir}")

    tile_index = build_dem_tile_index(arguments.raw_dem_dir)

    if not tile_index:
        raise FileNotFoundError(f"No DEM .tif files were found in: {arguments.raw_dem_dir}")

    stations = load_station_candidates(TARGET_CANDIDATE_FILE, HUB_CANDIDATE_FILE)
    metadata = load_station_metadata([TARGET_DAILY_FILE, HUB_DAILY_FILE])
    station_list = sorted(
        stations.values(),
        key=lambda station: (
            tile_key_for_coordinate(
                to_float(station["latitude"]) or 0.0,
                to_float(station["longitude"]) or 0.0,
            ),
            station["station_id"],
        ),
    )

    if arguments.limit is not None:
        station_list = station_list[:arguments.limit]

    print("Validate DEM alignment")
    print("======================")
    print(f"DEM tiles indexed: {len(tile_index)}")
    print(f"Stations to validate: {len(station_list)}")
    print(f"Output file: {arguments.output}")

    loaded_tiles = {}
    rows = []

    for index, station in enumerate(station_list, start=1):
        rows.append(validate_station(station, metadata, tile_index, loaded_tiles))

        if index % 100 == 0 or index == len(station_list):
            ok_count = sum(row["alignment_status"] == "ok" for row in rows)
            print(f"Validated {index}/{len(station_list)} stations ({ok_count} ok)")

    write_rows(arguments.output, rows)

    status_counts = {}

    for row in rows:
        status = row["alignment_status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    print()
    print("DEM alignment validation complete")
    print("---------------------------------")

    for status, count in sorted(status_counts.items()):
        print(f"{status}: {count}")

    print(f"Output file: {arguments.output}")


if __name__ == "__main__":
    main()
