"""Test station-selection pipeline helpers.

The checks cover physical similarity, training eligibility, and hub scoring rules."""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from pipeline.station_selection import (
    find_training_eligible_hubs,
    is_training_eligible,
    score_hub,
    score_physical_similarity,
)
from pipeline.training_tables import build_shared_date_rows


def assert_close(actual: float, expected: float, tolerance: float = 1e-9) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"Expected {expected}, got {actual}")


def make_hub(station_id: str, latitude: str, elevation_start: str = "1900") -> dict[str, str]:
    return {
        "station_id": station_id,
        "latitude": latitude,
        "longitude": "-105.0000",
        "usable_temp_start": elevation_start,
        "usable_temp_end": "2026",
    }


def test_score_hub_calculates_overlap_distance_and_elevation_difference() -> None:
    target_station = {
        "station_id": "TARGET",
        "latitude": "40.0000",
        "longitude": "-105.0000",
    }
    hub = make_hub("HUB_A", "40.1000")
    scored_hub = score_hub(
        40.0,
        -105.0,
        1600.0,
        {"2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"},
        hub,
        {"2024-01-01", "2024-01-03"},
        {"station_name": "Hub A", "elevation": "1700"},
    )

    assert target_station["station_id"] == "TARGET"
    assert scored_hub.station_id == "HUB_A"
    assert scored_hub.station_name == "Hub A"
    assert_close(scored_hub.overlap_percent, 50.0)
    assert scored_hub.overlap_days == 2
    assert_close(scored_hub.elevation_difference_m, 100.0)
    assert 0.0 < scored_hub.selection_score <= 100.0
    assert 0.0 < scored_hub.physical_similarity_score <= 100.0
    assert scored_hub.pair_overlap_days == 0
    assert scored_hub.pair_skill_score is None
    assert 11.0 < scored_hub.distance_km < 12.0


def test_is_training_eligible_applies_overlap_days_and_elevation_thresholds() -> None:
    scored_hub = score_hub(
        40.0,
        -105.0,
        1600.0,
        {"2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"},
        make_hub("HUB_A", "40.1000"),
        {"2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"},
        {"station_name": "Hub A", "elevation": "1700"},
    )

    assert is_training_eligible(scored_hub, 90.0, 4, 150.0)
    assert not is_training_eligible(scored_hub, 100.1, 4, 150.0)
    assert not is_training_eligible(scored_hub, 90.0, 5, 150.0)
    assert not is_training_eligible(scored_hub, 90.0, 4, 50.0)


def test_find_training_eligible_hubs_returns_nearest_eligible_hubs() -> None:
    target_station = {
        "station_id": "TARGET",
        "latitude": "40.0000",
        "longitude": "-105.0000",
    }
    hubs = [
        make_hub("TOO_FAR_ELEVATION", "40.0100"),
        make_hub("NEAR_ELIGIBLE", "40.0200"),
        make_hub("FAR_ELIGIBLE", "40.3000"),
        make_hub("LOW_OVERLAP", "40.0050"),
    ]
    target_dates = {"2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"}
    hub_dates_by_station = {
        "TOO_FAR_ELEVATION": target_dates,
        "NEAR_ELIGIBLE": target_dates,
        "FAR_ELIGIBLE": target_dates,
        "LOW_OVERLAP": {"2024-01-01"},
    }
    hub_metadata_by_station = {
        "TOO_FAR_ELEVATION": {"station_name": "Too High", "elevation": "2500"},
        "NEAR_ELIGIBLE": {"station_name": "Near", "elevation": "1650"},
        "FAR_ELIGIBLE": {"station_name": "Far", "elevation": "1625"},
        "LOW_OVERLAP": {"station_name": "Sparse", "elevation": "1600"},
    }

    selected_hubs, eligible_hubs, rejected_hubs = find_training_eligible_hubs(
        target_station,
        hubs,
        target_dates,
        {"elevation": "1600"},
        hub_dates_by_station,
        hub_metadata_by_station,
        1,
        90.0,
        4,
        500.0,
    )

    assert [hub["station_id"] for hub in selected_hubs] == ["NEAR_ELIGIBLE"]
    assert [hub["station_id"] for hub in eligible_hubs] == ["NEAR_ELIGIBLE", "FAR_ELIGIBLE"]
    assert {hub["station_id"] for hub in rejected_hubs} == {"LOW_OVERLAP", "TOO_FAR_ELEVATION"}


