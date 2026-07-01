"""Test the single-point confidence scoring CLI.

The checks verify JSON output and error behavior using temporary support inputs."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = SCRIPT_DIR.parents[1]
SCORE_SCRIPT = SCRIPT_DIR / "score_confidence_point.py"
sys.path.insert(0, str(SCRIPT_DIR))

from common.csv_utils import write_csv_rows


def write_candidate_file(path: Path, station_id: str, latitude: float, longitude: float) -> None:
    write_csv_rows(
        path,
        [
            {
                "station_id": station_id,
                "latitude": latitude,
                "longitude": longitude,
                "usable_temp_start": 1980,
                "usable_temp_end": 2026,
                "usable_temp_years": 47,
            }
        ],
        [
            "station_id",
            "latitude",
            "longitude",
            "usable_temp_start",
            "usable_temp_end",
            "usable_temp_years",
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
                "noaa_elevation_m": 1600,
                "dem_elevation_m": 1595,
                "slope_degrees": 3,
                "local_relief_m": 60,
                "terrain_position_index_m": 5,
            },
            {
                "station_id": "H1",
                "station_role": "hub",
                "station_name": "HUB ONE",
                "latitude": 39.80,
                "longitude": -105.05,
                "noaa_elevation_m": 1610,
                "dem_elevation_m": 1608,
                "slope_degrees": 4,
                "local_relief_m": 70,
                "terrain_position_index_m": 6,
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
                "mae": 1.2,
                "rmse": 1.8,
                "correlation": 0.995,
                "strict_pass": "True",
            }
        ],
        [
            "target_station_id",
            "target_name",
            "test_rows",
            "mae",
            "rmse",
            "correlation",
            "strict_pass",
        ],
    )


def run_score_command(*extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCORE_SCRIPT),
            *extra_args,
        ],
        cwd=PROJECT_DIR,
        check=True,
        text=True,
        capture_output=True,
    )


def test_score_confidence_point_writes_valid_json() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        target_file = temp_path / "target_candidates.csv"
        hub_file = temp_path / "hub_candidates.csv"
        terrain_file = temp_path / "terrain.csv"
        metrics_file = temp_path / "metrics.csv"

        write_candidate_file(target_file, "T1", 39.75, -105.0)
        write_candidate_file(hub_file, "H1", 39.80, -105.05)
        write_terrain_file(terrain_file)
        write_metrics_file(metrics_file)

        completed = run_score_command(
            "39.75",
            "-105.0",
            "--elevation-m",
            "1600",
            "--target-candidates",
            str(target_file),
            "--hub-candidates",
            str(hub_file),
            "--terrain-features",
            str(terrain_file),
            "--validation-metrics",
            str(metrics_file),
            "--model-reference",
            "cli-fixture-model",
            "--score-version",
            "cli-test-v1",
            "--component-weight",
            "stationCoverage=0.5",
            "--compact",
        )

    data = json.loads(completed.stdout)
    assert data["status"] == "ok"
    assert data["scoreVersion"] == "cli-test-v1"
    assert data["modelReference"] == "cli-fixture-model"
    assert data["score"] >= 0
    assert data["score"] <= 100
    assert data["components"]["stationCoverage"] >= 0
    assert data["nearestStations"][0]["stationId"] == "T1"
    assert data["reasons"]


def test_score_confidence_point_rejects_unknown_weight() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        target_file = temp_path / "target_candidates.csv"
        hub_file = temp_path / "hub_candidates.csv"
        terrain_file = temp_path / "terrain.csv"

        write_candidate_file(target_file, "T1", 39.75, -105.0)
        write_candidate_file(hub_file, "H1", 39.80, -105.05)
        write_terrain_file(terrain_file)

        completed = subprocess.run(
            [
                sys.executable,
                str(SCORE_SCRIPT),
                "39.75",
                "-105.0",
                "--target-candidates",
                str(target_file),
                "--hub-candidates",
                str(hub_file),
                "--terrain-features",
                str(terrain_file),
                "--no-validation",
                "--component-weight",
                "unknownComponent=1.0",
            ],
            cwd=PROJECT_DIR,
            text=True,
            capture_output=True,
        )

    assert completed.returncode != 0
    assert "Unknown component weight" in completed.stderr


def main() -> None:
    test_score_confidence_point_writes_valid_json()
    test_score_confidence_point_rejects_unknown_weight()
    print("score confidence point CLI tests passed")


if __name__ == "__main__":
    main()
