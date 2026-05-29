from __future__ import annotations

from pathlib import Path
import sqlite3
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from common.csv_utils import write_csv_rows
from common.weather_cache import (
    TARGET_SOURCE,
    connect_cache,
    initialize_cache,
    load_daily_for_station_ids,
    rebuild_source_from_csv,
)


def assert_close(actual: float, expected: float, tolerance: float = 1e-9) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"Expected {expected}, got {actual}")


def assert_raises(expected_error: type[Exception], callback) -> Exception:
    try:
        callback()
    except expected_error as error:
        return error

    raise AssertionError(f"Expected {expected_error.__name__}")


def write_daily_file(path: Path) -> None:
    write_csv_rows(
        path,
        [
            {
                "station_id": "T1",
                "station_name": "TARGET ONE",
                "latitude": "39.75",
                "longitude": "-105.00",
                "elevation": "1600.0",
                "date": "2024-01-01",
                "tmax": "50.0",
                "tmin": "20.0",
            },
            {
                "station_id": "T1",
                "station_name": "TARGET ONE",
                "latitude": "39.75",
                "longitude": "-105.00",
                "elevation": "1600.0",
                "date": "2024-01-02",
                "tmax": "60.0",
                "tmin": "30.0",
            },
            {
                "station_id": "T2",
                "station_name": "TARGET TWO",
                "latitude": "40.00",
                "longitude": "-106.00",
                "elevation": "1700.0",
                "date": "2024-01-01",
                "tmax": "48.0",
                "tmin": "18.0",
            },
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


def test_rebuild_source_stores_tmax_tmin_and_tavg() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        daily_file = temp_path / "target_daily.csv"
        cache_file = temp_path / "weather.sqlite"
        write_daily_file(daily_file)

        with connect_cache(cache_file) as connection:
            rows_read, station_count = rebuild_source_from_csv(
                connection,
                TARGET_SOURCE,
                daily_file,
            )
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(daily_temperature)")
            }
            stored_row = connection.execute(
                """
                SELECT tmax, tmin, tavg
                FROM daily_temperature
                WHERE source_type = ? AND station_id = ? AND date = ?
                """,
                (TARGET_SOURCE, "T1", "2024-01-01"),
            ).fetchone()

        assert rows_read == 3
        assert station_count == 2
        assert {"tmax", "tmin", "tavg"}.issubset(columns)
        assert_close(stored_row[0], 50.0)
        assert_close(stored_row[1], 20.0)
        assert_close(stored_row[2], 35.0)

        tavg_daily, metadata, total_rows, rows_kept = load_daily_for_station_ids(
            cache_file,
            TARGET_SOURCE,
            ["T1"],
        )
        tmax_daily, _, _, _ = load_daily_for_station_ids(
            cache_file,
            TARGET_SOURCE,
            ["T1"],
            variable="tmax",
        )
        tmin_daily, _, _, _ = load_daily_for_station_ids(
            cache_file,
            TARGET_SOURCE,
            ["T1"],
            variable="tmin",
        )

    assert total_rows == 3
    assert rows_kept == 2
    assert metadata["T1"]["station_name"] == "TARGET ONE"
    assert_close(tavg_daily["T1"]["2024-01-01"], 35.0)
    assert_close(tavg_daily["T1"]["2024-01-02"], 45.0)
    assert_close(tmax_daily["T1"]["2024-01-01"], 50.0)
    assert_close(tmin_daily["T1"]["2024-01-02"], 30.0)


def test_load_daily_rejects_unknown_temperature_variable() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_file = Path(temp_dir) / "weather.sqlite"

        with connect_cache(cache_file) as connection:
            initialize_cache(connection)

        error = assert_raises(
            ValueError,
            lambda: load_daily_for_station_ids(
                cache_file,
                TARGET_SOURCE,
                variable="prcp",
            ),
        )

    assert "Unsupported temperature variable" in str(error)


def test_load_daily_reports_old_cache_schema_for_new_variables() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_file = Path(temp_dir) / "old_weather.sqlite"

        with sqlite3.connect(cache_file) as connection:
            connection.executescript(
                """
                CREATE TABLE stations (
                    source_type TEXT NOT NULL,
                    station_id TEXT NOT NULL,
                    station_name TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    elevation_m REAL NOT NULL,
                    PRIMARY KEY (source_type, station_id)
                );

                CREATE TABLE daily_temperature (
                    source_type TEXT NOT NULL,
                    station_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    tavg REAL NOT NULL,
                    PRIMARY KEY (source_type, station_id, date)
                );
                """
            )

        error = assert_raises(
            ValueError,
            lambda: load_daily_for_station_ids(
                cache_file,
                TARGET_SOURCE,
                variable="tmin",
            ),
        )

    assert "Rebuild the weather cache" in str(error)


def main() -> None:
    test_rebuild_source_stores_tmax_tmin_and_tavg()
    test_load_daily_rejects_unknown_temperature_variable()
    test_load_daily_reports_old_cache_schema_for_new_variables()
    print("weather cache tests passed")


if __name__ == "__main__":
    main()