def test_find_training_eligible_hubs_prefers_physical_similarity_over_distance() -> None:
    target_station = {
        "station_id": "TARGET",
        "latitude": "40.0000",
        "longitude": "-105.0000",
    }
    hubs = [
        make_hub("NEAR_TERRAIN_MISMATCH", "40.0100"),
        make_hub("FAR_TERRAIN_MATCH", "40.1500"),
    ]
    target_dates = {"2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"}
    hub_dates_by_station = {
        "NEAR_TERRAIN_MISMATCH": target_dates,
        "FAR_TERRAIN_MATCH": target_dates,
    }
    hub_metadata_by_station = {
        "NEAR_TERRAIN_MISMATCH": {"station_name": "Near Mismatch", "elevation": "2200"},
        "FAR_TERRAIN_MATCH": {"station_name": "Far Match", "elevation": "1610"},
    }
    target_terrain = {
        "terrain_position_index_m": "-30",
        "local_relief_m": "120",
        "slope_degrees": "4",
        "aspect_sin": "0",
        "aspect_cos": "1",
    }
    terrain_by_station = {
        "NEAR_TERRAIN_MISMATCH": {
            "terrain_position_index_m": "250",
            "local_relief_m": "900",
            "slope_degrees": "24",
            "aspect_sin": "0",
            "aspect_cos": "-1",
        },
        "FAR_TERRAIN_MATCH": {
            "terrain_position_index_m": "-25",
            "local_relief_m": "135",
            "slope_degrees": "5",
            "aspect_sin": "0",
            "aspect_cos": "1",
        },
    }

    selected_hubs, eligible_hubs, rejected_hubs = find_training_eligible_hubs(
        target_station,
        hubs,
        target_dates,
        {"elevation": "1600"},
        hub_dates_by_station,
        hub_metadata_by_station,
        1,
        90.0,
        4,
        800.0,
        target_terrain,
        terrain_by_station,
    )

    assert [hub["station_id"] for hub in selected_hubs] == ["FAR_TERRAIN_MATCH"]
    assert [hub["station_id"] for hub in eligible_hubs] == [
        "FAR_TERRAIN_MATCH",
        "NEAR_TERRAIN_MISMATCH",
    ]
    assert rejected_hubs == []


def test_find_training_eligible_hubs_prefers_historical_skill_when_available() -> None:
    target_station = {
        "station_id": "TARGET",
        "latitude": "40.0000",
        "longitude": "-105.0000",
    }
    hubs = [
        make_hub("PHYSICAL_ONLY", "40.0100"),
        make_hub("HISTORICALLY_STRONG", "40.0400"),
    ]
    target_dates = {"2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"}
    hub_dates_by_station = {
        "PHYSICAL_ONLY": target_dates,
        "HISTORICALLY_STRONG": target_dates,
    }
    hub_metadata_by_station = {
        "PHYSICAL_ONLY": {"station_name": "Physical", "elevation": "1600"},
        "HISTORICALLY_STRONG": {"station_name": "Historical", "elevation": "1700"},
    }
    pairwise_skill_by_station = {
        "PHYSICAL_ONLY": {
            "pair_overlap_days": "1500",
            "pair_corr": "0.60",
            "pair_mae": "5.0",
            "pair_rmse": "6.0",
            "pair_mean_bias": "3.0",
            "pair_abs_mean_bias": "3.0",
            "pair_skill_score": "45.0",
        },
        "HISTORICALLY_STRONG": {
            "pair_overlap_days": "1500",
            "pair_corr": "0.99",
            "pair_mae": "0.9",
            "pair_rmse": "1.3",
            "pair_mean_bias": "0.2",
            "pair_abs_mean_bias": "0.2",
            "pair_skill_score": "90.0",
        },
    }

    selected_hubs, eligible_hubs, rejected_hubs = find_training_eligible_hubs(
        target_station,
        hubs,
        target_dates,
        {"elevation": "1600"},
        hub_dates_by_station,
        hub_metadata_by_station,
        1,
        90.0,
        4,
        500.0,
        {},
        {},
        pairwise_skill_by_station,
    )

    assert [hub["station_id"] for hub in selected_hubs] == ["HISTORICALLY_STRONG"]
    assert selected_hubs[0]["pair_skill_score"] == 90.0
    assert [hub["station_id"] for hub in eligible_hubs] == [
        "HISTORICALLY_STRONG",
        "PHYSICAL_ONLY",
    ]
    assert rejected_hubs == []


