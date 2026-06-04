from __future__ import annotations

from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from common.confidence_support import (
    ConfidenceSupportConfig,
    SupportPoint,
    SupportStation,
    TerrainFeatures,
    ValidationEvidence,
    calculate_confidence_support,
    score_terrain_complexity,
)


def assert_between(value: float, minimum: float, maximum: float) -> None:
    if value < minimum or value > maximum:
        raise AssertionError(f"Expected {value} to be between {minimum} and {maximum}.")


def assert_greater(actual: float, expected_lower_bound: float) -> None:
    if actual <= expected_lower_bound:
        raise AssertionError(f"Expected {actual} to be greater than {expected_lower_bound}.")


def assert_result_is_bounded(result) -> None:
    assert_between(result.score, 0.0, 100.0)
    for component_name, component_score in result.components.items():
        assert_between(component_score, 0.0, 100.0)
        if not component_name:
            raise AssertionError("Component names should not be blank.")


def simple_terrain(elevation_m: float = 1600.0) -> TerrainFeatures:
    return TerrainFeatures(
        dem_elevation_m=elevation_m,
        slope_degrees=2.5,
        local_relief_m=60.0,
        terrain_position_index_m=4.0,
        slope_degrees_r990m=3.0,
        local_relief_m_r3000m=85.0,
        terrain_position_index_m_r990m=8.0,
    )


def rugged_terrain(elevation_m: float = 2600.0) -> TerrainFeatures:
    return TerrainFeatures(
        dem_elevation_m=elevation_m,
        slope_degrees=28.0,
        local_relief_m=900.0,
        terrain_position_index_m=260.0,
        slope_degrees_r990m=24.0,
        local_relief_m_r3000m=1300.0,
        terrain_position_index_m_r990m=420.0,
    )


def support_point() -> SupportPoint:
    return SupportPoint(
        latitude=39.75,
        longitude=-105.00,
        elevation_m=1600.0,
        terrain=simple_terrain(1600.0),
    )


def station(
    station_id: str,
    role: str,
    latitude: float,
    longitude: float,
    elevation_m: float = 1600.0,
    terrain: TerrainFeatures | None = None,
    usable_years: float = 50.0,
    usable_end_year: int = 2025,
    completeness: float = 0.95,
) -> SupportStation:
    return SupportStation(
        station_id=station_id,
        station_name=f"{station_id} Station",
        station_role=role,
        latitude=latitude,
        longitude=longitude,
        elevation_m=elevation_m,
        usable_years=usable_years,
        usable_start_year=usable_end_year - int(usable_years),
        usable_end_year=usable_end_year,
        completeness=completeness,
        terrain=terrain or simple_terrain(elevation_m),
    )


def near_target(station_id: str = "T_NEAR") -> SupportStation:
    return station(
        station_id,
        "target",
        39.76,
        -105.01,
        elevation_m=1590.0,
        terrain=simple_terrain(1590.0),
    )


def near_hub(station_id: str = "H_NEAR") -> SupportStation:
    return station(
        station_id,
        "hub",
        39.80,
        -105.05,
        elevation_m=1610.0,
        terrain=simple_terrain(1610.0),
        usable_years=65.0,
    )


def test_result_contract_and_config_metadata() -> None:
    config = ConfidenceSupportConfig(
        score_version="confidence-support-test-v2",
        model_reference="future-model-fixture",
    )
    result = calculate_confidence_support(
        support_point(),
        target_stations=[
            near_target("T1"),
            station("T2", "target", 39.74, -105.02),
            station("T3", "target", 39.77, -104.98),
        ],
        hub_stations=[
            near_hub("H1"),
            station("H2", "hub", 39.90, -105.10, usable_years=70.0),
        ],
        validation_by_station_id={
            "T1": ValidationEvidence(
                station_id="T1",
                mae=1.2,
                rmse=1.8,
                correlation=0.995,
                test_rows=500,
                strict_pass=True,
                model_reference="future-model-fixture",
                extra_metrics={"p90_abs_error": 2.4},
            ),
        },
        config=config,
    )
    data = result.as_dict()

    assert data["scoreVersion"] == "confidence-support-test-v2"
    assert data["modelReference"] == "future-model-fixture"
    assert data["status"] == "ok"
    assert data["nearestStations"]
    assert result.reasons
    assert_result_is_bounded(result)


