from __future__ import annotations

import csv
import math
from datetime import date
from pathlib import Path
from typing import Mapping, Union

from common.csv_utils import write_csv_rows
from common.number_utils import to_float
from common.pairwise_skill import PAIRWISE_SKILL_COLUMNS
from common.weather_cache import validate_temperature_variable


DailySeries = Mapping[str, float]
DailyByStation = Mapping[str, DailySeries]
TERRAIN_FEATURE_COLUMNS = [
    "dem_elevation_m",
    "dem_minus_noaa_elevation_m",
    "slope_degrees",
    "aspect_sin",
    "aspect_cos",
    "local_relief_m",
    "terrain_position_index_m",
]
MULTI_SCALE_TERRAIN_RADIUS_LABELS = [
    "r90m",
    "r300m",
    "r990m",
    "r3000m",
]
MULTI_SCALE_TERRAIN_FEATURE_STEMS = [
    "slope_degrees",
    "aspect_sin",
    "aspect_cos",
    "local_relief_m",
    "terrain_position_index_m",
]
MULTI_SCALE_TERRAIN_FEATURE_COLUMNS = [
    f"{stem}_{radius_label}"
    for radius_label in MULTI_SCALE_TERRAIN_RADIUS_LABELS
    for stem in MULTI_SCALE_TERRAIN_FEATURE_STEMS
]
ALL_TERRAIN_FEATURE_COLUMNS = TERRAIN_FEATURE_COLUMNS + MULTI_SCALE_TERRAIN_FEATURE_COLUMNS
ENGINEERED_HUB_FEATURE_SUFFIXES = [
    "dem_elevation_delta_m",
    "abs_dem_elevation_delta_m",
    "slope_delta_degrees",
    "abs_slope_delta_degrees",
    "local_relief_delta_m",
    "abs_local_relief_delta_m",
    "terrain_position_delta_m",
    "abs_terrain_position_delta_m",
    "aspect_similarity",
    "distance_x_abs_dem_elevation_delta",
    "season_sin_x_dem_elevation_delta",
    "season_cos_x_dem_elevation_delta",
    "season_sin_x_terrain_position_delta",
    "season_cos_x_terrain_position_delta",
]
PREDICTOR_SELECTION_FEATURE_SUFFIXES = [
    "selection_score",
    "physical_similarity_score",
    "distance_score",
    "elevation_score",
    "terrain_position_score",
    "relief_score",
    "slope_score",
    "aspect_score",
]
PREDICTOR_PAIRWISE_FEATURE_SUFFIXES = PAIRWISE_SKILL_COLUMNS
DATE_PARTS_BY_DATE = {}


