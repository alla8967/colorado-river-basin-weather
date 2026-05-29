from pathlib import Path
import argparse
import csv
import math
import re
import sys
from multiprocessing import Pool

import config
from common.csv_utils import read_csv_rows, write_csv_rows
from common.number_utils import to_optional_float as to_float


PROJECT_DIR = config.PROJECT_DIR
RAW_DEM_DIR = PROJECT_DIR / "Raw_DEM"
TERRAIN_OUTPUT_DIR = PROJECT_DIR / "ml_reconstruction/terrain_data" / "processed"
DEFAULT_OUTPUT_FILE = TERRAIN_OUTPUT_DIR / "station_terrain_features.csv"
TARGET_CANDIDATE_FILE = config.TARGET_CANDIDATE_FILE
HUB_CANDIDATE_FILE = config.HUB_CANDIDATE_FILE
TARGET_DAILY_FILE = config.TARGET_DAILY_FILE
HUB_DAILY_FILE = config.HUB_DAILY_FILE
TILE_NAME_PATTERN = re.compile(r"_n(\d+)w(\d+)_", re.IGNORECASE)
NO_DATA_THRESHOLD = -100000
DEFAULT_MULTI_SCALE_RADII = [3, 10, 33, 100]


try:
    import numpy as np
    from PIL import Image
except ModuleNotFoundError as error:
    print()
    print("Missing terrain-reading dependency.")
    print("-----------------------------------")
    print("This script needs Pillow and NumPy to read GeoTIFF DEM tiles.")
    print()
    print("Install the project dependencies and rerun this script with the project Python environment.")
    print("For example: .venv/bin/python ml_reconstruction/weather_reconstruction_model/scripts/build_station_terrain_features.py")
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

        column = int(round(tie_col + ((longitude - tie_x) / scale_x)))
        row = int(round(tie_row + ((tie_y - latitude) / scale_y)))

        if row < 0 or row >= self.height or column < 0 or column >= self.width:
            return None

        return row, column

    def value_at(self, latitude, longitude):
        row_col = self.row_col_for_coordinate(latitude, longitude)

        if row_col is None:
            return None

        row, column = row_col
        array = self.load_array()
        value = array[row, column]

        if np.isnan(value):
            return None

        return float(value)

    def window_at(self, latitude, longitude, radius_cells):
        row_col = self.row_col_for_coordinate(latitude, longitude)

        if row_col is None:
            return None

        row, column = row_col
        array = self.load_array()
        row_min = max(0, row - radius_cells)
        row_max = min(self.height, row + radius_cells + 1)
        column_min = max(0, column - radius_cells)
        column_max = min(self.width, column + radius_cells + 1)

        return array[row_min:row_max, column_min:column_max]


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


def calculate_cell_sizes_m(latitude, tile):
    scale_x_degrees, scale_y_degrees, _ = tile.pixel_scale
    meters_per_degree_latitude = 111_320.0
    meters_per_degree_longitude = meters_per_degree_latitude * math.cos(math.radians(latitude))

    return (
        abs(scale_x_degrees) * meters_per_degree_longitude,
        abs(scale_y_degrees) * meters_per_degree_latitude,
    )


def calculate_slope_aspect(tile, latitude, longitude, radius_cells):
    window = tile.window_at(latitude, longitude, radius_cells)

    if window is None or window.size == 0 or np.isnan(window).all():
        return None

    center_row = window.shape[0] // 2
    center_column = window.shape[1] // 2

    if window.shape[0] < 3 or window.shape[1] < 3:
        return None

    filled_window = np.array(window, dtype=float)

    if np.isnan(filled_window).any():
        mean_value = np.nanmean(filled_window)
        filled_window[np.isnan(filled_window)] = mean_value

    cell_width_m, cell_height_m = calculate_cell_sizes_m(latitude, tile)
    north_gradient, east_gradient = np.gradient(
        filled_window,
        cell_height_m,
        cell_width_m,
    )
    dz_dn = north_gradient[center_row, center_column]
    dz_de = east_gradient[center_row, center_column]
    slope_radians = math.atan(math.sqrt(dz_de ** 2 + dz_dn ** 2))
    slope_degrees = math.degrees(slope_radians)

    # Aspect is the compass direction of steepest descent.
    aspect_degrees = (math.degrees(math.atan2(-dz_de, -dz_dn)) + 360) % 360

    return {
        "slope_degrees": slope_degrees,
        "aspect_degrees": aspect_degrees,
        "aspect_sin": math.sin(math.radians(aspect_degrees)),
        "aspect_cos": math.cos(math.radians(aspect_degrees)),
    }


