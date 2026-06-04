from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = SCRIPT_DIR.parents[1]
BUILD_SCRIPT = SCRIPT_DIR / "build_reliability_surfaces.py"
PREP_SCRIPT = SCRIPT_DIR / "prepare_paloma_reliability_inputs.py"
sys.path.insert(0, str(SCRIPT_DIR))

from common.csv_utils import write_csv_rows
from common.reliability_surface import (
    build_grid_cells,
    build_station_extent_boundary_geojson,
    color_for_reliability,
    empirical_percentile,
    expected_mae_usefulness_score,
    extract_polygon_rings,
    load_boundary_geojson,
    point_in_boundary,
    reliability_from_expected_mae,
    surface_relative_visual_scale,
)


def square_basin() -> dict[str, object]:
    return {
        "type": "Feature",
        "properties": {"name": "Fixture Basin"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-105.4, 39.0],
                [-105.0, 39.0],
                [-105.0, 39.4],
                [-105.4, 39.4],
                [-105.4, 39.0],
            ]],
        },
    }


def write_boundary(path: Path) -> None:
    path.write_text(json.dumps(square_basin()) + "\n")


def write_candidates(path: Path) -> None:
    write_csv_rows(
        path,
        [
            {"station_id": "GOOD", "latitude": 39.32, "longitude": -105.32},
            {"station_id": "MID", "latitude": 39.20, "longitude": -105.20},
            {"station_id": "BAD", "latitude": 39.08, "longitude": -105.08},
        ],
        ["station_id", "latitude", "longitude"],
    )


def write_empty_hub_candidates(path: Path) -> None:
    write_csv_rows(
        path,
        [{"station_id": "HUB", "latitude": 39.18, "longitude": -105.18}],
        ["station_id", "latitude", "longitude"],
    )


def write_station_metrics(path: Path, variable_offset: float) -> None:
    write_csv_rows(
        path,
        [
            {
                "target_station_id": "GOOD",
                "target_name": "Good Station",
                "test_rows": 400,
                "mae": 1.0 + variable_offset,
                "rmse": 1.5,
                "correlation": 0.99,
            },
            {
                "target_station_id": "MID",
                "target_name": "Middle Station",
                "test_rows": 400,
                "mae": 2.5 + variable_offset,
                "rmse": 3.0,
                "correlation": 0.96,
            },
            {
                "target_station_id": "BAD",
                "target_name": "Bad Station",
                "test_rows": 400,
                "mae": 5.0 + variable_offset,
                "rmse": 6.0,
                "correlation": 0.89,
            },
        ],
        ["target_station_id", "target_name", "test_rows", "mae", "rmse", "correlation"],
    )


def build_fixture_model_runs(root: Path) -> None:
    offsets = {"tavg": 0.0, "tmin": 0.2, "tmax": 0.4}
    for variable, offset in offsets.items():
        run_dir = root / f"paloma_v1_{variable}"
        run_dir.mkdir(parents=True)
        write_station_metrics(run_dir / "station_metrics.csv", offset)


def test_low_mae_maps_to_higher_reliability() -> None:
    sorted_maes = [1.0, 2.0, 4.0, 8.0]

    low_reliability = reliability_from_expected_mae(sorted_maes, 1.25)
    high_reliability = reliability_from_expected_mae(sorted_maes, 7.0)

    assert empirical_percentile(sorted_maes, 1.25) < empirical_percentile(sorted_maes, 7.0)
    assert low_reliability > high_reliability


def test_surface_relative_visual_scale_makes_top_trend_green() -> None:
    values = [float(value) for value in range(100)]
    visual_scale = surface_relative_visual_scale(values)

    assert color_for_reliability(5.0, visual_scale)[:3] == (185, 28, 28)
    assert color_for_reliability(90.0, visual_scale)[:3] == (22, 163, 74)


def test_expected_mae_usefulness_rewards_lower_error() -> None:
    assert expected_mae_usefulness_score(2.0) > expected_mae_usefulness_score(5.0)


def test_boundary_mask_excludes_outside_points() -> None:
    polygons = extract_polygon_rings(square_basin())

    assert point_in_boundary(39.2, -105.2, polygons)
    assert not point_in_boundary(39.8, -105.2, polygons)

    bounds, grid, cells = build_grid_cells(polygons, spacing_km=10.0, max_points=1000)

    assert bounds.lat_min == 39.0
    assert grid["maskedPointCount"] == len(cells)
    assert len(cells) > 0
    assert all(point_in_boundary(cell.latitude, cell.longitude, polygons) for cell in cells)


