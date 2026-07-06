"""Expose the FastAPI routes and static frontend for the station proxy app.

This is the local web entry point that connects browser requests to the C++ engine and model artifact services."""

import atexit
from pathlib import Path
from typing import Optional

from api_models import (
    AnalyzeConfidenceResponse,
    CurrentModelRunResponse,
    HealthResponse,
)
from confidence_service import ConfidenceService
from engine_adapter import build_engine_client
from engine_client import EngineClientConfig
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from model_run_service import ModelRunService
from reliability_service import ReliabilitySurfaceService
from response_safety import display_path as safe_display_path
from response_safety import sanitize_response_paths

# settings configures imports for weather_reconstruction_model/scripts.
from settings import settings

app = FastAPI()

# The API is public and read-only: no cookies or credentials exist, so
# cross-origin GET reads are safe to allow.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=6)

# Model-run artifacts and static assets are immutable for a given deployment,
# so browsers and CDNs may cache them. Query-string versions (?v=...) handle
# cache busting for static files.
CACHEABLE_PATH_PREFIXES = ("/model-runs/", "/static/", "/assets/")
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' https://unpkg.com https://cdn.jsdelivr.net; "
        "style-src 'self' https://unpkg.com 'unsafe-inline'; "
        # unpkg.com serves Leaflet's default marker icons (marker-icon.png etc.)
        # alongside leaflet.js/css, so images from it must stay allowed.
        "img-src 'self' data: https://server.arcgisonline.com https://unpkg.com; "
        "connect-src 'self' http://127.0.0.1:8000 http://127.0.0.1:8001 "
        "http://localhost:8000 http://localhost:8001; "
        "font-src 'self' data:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}


@app.middleware("http")
async def artifact_cache_headers(request: Request, call_next):
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    if (
        request.method == "GET"
        and response.status_code == 200
        and request.url.path.startswith(CACHEABLE_PATH_PREFIXES)
    ):
        response.headers.setdefault("Cache-Control", "public, max-age=86400")
    return response


app.mount("/assets", StaticFiles(directory=settings.backend_dir / "assets"), name="assets")
app.mount("/static", StaticFiles(directory=settings.backend_dir / "static"), name="static")


def display_path(path: Path) -> str:
    """Report artifact locations relative to the project so absolute server paths stay private."""
    return safe_display_path(path, settings.project_dir)


LATITUDE_QUERY = Query(ge=-90.0, le=90.0)
LONGITUDE_QUERY = Query(ge=-180.0, le=180.0)
ELEVATION_QUERY = Query(default=None, ge=-500.0, le=9000.0)


def sanitize_engine_response(payload: dict) -> dict:
    """Rewrite absolute file paths echoed by the C++ engine to project-relative paths."""
    return sanitize_response_paths(payload, settings.project_dir)

engine_client = build_engine_client(
    EngineClientConfig(
        executable=settings.engine_executable,
        server_dir=settings.engine_server_dir,
        target_data_file=settings.target_data_file,
        hub_data_file=settings.hub_data_file,
    ),
    settings.engine_mode,
)
confidence_service = ConfidenceService(settings)
model_run_service = ModelRunService(settings)
reliability_service = ReliabilitySurfaceService(settings)


atexit.register(engine_client.stop)


@app.on_event("startup")
def startup_event():
    # Launching the engine here starts the one-time NOAA data load early.
    # First startup can take a while; later requests reuse the loaded process.
    try:
        engine_client.start(wait_until_ready=True)
    except Exception as error:
        print(f"[station_engine_server] Failed to start on FastAPI startup: {error}")

    try:
        confidence_service.load_inputs_once()
    except Exception as error:
        print(f"[confidence_support] Failed to load on FastAPI startup: {error}")

    try:
        warmed = reliability_service.warm_cache()
        print(f"[reliability] Warmed artifact cache: {', '.join(warmed) or 'none available'}")
    except Exception as error:
        print(f"[reliability] Failed to warm artifact cache on startup: {error}")


@app.on_event("shutdown")
def shutdown_event():
    engine_client.stop()


# The HTML shell must always revalidate: versioned ?v= asset URLs only bust
# caches if browsers re-read the HTML that references them.
HTML_SHELL_HEADERS = {"Cache-Control": "no-cache"}


@app.get("/")
def home():
    return FileResponse(settings.backend_dir / "index.html", headers=HTML_SHELL_HEADERS)


@app.get("/index.html")
def home_index():
    return FileResponse(settings.backend_dir / "index.html", headers=HTML_SHELL_HEADERS)


@app.get("/test", response_model=HealthResponse)
def test() -> HealthResponse:
    engine_status = sanitize_response_paths(engine_client.status(), settings.project_dir)
    return HealthResponse(
        status="ok",
        engine="Persistent C++ station matcher is connected through FastAPI",
        **engine_status,
        engineExecutable=display_path(settings.engine_executable),
        targetDataFile=display_path(settings.target_data_file),
        hubDataFile=display_path(settings.hub_data_file),
        stationDataMode=settings.station_data_mode,
        stationDataNotice=settings.station_data_notice,
        engineMode=settings.engine_mode,
        activeModelRunId=settings.active_model_run_id,
        modelRunRoot=display_path(settings.model_run_root),
    )


@app.get("/model-runs/current", response_model=CurrentModelRunResponse)
def current_model_run() -> CurrentModelRunResponse:
    return model_run_service.current_summary()


@app.get("/model-runs/current/confidence-grid")
def current_model_run_confidence_grid():
    return model_run_service.current_confidence_grid()


@app.get("/model-runs/reliability/summary")
def reliability_summary():
    return reliability_service.summary()


@app.get("/model-runs/reliability/surface")
def reliability_surface(request: Request, layer: str = "overall"):
    accepts_gzip = "gzip" in request.headers.get("accept-encoding", "")
    return reliability_service.surface_response(layer, accepts_gzip)


@app.get("/model-runs/reliability/surface.png")
def reliability_surface_image(layer: str = "overall"):
    return reliability_service.image_response(layer)


@app.get("/model-runs/reliability/station-overlay.png")
def reliability_station_overlay_image(layer: str = "overall", mode: str = "bias"):
    return reliability_service.station_overlay_image_response(layer, mode)


@app.get("/model-runs/reliability/sample")
def reliability_surface_sample(
    lat: float = LATITUDE_QUERY,
    lon: float = LONGITUDE_QUERY,
    layer: str = "overall",
):
    return reliability_service.sample(layer, lat, lon)


@app.get("/model-runs/reliability/station")
def reliability_station_detail(station_id: str, layer: str = "overall"):
    return reliability_service.station(layer, station_id)


@app.get("/run-engine")
def run_engine():
    return sanitize_engine_response(engine_client.query(39.75, -105.0))


@app.get("/analyze-location")
def analyze_location(lat: float = LATITUDE_QUERY, lon: float = LONGITUDE_QUERY):
    return sanitize_engine_response(engine_client.query(lat, lon))


@app.get("/analyze-confidence", response_model=AnalyzeConfidenceResponse)
def analyze_confidence(
    lat: float = LATITUDE_QUERY,
    lon: float = LONGITUDE_QUERY,
    elevation_m: Optional[float] = ELEVATION_QUERY,
) -> AnalyzeConfidenceResponse:
    return confidence_service.analyze_point(lat, lon, elevation_m)