def calculate_window_plane_slope_aspect(tile, latitude, longitude, radius_cells):
    window = tile.window_at(latitude, longitude, radius_cells)

    if window is None or window.size == 0 or np.isnan(window).all():
        return None

    if window.shape[0] < 3 or window.shape[1] < 3:
        return None

    filled_window = np.array(window, dtype=float)

    if np.isnan(filled_window).any():
        mean_value = np.nanmean(filled_window)
        filled_window[np.isnan(filled_window)] = mean_value

    cell_width_m, cell_height_m = calculate_cell_sizes_m(latitude, tile)
    row_indices, column_indices = np.indices(filled_window.shape)
    center_row = (filled_window.shape[0] - 1) / 2
    center_column = (filled_window.shape[1] - 1) / 2
    east_m = (column_indices - center_column) * cell_width_m
    north_m = -(row_indices - center_row) * cell_height_m
    design_matrix = np.column_stack([
        east_m.ravel(),
        north_m.ravel(),
        np.ones(filled_window.size),
    ])
    east_slope, north_slope, _ = np.linalg.lstsq(
        design_matrix,
        filled_window.ravel(),
        rcond=None,
    )[0]
    slope_radians = math.atan(math.sqrt(east_slope ** 2 + north_slope ** 2))
    slope_degrees = math.degrees(slope_radians)
    aspect_degrees = (math.degrees(math.atan2(-east_slope, -north_slope)) + 360) % 360

    return {
        "slope_degrees": slope_degrees,
        "aspect_degrees": aspect_degrees,
        "aspect_sin": math.sin(math.radians(aspect_degrees)),
        "aspect_cos": math.cos(math.radians(aspect_degrees)),
    }


def calculate_local_relief(tile, latitude, longitude, radius_cells):
    window = tile.window_at(latitude, longitude, radius_cells)

    if window is None or window.size == 0 or np.isnan(window).all():
        return None

    return float(np.nanmax(window) - np.nanmin(window))


def calculate_terrain_position(tile, latitude, longitude, radius_cells):
    center_value = tile.value_at(latitude, longitude)
    window = tile.window_at(latitude, longitude, radius_cells)

    if center_value is None or window is None or window.size == 0 or np.isnan(window).all():
        return None

    return float(center_value - np.nanmean(window))


def format_optional(value, decimals):
    if value is None:
        return ""

    return f"{value:.{decimals}f}"


def radius_label(radius_cells):
    return f"r{radius_cells * 30}m"


def multi_scale_fieldnames(radius_cells_values):
    fieldnames = []

    for radius_cells in radius_cells_values:
        label = radius_label(radius_cells)
        fieldnames.extend([
            f"slope_degrees_{label}",
            f"aspect_degrees_{label}",
            f"aspect_sin_{label}",
            f"aspect_cos_{label}",
            f"local_relief_m_{label}",
            f"terrain_position_index_m_{label}",
        ])

    return fieldnames


def add_empty_multi_scale_columns(row, radius_cells_values):
    for fieldname in multi_scale_fieldnames(radius_cells_values):
        row[fieldname] = ""


def add_multi_scale_terrain_columns(row, tile, latitude, longitude, radius_cells_values):
    for radius_cells in radius_cells_values:
        label = radius_label(radius_cells)
        slope_aspect = calculate_window_plane_slope_aspect(
            tile,
            latitude,
            longitude,
            radius_cells,
        )
        local_relief = calculate_local_relief(
            tile,
            latitude,
            longitude,
            radius_cells,
        )
        terrain_position = calculate_terrain_position(
            tile,
            latitude,
            longitude,
            radius_cells,
        )

        if slope_aspect is not None:
            row[f"slope_degrees_{label}"] = format_optional(
                slope_aspect["slope_degrees"],
                3,
            )
            row[f"aspect_degrees_{label}"] = format_optional(
                slope_aspect["aspect_degrees"],
                3,
            )
            row[f"aspect_sin_{label}"] = format_optional(
                slope_aspect["aspect_sin"],
                6,
            )
            row[f"aspect_cos_{label}"] = format_optional(
                slope_aspect["aspect_cos"],
                6,
            )

        row[f"local_relief_m_{label}"] = format_optional(local_relief, 2)
        row[f"terrain_position_index_m_{label}"] = format_optional(terrain_position, 2)


def parse_radius_list(radius_text):
    return [
        int(value.strip())
        for value in radius_text.split(",")
        if value.strip()
    ]


def station_sort_index(station):
    return station.get("_sort_index", 0)


def clean_output_row(row):
    row.pop("_sort_index", None)
    return row


