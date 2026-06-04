from __future__ import annotations

from pathlib import Path
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from common.confidence_data import (
    load_confidence_support_inputs,
    load_support_stations,
    load_terrain_station_records,
    load_validation_evidence,
    parse_optional_bool,
    terrain_features_from_row,
)
from common.csv_utils import write_csv_rows


def assert_close(actual: float, expected: float, tolerance: float = 1e-9) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"Expected {expected}, got {actual}")


def write_candidate_file(path: Path, station_id: str, latitude: float, longitude: float) -> None:
    write_csv_rows(
        path,
        [
            {
                "station_id": station_id,
                "latitude": latitude,
                "longitude": longitude,
                "has_tmax": 1,
                "has_tmin": 1,
                "tmax_start": 1980,
                "tmax_end": 2026,
                "tmin_start": 1980,
                "tmin_end": 2026,
                "usable_temp_start": 1980,
                "usable_temp_end": 2026,
                "usable_temp_years": 47,
                "is_target_candidate": 1,
                "is_hub_candidate": 0,
            }
        ],
        [
            "station_id",
            "latitude",
            "longitude",
            "has_tmax",
            "has_tmin",
            "tmax_start",
            "tmax_end",
            "tmin_start",
            "tmin_end",
            "usable_temp_start",
            "usable_temp_end",
            "usable_temp_years",
            "is_target_candidate",
            "is_hub_candidate",
        ],
    )


def write_terrain_file(path: Path) -> None:
    write_csv_rows(
        path,
        [
            {
                "station_id": "T1",
                "station_role": "target",
                "station_name": "TARGET ONE",
                "latitude": 39.75,
                "longitude": -105.0,
                "noaa_elevation_m": 1601.0,
                "dem_elevation_m": 1598.0,
                "slope_degrees": 3.0,
                "local_relief_m": 70.0,
                "terrain_position_index_m": 5.0,
                "slope_degrees_r300m": 2.5,
                "local_relief_m_r300m": 65.0,
                "terrain_position_index_m_r300m": 4.0,
                "slope_degrees_r990m": 4.0,
                "local_relief_m_r990m": 90.0,
                "terrain_position_index_m_r990m": 8.0,
                "slope_degrees_r3000m": 4.5,
                "local_relief_m_r3000m": 120.0,
                "terrain_position_index_m_r3000m": 12.0,
            },
            {
                "station_id": "H1",
                "station_role": "hub",
                "station_name": "HUB ONE",
                "latitude": 39.8,
                "longitude": -105.05,
                "noaa_elevation_m": 1620.0,
                "dem_elevation_m": 1615.0,
                "slope_degrees": 4.0,
                "local_relief_m": 80.0,
                "terrain_position_index_m": 6.0,
                "slope_degrees_r300m": 3.0,
                "local_relief_m_r300m": 75.0,
                "terrain_position_index_m_r300m": 5.0,
                "slope_degrees_r990m": 5.0,
                "local_relief_m_r990m": 100.0,
                "terrain_position_index_m_r990m": 9.0,
                "slope_degrees_r3000m": 5.5,
                "local_relief_m_r3000m": 130.0,
                "terrain_position_index_m_r3000m": 13.0,
            },
        ],
        [
            "station_id",
            "station_role",
            "station_name",
            "latitude",
            "longitude",
            "noaa_elevation_m",
            "dem_elevation_m",
            "slope_degrees",
            "local_relief_m",
            "terrain_position_index_m",
            "slope_degrees_r300m",
            "local_relief_m_r300m",
            "terrain_position_index_m_r300m",
            "slope_degrees_r990m",
            "local_relief_m_r990m",
            "terrain_position_index_m_r990m",
            "slope_degrees_r3000m",
            "local_relief_m_r3000m",
            "terrain_position_index_m_r3000m",
        ],
    )


def write_metrics_file(path: Path) -> None:
    write_csv_rows(
        path,
        [
            {
                "target_station_id": "T1",
                "target_name": "TARGET ONE",
                "test_rows": 500,
                "mae": 1.25,
                "rmse": 1.90,
                "correlation": 0.995,
                "strict_pass": "True",
                "p90_abs_error": 2.8,
            },
            {
                "target_station_id": "T2",
                "target_name": "TARGET TWO",
                "test_rows": 25,
                "mae": 5.50,
                "rmse": 7.20,
                "correlation": 0.83,
                "strict_pass": "False",
                "p90_abs_error": 9.1,
            },
        ],
        [
            "target_station_id",
            "target_name",
            "test_rows",
            "mae",
            "rmse",
            "correlation",
            "strict_pass",
            "p90_abs_error",
        ],
    )


