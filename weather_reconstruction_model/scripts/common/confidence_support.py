"""Calculate confidence-support scores from nearby station evidence and terrain context.

This shared logic keeps CLI scoring, grid building, and backend analysis consistent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from common.geo_utils import calculate_distance_km


SCORE_MIN = 0.0
SCORE_MAX = 100.0
DEFAULT_SCORE_VERSION = "confidence-support-v1"


DEFAULT_COMPONENT_WEIGHTS: dict[str, float] = {
    "stationCoverage": 0.20,
    "hubSupport": 0.15,
    "dataQuality": 0.10,
    "elevationMatch": 0.15,
    "terrainSimilarity": 0.15,
    "terrainComplexity": 0.10,
    "validationEvidence": 0.10,
    "extrapolationRisk": 0.05,
}


@dataclass(frozen=True)
class ConfidenceSupportConfig:
    """Tunable scoring contract for model-agnostic confidence support."""

    score_version: str = DEFAULT_SCORE_VERSION
    model_reference: str | None = None
    component_weights: Mapping[str, float] = field(
        default_factory=lambda: dict(DEFAULT_COMPONENT_WEIGHTS)
    )

    very_high_support_min: float = 85.0
    high_support_min: float = 70.0
    moderate_support_min: float = 50.0
    low_support_min: float = 30.0

    station_nearest_best_km: float = 5.0
    station_nearest_worst_km: float = 100.0
    station_close_radius_km: float = 25.0
    station_medium_radius_km: float = 50.0
    station_broad_radius_km: float = 100.0
    station_within_25km_target_count: int = 2
    station_within_50km_target_count: int = 5
    station_within_100km_target_count: int = 10

    hub_nearest_best_km: float = 25.0
    hub_nearest_worst_km: float = 200.0
    hub_close_radius_km: float = 50.0
    hub_medium_radius_km: float = 100.0
    hub_broad_radius_km: float = 200.0
    hub_within_50km_target_count: int = 2
    hub_within_100km_target_count: int = 5
    hub_within_200km_target_count: int = 10

    data_quality_radius_km: float = 100.0
    usable_years_best: float = 50.0
    usable_years_worst: float = 10.0
    recency_best_year: float = 2025.0
    recency_worst_year: float = 2000.0
    completeness_best: float = 0.95
    completeness_worst: float = 0.50

    elevation_useful_count: int = 5
    elevation_difference_best_m: float = 50.0
    elevation_difference_worst_m: float = 1000.0

    terrain_slope_best_degrees: float = 2.0
    terrain_slope_worst_degrees: float = 25.0
    terrain_relief_best_m: float = 50.0
    terrain_relief_worst_m: float = 1200.0
    terrain_tpi_best_abs_m: float = 10.0
    terrain_tpi_worst_abs_m: float = 500.0

    terrain_similarity_useful_count: int = 5
    terrain_similarity_elevation_best_m: float = 50.0
    terrain_similarity_elevation_worst_m: float = 1000.0
    terrain_similarity_slope_best_degrees: float = 2.0
    terrain_similarity_slope_worst_degrees: float = 20.0
    terrain_similarity_relief_best_m: float = 50.0
    terrain_similarity_relief_worst_m: float = 1000.0
    terrain_similarity_tpi_best_m: float = 25.0
    terrain_similarity_tpi_worst_m: float = 500.0

    validation_radius_km: float = 150.0
    validation_mae_best: float = 1.5
    validation_mae_worst: float = 5.0
    validation_rmse_best: float = 2.0
    validation_rmse_worst: float = 7.0
    validation_correlation_best: float = 0.99
    validation_correlation_worst: float = 0.90
    validation_test_rows_best: float = 365.0
    validation_test_rows_worst: float = 90.0
    validation_min_distance_weight: float = 0.10

    extrapolation_nearest_best_km: float = 10.0
    extrapolation_nearest_worst_km: float = 200.0
    extrapolation_support_radius_km: float = 150.0
    extrapolation_elevation_gap_worst_m: float = 1000.0


@dataclass(frozen=True)
class TerrainFeatures:
    dem_elevation_m: float | None = None
    slope_degrees: float | None = None
    aspect_sin: float | None = None
    aspect_cos: float | None = None
    local_relief_m: float | None = None
    terrain_position_index_m: float | None = None
    slope_degrees_r300m: float | None = None
    aspect_sin_r300m: float | None = None
    aspect_cos_r300m: float | None = None
    local_relief_m_r300m: float | None = None
    terrain_position_index_m_r300m: float | None = None
    slope_degrees_r990m: float | None = None
    aspect_sin_r990m: float | None = None
    aspect_cos_r990m: float | None = None
    local_relief_m_r990m: float | None = None
    terrain_position_index_m_r990m: float | None = None
    slope_degrees_r3000m: float | None = None
    aspect_sin_r3000m: float | None = None
    aspect_cos_r3000m: float | None = None
    local_relief_m_r3000m: float | None = None
    terrain_position_index_m_r3000m: float | None = None


@dataclass(frozen=True)
class SupportPoint:
    latitude: float
    longitude: float
    elevation_m: float | None = None
    terrain: TerrainFeatures | None = None


@dataclass(frozen=True)
class SupportStation:
    station_id: str
    station_name: str
    station_role: str
    latitude: float
    longitude: float
    elevation_m: float | None = None
    usable_years: float | None = None
    usable_start_year: int | None = None
    usable_end_year: int | None = None
    completeness: float | None = None
    terrain: TerrainFeatures | None = None


@dataclass(frozen=True)
class ValidationEvidence:
    """Model validation metrics associated with a known station or location."""

    station_id: str
    mae: float | None = None
    rmse: float | None = None
    correlation: float | None = None
    test_rows: int | None = None
    strict_pass: bool | None = None
    model_reference: str | None = None
    extra_metrics: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class NearbyStation:
    station: SupportStation
    distance_km: float
    elevation_difference_m: float | None = None


@dataclass(frozen=True)
class ConfidenceSupportResult:
    score_version: str
    model_reference: str | None
    status: str
    latitude: float
    longitude: float
    score: float
    label: str
    components: dict[str, float]
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    nearest_stations: list[NearbyStation] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "scoreVersion": self.score_version,
            "modelReference": self.model_reference,
            "status": self.status,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "score": self.score,
            "label": self.label,
            "components": self.components,
            "reasons": self.reasons,
            "warnings": self.warnings,
            "nearestStations": [
                {
                    "stationId": nearby.station.station_id,
                    "stationName": nearby.station.station_name,
                    "stationRole": nearby.station.station_role,
                    "distanceKm": nearby.distance_km,
                    "elevationDifferenceM": nearby.elevation_difference_m,
                }
                for nearby in self.nearest_stations
            ],
        }


def clamp(value: float, minimum: float = SCORE_MIN, maximum: float = SCORE_MAX) -> float:
    return max(minimum, min(maximum, value))


def linear_score(
    value: float,
    best_value: float,
    worst_value: float,
) -> float:
    """Return 100 at best_value or better, and 0 at worst_value or worse."""
    if worst_value == best_value:
        raise ValueError("best_value and worst_value must be different.")

    if best_value < worst_value:
        if value <= best_value:
            return SCORE_MAX
        if value >= worst_value:
            return SCORE_MIN
        return clamp(SCORE_MAX * (worst_value - value) / (worst_value - best_value))

    if value >= best_value:
        return SCORE_MAX
    if value <= worst_value:
        return SCORE_MIN
    return clamp(SCORE_MAX * (value - worst_value) / (best_value - worst_value))


def count_score(
    count: int,
    target_count: int,
) -> float:
    if target_count <= 0:
        raise ValueError("target_count must be positive.")

    return clamp(SCORE_MAX * count / target_count)


def label_for_score(
    score: float,
    config: ConfidenceSupportConfig | None = None,
) -> str:
    config = config or ConfidenceSupportConfig()

    if score >= config.very_high_support_min:
        return "Very high support"
    if score >= config.high_support_min:
        return "High support"
    if score >= config.moderate_support_min:
        return "Moderate support"
    if score >= config.low_support_min:
        return "Low support"
    return "Very low support"


def distance_between(point: SupportPoint, station: SupportStation) -> float:
    return calculate_distance_km(
        point.latitude,
        point.longitude,
        station.latitude,
        station.longitude,
    )


def elevation_difference(
    point: SupportPoint,
    station: SupportStation,
) -> float | None:
    point_elevation = point.elevation_m
    if point_elevation is None and point.terrain is not None:
        point_elevation = point.terrain.dem_elevation_m

    station_elevation = station.elevation_m
    if station_elevation is None and station.terrain is not None:
        station_elevation = station.terrain.dem_elevation_m

    if point_elevation is None or station_elevation is None:
        return None

    return abs(point_elevation - station_elevation)


def find_nearby_stations(
    point: SupportPoint,
    stations: Sequence[SupportStation],
    limit: int | None = None,
) -> list[NearbyStation]:
    nearby = [
        NearbyStation(
            station=station,
            distance_km=distance_between(point, station),
            elevation_difference_m=elevation_difference(point, station),
        )
        for station in stations
    ]
    nearby.sort(key=lambda item: item.distance_km)

    if limit is None:
        return nearby

    return nearby[:limit]


def stations_within_radius(
    nearby_stations: Sequence[NearbyStation],
    radius_km: float,
) -> list[NearbyStation]:
    return [
        nearby
        for nearby in nearby_stations
        if nearby.distance_km <= radius_km
    ]


def score_station_coverage(
    nearby_targets: Sequence[NearbyStation],
    config: ConfidenceSupportConfig,
) -> float:
    if not nearby_targets:
        return SCORE_MIN

    nearest_distance_score = linear_score(
        nearby_targets[0].distance_km,
        best_value=config.station_nearest_best_km,
        worst_value=config.station_nearest_worst_km,
    )
    nearby_25_score = count_score(
        len(stations_within_radius(nearby_targets, config.station_close_radius_km)),
        config.station_within_25km_target_count,
    )
    nearby_50_score = count_score(
        len(stations_within_radius(nearby_targets, config.station_medium_radius_km)),
        config.station_within_50km_target_count,
    )
    nearby_100_score = count_score(
        len(stations_within_radius(nearby_targets, config.station_broad_radius_km)),
        config.station_within_100km_target_count,
    )

    return weighted_average(
        {
            "nearest": nearest_distance_score,
            "within25": nearby_25_score,
            "within50": nearby_50_score,
            "within100": nearby_100_score,
        },
        {
            "nearest": 0.45,
            "within25": 0.20,
            "within50": 0.20,
            "within100": 0.15,
        },
    )


def score_hub_support(
    nearby_hubs: Sequence[NearbyStation],
    config: ConfidenceSupportConfig,
) -> float:
    if not nearby_hubs:
        return SCORE_MIN

    nearest_distance_score = linear_score(
        nearby_hubs[0].distance_km,
        best_value=config.hub_nearest_best_km,
        worst_value=config.hub_nearest_worst_km,
    )
    nearby_50_score = count_score(
        len(stations_within_radius(nearby_hubs, config.hub_close_radius_km)),
        config.hub_within_50km_target_count,
    )
    nearby_100_score = count_score(
        len(stations_within_radius(nearby_hubs, config.hub_medium_radius_km)),
        config.hub_within_100km_target_count,
    )
    nearby_200_score = count_score(
        len(stations_within_radius(nearby_hubs, config.hub_broad_radius_km)),
        config.hub_within_200km_target_count,
    )

    return weighted_average(
        {
            "nearest": nearest_distance_score,
            "within50": nearby_50_score,
            "within100": nearby_100_score,
            "within200": nearby_200_score,
        },
        {
            "nearest": 0.40,
            "within50": 0.20,
            "within100": 0.25,
            "within200": 0.15,
        },
    )


def score_data_quality(
    nearby_stations: Sequence[NearbyStation],
    config: ConfidenceSupportConfig,
) -> float | None:
    useful_stations = stations_within_radius(
        nearby_stations,
        config.data_quality_radius_km,
    )
    station_scores = []

    for nearby in useful_stations:
        station = nearby.station
        pieces = {}
        weights = {}

        if station.usable_years is not None:
            pieces["usableYears"] = linear_score(
                station.usable_years,
                best_value=config.usable_years_best,
                worst_value=config.usable_years_worst,
            )
            weights["usableYears"] = 0.50

        if station.usable_end_year is not None:
            pieces["recency"] = linear_score(
                station.usable_end_year,
                best_value=config.recency_best_year,
                worst_value=config.recency_worst_year,
            )
            weights["recency"] = 0.25

        if station.completeness is not None:
            pieces["completeness"] = linear_score(
                station.completeness,
                best_value=config.completeness_best,
                worst_value=config.completeness_worst,
            )
            weights["completeness"] = 0.25

        if pieces:
            station_scores.append(weighted_average(pieces, weights))

    if not station_scores:
        return None

    return sum(station_scores) / len(station_scores)


def score_elevation_match(
    nearby_stations: Sequence[NearbyStation],
    config: ConfidenceSupportConfig,
) -> float | None:
    elevation_differences = [
        nearby.elevation_difference_m
        for nearby in nearby_stations[:config.elevation_useful_count]
        if nearby.elevation_difference_m is not None
    ]

    if not elevation_differences:
        return None

    elevation_scores = [
        linear_score(
            difference,
            best_value=config.elevation_difference_best_m,
            worst_value=config.elevation_difference_worst_m,
        )
        for difference in elevation_differences
    ]

    return sum(elevation_scores) / len(elevation_scores)


def score_terrain_complexity(
    terrain: TerrainFeatures | None,
    config: ConfidenceSupportConfig,
) -> float | None:
    if terrain is None:
        return None

    pieces = {}
    weights = {}

    slope = first_available(
        terrain.slope_degrees_r990m,
        terrain.slope_degrees_r300m,
        terrain.slope_degrees,
    )
    if slope is not None:
        pieces["slope"] = linear_score(
            slope,
            best_value=config.terrain_slope_best_degrees,
            worst_value=config.terrain_slope_worst_degrees,
        )
        weights["slope"] = 0.35

    relief = first_available(
        terrain.local_relief_m_r3000m,
        terrain.local_relief_m_r990m,
        terrain.local_relief_m,
    )
    if relief is not None:
        pieces["relief"] = linear_score(
            relief,
            best_value=config.terrain_relief_best_m,
            worst_value=config.terrain_relief_worst_m,
        )
        weights["relief"] = 0.45

    tpi = first_available(
        terrain.terrain_position_index_m_r990m,
        terrain.terrain_position_index_m_r300m,
        terrain.terrain_position_index_m,
    )
    if tpi is not None:
        pieces["terrainPosition"] = linear_score(
            abs(tpi),
            best_value=config.terrain_tpi_best_abs_m,
            worst_value=config.terrain_tpi_worst_abs_m,
        )
        weights["terrainPosition"] = 0.20

    if not pieces:
        return None

    return weighted_average(pieces, weights)


def score_terrain_similarity(
    point: SupportPoint,
    nearby_stations: Sequence[NearbyStation],
    config: ConfidenceSupportConfig,
) -> float | None:
    if point.terrain is None:
        return None

    station_scores = []

    for nearby in nearby_stations[:config.terrain_similarity_useful_count]:
        station_terrain = nearby.station.terrain
        if station_terrain is None:
            continue

        pieces = {}
        weights = {}

        if point.terrain.dem_elevation_m is not None and station_terrain.dem_elevation_m is not None:
            pieces["elevation"] = linear_score(
                abs(point.terrain.dem_elevation_m - station_terrain.dem_elevation_m),
                best_value=config.terrain_similarity_elevation_best_m,
                worst_value=config.terrain_similarity_elevation_worst_m,
            )
            weights["elevation"] = 0.35

        point_slope = first_available(point.terrain.slope_degrees_r990m, point.terrain.slope_degrees)
        station_slope = first_available(station_terrain.slope_degrees_r990m, station_terrain.slope_degrees)
        if point_slope is not None and station_slope is not None:
            pieces["slope"] = linear_score(
                abs(point_slope - station_slope),
                best_value=config.terrain_similarity_slope_best_degrees,
                worst_value=config.terrain_similarity_slope_worst_degrees,
            )
            weights["slope"] = 0.20

        point_relief = first_available(point.terrain.local_relief_m_r3000m, point.terrain.local_relief_m)
        station_relief = first_available(station_terrain.local_relief_m_r3000m, station_terrain.local_relief_m)
        if point_relief is not None and station_relief is not None:
            pieces["relief"] = linear_score(
                abs(point_relief - station_relief),
                best_value=config.terrain_similarity_relief_best_m,
                worst_value=config.terrain_similarity_relief_worst_m,
            )
            weights["relief"] = 0.25

        point_tpi = first_available(
            point.terrain.terrain_position_index_m_r990m,
            point.terrain.terrain_position_index_m,
        )
        station_tpi = first_available(
            station_terrain.terrain_position_index_m_r990m,
            station_terrain.terrain_position_index_m,
        )
        if point_tpi is not None and station_tpi is not None:
            pieces["terrainPosition"] = linear_score(
                abs(point_tpi - station_tpi),
                best_value=config.terrain_similarity_tpi_best_m,
                worst_value=config.terrain_similarity_tpi_worst_m,
            )
            weights["terrainPosition"] = 0.20

        if pieces:
            station_scores.append(weighted_average(pieces, weights))

    if not station_scores:
        return None

    return sum(station_scores) / len(station_scores)


def score_validation_evidence(
    nearby_stations: Sequence[NearbyStation],
    validation_by_station_id: Mapping[str, ValidationEvidence],
    config: ConfidenceSupportConfig,
) -> float | None:
    validation_scores = []

    for nearby in stations_within_radius(
        nearby_stations,
        config.validation_radius_km,
    ):
        evidence = validation_by_station_id.get(nearby.station.station_id)
        if evidence is None:
            continue

        pieces = {}
        weights = {}

        if evidence.mae is not None:
            pieces["mae"] = linear_score(
                evidence.mae,
                best_value=config.validation_mae_best,
                worst_value=config.validation_mae_worst,
            )
            weights["mae"] = 0.40

        if evidence.rmse is not None:
            pieces["rmse"] = linear_score(
                evidence.rmse,
                best_value=config.validation_rmse_best,
                worst_value=config.validation_rmse_worst,
            )
            weights["rmse"] = 0.30

        if evidence.correlation is not None:
            pieces["correlation"] = linear_score(
                evidence.correlation,
                best_value=config.validation_correlation_best,
                worst_value=config.validation_correlation_worst,
            )
            weights["correlation"] = 0.20

        if evidence.test_rows is not None:
            pieces["testRows"] = linear_score(
                evidence.test_rows,
                best_value=config.validation_test_rows_best,
                worst_value=config.validation_test_rows_worst,
            )
            weights["testRows"] = 0.10

        if pieces:
            distance_weight = max(
                config.validation_min_distance_weight,
                linear_score(
                    nearby.distance_km,
                    0.0,
                    config.validation_radius_km,
                ) / 100.0,
            )
            validation_scores.append(weighted_average(pieces, weights) * distance_weight)

    if not validation_scores:
        return None

    return clamp(sum(validation_scores) / len(validation_scores))


def score_extrapolation_risk(
    point: SupportPoint,
    nearby_stations: Sequence[NearbyStation],
    config: ConfidenceSupportConfig,
) -> float:
    if not nearby_stations:
        return SCORE_MIN

    nearest_distance_score = linear_score(
        nearby_stations[0].distance_km,
        best_value=config.extrapolation_nearest_best_km,
        worst_value=config.extrapolation_nearest_worst_km,
    )

    quadrant_score = score_station_quadrant_coverage(
        point,
        nearby_stations,
        config.extrapolation_support_radius_km,
    )

    elevation_score = None
    point_elevation = point.elevation_m
    if point_elevation is None and point.terrain is not None:
        point_elevation = point.terrain.dem_elevation_m

    station_elevations = [
        nearby.station.elevation_m
        for nearby in nearby_stations
        if (
            nearby.distance_km <= config.extrapolation_support_radius_km
            and nearby.station.elevation_m is not None
        )
    ]

    if point_elevation is not None and station_elevations:
        min_elevation = min(station_elevations)
        max_elevation = max(station_elevations)
        if min_elevation <= point_elevation <= max_elevation:
            elevation_score = SCORE_MAX
        else:
            elevation_gap = min(
                abs(point_elevation - min_elevation),
                abs(point_elevation - max_elevation),
            )
            elevation_score = linear_score(
                elevation_gap,
                best_value=0.0,
                worst_value=config.extrapolation_elevation_gap_worst_m,
            )

    pieces = {
        "nearest": nearest_distance_score,
        "quadrants": quadrant_score,
    }
    weights = {
        "nearest": 0.45,
        "quadrants": 0.35,
    }

    if elevation_score is not None:
        pieces["elevationRange"] = elevation_score
        weights["elevationRange"] = 0.20

    return weighted_average(pieces, weights)


def score_station_quadrant_coverage(
    point: SupportPoint,
    nearby_stations: Sequence[NearbyStation],
    radius_km: float,
) -> float:
    quadrants = set()

    for nearby in nearby_stations:
        if nearby.distance_km > radius_km:
            continue

        lat_delta = nearby.station.latitude - point.latitude
        lon_delta = nearby.station.longitude - point.longitude
        if lat_delta >= 0 and lon_delta >= 0:
            quadrants.add("ne")
        elif lat_delta >= 0 and lon_delta < 0:
            quadrants.add("nw")
        elif lat_delta < 0 and lon_delta >= 0:
            quadrants.add("se")
        else:
            quadrants.add("sw")

    return count_score(len(quadrants), 4)


def calculate_confidence_support(
    point: SupportPoint,
    target_stations: Sequence[SupportStation],
    hub_stations: Sequence[SupportStation],
    validation_by_station_id: Mapping[str, ValidationEvidence] | None = None,
    config: ConfidenceSupportConfig | None = None,
    component_weights: Mapping[str, float] | None = None,
) -> ConfidenceSupportResult:
    validation_by_station_id = validation_by_station_id or {}
    config = config or ConfidenceSupportConfig()
    component_weights = component_weights or config.component_weights

    nearby_targets = find_nearby_stations(point, target_stations)
    nearby_hubs = find_nearby_stations(point, hub_stations)
    all_nearby = sorted(
        [*nearby_targets, *nearby_hubs],
        key=lambda item: item.distance_km,
    )

    components: dict[str, float] = {
        "stationCoverage": score_station_coverage(nearby_targets, config),
        "hubSupport": score_hub_support(nearby_hubs, config),
        "extrapolationRisk": score_extrapolation_risk(point, all_nearby, config),
    }

    optional_components = {
        "dataQuality": score_data_quality(all_nearby, config),
        "elevationMatch": score_elevation_match(all_nearby, config),
        "terrainSimilarity": score_terrain_similarity(point, all_nearby, config),
        "terrainComplexity": score_terrain_complexity(point.terrain, config),
        "validationEvidence": score_validation_evidence(
            all_nearby,
            validation_by_station_id,
            config,
        ),
    }

    warnings = []
    for component_name, component_score in optional_components.items():
        if component_score is None:
            warnings.append(f"{component_name} could not be calculated from available inputs.")
            continue
        components[component_name] = component_score

    score = weighted_average(components, component_weights)
    reasons = build_reasons(
        nearby_targets=nearby_targets,
        nearby_hubs=nearby_hubs,
        components=components,
        config=config,
    )

    return ConfidenceSupportResult(
        score_version=config.score_version,
        model_reference=config.model_reference,
        status="ok",
        latitude=point.latitude,
        longitude=point.longitude,
        score=round(score, 2),
        label=label_for_score(score, config),
        components={
            key: round(value, 2)
            for key, value in components.items()
        },
        reasons=reasons,
        warnings=warnings,
        nearest_stations=all_nearby[:5],
    )


def build_reasons(
    nearby_targets: Sequence[NearbyStation],
    nearby_hubs: Sequence[NearbyStation],
    components: Mapping[str, float],
    config: ConfidenceSupportConfig | None = None,
) -> list[str]:
    config = config or ConfidenceSupportConfig()
    reasons = []

    if nearby_targets:
        reasons.append(f"Nearest target station is {nearby_targets[0].distance_km:.1f} km away.")
        within_medium_radius = len(stations_within_radius(
            nearby_targets,
            config.station_medium_radius_km,
        ))
        reasons.append(
            f"{within_medium_radius} target stations are within "
            f"{config.station_medium_radius_km:g} km."
        )
    else:
        reasons.append("No target stations are available for station coverage scoring.")

    if nearby_hubs:
        reasons.append(f"Nearest hub station is {nearby_hubs[0].distance_km:.1f} km away.")
        within_medium_radius = len(stations_within_radius(
            nearby_hubs,
            config.hub_medium_radius_km,
        ))
        reasons.append(
            f"{within_medium_radius} hub stations are within "
            f"{config.hub_medium_radius_km:g} km."
        )
    else:
        reasons.append("No hub stations are available for hub support scoring.")

    for component_name, component_score in components.items():
        if component_score >= config.very_high_support_min:
            reasons.append(f"{component_name} is very strong.")
        elif component_score < config.low_support_min:
            reasons.append(f"{component_name} is weak and reduces confidence.")

    return reasons


def weighted_average(
    values: Mapping[str, float],
    weights: Mapping[str, float],
) -> float:
    weighted_total = 0.0
    used_weight_total = 0.0

    for key, value in values.items():
        weight = weights.get(key)
        if weight is None or weight <= 0:
            continue

        weighted_total += clamp(value) * weight
        used_weight_total += weight

    if used_weight_total == 0:
        return SCORE_MIN

    return clamp(weighted_total / used_weight_total)


def first_available(*values: float | None) -> float | None:
    for value in values:
        if value is not None:
            return value

    return None
