from __future__ import annotations

import argparse
import csv
from pathlib import Path

import config


REQUIRED_FILES = [
    config.TARGET_CANDIDATE_FILE,
    config.HUB_CANDIDATE_FILE,
    config.TARGET_DAILY_FILE,
    config.HUB_DAILY_FILE,
    config.TERRAIN_FEATURE_FILE,
    config.WEATHER_CACHE_FILE,
]
IMPORTANT_SCRIPTS = [
    config.PROJECT_DIR / "weather_reconstruction_model" / "scripts" / "build_weather_cache.py",
    config.PROJECT_DIR / "weather_reconstruction_model" / "scripts" / "build_station_terrain_features.py",
    config.PROJECT_DIR / "weather_reconstruction_model" / "scripts" / "build_general_training_table.py",
    config.PROJECT_DIR / "weather_reconstruction_model" / "scripts" / "train_tree_temperature_model.py",
    config.PROJECT_DIR / "weather_reconstruction_model" / "scripts" / "train_station_holdout_model.py",
]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit local files and generated artifacts before long model runs."
    )
    parser.add_argument(
        "--large-file-threshold-mb",
        type=float,
        default=500.0,
        help="Report generated files larger than this size.",
    )
    return parser.parse_args()


def file_size_mb(file_path: Path) -> float:
    return file_path.stat().st_size / (1024 * 1024)


def count_csv_rows(file_path: Path) -> int | None:
    if not file_path.exists() or file_path.suffix.lower() != ".csv":
        return None

    with file_path.open("r", newline="") as file:
        return max(0, sum(1 for _ in file) - 1)


def csv_columns(file_path: Path) -> list[str]:
    if not file_path.exists() or file_path.suffix.lower() != ".csv":
        return []

    with file_path.open("r", newline="") as file:
        reader = csv.reader(file)
        return next(reader, [])


def status_line(label: str, ok: bool, detail: str = "") -> str:
    status = "OK" if ok else "MISSING"
    return f"{status:<8} {label} {detail}".rstrip()


def audit_required_files() -> None:
    print("Required files")
    print("--------------")

    for file_path in REQUIRED_FILES:
        if file_path.exists():
            detail = f"({file_size_mb(file_path):.1f} MB)"
            row_count = count_csv_rows(file_path)

            if row_count is not None:
                detail += f", {row_count} rows"

            print(status_line(str(file_path), True, detail))
        else:
            print(status_line(str(file_path), False))


def audit_scripts() -> None:
    print()
    print("Core scripts")
    print("------------")

    for script_path in IMPORTANT_SCRIPTS:
        print(status_line(str(script_path), script_path.exists()))


def audit_terrain_columns() -> None:
    columns = csv_columns(config.TERRAIN_FEATURE_FILE)
    expected_columns = [
        "slope_degrees_r90m",
        "local_relief_m_r300m",
        "terrain_position_index_m_r990m",
        "slope_degrees_r3000m",
        "terrain_position_index_m_r3000m",
    ]
    missing_columns = [
        column
        for column in expected_columns
        if column not in columns
    ]

    print()
    print("Terrain schema")
    print("--------------")
    if missing_columns:
        print("MISSING  multi-scale columns: " + ", ".join(missing_columns))
    else:
        print("OK       multi-scale terrain columns present")


def audit_large_outputs(threshold_mb: float) -> None:
    output_roots = [
        config.OUTPUT_DIR,
        config.CACHE_DIR,
        config.PROJECT_DIR / "terrain_data" / "processed",
    ]
    large_files = []

    for root in output_roots:
        if not root.exists():
            continue

        for file_path in root.rglob("*"):
            if file_path.is_file():
                size_mb = file_size_mb(file_path)

                if size_mb >= threshold_mb:
                    large_files.append((size_mb, file_path))

    print()
    print("Large generated files")
    print("---------------------")
    if not large_files:
        print(f"OK       no generated files >= {threshold_mb:g} MB")
        return

    for size_mb, file_path in sorted(large_files, reverse=True):
        print(f"{size_mb:8.1f} MB  {file_path}")


def main() -> None:
    arguments = parse_arguments()
    print("Weather Reconstruction Readiness Audit")
    print("======================================")
    audit_required_files()
    audit_scripts()
    audit_terrain_columns()
    audit_large_outputs(arguments.large_file_threshold_mb)


if __name__ == "__main__":
    main()
