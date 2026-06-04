from __future__ import annotations

from pathlib import Path
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import batch_validate_models as batch_tools
from common.csv_utils import write_csv_rows
from pipeline.training_tables import (
    build_general_rows_for_target,
    fieldnames_for_hub_count,
)


def assert_close(actual: float, expected: float, tolerance: float = 1e-9) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"Expected {expected}, got {actual}")


def test_fieldnames_are_variable_specific() -> None:
    fieldnames = fieldnames_for_hub_count(
        hub_count=1,
        target_neighbor_count=1,
        variable="tmin",
    )

    assert "target_tmin" in fieldnames
    assert "regional_baseline_tmin" in fieldnames
    assert "target_tmin_offset_from_baseline" in fieldnames
    assert "hub_1_tmin" in fieldnames
    assert "hub_1_tmin_offset_from_baseline" in fieldnames
    assert "target_neighbor_1_tmin" in fieldnames
    assert "target_tavg" not in fieldnames
    assert "hub_1_tavg" not in fieldnames


def test_general_rows_are_variable_specific() -> None:
    rows = build_general_rows_for_target(
        target_station={
            "station_id": "T1",
            "latitude": "40.0000",
            "longitude": "-105.0000",
        },
        target_metadata={
            "station_name": "TARGET ONE",
            "elevation": "1600",
        },
        target_daily={
            "2024-01-01": 20.0,
            "2024-01-02": 30.0,
        },
        selected_hubs=[
            {
                "station_id": "H1",
                "latitude": "40.1000",
                "longitude": "-105.1000",
                "distance_km": 12.5,
                "elevation_difference_m": 50.0,
                "overlap_percent": 100.0,
            }
        ],
        selected_target_neighbors=[],
        hub_daily_by_station={
            "H1": {
                "2024-01-01": 15.0,
                "2024-01-02": 25.0,
            }
        },
        hub_metadata_by_station={
            "H1": {
                "station_name": "HUB ONE",
                "elevation": "1550",
            }
        },
        target_neighbor_daily_by_station={},
        target_neighbor_metadata_by_station={},
        terrain_by_station={},
        variable="tmin",
    )

    assert len(rows) == 2
    first_row = rows[0]
    assert first_row["target_tmin"] == "20.00"
    assert first_row["regional_baseline_tmin"] == "15.00"
    assert first_row["target_tmin_offset_from_baseline"] == "5.00"
    assert first_row["hub_1_tmin"] == "15.00"
    assert first_row["hub_1_tmin_offset_from_baseline"] == "0.00"
    assert "target_tavg" not in first_row
    assert "hub_1_tavg" not in first_row