def build_station_groups(station_list):
    station_groups = {}

    for station in station_list:
        latitude = to_float(station["latitude"])
        longitude = to_float(station["longitude"])
        tile_key = "missing_coordinate"

        if latitude is not None and longitude is not None:
            tile_key = tile_key_for_coordinate(latitude, longitude)

        station_groups.setdefault(tile_key, []).append(station)

    return [
        (tile_key, stations)
        for tile_key, stations in sorted(station_groups.items())
    ]


def process_station_group(task):
    (
        _tile_key,
        stations,
        metadata,
        tile_index,
        slope_radius,
        relief_radius,
        tpi_radius,
        multi_scale_radii,
    ) = task
    loaded_tiles = {}
    rows = []

    for station in stations:
        row = build_terrain_row(
            station,
            metadata,
            tile_index,
            loaded_tiles,
            slope_radius,
            relief_radius,
            tpi_radius,
            multi_scale_radii,
        )
        row["_sort_index"] = station_sort_index(station)
        rows.append(row)

    return rows


def build_terrain_row(
    station,
    metadata,
    tile_index,
    loaded_tiles,
    slope_radius,
    relief_radius,
    tpi_radius,
    multi_scale_radii,
):
    station_id = station["station_id"]
    latitude = to_float(station["latitude"])
    longitude = to_float(station["longitude"])

    row = {
        "station_id": station_id,
        "station_role": "+".join(sorted(station["roles"])),
        "station_name": metadata.get(station_id, {}).get("station_name", ""),
        "latitude": station["latitude"],
        "longitude": station["longitude"],
        "noaa_elevation_m": metadata.get(station_id, {}).get("noaa_elevation_m", ""),
        "dem_tile": "",
        "dem_elevation_m": "",
        "dem_minus_noaa_elevation_m": "",
        "elevation_qa_status": "",
        "slope_degrees": "",
        "aspect_degrees": "",
        "aspect_sin": "",
        "aspect_cos": "",
        "local_relief_m": "",
        "terrain_position_index_m": "",
        "terrain_status": "missing_coordinate",
    }
    add_empty_multi_scale_columns(row, multi_scale_radii)

    if latitude is None or longitude is None:
        return row

    tile_key = tile_key_for_coordinate(latitude, longitude)
    tile_path = tile_index.get(tile_key)
    row["dem_tile"] = tile_key

    if tile_path is None:
        row["terrain_status"] = "missing_dem_tile"
        return row

    if tile_key not in loaded_tiles:
        loaded_tiles[tile_key] = DemTile(tile_path)

    tile = loaded_tiles[tile_key]
    dem_elevation = tile.value_at(latitude, longitude)

    if dem_elevation is None:
        row["terrain_status"] = "missing_dem_value"
        return row

    noaa_elevation = to_float(row["noaa_elevation_m"])
    slope_aspect = calculate_slope_aspect(tile, latitude, longitude, slope_radius)
    local_relief = calculate_local_relief(tile, latitude, longitude, relief_radius)
    terrain_position = calculate_terrain_position(tile, latitude, longitude, tpi_radius)

    row["dem_elevation_m"] = format_optional(dem_elevation, 2)

    if noaa_elevation is not None:
        elevation_difference = dem_elevation - noaa_elevation
        row["dem_minus_noaa_elevation_m"] = format_optional(elevation_difference, 2)

        if abs(elevation_difference) <= 100:
            row["elevation_qa_status"] = "close"
        elif abs(elevation_difference) <= 500:
            row["elevation_qa_status"] = "review"
        else:
            row["elevation_qa_status"] = "large_difference"

    if slope_aspect is not None:
        row["slope_degrees"] = format_optional(slope_aspect["slope_degrees"], 3)
        row["aspect_degrees"] = format_optional(slope_aspect["aspect_degrees"], 3)
        row["aspect_sin"] = format_optional(slope_aspect["aspect_sin"], 6)
        row["aspect_cos"] = format_optional(slope_aspect["aspect_cos"], 6)

    row["local_relief_m"] = format_optional(local_relief, 2)
    row["terrain_position_index_m"] = format_optional(terrain_position, 2)
    add_multi_scale_terrain_columns(row, tile, latitude, longitude, multi_scale_radii)
    row["terrain_status"] = "ok"

    return row


