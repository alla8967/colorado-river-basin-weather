import atexit
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api_models import (
    AnalyzeConfidenceResponse,
    CurrentModelRunResponse,
    HealthResponse,
)
# settings configures imports for weather_reconstruction_model/scripts.
from settings import settings
from confidence_service import ConfidenceService
from engine_client import EngineClient, EngineClientConfig
from model_run_service import ModelRunService
from reliability_service import ReliabilitySurfaceService

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/assets", StaticFiles(directory=settings.backend_dir / "assets"), name="assets")
app.mount("/static", StaticFiles(directory=settings.backend_dir / "static"), name="static")

engine_client = EngineClient(
    EngineClientConfig(
        executable=settings.engine_executable,
        server_dir=settings.engine_server_dir,
        target_data_file=settings.target_data_file,
        hub_data_file=settings.hub_data_file,
    )
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
        engine_client.start()
    except Exception as error:
        print(f"[station_engine_server] Failed to start on FastAPI startup: {error}")

    try:
        confidence_service.load_inputs_once()
    except Exception as error:
        print(f"[confidence_support] Failed to load on FastAPI startup: {error}")


@app.on_event("shutdown")
def shutdown_event():
    engine_client.stop()


@app.get("/")
def home():
    return FileResponse(settings.backend_dir / "index.html")


@app.get("/index.html")
def home_index():
    return FileResponse(settings.backend_dir / "index.html")


@app.get("/test", response_model=HealthResponse)
def test() -> HealthResponse:
    return HealthResponse(
        status="ok",
        engine="Persistent C++ station matcher is connected through FastAPI",
        engineRunning=engine_client.is_running(),
        engineExecutable=str(settings.engine_executable),
        targetDataFile=str(settings.target_data_file),
        hubDataFile=str(settings.hub_data_file),
        activeModelRunId=settings.active_model_run_id,
        modelRunRoot=str(settings.model_run_root),
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
def reliability_surface(layer: str = "overall"):
    return reliability_service.surface(layer)


@app.get("/model-runs/reliability/surface.png")
def reliability_surface_image(layer: str = "overall"):
    return reliability_service.image_response(layer)


@app.get("/model-runs/reliability/station-overlay.png")
def reliability_station_overlay_image(layer: str = "overall", mode: str = "bias"):
    return reliability_service.station_overlay_image_response(layer, mode)


@app.get("/model-runs/reliability/sample")
def reliability_surface_sample(lat: float, lon: float, layer: str = "overall"):
    return reliability_service.sample(layer, lat, lon)


@app.get("/model-runs/reliability/station")
def reliability_station_detail(station_id: str, layer: str = "overall"):
    return reliability_service.station(layer, station_id)


@app.get("/run-engine")
def run_engine():
    return engine_client.query(39.75, -105.0)


@app.get("/analyze-location")
def analyze_location(lat: float, lon: float):
    return engine_client.query(lat, lon)


@app.get("/analyze-confidence", response_model=AnalyzeConfidenceResponse)
def analyze_confidence(
    lat: float,
    lon: float,
    elevation_m: Optional[float] = None,
) -> AnalyzeConfidenceResponse:
    return confidence_service.analyze_point(lat, lon, elevation_m)