def test_score_physical_similarity_returns_component_scores() -> None:
    score = score_physical_similarity(
        distance_km=25.0,
        elevation_difference_m=50.0,
        target_terrain={
            "terrain_position_index_m": "10",
            "local_relief_m": "200",
            "slope_degrees": "8",
            "aspect_sin": "1",
            "aspect_cos": "0",
        },
        hub_terrain={
            "terrain_position_index_m": "20",
            "local_relief_m": "225",
            "slope_degrees": "9",
            "aspect_sin": "1",
            "aspect_cos": "0",
        },
        overlap_percent=95.0,
    )

    assert score["selection_score"] > 80.0
    assert score["physical_similarity_score"] > 80.0
    assert score["aspect_score"] == 100.0


def test_build_shared_date_rows_supports_nested_and_flat_target_daily_data() -> None:
    hub_daily = {
        "HUB_A": {
            "2024-01-01": 10.0,
            "2024-01-02": 11.0,
            "2024-01-03": 12.0,
        },
        "HUB_B": {
            "2024-01-02": 20.0,
            "2024-01-03": 21.0,
            "2024-01-04": 22.0,
        },
    }
    flat_target_daily = {
        "2024-01-01": 30.0,
        "2024-01-02": 31.0,
        "2024-01-03": 32.0,
    }
    nested_target_daily = {"TARGET": flat_target_daily}
    expected_rows = [
        {
            "date": "2024-01-02",
            "target_station_id": "TARGET",
            "target_tavg": "31.00",
            "hub_1_station_id": "HUB_A",
            "hub_1_tavg": "11.00",
            "hub_2_station_id": "HUB_B",
            "hub_2_tavg": "20.00",
        },
        {
            "date": "2024-01-03",
            "target_station_id": "TARGET",
            "target_tavg": "32.00",
            "hub_1_station_id": "HUB_A",
            "hub_1_tavg": "12.00",
            "hub_2_station_id": "HUB_B",
            "hub_2_tavg": "21.00",
        },
    ]

    assert build_shared_date_rows("TARGET", ["HUB_A", "HUB_B"], flat_target_daily, hub_daily) == expected_rows
    assert build_shared_date_rows("TARGET", ["HUB_A", "HUB_B"], nested_target_daily, hub_daily) == expected_rows


def main() -> None:
    test_score_hub_calculates_overlap_distance_and_elevation_difference()
    test_is_training_eligible_applies_overlap_days_and_elevation_thresholds()
    test_find_training_eligible_hubs_returns_nearest_eligible_hubs()
    test_find_training_eligible_hubs_prefers_physical_similarity_over_distance()
    test_find_training_eligible_hubs_prefers_historical_skill_when_available()
    test_score_physical_similarity_returns_component_scores()
    test_build_shared_date_rows_supports_nested_and_flat_target_daily_data()
    print("pipeline utility tests passed")


if __name__ == "__main__":
    main()