def test_terrain_features_from_row() -> None:
    terrain = terrain_features_from_row(
        {
            "dem_elevation_m": "1598.5",
            "slope_degrees": "3.2",
            "local_relief_m": "70.5",
            "terrain_position_index_m": "5.5",
            "slope_degrees_r300m": "2.6",
            "local_relief_m_r300m": "65.4",
            "terrain_position_index_m_r300m": "4.3",
            "slope_degrees_r990m": "4.1",
            "local_relief_m_r990m": "90.2",
            "terrain_position_index_m_r990m": "8.2",
            "slope_degrees_r3000m": "4.8",
            "local_relief_m_r3000m": "120.2",
            "terrain_position_index_m_r3000m": "12.2",
        }
    )

    assert_close(terrain.dem_elevation_m, 1598.5)
    assert_close(terrain.local_relief_m_r3000m, 120.2)
    assert_close(terrain.terrain_position_index_m_r990m, 8.2)


def test_load_support_stations_joins_candidate_and_terrain_data() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        candidate_file = temp_path / "target_candidates.csv"
        terrain_file = temp_path / "terrain.csv"
        write_candidate_file(candidate_file, "T1", 39.75, -105.0)
        write_terrain_file(terrain_file)

        terrain_by_station_id = load_terrain_station_records(terrain_file)
        stations = load_support_stations(
            candidate_file,
            station_role="target",
            terrain_by_station_id=terrain_by_station_id,
        )

    assert len(stations) == 1
    station = stations[0]
    assert station.station_id == "T1"
    assert station.station_name == "TARGET ONE"
    assert station.station_role == "target"
    assert_close(station.latitude, 39.75)
    assert_close(station.longitude, -105.0)
    assert_close(station.elevation_m, 1601.0)
    assert_close(station.usable_years, 47.0)
    assert station.usable_start_year == 1980
    assert station.usable_end_year == 2026
    assert station.terrain is not None
    assert_close(station.terrain.dem_elevation_m, 1598.0)


def test_load_validation_evidence_supports_standard_station_metrics() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        metrics_file = Path(temp_dir) / "metrics.csv"
        write_metrics_file(metrics_file)

        evidence = load_validation_evidence(
            metrics_file,
            model_reference="fixture-model",
        )

    assert set(evidence) == {"T1", "T2"}
    assert_close(evidence["T1"].mae, 1.25)
    assert_close(evidence["T1"].rmse, 1.90)
    assert_close(evidence["T1"].correlation, 0.995)
    assert evidence["T1"].test_rows == 500
    assert evidence["T1"].strict_pass is True
    assert evidence["T1"].model_reference == "fixture-model"
    assert_close(evidence["T1"].extra_metrics["p90_abs_error"], 2.8)
    assert evidence["T2"].strict_pass is False


def test_load_confidence_support_inputs_combines_all_sources() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        target_file = temp_path / "target_candidates.csv"
        hub_file = temp_path / "hub_candidates.csv"
        terrain_file = temp_path / "terrain.csv"
        metrics_file = temp_path / "metrics.csv"

        write_candidate_file(target_file, "T1", 39.75, -105.0)
        write_candidate_file(hub_file, "H1", 39.8, -105.05)
        write_terrain_file(terrain_file)
        write_metrics_file(metrics_file)

        inputs = load_confidence_support_inputs(
            target_candidate_file=target_file,
            hub_candidate_file=hub_file,
            terrain_file=terrain_file,
            validation_metrics_file=metrics_file,
            model_reference="combined-model",
        )

    assert len(inputs.target_stations) == 1
    assert len(inputs.hub_stations) == 1
    assert set(inputs.terrain_by_station_id) == {"T1", "H1"}
    assert set(inputs.validation_by_station_id) == {"T1", "T2"}
    assert inputs.target_stations[0].station_name == "TARGET ONE"
    assert inputs.hub_stations[0].station_name == "HUB ONE"
    assert inputs.validation_by_station_id["T1"].model_reference == "combined-model"


def test_parse_optional_bool() -> None:
    assert parse_optional_bool("True") is True
    assert parse_optional_bool("1") is True
    assert parse_optional_bool("yes") is True
    assert parse_optional_bool("False") is False
    assert parse_optional_bool("0") is False
    assert parse_optional_bool("no") is False
    assert parse_optional_bool("") is None
    assert parse_optional_bool("maybe") is None
    assert parse_optional_bool(None) is None


def main() -> None:
    test_terrain_features_from_row()
    test_load_support_stations_joins_candidate_and_terrain_data()
    test_load_validation_evidence_supports_standard_station_metrics()
    test_load_confidence_support_inputs_combines_all_sources()
    test_parse_optional_bool()
    print("confidence data adapter tests passed")


if __name__ == "__main__":
    main()
