"""Validate that an Alpine or remote workspace has required inputs and packages.

Run this before long jobs to catch missing data, cache, disk, or dependency problems early."""

from __future__ import annotations

import argparse
import importlib.util
import sqlite3
import sys
from pathlib import Path
from shutil import disk_usage

import config


MIN_FREE_DISK_GB = 10.0


REQUIRED_FILES = [
    ("target station candidates", config.TARGET_CANDIDATE_FILE),
    ("hub station candidates", config.HUB_CANDIDATE_FILE),
    ("target daily temperatures", config.TARGET_DAILY_FILE),
    ("hub daily temperatures", config.HUB_DAILY_FILE),
    ("station terrain features", config.TERRAIN_FEATURE_FILE),
    ("weather SQLite cache", config.WEATHER_CACHE_FILE),
]


REQUIRED_OUTPUT_DIRS = [
    config.OUTPUT_DIR,
    config.GENERAL_TABLE_DIR,
    config.PREDICTION_DIR,
    config.REPORT_DIR,
]


def file_size_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)


def has_module(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def check_file(label: str, path: Path) -> bool:
    if not path.exists():
        print(f"MISSING  {label}: {path}")
        return False

    if not path.is_file():
        print(f"INVALID  {label}: {path} is not a file")
        return False

    print(f"OK       {label}: {path} ({file_size_mb(path):.1f} MB)")
    return True


def check_output_dir(path: Path) -> bool:
    path.mkdir(parents=True, exist_ok=True)

    if not path.is_dir():
        print(f"INVALID  output directory: {path}")
        return False

    test_file = path / ".remote_write_test"
    try:
        test_file.write_text("ok\n")
        test_file.unlink()
    except OSError as error:
        print(f"BLOCKED  output directory not writable: {path} ({error})")
        return False

    print(f"OK       writable output directory: {path}")
    return True


def check_sqlite_cache(path: Path, check_integrity: bool) -> bool:
    if not path.exists():
        return False

    try:
        with sqlite3.connect(path) as connection:
            table_count = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
            ).fetchone()[0]
            if check_integrity:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    print(f"FAILED   SQLite integrity check: {integrity}")
                    return False
    except sqlite3.Error as error:
        print(f"FAILED   SQLite cache could not be opened: {path} ({error})")
        return False

    print(f"OK       SQLite cache opens cleanly ({table_count} tables)")
    return True


def check_disk_space(path: Path, minimum_free_gb: float) -> bool:
    usage = disk_usage(path)
    free_gb = usage.free / (1024 ** 3)
    total_gb = usage.total / (1024 ** 3)

    if free_gb < minimum_free_gb:
        print(
            f"LOW      disk free space: {free_gb:.1f} GB free of {total_gb:.1f} GB "
            f"(minimum requested: {minimum_free_gb:.1f} GB)"
        )
        return False

    print(f"OK       disk free space: {free_gb:.1f} GB free of {total_gb:.1f} GB")
    return True


def check_python_modules(require_sklearn: bool, require_rasterio: bool) -> bool:
    ok = True
    print(f"Python   {sys.version.split()[0]} at {sys.executable}")

    for module_name in ["csv", "sqlite3", "pathlib"]:
        print(f"OK       stdlib module available: {module_name}")

    if require_sklearn:
        for module_name in ["numpy", "sklearn"]:
            if has_module(module_name):
                print(f"OK       Python package available: {module_name}")
            else:
                print(f"MISSING  Python package required for model training: {module_name}")
                ok = False

    if require_rasterio:
        for module_name in ["numpy", "rasterio"]:
            if has_module(module_name):
                print(f"OK       Python package available: {module_name}")
            else:
                print(f"MISSING  Python package required for terrain rebuilds: {module_name}")
                ok = False

    return ok


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check whether this machine is ready to run the weather reconstruction pipeline."
    )
    parser.add_argument(
        "--require-sklearn",
        action="store_true",
        help="Require numpy and scikit-learn imports for model training.",
    )
    parser.add_argument(
        "--require-rasterio",
        action="store_true",
        help="Require rasterio for rebuilding DEM-derived terrain features.",
    )
    parser.add_argument(
        "--check-cache-integrity",
        action="store_true",
        help="Run PRAGMA integrity_check on the SQLite weather cache.",
    )
    parser.add_argument(
        "--min-free-disk-gb",
        type=float,
        default=MIN_FREE_DISK_GB,
        help="Minimum free disk space expected at the project root.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    ok = True

    print("Remote Environment Check")
    print("========================")
    print(f"Project root: {config.PROJECT_DIR}")
    print()

    print("Python")
    print("------")
    ok = check_python_modules(arguments.require_sklearn, arguments.require_rasterio) and ok
    print()

    print("Required Files")
    print("--------------")
    for label, path in REQUIRED_FILES:
        ok = check_file(label, path) and ok
    ok = check_sqlite_cache(config.WEATHER_CACHE_FILE, arguments.check_cache_integrity) and ok
    print()

    print("Output Directories")
    print("------------------")
    for path in REQUIRED_OUTPUT_DIRS:
        ok = check_output_dir(path) and ok
    print()

    print("Disk")
    print("----")
    ok = check_disk_space(config.PROJECT_DIR, arguments.min_free_disk_gb) and ok
    print()

    if ok:
        print("READY    Remote environment checks passed.")
        return

    print("FAILED   Fix the missing or blocked items above before a long run.")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