def write_rows(output_file, rows, multi_scale_radii):
    fieldnames = [
        "station_id",
        "station_role",
        "station_name",
        "latitude",
        "longitude",
        "noaa_elevation_m",
        "dem_tile",
        "dem_elevation_m",
        "dem_minus_noaa_elevation_m",
        "elevation_qa_status",
        "slope_degrees",
        "aspect_degrees",
        "aspect_sin",
        "aspect_cos",
        "local_relief_m",
        "terrain_position_index_m",
        *multi_scale_fieldnames(multi_scale_radii),
        "terrain_status",
    ]

    write_csv_rows(output_file, rows, fieldnames)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Sample DEM-derived terrain features for target and hub weather stations."
    )
    parser.add_argument(
        "--raw-dem-dir",
        type=Path,
        default=RAW_DEM_DIR,
        help="Folder containing USGS DEM GeoTIFF tiles.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="Output station terrain feature CSV.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process the first N unique stations. Useful for testing.",
    )
    parser.add_argument(
        "--slope-radius",
        type=int,
        default=1,
        help="Pixel radius used for local slope/aspect calculation.",
    )
    parser.add_argument(
        "--relief-radius",
        type=int,
        default=33,
        help="Pixel radius used for local relief calculation. 33 pixels is roughly 1 km at 30 m resolution.",
    )
    parser.add_argument(
        "--tpi-radius",
        type=int,
        default=33,
        help="Pixel radius used for terrain position index calculation.",
    )
    parser.add_argument(
        "--multi-scale-radii",
        default=",".join(str(radius) for radius in DEFAULT_MULTI_SCALE_RADII),
        help=(
            "Comma-separated pixel radii for additional multi-scale terrain "
            "columns. Defaults to 3,10,33,100, roughly 90 m, 300 m, 990 m, "
            "and 3000 m at 30 m DEM resolution."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes. Use 2 or more to process DEM tile groups in parallel.",
    )
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    multi_scale_radii = parse_radius_list(arguments.multi_scale_radii)

    if not arguments.raw_dem_dir.exists():
        raise FileNotFoundError(f"DEM folder was not found: {arguments.raw_dem_dir}")

    tile_index = build_dem_tile_index(arguments.raw_dem_dir)

    if not tile_index:
        raise FileNotFoundError(f"No .tif DEM tiles were found in: {arguments.raw_dem_dir}")

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

    for index, station in enumerate(station_list):
        station["_sort_index"] = index

    print("Build station terrain features")
    print("==============================")
    print(f"DEM tiles indexed: {len(tile_index)}")
    print(f"Stations to process: {len(station_list)}")
    print(f"Multi-scale terrain radii: {multi_scale_radii}")
    print(f"Worker processes: {arguments.workers}")
    print(f"Output file: {arguments.output}")

    rows = []

    if arguments.workers > 1:
        station_groups = build_station_groups(station_list)
        tasks = [
            (
                tile_key,
                stations,
                metadata,
                tile_index,
                arguments.slope_radius,
                arguments.relief_radius,
                arguments.tpi_radius,
                multi_scale_radii,
            )
            for tile_key, stations in station_groups
        ]
        processed_count = 0

        with Pool(processes=arguments.workers) as pool:
            for group_rows in pool.imap_unordered(process_station_group, tasks):
                rows.extend(group_rows)
                processed_count += len(group_rows)

                if processed_count % 100 == 0 or processed_count == len(station_list):
                    ok_count = sum(
                        1
                        for output_row in rows
                        if output_row["terrain_status"] == "ok"
                    )
                    print(f"Processed {processed_count}/{len(station_list)} stations ({ok_count} ok)")
    else:
        loaded_tiles = {}
        current_tile_key = None

        for index, station in enumerate(station_list, start=1):
            latitude = to_float(station["latitude"])
            longitude = to_float(station["longitude"])
            station_tile_key = None

            if latitude is not None and longitude is not None:
                station_tile_key = tile_key_for_coordinate(latitude, longitude)

            if station_tile_key != current_tile_key:
                loaded_tiles.clear()
                current_tile_key = station_tile_key

            row = build_terrain_row(
                station,
                metadata,
                tile_index,
                loaded_tiles,
                arguments.slope_radius,
                arguments.relief_radius,
                arguments.tpi_radius,
                multi_scale_radii,
            )
            row["_sort_index"] = station_sort_index(station)
            rows.append(row)

            if index % 100 == 0 or index == len(station_list):
                ok_count = sum(1 for output_row in rows if output_row["terrain_status"] == "ok")
                print(f"Processed {index}/{len(station_list)} stations ({ok_count} ok)")

    rows.sort(key=lambda row: row.get("_sort_index", 0))
    rows = [clean_output_row(row) for row in rows]
    write_rows(arguments.output, rows, multi_scale_radii)

    ok_count = sum(1 for row in rows if row["terrain_status"] == "ok")
    missing_count = len(rows) - ok_count

    print()
    print("Terrain feature extraction complete")
    print("-----------------------------------")
    print(f"Rows written: {len(rows)}")
    print(f"Successful terrain rows: {ok_count}")
    print(f"Missing/problem rows: {missing_count}")
    print(f"Output file: {arguments.output}")


if __name__ == "__main__":
    main()
