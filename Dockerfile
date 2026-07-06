# Container image for the Station Proxy app on Cloud Run (or any container host).
#
# Build context requirements: this image bakes in the full app-ready NOAA CSVs
# and model-run artifacts, which are intentionally not tracked in git. Build
# from a machine that has them locally (see docs/deploy_cloud_run.md). If the
# full CSVs are absent, the app falls back to the tiny tracked fixtures.

# --- Stage 1: compile the persistent C++ station engine -----------------------
FROM debian:bookworm-slim AS engine-build

RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY C++_Weather_Station_Proxy_Engine/ C++_Weather_Station_Proxy_Engine/
COPY Station_Engine_Server/station_engine_server.cpp Station_Engine_Server/

# Keep this source list in sync with SERVER_SOURCES in the Makefile.
RUN g++ -std=c++17 -O2 -DNDEBUG -Wall -Wextra \
    -I"C++_Weather_Station_Proxy_Engine" \
    Station_Engine_Server/station_engine_server.cpp \
    C++_Weather_Station_Proxy_Engine/STATION_PROXY_ENGINE.cpp \
    C++_Weather_Station_Proxy_Engine/csv_filereader.cpp \
    C++_Weather_Station_Proxy_Engine/seasonal_analysis.cpp \
    C++_Weather_Station_Proxy_Engine/similarity_scores.cpp \
    C++_Weather_Station_Proxy_Engine/station_dataset.cpp \
    C++_Weather_Station_Proxy_Engine/station_distance.cpp \
    C++_Weather_Station_Proxy_Engine/station_matcher.cpp \
    C++_Weather_Station_Proxy_Engine/station_pair_score.cpp \
    C++_Weather_Station_Proxy_Engine/station_locator.cpp \
    -o Station_Engine_Server/station_engine_server

# --- Stage 2: Python runtime with app code and data ---------------------------
FROM python:3.11-slim

# Keep these bounds in sync with [project.dependencies] in pyproject.toml.
RUN pip install --no-cache-dir "fastapi>=0.110,<1.0" "uvicorn[standard]>=0.29,<1.0"

WORKDIR /app

COPY --from=engine-build /build/Station_Engine_Server/station_engine_server Station_Engine_Server/station_engine_server

# Application code.
COPY station-proxy-backend/ station-proxy-backend/
COPY weather_reconstruction_model/scripts/ weather_reconstruction_model/scripts/

# Model evidence artifacts served by the reliability and model-run routes.
COPY weather_reconstruction_model/model_runs/ weather_reconstruction_model/model_runs/
COPY alpine_outputs/paloma/ alpine_outputs/paloma/
COPY alpine_outputs/predictions/ alpine_outputs/predictions/

# Station data: full app-ready CSVs plus tracked candidate lists and the tiny
# fixture fallback used when the full CSVs were not present at build time.
COPY NOAA_Inventory_Sort/ NOAA_Inventory_Sort/
COPY tests/fixtures/ tests/fixtures/

ENV PORT=8080
EXPOSE 8080

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

WORKDIR /app/station-proxy-backend
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --no-access-log