def test_station_extent_boundary_uses_padded_station_rectangle() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        stations = temp_path / "stations.csv"
        write_csv_rows(
            stations,
            [
                {"station_id": "SOUTHWEST", "latitude": 31.0, "longitude": -115.0},
                {"station_id": "NORTHEAST", "latitude": 43.5, "longitude": -102.0},
            ],
            ["station_id", "latitude", "longitude"],
        )

        boundary = build_station_extent_boundary_geojson([stations], padding_km=30.0)

    properties = boundary["properties"]
    padded_bounds = properties["paddedBounds"]
    raw_bounds = properties["rawStationBounds"]

    assert properties["boundaryType"] == "station_extent_rectangle"
    assert properties["stationCount"] == 2
    assert raw_bounds["latMin"] == 31.0
    assert raw_bounds["latMax"] == 43.5
    assert raw_bounds["lonMin"] == -115.0
    assert raw_bounds["lonMax"] == -102.0
    assert padded_bounds["latMin"] < 31.0
    assert padded_bounds["latMax"] > 43.5
    assert padded_bounds["lonMin"] < -115.0
    assert padded_bounds["lonMax"] > -102.0


def test_build_reliability_surfaces_writes_json_and_png_artifacts() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        model_run_root = temp_path / "model_runs"
        output_dir = temp_path / "paloma_v1_reliability"
        boundary_file = temp_path / "basin.geojson"
        target_candidates = temp_path / "targets.csv"
        hub_candidates = temp_path / "hubs.csv"
        terrain_file = temp_path / "missing_terrain.csv"

        write_boundary(boundary_file)
        write_candidates(target_candidates)
        write_empty_hub_candidates(hub_candidates)
        build_fixture_model_runs(model_run_root)

        completed = subprocess.run(
            [
                sys.executable,
                str(BUILD_SCRIPT),
                "--model-run-root",
                str(model_run_root),
                "--output-dir",
                str(output_dir),
                "--boundary-file",
                str(boundary_file),
                "--target-candidates",
                str(target_candidates),
                "--hub-candidates",
                str(hub_candidates),
                "--terrain-features",
                str(terrain_file),
                "--spacing-km",
                "10",
            ],
            cwd=PROJECT_DIR,
            check=True,
            text=True,
            capture_output=True,
        )

        summary = json.loads((output_dir / "reliability_summary.json").read_text())
        helpfulness = json.loads((output_dir / "reliability_surface_helpfulness.json").read_text())
        overall = json.loads((output_dir / "reliability_surface_overall.json").read_text())
        tavg = json.loads((output_dir / "reliability_surface_tavg.json").read_text())
        helpfulness_png_exists = (output_dir / "reliability_surface_helpfulness.png").exists()
        overall_png_exists = (output_dir / "reliability_surface_overall.png").exists()
        tavg_png_header = (output_dir / "reliability_surface_tavg.png").read_bytes()[:8]

        assert "Reliability run:" in completed.stdout
        assert summary["schemaVersion"] == "reliability-summary-v1"
        assert summary["defaultLayer"] == "helpfulness"
        assert helpfulness["layer"] == "helpfulness"
        assert helpfulness["status"] == "ok"
        assert helpfulness["calibration"]["method"] == "weighted_decision_support_score"
        assert len(helpfulness["holdoutStations"]) == 3
        assert helpfulness["holdoutStations"][0]["sourceVariable"] in {"tavg", "tmin", "tmax"}
        assert overall["schemaVersion"] == "reliability-surface-v1"
        assert overall["layer"] == "overall"
        assert tavg["layer"] == "tavg"
        assert tavg["calibration"]["lowMaeMeaning"] == "Higher reliability"
        assert tavg["surfaceSummary"]["count"] > 0
        assert helpfulness_png_exists
        assert overall_png_exists
        assert tavg_png_header.startswith(b"\x89PNG")


