from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = SCRIPT_DIR.parents[1]
BUILD_SCRIPT = SCRIPT_DIR / "build_confidence_points.py"
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


def build_base_files(temp_path: Path) -> dict[str, Path]:
    target_file = temp_path / "target_candidates.csv"
    hub_file = temp_path / "hub_candidates.csv"
    terrain_file = temp_path / "terrain.csv"
    metrics_file = temp_path / "metrics.csv"

    write_candidate_file(target_file, "T1", 39.75, -105.0)
    write_candidate_file(hub_file, "H1", 39.80, -105.05)
    write_terrain_file(terrain_file)
    write_metrics_file(metrics_file)

    return {
        "target": target_file,
        "hub": hub_file,
        "terrain": terrain_file,
        "metrics": metrics_file,
    }


def run_build_command(*extra_args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(BUILD_SCRIPT),
            *extra_args,
        ],
        cwd=PROJECT_DIR,
        check=check,
        text=True,
        capture_output=True,
    )


def common_args(files: dict[str, Path]) -> list[str]:
    return [
        "--target-candidates",
        str(files["target"]),
        "--hub-candidates",
        str(files["hub"]),
        "--terrain-features",
        str(files["terrain"]),
        "--validation-metrics",
        str(files["metrics"]),
        "--lat-min",
        "39.75",
        "--lat-max",
        "39.86",
        "--lon-min",
        "-105.05",
        "--lon-max",
        "-104.94",
        "--spacing-km",
        "10",
        "--model-reference",
        "surface-fixture-model",
        "--score-version",
        "surface-test-v1",
    ]


def test_build_confidence_points_writes_json_surface() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        files = build_base_files(temp_path)
        output_file = temp_path / "confidence-points.json"

        completed = run_build_command(
            *common_args(files),
            "--output-file",
            str(output_file),
            "--nearest-station-limit",
            "1",
            "--compact",
        )

        payload = json.loads(output_file.read_text())

    assert "Wrote" in completed.stdout
    assert payload["schemaVersion"] == "confidence-points-v1"
    assert payload["scoreVersion"] == "surface-test-v1"
    assert payload["modelReference"] == "surface-fixture-model"
    assert payload["spacingKm"] == 10.0
    assert payload["pointCount"] == len(payload["points"])
    assert payload["pointCount"] > 0
    assert payload["bounds"]["latMin"] == 39.75
    first_point = payload["points"][0]
    assert first_point["score"] >= 0
    assert first_point["score"] <= 100
    assert first_point["components"]
    assert len(first_point["nearestStations"]) <= 1


def test_build_confidence_points_dry_run_does_not_write_file() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        files = build_base_files(temp_path)
        output_file = temp_path / "dry-run.json"

        completed = run_build_command(
            *common_args(files),
            "--output-file",
            str(output_file),
            "--dry-run",
        )

        assert not output_file.exists()

    assert "Confidence point generation dry run" in completed.stdout
    assert "Point count:" in completed.stdout


def test_build_confidence_points_respects_max_points_guard() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        files = build_base_files(temp_path)
        output_file = temp_path / "too-many.json"

        completed = run_build_command(
            *common_args(files),
            "--output-file",
            str(output_file),
            "--max-points",
            "1",
            check=False,
        )

        assert not output_file.exists()

    assert completed.returncode != 0
    assert "exceeds --max-points" in completed.stderr


def main() -> None:
    test_build_confidence_points_writes_json_surface()
    test_build_confidence_points_dry_run_does_not_write_file()
    test_build_confidence_points_respects_max_points_guard()
    print("build confidence points tests passed")


if __name__ == "__main__":
    main()
