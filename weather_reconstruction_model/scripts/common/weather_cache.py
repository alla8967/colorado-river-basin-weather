from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Iterable

from common.number_utils import to_float


TARGET_SOURCE = "target"
HUB_SOURCE = "hub"
BATCH_SIZE = 50000
TEMPERATURE_VARIABLES = {"tavg", "tmax", "tmin"}


def connect_cache(cache_file: Path) -> sqlite3.Connection:
    """Open the weather SQLite cache."""
    return sqlite3.connect(cache_file)


def initialize_cache(connection: sqlite3.Connection) -> None:
    """Create the cache schema and indexes if they do not already exist."""
    connection.executescript(
        """
        PRAGMA journal_mode = WAL;
        PRAGMA synchronous = NORMAL;

        CREATE TABLE IF NOT EXISTS stations (
            source_type TEXT NOT NULL,
            station_id TEXT NOT NULL,
            station_name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            elevation_m REAL NOT NULL,
            PRIMARY KEY (source_type, station_id)
        );

        CREATE TABLE IF NOT EXISTS daily_temperature (
            source_type TEXT NOT NULL,
            station_id TEXT NOT NULL,
            date TEXT NOT NULL,
            tmax REAL NOT NULL,
            tmin REAL NOT NULL,
            tavg REAL NOT NULL,
            PRIMARY KEY (source_type, station_id, date)
        );

        CREATE TABLE IF NOT EXISTS station_year_coverage (
            source_type TEXT NOT NULL,
            station_id TEXT NOT NULL,
            year INTEGER NOT NULL,
            days_observed INTEGER NOT NULL,
            PRIMARY KEY (source_type, station_id, year)
        );

        CREATE TABLE IF NOT EXISTS station_date_summary (
            source_type TEXT NOT NULL,
            station_id TEXT NOT NULL,
            first_date TEXT NOT NULL,
            last_date TEXT NOT NULL,
            total_days INTEGER NOT NULL,
            PRIMARY KEY (source_type, station_id)
        );

        CREATE INDEX IF NOT EXISTS idx_daily_source_station
            ON daily_temperature (source_type, station_id);

        CREATE INDEX IF NOT EXISTS idx_daily_source_date
            ON daily_temperature (source_type, date);

        CREATE INDEX IF NOT EXISTS idx_year_coverage_source_station
            ON station_year_coverage (source_type, station_id);
        """
    )
    migrate_daily_temperature_schema(connection)
    connection.commit()


def migrate_daily_temperature_schema(connection: sqlite3.Connection) -> None:
    """Add variable columns to caches created before tmax/tmin were stored."""
    existing_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(daily_temperature)")
    }

    for column in ("tmax", "tmin"):
        if column not in existing_columns:
            connection.execute(f"ALTER TABLE daily_temperature ADD COLUMN {column} REAL")


def validate_temperature_variable(variable: str) -> str:
    if variable not in TEMPERATURE_VARIABLES:
        allowed_variables = ", ".join(sorted(TEMPERATURE_VARIABLES))
        raise ValueError(
            f"Unsupported temperature variable '{variable}'. "
            f"Expected one of: {allowed_variables}."
        )

    return variable


def daily_temperature_columns(connection: sqlite3.Connection) -> set[str]:
    return {
        row[1]
        for row in connection.execute("PRAGMA table_info(daily_temperature)")
    }


def require_temperature_variable_column(
    connection: sqlite3.Connection,
    variable: str,
) -> None:
    if variable not in daily_temperature_columns(connection):
        raise ValueError(
            f"Cache schema does not include {variable}. "
            "Rebuild the weather cache before loading this variable."
        )


def calculate_tavg(row: dict[str, str]) -> float:
    return (to_float(row["tmax"]) + to_float(row["tmin"])) / 2