def test_general_rows_include_predictor_sections() -> None:
    terrain_by_station = {
        "T1": {
            "dem_elevation_m": "1610",
            "dem_minus_noaa_elevation_m": "10",
            "slope_degrees": "4",
            "aspect_sin": "0",
            "aspect_cos": "1",
            "local_relief_m": "80",
            "terrain_position_index_m": "-20",
            "slope_degrees_r3000m": "3",
        },
        "H1": {
            "dem_elevation_m": "1560",
            "dem_minus_noaa_elevation_m": "10",
            "slope_degrees": "6",
            "aspect_sin": "0",
            "aspect_cos": "1",
            "local_relief_m": "100",
            "terrain_position_index_m": "-10",
        },
        "N1": {
            "dem_elevation_m": "1500",
            "dem_minus_noaa_elevation_m": "20",
            "slope_degrees": "10",
            "aspect_sin": "1",
            "aspect_cos": "0",
            "local_relief_m": "120",
            "terrain_position_index_m": "5",
        },
    }
    selected_hubs = [
        {
            "station_id": "H1",
            "latitude": "40.1000",
            "longitude": "-105.1000",
            "distance_km": 12.5,
            "elevation_difference_m": 50.0,
            "overlap_percent": 100.0,
            "selection_score": 90.0,
            "physical_similarity_score": 85.0,
            "distance_score": 95.0,
            "pair_overlap_days": "365",
            "pair_skill_score": "88.25",
            "pair_corr": "0.95",
        }
    ]
    selected_neighbors = [
        {
            "station_id": "N1",
            "latitude": "40.2000",
            "longitude": "-105.2000",
            "distance_km": 20.0,
            "elevation_difference_m": 100.0,
            "overlap_percent": 98.0,
            "selection_score": 80.0,
            "physical_similarity_score": 75.0,
            "distance_score": 70.0,
            "pair_overlap_days": "200",
            "pair_skill_score": "70.5",
            "pair_corr": "0.85",
        }
    ]

    rows = build_general_rows_for_target(
        target_station={
            "station_id": "T1",
            "latitude": "40.0000",
            "longitude": "-105.0000",
        },
        target_metadata={
            "station_name": "TARGET ONE",
            "elevation": "1600",
        },
        target_daily={"2024-01-01": 20.0},
        selected_hubs=selected_hubs,
        selected_target_neighbors=selected_neighbors,
        hub_daily_by_station={"H1": {"2024-01-01": 15.0}},
        hub_metadata_by_station={
            "H1": {"station_name": "HUB ONE", "elevation": "1550"}
        },
        target_neighbor_daily_by_station={"N1": {"2024-01-01": 18.0}},
        target_neighbor_metadata_by_station={
            "N1": {"station_name": "NEIGHBOR ONE", "elevation": "1500"}
        },
        terrain_by_station=terrain_by_station,
        variable="tmin",
    )

    row = rows[0]
    assert row["target_dem_elevation_m"] == "1610"
    assert row["target_slope_degrees_r3000m"] == "3"
    assert row["hub_1_name"] == "HUB ONE"
    assert row["hub_1_tmin"] == "15.00"
    assert row["hub_1_tmin_offset_from_baseline"] == "0.00"
    assert row["hub_1_selection_score"] == "90.000000"
    assert row["hub_1_pair_overlap_days"] == "365"
    assert row["hub_1_pair_skill_score"] == "88.250000"
    assert row["hub_1_dem_elevation_delta_m"] == "50.000000"
    assert row["hub_1_abs_terrain_position_delta_m"] == "10.000000"
    assert row["target_neighbor_1_name"] == "NEIGHBOR ONE"
    assert row["target_neighbor_1_tmin"] == "18.00"
    assert row["target_neighbor_1_tmin_offset_from_baseline"] == "3.00"
    assert row["target_neighbor_1_pair_corr"] == "0.850000"


def test_fieldnames_include_predictor_sections() -> None:
    fieldnames = fieldnames_for_hub_count(
        hub_count=1,
        target_neighbor_count=1,
        variable="tmin",
    )

    for expected_fieldname in [
        "target_slope_degrees_r3000m",
        "hub_1_selection_score",
        "hub_1_pair_skill_score",
        "hub_1_dem_elevation_delta_m",
        "target_neighbor_1_selection_score",
        "target_neighbor_1_pair_corr",
        "target_neighbor_1_abs_terrain_position_delta_m",
    ]:
        assert expected_fieldname in fieldnames


def test_csv_batch_loaders_are_variable_specific() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        daily_file = Path(temp_dir) / "daily.csv"
        write_csv_rows(
            daily_file,
            [
                {
                    "station_id": "T1",
                    "station_name": "TARGET ONE",
                    "latitude": "40.0",
                    "longitude": "-105.0",
                    "elevation": "1600",
                    "date": "2024-01-01",
                    "tmax": "50.0",
                    "tmin": "20.0",
                }
            ],
            [
                "station_id",
                "station_name",
                "latitude",
                "longitude",
                "elevation",
                "date",
                "tmax",
                "tmin",
            ],
        )

        target_tmin, metadata, rows_read, rows_kept = batch_tools.load_target_daily_for_batch(
            daily_file,
            ["T1"],
            variable="tmin",
        )
        target_tavg, _, _, _ = batch_tools.load_target_daily_for_batch(
            daily_file,
            ["T1"],
        )

    assert rows_read == 1
    assert rows_kept == 1
    assert metadata["T1"]["station_name"] == "TARGET ONE"
    assert_close(target_tmin["T1"]["2024-01-01"], 20.0)
    assert_close(target_tavg["T1"]["2024-01-01"], 35.0)


def main() -> None:
    test_fieldnames_are_variable_specific()
    test_general_rows_are_variable_specific()
    test_general_rows_include_predictor_sections()
    test_fieldnames_include_predictor_sections()
    test_csv_batch_loaders_are_variable_specific()
    print("general training table variable tests passed")


if __name__ == "__main__":
    main()