def test_build_reliability_surfaces_allows_partial_variable_artifacts() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        model_run_root = temp_path / "model_runs"
        output_dir = temp_path / "paloma_v1_reliability"
        boundary_file = temp_path / "basin.geojson"
        target_candidates = temp_path / "targets.csv"
        hub_candidates = temp_path / "hubs.csv"
        terrain_file = temp_path / "missing_terrain.csv"

        write_boundary(boundary_file)
        write_candidates(target_candidates)
        write_empty_hub_candidates(hub_candidates)
        tavg_dir = model_run_root / "paloma_v1_tavg"
        tavg_dir.mkdir(parents=True)
        write_station_metrics(tavg_dir / "station_metrics.csv", 0.0)

        completed = subprocess.run(
            [
                sys.executable,
                str(BUILD_SCRIPT),
                "--model-run-root",
                str(model_run_root),
                "--output-dir",
                str(output_dir),
                "--boundary-file",
                str(boundary_file),
                "--target-candidates",
                str(target_candidates),
                "--hub-candidates",
                str(hub_candidates),
                "--terrain-features",
                str(terrain_file),
                "--spacing-km",
                "10",
                "--allow-missing",
            ],
            cwd=PROJECT_DIR,
            check=True,
            text=True,
            capture_output=True,
        )

        summary = json.loads((output_dir / "reliability_summary.json").read_text())
        helpfulness = json.loads((output_dir / "reliability_surface_helpfulness.json").read_text())

        assert "Skipped missing variables: tmin, tmax" in completed.stdout
        assert summary["defaultLayer"] == "helpfulness"
        assert summary["availableLayers"] == ["helpfulness", "tavg"]
        assert helpfulness["status"] == "partial"
        assert helpfulness["sourceVariableLayers"] == ["tavg"]
        assert helpfulness["missingVariableLayers"] == ["tmin", "tmax"]
        assert len(helpfulness["holdoutStations"]) == 3
        assert {station["sourceVariable"] for station in helpfulness["holdoutStations"]} == {"tavg"}
        assert (output_dir / "reliability_surface_helpfulness.json").exists()
        assert (output_dir / "reliability_surface_helpfulness.png").exists()
        assert (output_dir / "reliability_surface_tavg.json").exists()
        assert (output_dir / "reliability_surface_tavg.png").exists()
        assert not (output_dir / "reliability_surface_overall.json").exists()


def test_prepare_paloma_reliability_inputs_normalizes_explicit_metrics() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        model_run_root = temp_path / "model_runs"
        boundary_file = temp_path / "boundary.geojson"
        report_file = temp_path / "readiness.json"
        target_candidates = temp_path / "targets.csv"
        hub_candidates = temp_path / "hubs.csv"
        terrain_file = temp_path / "missing_terrain.csv"

        write_candidates(target_candidates)
        write_empty_hub_candidates(hub_candidates)
        metric_files = {}
        for variable, offset in {"tavg": 0.0, "tmin": 0.2, "tmax": 0.6}.items():
            metric_file = temp_path / f"{variable}_station_metrics.csv"
            write_station_metrics(metric_file, offset)
            metric_files[variable] = metric_file

        completed = subprocess.run(
            [
                sys.executable,
                str(PREP_SCRIPT),
                "--model-run-root",
                str(model_run_root),
                "--boundary-file",
                str(boundary_file),
                "--target-candidates",
                str(target_candidates),
                "--hub-candidates",
                str(hub_candidates),
                "--terrain-features",
                str(terrain_file),
                "--tavg-metrics",
                str(metric_files["tavg"]),
                "--tmin-metrics",
                str(metric_files["tmin"]),
                "--tmax-metrics",
                str(metric_files["tmax"]),
                "--report-file",
                str(report_file),
                "--skip-scan",
            ],
            cwd=PROJECT_DIR,
            check=True,
            text=True,
            capture_output=True,
        )
        report = json.loads(report_file.read_text())

        assert "Readiness report:" in completed.stdout
        assert report["status"] == "ready"
        assert report["missingVariables"] == []
        assert boundary_file.exists()
        assert (model_run_root / "paloma_v1_tavg" / "station_metrics.csv").exists()
        assert (model_run_root / "paloma_v1_tmin" / "station_metrics.csv").exists()
        assert (model_run_root / "paloma_v1_tmax" / "station_metrics.csv").exists()


def main() -> None:
    test_low_mae_maps_to_higher_reliability()
    test_surface_relative_visual_scale_makes_top_trend_green()
    test_expected_mae_usefulness_rewards_lower_error()
    test_boundary_mask_excludes_outside_points()
    test_station_extent_boundary_uses_padded_station_rectangle()
    test_build_reliability_surfaces_writes_json_and_png_artifacts()
    test_build_reliability_surfaces_allows_partial_variable_artifacts()
    test_prepare_paloma_reliability_inputs_normalizes_explicit_metrics()
    print("reliability surface tests passed")


if __name__ == "__main__":
    main()
