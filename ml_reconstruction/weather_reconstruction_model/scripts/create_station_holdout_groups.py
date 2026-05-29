from __future__ import annotations

import argparse
import csv
import math
import random
from pathlib import Path
from typing import Optional

import config
from common.csv_utils import write_csv_rows
from common.number_utils import to_float
from common.weather_cache import TEMPERATURE_VARIABLES, validate_temperature_variable


DEFAULT_OUTPUT_ROOT = config.OUTPUT_DIR / "paloma" / "station_holdout_groups"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create geographically and physically diverse grouped station-holdout "
            "sets for Paloma validation pilots."
        )
    )
    parser.add_argument("general_table", type=Path)
    parser.add_argument(
        "--variable",
        choices=sorted(TEMPERATURE_VARIABLES),
        default="tavg",
    )
    parser.add_argument("--group-count", type=int, default=None)
    parser.add_argument("--group-size", type=int, default=4)
    parser.add_argument(
        "--strategy",
        choices=["balanced-quadrant", "diverse"],
        default="balanced-quadrant",
        help=(
            "balanced-quadrant puts roughly one station from each spatial "
            "quadrant in every group; diverse uses farthest-point selection."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible quadrant shuffling.",
    )
    parser.add_argument(
        "--all-stations",
        action="store_true",
        help=(
            "Group every eligible target station. If --group-count is omitted, "
            "uses floor(station_count / group_size) and allows a few groups to "
            "have one extra station."
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def unique_station_rows(general_table: Path, variable: str) -> list[dict[str, object]]:
    variable = validate_temperature_variable(variable)
    target_column = f"target_{variable}"
    stations_by_id: dict[str, dict[str, object]] = {}

    with general_table.open("r", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = set(reader.fieldnames or [])
        if target_column not in fieldnames:
            raise ValueError(f"General table is missing {target_column}.")

        for row in reader:
            station_id = row["target_station_id"]
            if station_id in stations_by_id:
                continue

            stations_by_id[station_id] = {
                "station_id": station_id,
                "station_name": row.get("target_name", ""),
                "latitude": to_float(row.get("target_latitude", "")),
                "longitude": to_float(row.get("target_longitude", "")),
                "elevation_m": to_float(row.get("target_elevation_m", "")),
                "local_relief_m": to_float(row.get("target_local_relief_m", "")),
                "terrain_position_index_m": to_float(
                    row.get("target_terrain_position_index_m", "")
                ),
            }

    return sorted(stations_by_id.values(), key=lambda row: str(row["station_id"]))


def feature_ranges(stations: list[dict[str, object]]) -> dict[str, tuple[float, float]]:
    ranges = {}
    for key in (
        "latitude",
        "longitude",
        "elevation_m",
        "local_relief_m",
        "terrain_position_index_m",
    ):
        values = [float(station[key]) for station in stations]
        ranges[key] = (min(values), max(values))
    return ranges


def normalize(value: float, minimum: float, maximum: float) -> float:
    if maximum == minimum:
        return 0.0
    return (value - minimum) / (maximum - minimum)


def station_vector(
    station: dict[str, object],
    ranges: dict[str, tuple[float, float]],
) -> tuple[float, ...]:
    weights = {
        "latitude": 1.25,
        "longitude": 1.25,
        "elevation_m": 1.0,
        "local_relief_m": 0.5,
        "terrain_position_index_m": 0.5,
    }
    return tuple(
        normalize(float(station[key]), *ranges[key]) * weights[key]
        for key in weights
    )


def euclidean_distance(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return math.sqrt(sum((left - right) ** 2 for left, right in zip(a, b)))


def build_vectors(
    stations: list[dict[str, object]],
) -> dict[str, tuple[float, ...]]:
    ranges = feature_ranges(stations)
    return {
        str(station["station_id"]): station_vector(station, ranges)
        for station in stations
    }


def choose_diverse_stations(
    stations: list[dict[str, object]],
    total_count: int,
) -> list[dict[str, object]]:
    if total_count > len(stations):
        raise ValueError(
            f"Cannot choose {total_count} stations from only {len(stations)} candidates."
        )

    vectors = build_vectors(stations)
    centroid = tuple(
        sum(vector[index] for vector in vectors.values()) / len(vectors)
        for index in range(len(next(iter(vectors.values()))))
    )
    stations_by_id = {
        str(station["station_id"]): station
        for station in stations
    }
    first_station_id = max(
        vectors,
        key=lambda station_id: euclidean_distance(vectors[station_id], centroid),
    )
    selected_station_ids = [first_station_id]

    while len(selected_station_ids) < total_count:
        selected_set = set(selected_station_ids)
        next_station_id = max(
            [
                station_id
                for station_id in vectors
                if station_id not in selected_set
            ],
            key=lambda station_id: min(
                euclidean_distance(vectors[station_id], vectors[selected_station_id])
                for selected_station_id in selected_station_ids
            ),
        )
        selected_station_ids.append(next_station_id)

    return [stations_by_id[station_id] for station_id in selected_station_ids]


def assign_groups(
    selected_stations: list[dict[str, object]],
    group_count: int,
    group_size: int,
) -> list[list[dict[str, object]]]:
    vectors = build_vectors(selected_stations)
    groups = [[] for _ in range(group_count)]

    for station in selected_stations[:group_count]:
        groups[len([group for group in groups if group])].append(station)

    for station in selected_stations[group_count:]:
        station_id = str(station["station_id"])
        candidate_indexes = [
            index
            for index, group in enumerate(groups)
            if len(group) < group_size
        ]
        best_index = max(
            candidate_indexes,
            key=lambda index: sum(
                euclidean_distance(
                    vectors[station_id],
                    vectors[str(group_station["station_id"])],
                )
                for group_station in groups[index]
            ) / len(groups[index]),
        )
        groups[best_index].append(station)

    return groups


def balanced_quadrants(
    stations: list[dict[str, object]],
) -> dict[str, list[dict[str, object]]]:
    by_latitude = sorted(stations, key=lambda station: float(station["latitude"]))
    south = by_latitude[:len(by_latitude) // 2]
    north = by_latitude[len(by_latitude) // 2:]

    def split_west_east(
        region_stations: list[dict[str, object]],
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        by_longitude = sorted(
            region_stations,
            key=lambda station: float(station["longitude"]),
        )
        midpoint = len(by_longitude) // 2
        return by_longitude[:midpoint], by_longitude[midpoint:]

    southwest, southeast = split_west_east(south)
    northwest, northeast = split_west_east(north)

    return {
        "southwest": southwest,
        "southeast": southeast,
        "northwest": northwest,
        "northeast": northeast,
    }


def assign_balanced_quadrant_groups(
    selected_stations: list[dict[str, object]],
    group_count: int,
    seed: int,
) -> list[list[dict[str, object]]]:
    rng = random.Random(seed)
    groups = [[] for _ in range(group_count)]
    quadrants = balanced_quadrants(selected_stations)

    for quadrant_name in ("southwest", "southeast", "northwest", "northeast"):
        quadrant_stations = list(quadrants[quadrant_name])
        rng.shuffle(quadrant_stations)

        for index, station in enumerate(quadrant_stations):
            station["_holdout_quadrant"] = quadrant_name
            groups[index % group_count].append(station)

    return [
        group
        for group in groups
        if group
    ]


def resolve_selected_stations_and_group_count(
    stations: list[dict[str, object]],
    group_size: int,
    group_count: Optional[int],
    all_stations: bool,
) -> tuple[list[dict[str, object]], int]:
    if group_size <= 0:
        raise ValueError("--group-size must be positive.")

    if all_stations:
        selected_stations = stations
        resolved_group_count = group_count or max(1, len(stations) // group_size)
        return selected_stations, resolved_group_count

    if group_count is None or group_count <= 0:
        raise ValueError("--group-count must be positive unless --all-stations is used.")

    total_count = group_count * group_size
    selected_stations = choose_diverse_stations(stations, total_count)
    return selected_stations, group_count


def group_rows(groups: list[list[dict[str, object]]]) -> list[dict[str, object]]:
    rows = []
    for group_index, group in enumerate(groups, start=1):
        group_id = f"group_{group_index:03d}"
        for station in group:
            rows.append({
                "group_id": group_id,
                "station_id": station["station_id"],
                "station_name": station["station_name"],
                "latitude": f"{float(station['latitude']):.6f}",
                "longitude": f"{float(station['longitude']):.6f}",
                "elevation_m": f"{float(station['elevation_m']):.1f}",
                "local_relief_m": f"{float(station['local_relief_m']):.3f}",
                "terrain_position_index_m": (
                    f"{float(station['terrain_position_index_m']):.3f}"
                ),
                "holdout_quadrant": station.get("_holdout_quadrant", ""),
            })
    return rows


def summarize_groups(groups: list[list[dict[str, object]]]) -> dict[str, object]:
    group_sizes = [len(group) for group in groups]
    return {
        "groupCount": len(groups),
        "minGroupSize": min(group_sizes) if group_sizes else 0,
        "maxGroupSize": max(group_sizes) if group_sizes else 0,
    }


def main() -> None:
    arguments = parse_arguments()
    variable = validate_temperature_variable(arguments.variable)
    stations = unique_station_rows(arguments.general_table, variable)
    selected_stations, group_count = resolve_selected_stations_and_group_count(
        stations,
        arguments.group_size,
        arguments.group_count,
        arguments.all_stations,
    )

    if arguments.strategy == "balanced-quadrant":
        groups = assign_balanced_quadrant_groups(
            selected_stations,
            group_count,
            arguments.seed,
        )
    else:
        groups = assign_groups(
            selected_stations,
            group_count,
            arguments.group_size,
        )

    output_dir = arguments.output_dir / variable
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = group_rows(groups)
    summary = summarize_groups(groups)
    fieldnames = [
        "group_id",
        "station_id",
        "station_name",
        "latitude",
        "longitude",
        "elevation_m",
        "local_relief_m",
        "terrain_position_index_m",
        "holdout_quadrant",
    ]
    master_file = output_dir / "holdout_groups.csv"
    write_csv_rows(master_file, rows, fieldnames)

    for group_index, group in enumerate(groups, start=1):
        group_id = f"group_{group_index:03d}"
        group_file = output_dir / f"{group_id}.csv"
        write_csv_rows(
            group_file,
            [
                row
                for row in rows
                if row["group_id"] == group_id
            ],
            fieldnames,
        )

    print("Grouped station holdouts created")
    print("================================")
    print(f"General table: {arguments.general_table}")
    print(f"Temperature variable: {variable}")
    print(f"Strategy: {arguments.strategy}")
    print(f"Candidate target stations: {len(stations)}")
    print(f"Groups: {summary['groupCount']}")
    print(f"Target group size: {arguments.group_size}")
    print(f"Group size range: {summary['minGroupSize']}-{summary['maxGroupSize']}")
    print(f"Selected holdout stations: {len(rows)}")
    print(f"Master group file: {master_file}")
    print(f"Group files: {output_dir}/group_*.csv")


if __name__ == "__main__":
    main()