def build_shared_date_rows(
    target_station_id: str,
    hub_ids: list[str],
    target_daily: Union[DailyByStation, DailySeries],
    hub_daily: DailyByStation,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    target_series = daily_series_for_target(target_station_id, target_daily)
    shared_dates = set(target_series.keys())

    for hub_id in hub_ids:
        shared_dates = shared_dates.intersection(hub_daily[hub_id].keys())

    for date in sorted(shared_dates):
        row = {
            "date": date,
            "target_station_id": target_station_id,
            "target_tavg": f"{target_series[date]:.2f}",
        }

        for index, hub_id in enumerate(hub_ids, start=1):
            row[f"hub_{index}_station_id"] = hub_id
            row[f"hub_{index}_tavg"] = f"{hub_daily[hub_id][date]:.2f}"

        rows.append(row)

    return rows


def daily_series_for_target(
    target_station_id: str,
    target_daily: Union[DailyByStation, DailySeries],
) -> DailySeries:
    if target_station_id in target_daily:
        possible_series = target_daily[target_station_id]

        if isinstance(possible_series, Mapping):
            return possible_series

    return target_daily


def parse_date_parts(date_text):
    if date_text in DATE_PARTS_BY_DATE:
        return DATE_PARTS_BY_DATE[date_text]

    year = int(date_text[:4])
    month = int(date_text[5:7])
    day = int(date_text[8:10])
    day_of_year = date(year, month, day).timetuple().tm_yday
    angle = 2 * math.pi * day_of_year / 366

    date_parts = {
        "year": year,
        "month": month,
        "day": day,
        "day_of_year": day_of_year,
        "season_sin": math.sin(angle),
        "season_cos": math.cos(angle),
    }
    DATE_PARTS_BY_DATE[date_text] = date_parts
    return date_parts


def build_general_rows_for_target(
    target_station,
    target_metadata,
    target_daily,
    selected_hubs,
    selected_target_neighbors,
    hub_daily_by_station,
    hub_metadata_by_station,
    target_neighbor_daily_by_station,
    target_neighbor_metadata_by_station,
    terrain_by_station,
    variable="tavg",
):
    variable = validate_temperature_variable(variable)
    shared_dates = set(target_daily.keys())

    for hub in selected_hubs:
        shared_dates = shared_dates.intersection(hub_daily_by_station[hub["station_id"]].keys())

    for neighbor in selected_target_neighbors:
        shared_dates = shared_dates.intersection(
            target_neighbor_daily_by_station[neighbor["station_id"]].keys()
        )

    target_latitude = to_float(target_station["latitude"])
    target_longitude = to_float(target_station["longitude"])
    target_elevation = to_float(target_metadata.get("elevation", "0"))
    target_terrain = terrain_by_station.get(target_station["station_id"], {})
    selected_hubs = prepare_predictor_contexts(
        selected_hubs,
        hub_metadata_by_station,
        terrain_by_station,
        target_latitude,
        target_longitude,
        target_terrain,
    )
    selected_target_neighbors = prepare_predictor_contexts(
        selected_target_neighbors,
        target_neighbor_metadata_by_station,
        terrain_by_station,
        target_latitude,
        target_longitude,
        target_terrain,
    )
    rows = []
    target_value_column = f"target_{variable}"
    regional_baseline_column = f"regional_baseline_{variable}"
    target_offset_column = f"target_{variable}_offset_from_baseline"

    for date_text in sorted(shared_dates):
        date_parts = parse_date_parts(date_text)
        regional_baseline_value = calculate_regional_baseline_temperature(
            selected_hubs,
            hub_daily_by_station,
            date_text,
        )
        target_value = target_daily[date_text]
        row = {
            "date": date_text,
            "year": date_parts["year"],
            "month": date_parts["month"],
            "day": date_parts["day"],
            "day_of_year": date_parts["day_of_year"],
            "season_sin": f"{date_parts['season_sin']:.8f}",
            "season_cos": f"{date_parts['season_cos']:.8f}",
            "target_station_id": target_station["station_id"],
            "target_name": target_metadata.get("station_name", "Unknown station"),
            "target_latitude": f"{target_latitude:.6f}",
            "target_longitude": f"{target_longitude:.6f}",
            "target_elevation_m": f"{target_elevation:.1f}",
            target_value_column: f"{target_value:.2f}",
            regional_baseline_column: f"{regional_baseline_value:.2f}",
            target_offset_column: (
                f"{target_value - regional_baseline_value:.2f}"
            ),
        }
        add_terrain_columns(row, "target", target_terrain)

        for index, hub in enumerate(selected_hubs, start=1):
            add_predictor_columns(
                row,
                f"hub_{index}",
                hub,
                hub_daily_by_station,
                regional_baseline_value,
                date_parts,
                date_text,
                variable,
            )

        for index, neighbor in enumerate(selected_target_neighbors, start=1):
            add_predictor_columns(
                row,
                f"target_neighbor_{index}",
                neighbor,
                target_neighbor_daily_by_station,
                regional_baseline_value,
                date_parts,
                date_text,
                variable,
            )

        rows.append(row)

    return rows


def calculate_regional_baseline_temperature(selected_hubs, hub_daily_by_station, date_text):
    hub_values = [
        hub_daily_by_station[hub["station_id"]][date_text]
        for hub in selected_hubs
    ]
    return sum(hub_values) / len(hub_values)


def prepare_predictor_contexts(
    predictors,
    metadata_by_station,
    terrain_by_station,
    target_latitude,
    target_longitude,
    target_terrain,
):
    contexts = []

    for predictor in predictors:
        station_id = predictor["station_id"]
        metadata = metadata_by_station.get(station_id, {})
        terrain = terrain_by_station.get(station_id, {})
        latitude = to_float(predictor.get("latitude", "0"))
        longitude = to_float(predictor.get("longitude", "0"))
        elevation = to_float(metadata.get("elevation", "0"))

        context = dict(predictor)
        context["_station_name"] = metadata.get("station_name", "Unknown station")
        context["_latitude"] = latitude
        context["_longitude"] = longitude
        context["_elevation"] = elevation
        context["_latitude_offset"] = latitude - target_latitude
        context["_longitude_offset"] = longitude - target_longitude
        context["_terrain"] = terrain
        context["_engineered_base"] = build_engineered_base_values(
            predictor["distance_km"],
            target_terrain,
            terrain,
        )
        contexts.append(context)

    return contexts


def build_engineered_base_values(distance_km, target_terrain, hub_terrain):
    target_dem_elevation = to_float(target_terrain.get("dem_elevation_m", ""))
    hub_dem_elevation = to_float(hub_terrain.get("dem_elevation_m", ""))
    target_slope = to_float(target_terrain.get("slope_degrees", ""))
    hub_slope = to_float(hub_terrain.get("slope_degrees", ""))
    target_relief = to_float(target_terrain.get("local_relief_m", ""))
    hub_relief = to_float(hub_terrain.get("local_relief_m", ""))
    target_tpi = to_float(target_terrain.get("terrain_position_index_m", ""))
    hub_tpi = to_float(hub_terrain.get("terrain_position_index_m", ""))
    target_aspect_sin = to_float(target_terrain.get("aspect_sin", ""))
    target_aspect_cos = to_float(target_terrain.get("aspect_cos", ""))
    hub_aspect_sin = to_float(hub_terrain.get("aspect_sin", ""))
    hub_aspect_cos = to_float(hub_terrain.get("aspect_cos", ""))

    dem_elevation_delta = target_dem_elevation - hub_dem_elevation
    terrain_position_delta = target_tpi - hub_tpi

    return {
        "dem_elevation_delta_m": dem_elevation_delta,
        "abs_dem_elevation_delta_m": abs(dem_elevation_delta),
        "slope_delta_degrees": target_slope - hub_slope,
        "abs_slope_delta_degrees": abs(target_slope - hub_slope),
        "local_relief_delta_m": target_relief - hub_relief,
        "abs_local_relief_delta_m": abs(target_relief - hub_relief),
        "terrain_position_delta_m": terrain_position_delta,
        "abs_terrain_position_delta_m": abs(terrain_position_delta),
        "aspect_similarity": (
            target_aspect_sin * hub_aspect_sin
            + target_aspect_cos * hub_aspect_cos
        ),
        "distance_x_abs_dem_elevation_delta": distance_km * abs(dem_elevation_delta),
    }


def add_predictor_columns(
    row,
    prefix,
    predictor,
    daily_by_station,
    regional_baseline_value,
    date_parts,
    date_text,
    variable="tavg",
):
    variable = validate_temperature_variable(variable)
    station_id = predictor["station_id"]
    terrain = predictor["_terrain"]
    predictor_value = daily_by_station[station_id][date_text]

    row[f"{prefix}_station_id"] = station_id
    row[f"{prefix}_name"] = predictor["_station_name"]
    row[f"{prefix}_{variable}"] = f"{predictor_value:.2f}"
    row[f"{prefix}_{variable}_offset_from_baseline"] = (
        f"{predictor_value - regional_baseline_value:.2f}"
    )
    row[f"{prefix}_latitude"] = f"{predictor['_latitude']:.6f}"
    row[f"{prefix}_longitude"] = f"{predictor['_longitude']:.6f}"
    row[f"{prefix}_elevation_m"] = f"{predictor['_elevation']:.1f}"
    row[f"{prefix}_distance_km"] = f"{predictor['distance_km']:.3f}"
    row[f"{prefix}_elevation_difference_m"] = f"{predictor['elevation_difference_m']:.1f}"
    row[f"{prefix}_latitude_offset"] = f"{predictor['_latitude_offset']:.6f}"
    row[f"{prefix}_longitude_offset"] = f"{predictor['_longitude_offset']:.6f}"
    row[f"{prefix}_overlap_percent"] = f"{predictor['overlap_percent']:.2f}"
    add_predictor_selection_features(row, prefix, predictor)
    add_predictor_pairwise_features(row, prefix, predictor)
    add_terrain_columns(row, prefix, terrain)
    add_engineered_hub_features(
        row,
        prefix,
        date_parts,
        predictor["_engineered_base"],
    )


def add_predictor_selection_features(row, prefix, predictor):
    for suffix in PREDICTOR_SELECTION_FEATURE_SUFFIXES:
        row[f"{prefix}_{suffix}"] = f"{to_float(predictor.get(suffix, '')):.6f}"


def add_predictor_pairwise_features(row, prefix, predictor):
    for suffix in PREDICTOR_PAIRWISE_FEATURE_SUFFIXES:
        value = predictor.get(suffix)

        if value is None or value == "":
            row[f"{prefix}_{suffix}"] = ""
        elif suffix == "pair_overlap_days":
            row[f"{prefix}_{suffix}"] = str(int(to_float(value)))
        else:
            row[f"{prefix}_{suffix}"] = f"{to_float(value):.6f}"


def add_terrain_columns(row, prefix, terrain_row):
    for column in ALL_TERRAIN_FEATURE_COLUMNS:
        row[f"{prefix}_{column}"] = terrain_row.get(column, "")


def add_engineered_hub_features(row, prefix, date_parts, engineered_base_values):
    engineered_values = dict(engineered_base_values)
    engineered_values["season_sin_x_dem_elevation_delta"] = (
        date_parts["season_sin"] * engineered_base_values["dem_elevation_delta_m"]
    )
    engineered_values["season_cos_x_dem_elevation_delta"] = (
        date_parts["season_cos"] * engineered_base_values["dem_elevation_delta_m"]
    )
    engineered_values["season_sin_x_terrain_position_delta"] = (
        date_parts["season_sin"]
        * engineered_base_values["terrain_position_delta_m"]
    )
    engineered_values["season_cos_x_terrain_position_delta"] = (
        date_parts["season_cos"]
        * engineered_base_values["terrain_position_delta_m"]
    )

    for suffix, value in engineered_values.items():
        row[f"{prefix}_{suffix}"] = f"{value:.6f}"


def fieldnames_for_hub_count(hub_count, target_neighbor_count=0, variable="tavg"):
    variable = validate_temperature_variable(variable)
    fieldnames = [
        "date",
        "year",
        "month",
        "day",
        "day_of_year",
        "season_sin",
        "season_cos",
        "target_station_id",
        "target_name",
        "target_latitude",
        "target_longitude",
        "target_elevation_m",
        "target_dem_elevation_m",
        "target_dem_minus_noaa_elevation_m",
        "target_slope_degrees",
        "target_aspect_sin",
        "target_aspect_cos",
        "target_local_relief_m",
        "target_terrain_position_index_m",
        *[
            f"target_{column}"
            for column in MULTI_SCALE_TERRAIN_FEATURE_COLUMNS
        ],
        f"target_{variable}",
        f"regional_baseline_{variable}",
        f"target_{variable}_offset_from_baseline",
    ]

    add_predictor_fieldnames(fieldnames, "hub", hub_count, variable)
    add_predictor_fieldnames(
        fieldnames,
        "target_neighbor",
        target_neighbor_count,
        variable,
    )

    return fieldnames


def add_predictor_fieldnames(fieldnames, prefix, count, variable="tavg"):
    variable = validate_temperature_variable(variable)
    for index in range(1, count + 1):
        indexed_prefix = f"{prefix}_{index}"
        fieldnames.extend([
            f"{indexed_prefix}_station_id",
            f"{indexed_prefix}_name",
            f"{indexed_prefix}_{variable}",
            f"{indexed_prefix}_{variable}_offset_from_baseline",
            f"{indexed_prefix}_latitude",
            f"{indexed_prefix}_longitude",
            f"{indexed_prefix}_elevation_m",
            f"{indexed_prefix}_distance_km",
            f"{indexed_prefix}_elevation_difference_m",
            f"{indexed_prefix}_latitude_offset",
            f"{indexed_prefix}_longitude_offset",
            f"{indexed_prefix}_overlap_percent",
            *[
                f"{indexed_prefix}_{suffix}"
                for suffix in PREDICTOR_SELECTION_FEATURE_SUFFIXES
            ],
            *[
                f"{indexed_prefix}_{suffix}"
                for suffix in PREDICTOR_PAIRWISE_FEATURE_SUFFIXES
            ],
            f"{indexed_prefix}_dem_elevation_m",
            f"{indexed_prefix}_dem_minus_noaa_elevation_m",
            f"{indexed_prefix}_slope_degrees",
            f"{indexed_prefix}_aspect_sin",
            f"{indexed_prefix}_aspect_cos",
            f"{indexed_prefix}_local_relief_m",
            f"{indexed_prefix}_terrain_position_index_m",
            *[
                f"{indexed_prefix}_{column}"
                for column in MULTI_SCALE_TERRAIN_FEATURE_COLUMNS
            ],
        ])
        fieldnames.extend([
            f"{indexed_prefix}_{suffix}"
            for suffix in ENGINEERED_HUB_FEATURE_SUFFIXES
        ])


def write_general_training_table(
    output_file: Path,
    rows,
    hub_count,
    target_neighbor_count=0,
    variable="tavg",
):
    write_csv_rows(
        output_file,
        rows,
        fieldnames_for_hub_count(hub_count, target_neighbor_count, variable),
    )


def open_streaming_general_table_writer(
    output_file: Path,
    hub_count,
    target_neighbor_count=0,
    variable="tavg",
):
    output_file.parent.mkdir(parents=True, exist_ok=True)
    file = output_file.open("w", newline="")
    writer = csv.DictWriter(
        file,
        fieldnames_for_hub_count(hub_count, target_neighbor_count, variable),
    )
    writer.writeheader()
    return file, writer