def rebuild_source_from_csv(
    connection: sqlite3.Connection,
    source_type: str,
    csv_file: Path,
) -> tuple[int, int]:
    """Replace one source type in the cache from an app-ready daily CSV file."""
    initialize_cache(connection)
    connection.execute("DELETE FROM daily_temperature WHERE source_type = ?", (source_type,))
    connection.execute("DELETE FROM stations WHERE source_type = ?", (source_type,))
    connection.execute("DELETE FROM station_year_coverage WHERE source_type = ?", (source_type,))
    connection.execute("DELETE FROM station_date_summary WHERE source_type = ?", (source_type,))

    station_rows: dict[str, tuple[object, ...]] = {}
    station_summary_rows: dict[str, dict[str, object]] = {}
    year_coverage_counts: dict[tuple[str, int], int] = {}
    daily_rows: list[tuple[object, ...]] = []
    rows_read = 0

    with csv_file.open("r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            rows_read += 1
            station_id = row["station_id"]
            date_text = row["date"]
            year = int(date_text[:4])
            station_rows[station_id] = (
                source_type,
                station_id,
                row["station_name"],
                to_float(row["latitude"]),
                to_float(row["longitude"]),
                to_float(row["elevation"]),
            )
            daily_rows.append((
                source_type,
                station_id,
                date_text,
                to_float(row["tmax"]),
                to_float(row["tmin"]),
                calculate_tavg(row),
            ))
            year_key = (station_id, year)
            year_coverage_counts[year_key] = year_coverage_counts.get(year_key, 0) + 1

            if station_id not in station_summary_rows:
                station_summary_rows[station_id] = {
                    "first_date": date_text,
                    "last_date": date_text,
                    "total_days": 0,
                }

            summary = station_summary_rows[station_id]
            summary["first_date"] = min(str(summary["first_date"]), date_text)
            summary["last_date"] = max(str(summary["last_date"]), date_text)
            summary["total_days"] = int(summary["total_days"]) + 1

            if len(daily_rows) >= BATCH_SIZE:
                insert_daily_rows(connection, daily_rows)
                daily_rows.clear()

    if daily_rows:
        insert_daily_rows(connection, daily_rows)

    connection.executemany(
        """
        INSERT OR REPLACE INTO stations (
            source_type,
            station_id,
            station_name,
            latitude,
            longitude,
            elevation_m
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        station_rows.values(),
    )
    connection.executemany(
        """
        INSERT OR REPLACE INTO station_year_coverage (
            source_type,
            station_id,
            year,
            days_observed
        )
        VALUES (?, ?, ?, ?)
        """,
        [
            (source_type, station_id, year, days_observed)
            for (station_id, year), days_observed in year_coverage_counts.items()
        ],
    )
    connection.executemany(
        """
        INSERT OR REPLACE INTO station_date_summary (
            source_type,
            station_id,
            first_date,
            last_date,
            total_days
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                source_type,
                station_id,
                summary["first_date"],
                summary["last_date"],
                summary["total_days"],
            )
            for station_id, summary in station_summary_rows.items()
        ],
    )
    connection.commit()
    return rows_read, len(station_rows)


