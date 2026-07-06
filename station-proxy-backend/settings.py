"""Centralize backend paths and environment-variable overrides.

This lets the app run with the default repo layout while still supporting alternate local artifact locations."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

# Current evidence source (broad Paloma grouped station holdout). The older
# option_c_limit97_5_* run is superseded history; point
# STATION_PROXY_ACTIVE_MODEL_RUN_ID at it only for archival comparisons.
DEFAULT_MODEL_RUN_ID = "paloma_v1_tavg"


@dataclass(frozen=True)
class BackendSettings:
    """Resolved filesystem and model-run settings for the FastAPI backend."""

    backend_dir: Path
    project_dir: Path
    engine_server_dir: Path
    engine_executable: Path
    target_data_file: Path
    hub_data_file: Path
    station_data_mode: str
    station_data_notice: str
    confidence_script_dir: Path
    confidence_target_candidate_file: Path
    confidence_hub_candidate_file: Path
    confidence_terrain_feature_file: Path
    confidence_validation_metrics_file: Path
    confidence_model_reference: str
    confidence_score_version: str
    model_run_root: Path
    active_model_run_id: str
    reliability_model_run_id: str
    engine_mode: str
    cors_allow_origins: list[str]


def env_path(name: str, default: Path) -> Path:
    return Path(os.getenv(name, default)).resolve()


def env_list(name: str, default: list[str]) -> list[str]:
    configured = os.getenv(name, "")
    if not configured.strip():
        return default
    return [item.strip() for item in configured.split(",") if item.strip()]


def load_settings() -> BackendSettings:
    backend_dir = Path(__file__).resolve().parent
    project_dir = env_path("STATION_PROXY_PROJECT_DIR", backend_dir.parent)
    engine_server_dir = env_path(
        "STATION_PROXY_ENGINE_SERVER_DIR",
        project_dir / "Station_Engine_Server",
    )
    default_target_data_file = project_dir / "NOAA_Inventory_Sort" / "target_daily_app_ready.csv"
    default_hub_data_file = project_dir / "NOAA_Inventory_Sort" / "hub_daily_app_ready.csv"
    target_data_file = env_path("STATION_PROXY_TARGET_FILE", default_target_data_file)
    hub_data_file = env_path("STATION_PROXY_HUB_FILE", default_hub_data_file)
    station_data_mode = "configured" if (
        os.getenv("STATION_PROXY_TARGET_FILE") or os.getenv("STATION_PROXY_HUB_FILE")
    ) else "full-noaa"
    station_data_notice = ""

    if (
        station_data_mode == "full-noaa"
        and (not target_data_file.exists() or not hub_data_file.exists())
    ):
        fixture_target_data_file = project_dir / "tests" / "fixtures" / "target_daily_app_ready.csv"
        fixture_hub_data_file = project_dir / "tests" / "fixtures" / "hub_daily_app_ready.csv"
        if fixture_target_data_file.exists() and fixture_hub_data_file.exists():
            target_data_file = fixture_target_data_file
            hub_data_file = fixture_hub_data_file
            station_data_mode = "demo-fixture"
            station_data_notice = (
                "Using tiny tracked fixture station files because the full app-ready "
                "NOAA CSVs are not present. Set STATION_PROXY_TARGET_FILE and "
                "STATION_PROXY_HUB_FILE to run the full Station Proxy dataset."
            )

    return BackendSettings(
        backend_dir=backend_dir,
        project_dir=project_dir,
        engine_server_dir=engine_server_dir,
        engine_executable=env_path(
            "STATION_PROXY_ENGINE_EXECUTABLE",
            engine_server_dir / "station_engine_server",
        ),
        target_data_file=target_data_file,
        hub_data_file=hub_data_file,
        station_data_mode=station_data_mode,
        station_data_notice=station_data_notice,
        confidence_script_dir=project_dir / "weather_reconstruction_model" / "scripts",
        confidence_target_candidate_file=env_path(
            "STATION_PROXY_CONFIDENCE_TARGET_CANDIDATES",
            project_dir / "NOAA_Inventory_Sort" / "target_station_candidates.csv",
        ),
        confidence_hub_candidate_file=env_path(
            "STATION_PROXY_CONFIDENCE_HUB_CANDIDATES",
            project_dir / "NOAA_Inventory_Sort" / "hub_station_candidates.csv",
        ),
        confidence_terrain_feature_file=env_path(
            "STATION_PROXY_CONFIDENCE_TERRAIN_FEATURES",
            project_dir / "terrain_data" / "processed" / "station_terrain_features.csv",
        ),
        confidence_validation_metrics_file=env_path(
            "STATION_PROXY_CONFIDENCE_VALIDATION_METRICS",
            project_dir
            / "weather_reconstruction_model"
            / "outputs"
            / "reports"
            / (
                "option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain_"
                "offset_terrain_standard_random_forest_station_metrics.csv"
            ),
        ),
        confidence_model_reference=os.getenv(
            "STATION_PROXY_CONFIDENCE_MODEL_REFERENCE",
            "option-c-multiscale-rf",
        ),
        confidence_score_version=os.getenv("STATION_PROXY_CONFIDENCE_SCORE_VERSION", ""),
        model_run_root=env_path(
            "STATION_PROXY_MODEL_RUN_ROOT",
            project_dir / "weather_reconstruction_model" / "model_runs",
        ),
        active_model_run_id=os.getenv(
            "STATION_PROXY_ACTIVE_MODEL_RUN_ID",
            DEFAULT_MODEL_RUN_ID,
        ),
        reliability_model_run_id=os.getenv(
            "STATION_PROXY_RELIABILITY_MODEL_RUN_ID",
            "paloma_v1_reliability",
        ),
        engine_mode=os.getenv("STATION_PROXY_ENGINE_MODE", "process"),
        cors_allow_origins=env_list(
            "STATION_PROXY_CORS_ALLOW_ORIGINS",
            [
                "http://127.0.0.1:8000",
                "http://127.0.0.1:8001",
                "http://localhost:8000",
                "http://localhost:8001",
                "null",
            ],
        ),
    )


def configure_confidence_import_path(config: BackendSettings) -> None:
    script_dir = str(config.confidence_script_dir)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)


settings = load_settings()
configure_confidence_import_path(settings)