def test_near_station_scores_higher_than_far_station() -> None:
    point = support_point()
    near_result = calculate_confidence_support(
        point,
        target_stations=[near_target()],
        hub_stations=[],
        component_weights={"stationCoverage": 1.0},
    )
    far_result = calculate_confidence_support(
        point,
        target_stations=[
            station("T_FAR", "target", 41.50, -107.00, terrain=simple_terrain(1600.0)),
        ],
        hub_stations=[],
        component_weights={"stationCoverage": 1.0},
    )

    assert_greater(near_result.score, far_result.score)
    assert_result_is_bounded(near_result)
    assert_result_is_bounded(far_result)


def test_near_hub_support_scores_higher_than_far_hub_support() -> None:
    point = support_point()
    near_result = calculate_confidence_support(
        point,
        target_stations=[],
        hub_stations=[near_hub()],
        component_weights={"hubSupport": 1.0},
    )
    far_result = calculate_confidence_support(
        point,
        target_stations=[],
        hub_stations=[
            station("H_FAR", "hub", 42.00, -108.00, usable_years=65.0),
        ],
        component_weights={"hubSupport": 1.0},
    )

    assert_greater(near_result.score, far_result.score)


def test_elevation_mismatch_lowers_support() -> None:
    point = support_point()
    matched_result = calculate_confidence_support(
        point,
        target_stations=[near_target()],
        hub_stations=[],
        component_weights={"elevationMatch": 1.0},
    )
    mismatched_result = calculate_confidence_support(
        point,
        target_stations=[
            station(
                "T_HIGH",
                "target",
                39.76,
                -105.01,
                elevation_m=2850.0,
                terrain=simple_terrain(2850.0),
            ),
        ],
        hub_stations=[],
        component_weights={"elevationMatch": 1.0},
    )

    assert_greater(matched_result.score, mismatched_result.score)


def test_terrain_similarity_and_complexity_are_scored_separately() -> None:
    point = support_point()
    similar_result = calculate_confidence_support(
        point,
        target_stations=[near_target()],
        hub_stations=[],
        component_weights={"terrainSimilarity": 1.0},
    )
    dissimilar_result = calculate_confidence_support(
        point,
        target_stations=[
            station(
                "T_RUGGED",
                "target",
                39.76,
                -105.01,
                elevation_m=2600.0,
                terrain=rugged_terrain(2600.0),
            ),
        ],
        hub_stations=[],
        component_weights={"terrainSimilarity": 1.0},
    )

    simple_complexity_score = score_terrain_complexity(
        simple_terrain(),
        ConfidenceSupportConfig(),
    )
    rugged_complexity_score = score_terrain_complexity(
        rugged_terrain(),
        ConfidenceSupportConfig(),
    )

    assert_greater(similar_result.score, dissimilar_result.score)
    assert simple_complexity_score is not None
    assert rugged_complexity_score is not None
    assert_greater(simple_complexity_score, rugged_complexity_score)


def test_validation_evidence_can_improve_support_for_future_models() -> None:
    point = support_point()
    stations = [near_target("T_VALIDATED")]
    good_result = calculate_confidence_support(
        point,
        target_stations=stations,
        hub_stations=[],
        validation_by_station_id={
            "T_VALIDATED": ValidationEvidence(
                station_id="T_VALIDATED",
                mae=1.1,
                rmse=1.7,
                correlation=0.996,
                test_rows=500,
                model_reference="strong-model",
            ),
        },
        component_weights={"validationEvidence": 1.0},
    )
    weak_result = calculate_confidence_support(
        point,
        target_stations=stations,
        hub_stations=[],
        validation_by_station_id={
            "T_VALIDATED": ValidationEvidence(
                station_id="T_VALIDATED",
                mae=6.0,
                rmse=8.0,
                correlation=0.85,
                test_rows=40,
                model_reference="weak-model",
            ),
        },
        component_weights={"validationEvidence": 1.0},
    )

    assert_greater(good_result.score, weak_result.score)


def test_missing_optional_inputs_warn_without_breaking_result() -> None:
    result = calculate_confidence_support(
        SupportPoint(latitude=39.75, longitude=-105.00),
        target_stations=[
            station(
                "T_NO_TERRAIN",
                "target",
                39.76,
                -105.01,
                elevation_m=1600.0,
                terrain=None,
            ),
        ],
        hub_stations=[],
    )

    assert_result_is_bounded(result)
    assert result.warnings


def main() -> None:
    test_result_contract_and_config_metadata()
    test_near_station_scores_higher_than_far_station()
    test_near_hub_support_scores_higher_than_far_hub_support()
    test_elevation_mismatch_lowers_support()
    test_terrain_similarity_and_complexity_are_scored_separately()
    test_validation_evidence_can_improve_support_for_future_models()
    test_missing_optional_inputs_warn_without_breaking_result()
    print("confidence support tests passed")


if __name__ == "__main__":
    main()