def insert_daily_rows(
    connection: sqlite3.Connection,
    daily_rows: list[tuple[object, ...]],
) -> None:
    connection.executemany(
        """
        INSERT OR REPLACE INTO daily_temperature (
            source_type,
            station_id,
            date,
            tmax,
            tmin,
            tavg
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        daily_rows,
    )


def source_row_count(connection: sqlite3.Connection, source_type: str) -> int:
    row = connection.execute(
        "SELECT COUNT(*) FROM daily_temperature WHERE source_type = ?",
        (source_type,),
    ).fetchone()
    return int(row[0])


def load_daily_for_station_ids(
    cache_file: Path,
    source_type: str,
    station_ids: Iterable[str] | None = None,
    variable: str = "tavg",
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, str]], int, int]:
    """Load daily temperature values and station metadata from the SQLite cache."""
    variable = validate_temperature_variable(variable)
    station_id_list = sorted(set(station_ids)) if station_ids is not None else None

    with connect_cache(cache_file) as connection:
        require_temperature_variable_column(connection, variable)
        total_rows = source_row_count(connection, source_type)
        metadata_by_station = load_metadata(connection, source_type, station_id_list)
        daily_by_station = {
            station_id: {}
            for station_id in metadata_by_station
        }
        rows_kept = 0

        for station_id, date_text, value in query_daily_rows(
            connection,
            source_type,
            station_id_list,
            variable,
        ):
            if station_id not in daily_by_station:
                daily_by_station[station_id] = {}

            if value is None:
                raise ValueError(
                    f"Cache has no {variable} value for {source_type} station "
                    f"{station_id} on {date_text}. Rebuild the weather cache."
                )

            daily_by_station[station_id][date_text] = float(value)
            rows_kept += 1

    return daily_by_station, metadata_by_station, total_rows, rows_kept


def load_date_sets_for_station_ids(
    cache_file: Path,
    source_type: str,
    station_ids: Iterable[str] | None = None,
) -> tuple[dict[str, set[str]], dict[str, dict[str, str]], int, int]:
    """Load available dates and station metadata without loading temperatures."""
    station_id_list = sorted(set(station_ids)) if station_ids is not None else None

    with connect_cache(cache_file) as connection:
        total_rows = source_row_count(connection, source_type)
        metadata_by_station = load_metadata(connection, source_type, station_id_list)
        dates_by_station = {
            station_id: set()
            for station_id in metadata_by_station
        }
        rows_kept = 0

        if station_id_list is None:
            rows = connection.execute(
                """
                SELECT station_id, date
                FROM daily_temperature
                WHERE source_type = ?
                ORDER BY station_id, date
                """,
                (source_type,),
            )
        else:
            rows = query_with_station_chunks(
                connection,
                """
                SELECT station_id, date
                FROM daily_temperature
                WHERE source_type = ? AND station_id IN ({placeholders})
                ORDER BY station_id, date
                """,
                source_type,
                station_id_list,
            )

        for station_id, date_text in rows:
            if station_id not in dates_by_station:
                dates_by_station[station_id] = set()

            dates_by_station[station_id].add(date_text)
            rows_kept += 1

    return dates_by_station, metadata_by_station, total_rows, rows_kept


def load_year_coverage_for_station_ids(
    cache_file: Path,
    source_type: str,
    station_ids: Iterable[str] | None = None,
) -> dict[str, dict[int, int]]:
    """Load station/year coverage counts without loading daily dates."""
    station_id_list = sorted(set(station_ids)) if station_ids is not None else None
    coverage_by_station: dict[str, dict[int, int]] = {}

    with connect_cache(cache_file) as connection:
        if station_id_list is None:
            rows = connection.execute(
                """
                SELECT station_id, year, days_observed
                FROM station_year_coverage
                WHERE source_type = ?
                """,
                (source_type,),
            )
        else:
            rows = query_with_station_chunks(
                connection,
                """
                SELECT station_id, year, days_observed
                FROM station_year_coverage
                WHERE source_type = ? AND station_id IN ({placeholders})
                """,
                source_type,
                station_id_list,
            )

        for station_id, year, days_observed in rows:
            if station_id not in coverage_by_station:
                coverage_by_station[station_id] = {}

            coverage_by_station[station_id][int(year)] = int(days_observed)

    return coverage_by_station


def load_metadata_for_station_ids(
    cache_file: Path,
    source_type: str,
    station_ids: Iterable[str] | None = None,
) -> dict[str, dict[str, str]]:
    """Load only station metadata from the SQLite cache."""
    station_id_list = sorted(set(station_ids)) if station_ids is not None else None

    with connect_cache(cache_file) as connection:
        return load_metadata(connection, source_type, station_id_list)


def load_metadata(
    connection: sqlite3.Connection,
    source_type: str,
    station_ids: list[str] | None,
) -> dict[str, dict[str, str]]:
    metadata_by_station: dict[str, dict[str, str]] = {}

    if station_ids is None:
        rows = connection.execute(
            """
            SELECT station_id, station_name, elevation_m
            FROM stations
            WHERE source_type = ?
            """,
            (source_type,),
        )
    else:
        rows = query_with_station_chunks(
            connection,
            """
            SELECT station_id, station_name, elevation_m
            FROM stations
            WHERE source_type = ? AND station_id IN ({placeholders})
            """,
            source_type,
            station_ids,
        )

    for station_id, station_name, elevation_m in rows:
        metadata_by_station[station_id] = {
            "station_name": station_name,
            "elevation": f"{float(elevation_m):.1f}",
        }

    return metadata_by_station


def query_daily_rows(
    connection: sqlite3.Connection,
    source_type: str,
    station_ids: list[str] | None,
    variable: str = "tavg",
):
    variable = validate_temperature_variable(variable)

    if station_ids is None:
        yield from connection.execute(
            f"""
            SELECT station_id, date, {variable}
            FROM daily_temperature
            WHERE source_type = ?
            ORDER BY station_id, date
            """,
            (source_type,),
        )
        return

    yield from query_with_station_chunks(
        connection,
        f"""
        SELECT station_id, date, {variable}
        FROM daily_temperature
        WHERE source_type = ? AND station_id IN ({{placeholders}})
        ORDER BY station_id, date
        """,
        source_type,
        station_ids,
    )


def query_with_station_chunks(
    connection: sqlite3.Connection,
    query_template: str,
    source_type: str,
    station_ids: list[str],
):
    if not station_ids:
        return

    for start in range(0, len(station_ids), 900):
        chunk = station_ids[start:start + 900]
        placeholders = ",".join("?" for _ in chunk)
        query = query_template.format(placeholders=placeholders)
        yield from connection.execute(query, [source_type, *chunk])
