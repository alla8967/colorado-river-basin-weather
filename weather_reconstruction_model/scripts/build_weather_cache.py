from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import config
from common.weather_cache import (
    HUB_SOURCE,
    TARGET_SOURCE,
    connect_cache,
    initialize_cache,
    rebuild_source_from_csv,
)


def sqlite_sidecar_files(cache_file: Path) -> list[Path]:
    """Return SQLite sidecar files that may exist when WAL mode is enabled."""
    return [
        Path(f"{cache_file}-wal"),
        Path(f"{cache_file}-shm"),
    ]


def remove_cache_files(cache_file: Path) -> None:
    """Remove a cache file and its SQLite sidecars if they exist."""
    for file_path in [cache_file, *sqlite_sidecar_files(cache_file)]:
        try:
            file_path.unlink()
        except FileNotFoundError:
            pass


def checkpoint_existing_cache(cache_file: Path) -> None:
    """Flush WAL changes into the main database before copying/replacing it."""
    if not cache_file.exists():
        return

    with connect_cache(cache_file) as connection:
        connection.execute("PRAGMA wal_checkpoint(FULL)")


def atomic_cache_file(cache_file: Path) -> Path:
    return cache_file.with_name(f"{cache_file.stem}.building{cache_file.suffix}")


def prepare_atomic_build_file(cache_file: Path, preserve_existing_cache: bool) -> Path:
    """Create a temporary cache file that can be safely swapped in later."""
    temporary_file = atomic_cache_file(cache_file)
    remove_cache_files(temporary_file)

    if preserve_existing_cache and cache_file.exists():
        checkpoint_existing_cache(cache_file)
        shutil.copy2(cache_file, temporary_file)

    return temporary_file


def replace_cache_atomically(temporary_file: Path, cache_file: Path) -> None:
    """Replace the live cache only after the temporary rebuild succeeds."""
    checkpoint_existing_cache(temporary_file)
    temporary_file.replace(cache_file)

    for sidecar_file in sqlite_sidecar_files(cache_file):
        try:
            sidecar_file.unlink()
        except FileNotFoundError:
            pass

    remove_cache_files(temporary_file)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a SQLite cache from app-ready NOAA daily temperature CSVs."
    )
    parser.add_argument(
        "--cache-file",
        type=Path,
        default=config.WEATHER_CACHE_FILE,
        help="SQLite cache file to create or update.",
    )
    parser.add_argument(
        "--target-daily",
        type=Path,
        default=config.TARGET_DAILY_FILE,
        help="App-ready target daily CSV.",
    )
    parser.add_argument(
        "--hub-daily",
        type=Path,
        default=config.HUB_DAILY_FILE,
        help="App-ready hub daily CSV.",
    )
    parser.add_argument(
        "--source",
        choices=["all", "target", "hub"],
        default="all",
        help="Which source table to rebuild.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    arguments.cache_file.parent.mkdir(parents=True, exist_ok=True)
    build_file = prepare_atomic_build_file(
        arguments.cache_file,
        preserve_existing_cache=arguments.source != "all",
    )

    print("Build weather SQLite cache")
    print("==========================")
    print(f"Cache file: {arguments.cache_file}")
    print(f"Temporary build file: {build_file}")
    print(f"Source: {arguments.source}")
    print()

    try:
        with connect_cache(build_file) as connection:
            initialize_cache(connection)

            if arguments.source in ("all", "target"):
                rows_read, station_count = rebuild_source_from_csv(
                    connection,
                    TARGET_SOURCE,
                    arguments.target_daily,
                )
                print("Target source cached")
                print(f"  Rows read: {rows_read}")
                print(f"  Stations:  {station_count}")

            if arguments.source in ("all", "hub"):
                rows_read, station_count = rebuild_source_from_csv(
                    connection,
                    HUB_SOURCE,
                    arguments.hub_daily,
                )
                print("Hub source cached")
                print(f"  Rows read: {rows_read}")
                print(f"  Stations:  {station_count}")

        replace_cache_atomically(build_file, arguments.cache_file)
    except Exception:
        remove_cache_files(build_file)
        raise

    print()
    print("Cache build complete and swapped into place")


if __name__ == "__main__":
    main()
