"""Exercise reliability backend routes with generated temporary fixture artifacts.

The tests verify surface payloads, station overlays, and error handling without depending on local model runs."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import tempfile

from fastapi import HTTPException


PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / "station-proxy-backend"
SCRIPT_DIR = PROJECT_DIR / "weather_reconstruction_model" / "scripts"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common.json_utils import write_json_file
from common.reliability_surface import build_summary_payload, write_reliability_png
from common.csv_utils import write_csv_rows


def load_backend_module():
    backend_path = str(BACKEND_DIR)
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    module_name = "station_proxy_backend_main_reliability_test"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, BACKEND_DIR / "main.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write_fixture_artifacts(root: Path, project_dir: Path) -> None:
    run_dir = root / "paloma_v1_reliability"
    surface = {
        "schemaVersion": "reliability-surface-v1",
        "modelRunId": "paloma_v1_reliability",
        "scoreVersion": "holdout-mae-spatial-reliability-v1",
        "layer": "overall",
        "status": "ok",
        "bounds": {
            "latMin": 39.0,
            "latMax": 39.2,
            "lonMin": -105.2,
            "lonMax": -105.0,
        },
        "grid": {
            "width": 2,
            "height": 2,
            "spacingKm": 20.0,
            "maskedPointCount": 1,
        },
        "imageArtifact": "reliability_surface_overall.png",
        "surfaceSummary": {
            "count": 1,
            "median": 82.0,
            "mean": 82.0,
        },
        "points": [
            {
                "row": 0,
                "column": 0,
                "latitude": 39.1,
                "longitude": -105.1,
                "reliability": 82.0,
                "expectedMaeF": 1.7,
                "evidenceStrength": 88.0,
            }
        ],
        "holdoutStations": [
            {
                "stationId": "TEST001",
                "stationName": "Test Station",
                "latitude": 39.1,
                "longitude": -105.1,
                "observedMaeF": 1.7,
                "observedRmseF": 2.1,
                "observedCorrelation": 0.982,
                "testRows": 120,
                "observedReliability": 82.0,
                "maePercentile": 0.18,
                "sourceVariable": "tavg",
            }
        ],
    }
    write_json_file(run_dir / "reliability_surface_overall.json", surface)
    write_json_file(
        run_dir / "reliability_summary.json",
        build_summary_payload("paloma_v1_reliability", {"overall": surface}),
    )
    write_reliability_png(
        run_dir / "reliability_surface_overall.png",
        [[82.0, None], [None, None]],
    )
    write_csv_rows(
        root / "paloma_v1_tavg" / "station_metrics.csv",
        [
            {
                "target_station_id": "TEST001",
                "target_name": "Test Station",
                "test_rows": 120,
                "mae": 1.7,
                "rmse": 2.1,
                "correlation": 0.982,
            }
        ],
        ["target_station_id", "target_name", "test_rows", "mae", "rmse", "correlation"],
    )
    write_csv_rows(
        project_dir / "alpine_outputs" / "paloma" / "paloma_v1_tavg_station_holdout_master.csv",
        [
            {
                "model_id": "paloma_v1_tavg",
                "variable": "tavg",
                "target_station_id": "TEST001",
                "target_name": "Test Station",
                "train_rows": 1000,
                "test_rows": 120,
                "mae": 1.7,
                "rmse": 2.1,
                "correlation": 0.982,
                "bias": -0.45,
                "strict_pass": "True",
                "elapsed_seconds": 12.5,
                "holdout_group_id": "group_001",
                "holdout_group_size": 1,
            }
        ],
        [
            "model_id",
            "variable",
            "target_station_id",
            "target_name",
            "train_rows",
            "test_rows",
            "mae",
            "rmse",
            "correlation",
            "bias",
            "strict_pass",
            "elapsed_seconds",
            "holdout_group_id",
            "holdout_group_size",
        ],
    )
    write_csv_rows(
        root / "paloma_v1_tavg" / "final_model_station_metrics.csv",
        [
            {
                "model_run_id": "paloma_v1_tavg",
                "variable": "tavg",
                "target_station_id": "TEST001",
                "target_name": "Test Station",
                "evaluation_mode": "final_model_in_sample_fit",
                "row_count": 365,
                "start_date": "2020-01-01",
                "end_date": "2020-12-31",
                "mae": 0.42,
                "rmse": 0.61,
                "correlation": 0.9981,
                "bias": -0.03,
                "actual_mean": 52.4,
                "predicted_mean": 52.43,
            }
        ],
        [
            "model_run_id",
            "variable",
            "target_station_id",
            "target_name",
            "evaluation_mode",
            "row_count",
            "start_date",
            "end_date",
            "mae",
            "rmse",
            "correlation",
            "bias",
            "actual_mean",
            "predicted_mean",
        ],
    )
    write_csv_rows(
        root / "paloma_v1_tavg" / "final_model_predictions.csv",
        [
            {
                "date": "2020-01-01",
                "target_station_id": "TEST001",
                "target_name": "Test Station",
                "actual_tavg": 50.0,
                "predicted_tavg": 50.5,
            },
            {
                "date": "2020-01-02",
                "target_station_id": "TEST001",
                "target_name": "Test Station",
                "actual_tavg": 52.0,
                "predicted_tavg": 51.4,
            },
            {
                "date": "2020-01-03",
                "target_station_id": "OTHER",
                "target_name": "Other Station",
                "actual_tavg": 44.0,
                "predicted_tavg": 45.0,
            },
        ],
        ["date", "target_station_id", "target_name", "actual_tavg", "predicted_tavg"],
    )
    write_csv_rows(
        project_dir / "alpine_outputs" / "predictions" / "paloma_v1_tavg_group_holdout_group_001_predictions.csv",
        [
            {
                "date": "2024-01-01",
                "target_station_id": "TEST001",
                "target_name": "Test Station",
                "holdout_group_id": "group_001",
                "holdout_group_size": 1,
                "actual_tavg": 48.0,
                "predicted_tavg": 47.4,
                "error": 0.6,
            },
            {
                "date": "2024-01-02",
                "target_station_id": "TEST001",
                "target_name": "Test Station",
                "holdout_group_id": "group_001",
                "holdout_group_size": 1,
                "actual_tavg": 49.0,
                "predicted_tavg": 50.2,
                "error": -1.2,
            },
        ],
        [
            "date",
            "target_station_id",
            "target_name",
            "holdout_group_id",
            "holdout_group_size",
            "actual_tavg",
            "predicted_tavg",
            "error",
        ],
    )
    write_csv_rows(
        project_dir / "NOAA_Inventory_Sort" / "target_station_candidates.csv",
        [
            {
                "station_id": "TEST001",
                "latitude": 39.1,
                "longitude": -105.1,
                "has_tmax": 1,
                "has_tmin": 1,
                "tmax_start": 1980,
                "tmax_end": 2025,
                "tmin_start": 1981,
                "tmin_end": 2025,
                "usable_temp_start": 1981,
                "usable_temp_end": 2025,
                "usable_temp_years": 45,
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
    write_csv_rows(
        project_dir / "NOAA_Inventory_Sort" / "hub_station_candidates.csv",
        [
            {
                "station_id": "TEST001",
                "latitude": 39.1,
                "longitude": -105.1,
                "has_tmax": 1,
                "has_tmin": 1,
                "tmax_start": 1980,
                "tmax_end": 2025,
                "tmin_start": 1981,
                "tmin_end": 2025,
                "usable_temp_start": 1981,
                "usable_temp_end": 2025,
                "usable_temp_years": 45,
                "is_target_candidate": 1,
                "is_hub_candidate": 1,
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
    write_csv_rows(
        project_dir / "terrain_data" / "processed" / "station_terrain_features.csv",
        [
            {
                "station_id": "TEST001",
                "noaa_elevation_m": 1620.0,
                "dem_elevation_m": 1615.0,
                "dem_minus_noaa_elevation_m": -5.0,
                "slope_degrees": 3.4,
                "local_relief_m": 44.0,
                "terrain_position_index_m": 6.2,
                "slope_degrees_r300m": 4.2,
                "local_relief_m_r300m": 55.0,
                "terrain_position_index_m_r300m": 8.4,
            }
        ],
        [
            "station_id",
            "noaa_elevation_m",
            "dem_elevation_m",
            "dem_minus_noaa_elevation_m",
            "slope_degrees",
            "local_relief_m",
            "terrain_position_index_m",
            "slope_degrees_r300m",
            "local_relief_m_r300m",
            "terrain_position_index_m_r300m",
        ],
    )


def test_reliability_backend_routes_return_fixture_artifacts() -> None:
    backend = load_backend_module()

    with tempfile.TemporaryDirectory() as temp_dir:
        model_run_root = Path(temp_dir) / "model_runs"
        project_dir = Path(temp_dir) / "project"
        write_fixture_artifacts(model_run_root, project_dir)
        settings = backend.settings.__class__(
            **{
                **backend.settings.__dict__,
                "project_dir": project_dir,
                "model_run_root": model_run_root,
                "confidence_target_candidate_file": (
                    project_dir / "NOAA_Inventory_Sort" / "target_station_candidates.csv"
                ),
                "confidence_hub_candidate_file": (
                    project_dir / "NOAA_Inventory_Sort" / "hub_station_candidates.csv"
                ),
                "confidence_terrain_feature_file": (
                    project_dir / "terrain_data" / "processed" / "station_terrain_features.csv"
                ),
                "reliability_model_run_id": "paloma_v1_reliability",
            }
        )
        backend.reliability_service = backend.ReliabilitySurfaceService(settings)

        summary = backend.reliability_summary()
        surface = backend.reliability_surface("overall")
        sample = backend.reliability_surface_sample(lat=39.1, lon=-105.1, layer="overall")
        station = backend.reliability_station_detail(station_id="TEST001", layer="overall")
        image = backend.reliability_surface_image("overall")
        bias_overlay = backend.reliability_station_overlay_image("overall", "bias")
        correlation_overlay = backend.reliability_station_overlay_image("overall", "correlation")
        mae_overlay = backend.reliability_station_overlay_image("overall", "mae")
        rmse_overlay = backend.reliability_station_overlay_image("overall", "rmse")
        final_correlation_overlay = backend.reliability_station_overlay_image("overall", "final-correlation")
        final_mae_overlay = backend.reliability_station_overlay_image("overall", "final-mae")
        final_rmse_overlay = backend.reliability_station_overlay_image("overall", "final-rmse")
        final_bias_overlay = backend.reliability_station_overlay_image("overall", "final-bias")
        bias_overlay_header = Path(bias_overlay.path).read_bytes()[:8]

    assert summary["defaultLayer"] == "overall"
    assert summary["availableLayers"] == ["overall"]
    assert surface["imageUrl"] == (
        "/model-runs/reliability/surface.png?layer=overall"
        "&visual=holdout-mae-spatial-reliability-v1"
    )
    assert surface["holdoutStations"][0]["holdoutBiasF"] == -0.45
    assert surface["holdoutStations"][0]["holdoutStrictPass"] is True
    assert surface["holdoutStations"][0]["finalModelMetricStatus"] == "available"
    assert surface["holdoutStations"][0]["finalModelMaeF"] == 0.42
    assert surface["holdoutStations"][0]["finalModelRmseF"] == 0.61
    assert surface["holdoutStations"][0]["finalModelCorrelation"] == 0.9981
    assert surface["holdoutStations"][0]["finalModelBiasF"] == -0.03
    assert sample["status"] == "ok"
    assert sample["sample"]["reliability"] == 82.0
    assert station["station"]["stationId"] == "TEST001"
    assert station["station"]["profile"]["isTargetCandidate"] is True
    assert station["station"]["profile"]["isHubCandidate"] is True
    assert station["station"]["profile"]["usableTempYears"] == 45
    assert station["station"]["terrainFeatures"]["demElevationM"] == 1615.0
    assert station["context"]["terrainFeatureStatus"] == "available"
    assert station["fullyTrainedModelVsObserved"]["maeF"] == 0.42
    assert station["fullyTrainedModelVsObserved"]["rowCount"] == 365
    assert station["fullyTrainedModelVsObserved"]["evaluationMode"] == "final_model_in_sample_fit"
    assert station["preparedPalomaStationMetrics"]["maeF"] == 1.7
    assert station["context"]["fullyTrainedMetricStatus"] == "available"
    assert station["stationHoldoutTest"]["correlation"] == 0.982
    assert station["holdoutRun"]["biasF"] == -0.45
    assert station["holdoutRun"]["holdoutGroupId"] == "group_001"
    assert station["temperaturePredictionSeries"]["variable"] == "tavg"
    assert station["temperaturePredictionSeries"]["finalModel"]["status"] == "available"
    assert station["temperaturePredictionSeries"]["finalModel"]["totalRows"] == 2
    assert station["temperaturePredictionSeries"]["finalModel"]["points"][0] == {
        "date": "2020-01-01",
        "actualF": 50.0,
        "predictedF": 50.5,
        "errorF": -0.5,
    }
    assert station["temperaturePredictionSeries"]["holdout"]["status"] == "available"
    assert station["temperaturePredictionSeries"]["holdout"]["totalRows"] == 2
    assert station["temperaturePredictionSeries"]["holdout"]["points"][1] == {
        "date": "2024-01-02",
        "actualF": 49.0,
        "predictedF": 50.2,
        "errorF": -1.2,
    }
    assert Path(image.path).name == "reliability_surface_overall.png"
    assert Path(bias_overlay.path).name == "reliability_station_overlay_overall_bias.png"
    assert Path(correlation_overlay.path).name == "reliability_station_overlay_overall_correlation.png"
    assert Path(mae_overlay.path).name == "reliability_station_overlay_overall_mae.png"
    assert Path(rmse_overlay.path).name == "reliability_station_overlay_overall_rmse.png"
    assert Path(final_correlation_overlay.path).name == (
        "reliability_station_overlay_overall_final-correlation.png"
    )
    assert Path(final_mae_overlay.path).name == "reliability_station_overlay_overall_final-mae.png"
    assert Path(final_rmse_overlay.path).name == "reliability_station_overlay_overall_final-rmse.png"
    assert Path(final_bias_overlay.path).name == "reliability_station_overlay_overall_final-bias.png"
    assert bias_overlay_header == b"\x89PNG\r\n\x1a\n"


def test_reliability_backend_missing_summary_reports_404() -> None:
    backend = load_backend_module()

    with tempfile.TemporaryDirectory() as temp_dir:
        model_run_root = Path(temp_dir) / "model_runs"
        settings = backend.settings.__class__(
            **{
                **backend.settings.__dict__,
                "model_run_root": model_run_root,
                "reliability_model_run_id": "paloma_v1_reliability",
            }
        )
        backend.reliability_service = backend.ReliabilitySurfaceService(settings)

        try:
            backend.reliability_summary()
        except HTTPException as error:
            status_code = error.status_code
        else:
            raise AssertionError("Expected missing reliability summary to raise HTTPException.")

    assert status_code == 404


def main() -> None:
    test_reliability_backend_routes_return_fixture_artifacts()
    test_reliability_backend_missing_summary_reports_404()
    print("reliability backend tests passed")


if __name__ == "__main__":
    main()
