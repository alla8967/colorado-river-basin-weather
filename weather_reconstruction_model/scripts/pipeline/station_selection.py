"""Select physically suitable hub and neighbor stations for training rows.

The scoring combines distance, elevation, terrain, and optional pairwise skill evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Mapping, Sequence

from common.geo_utils import calculate_distance_km
from common.number_utils import to_float, to_optional_float
from common.pairwise_skill import PAIRWISE_SKILL_COLUMNS


StationRow = Mapping[str, str]
StationDates = Mapping[str, set[str]]
StationMetadata = Mapping[str, Mapping[str, str]]


@dataclass
class ScoredHub:
    station_id: str
    station_name: str
    distance_km: float
    elevation_difference_m: float
    overlap_days: int
    overlap_percent: float
    selection_score: float
    physical_similarity_score: float
    distance_score: float
    elevation_score: float
    terrain_position_score: float
    relief_score: float
    slope_score: float
    aspect_score: float
    pair_overlap_days: int
    pair_corr: float | None
    pair_mae: float | None
    pair_rmse: float | None
    pair_mean_bias: float | None
    pair_abs_mean_bias: float | None
    pair_winter_mae: float | None
    pair_summer_mae: float | None
    pair_winter_bias: float | None
    pair_summer_bias: float | None
    pair_skill_score: float | None
    usable_period: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def find_training_eligible_hubs(
    target_station: StationRow,
    hubs: Sequence[StationRow],
    target_dates: set[str],
    target_metadata: Mapping[str, str],
    hub_dates_by_station: StationDates,
    hub_metadata_by_station: StationMetadata,
    selected_count: int,
    min_overlap_percent: float,
    min_overlap_days: int,
    max_elevation_difference_m: float,
    target_terrain: Mapping[str, str] | None = None,
    terrain_by_station: StationMetadata | None = None,
    pairwise_skill_by_station: StationMetadata | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    target_latitude = to_float(target_station["latitude"])
    target_longitude = to_float(target_station["longitude"])
    target_elevation = to_float(target_metadata.get("elevation", "0"))
    eligible_hubs: list[ScoredHub] = []
    rejected_hubs: list[ScoredHub] = []

    for hub in hubs:
        scored_hub = score_hub(
            target_latitude,
            target_longitude,
            target_elevation,
            target_dates,
            hub,
            hub_dates_by_station.get(hub["station_id"], set()),
            hub_metadata_by_station.get(hub["station_id"], {}),
            target_terrain or {},
            (terrain_by_station or {}).get(hub["station_id"], {}),
            (pairwise_skill_by_station or {}).get(hub["station_id"], {}),
        )

        if is_training_eligible(
            scored_hub,
            min_overlap_percent,
            min_overlap_days,
            max_elevation_difference_m,
        ):
            eligible_hubs.append(scored_hub)
        else:
            rejected_hubs.append(scored_hub)

    eligible_hubs.sort(key=lambda hub: (-hub.selection_score, hub.distance_km))
    rejected_hubs.sort(key=lambda hub: hub.distance_km)

    selected_hubs = eligible_hubs[:selected_count]
    return (
        scored_hubs_as_dicts(selected_hubs),
        scored_hubs_as_dicts(eligible_hubs),
        scored_hubs_as_dicts(rejected_hubs),
    )


def score_hub(
    target_latitude: float,
    target_longitude: float,
    target_elevation: float,
    target_dates: set[str],
    hub: StationRow,
    hub_dates: set[str],
    hub_metadata: Mapping[str, str],
    target_terrain: Mapping[str, str] | None = None,
    hub_terrain: Mapping[str, str] | None = None,
    pairwise_skill: Mapping[str, str] | None = None,
) -> ScoredHub:
    overlap_days = len(target_dates.intersection(hub_dates))
    overlap_percent = 0.0

    if target_dates:
        overlap_percent = overlap_days / len(target_dates) * 100

    distance_km = calculate_distance_km(
        target_latitude,
        target_longitude,
        to_float(hub["latitude"]),
        to_float(hub["longitude"]),
    )
    elevation_difference_m = abs(
        target_elevation - to_float(hub_metadata.get("elevation", "0"))
    )
    similarity = score_physical_similarity(
        distance_km,
        elevation_difference_m,
        target_terrain or {},
        hub_terrain or {},
        overlap_percent,
        pairwise_skill or {},
    )

    return ScoredHub(
        station_id=hub["station_id"],
        station_name=hub_metadata.get("station_name", "Unknown station"),
        distance_km=distance_km,
        elevation_difference_m=elevation_difference_m,
        overlap_days=overlap_days,
        overlap_percent=overlap_percent,
        selection_score=similarity["selection_score"],
        physical_similarity_score=similarity["physical_similarity_score"],
        distance_score=similarity["distance_score"],
        elevation_score=similarity["elevation_score"],
        terrain_position_score=similarity["terrain_position_score"],
        relief_score=similarity["relief_score"],
        slope_score=similarity["slope_score"],
        aspect_score=similarity["aspect_score"],
        **coerce_pairwise_skill_fields(pairwise_skill or {}),
        usable_period=f"{hub['usable_temp_start']}-{hub['usable_temp_end']}",
    )


def decay_score(delta: float, scale: float) -> float:
    if delta < 0:
        delta = abs(delta)

    return 100.0 * math.exp(-delta / scale)


def terrain_delta_score(
    target_terrain: Mapping[str, str],
    hub_terrain: Mapping[str, str],
    column: str,
    scale: float,
) -> float:
    target_value = to_optional_float(target_terrain.get(column))
    hub_value = to_optional_float(hub_terrain.get(column))

    if target_value is None or hub_value is None:
        return 50.0

    return decay_score(abs(target_value - hub_value), scale)


def aspect_similarity_score(
    target_terrain: Mapping[str, str],
    hub_terrain: Mapping[str, str],
) -> float:
    target_sin = to_optional_float(target_terrain.get("aspect_sin"))
    target_cos = to_optional_float(target_terrain.get("aspect_cos"))
    hub_sin = to_optional_float(hub_terrain.get("aspect_sin"))
    hub_cos = to_optional_float(hub_terrain.get("aspect_cos"))

    if None in (target_sin, target_cos, hub_sin, hub_cos):
        return 50.0

    dot_product = max(-1.0, min(1.0, target_sin * hub_sin + target_cos * hub_cos))
    return (dot_product + 1.0) * 50.0


def score_physical_similarity(
    distance_km: float,
    elevation_difference_m: float,
    target_terrain: Mapping[str, str],
    hub_terrain: Mapping[str, str],
    overlap_percent: float,
    pairwise_skill: Mapping[str, str] | None = None,
) -> dict[str, float]:
    distance_score = decay_score(distance_km, 150.0)
    elevation_score = decay_score(elevation_difference_m, 500.0)
    terrain_position_score = terrain_delta_score(
        target_terrain,
        hub_terrain,
        "terrain_position_index_m",
        120.0,
    )
    relief_score = terrain_delta_score(
        target_terrain,
        hub_terrain,
        "local_relief_m",
        600.0,
    )
    slope_score = terrain_delta_score(
        target_terrain,
        hub_terrain,
        "slope_degrees",
        30.0,
    )
    aspect_score = aspect_similarity_score(target_terrain, hub_terrain)
    physical_similarity_score = (
        0.30 * distance_score
        + 0.30 * elevation_score
        + 0.15 * terrain_position_score
        + 0.10 * relief_score
        + 0.10 * slope_score
        + 0.05 * aspect_score
    )
    bounded_overlap_score = max(0.0, min(100.0, overlap_percent))
    pair_skill_score = to_optional_float((pairwise_skill or {}).get("pair_skill_score"))

    if pair_skill_score is None:
        selection_score = (
            0.85 * physical_similarity_score
            + 0.15 * bounded_overlap_score
        )
    else:
        selection_score = (
            0.55 * pair_skill_score
            + 0.35 * physical_similarity_score
            + 0.10 * bounded_overlap_score
        )

    return {
        "selection_score": selection_score,
        "physical_similarity_score": physical_similarity_score,
        "distance_score": distance_score,
        "elevation_score": elevation_score,
        "terrain_position_score": terrain_position_score,
        "relief_score": relief_score,
        "slope_score": slope_score,
        "aspect_score": aspect_score,
    }


def coerce_pairwise_skill_fields(
    pairwise_skill: Mapping[str, str],
) -> dict[str, float | int | None]:
    coerced: dict[str, float | int | None] = {}

    for column in PAIRWISE_SKILL_COLUMNS:
        value = to_optional_float(pairwise_skill.get(column))

        if column == "pair_overlap_days":
            coerced[column] = int(value or 0)
        else:
            coerced[column] = value

    return coerced


def is_training_eligible(
    scored_hub: ScoredHub,
    min_overlap_percent: float,
    min_overlap_days: int,
    max_elevation_difference_m: float,
) -> bool:
    return (
        scored_hub.overlap_percent >= min_overlap_percent
        and scored_hub.overlap_days >= min_overlap_days
        and scored_hub.elevation_difference_m <= max_elevation_difference_m
    )


def scored_hubs_as_dicts(scored_hubs: Sequence[ScoredHub]) -> list[dict[str, object]]:
    return [scored_hub.as_dict() for scored_hub in scored_hubs]
