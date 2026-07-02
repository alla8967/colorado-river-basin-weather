# Reviewer Runbook

This runbook is for a human reviewer who wants to understand, verify, and run
the local Colorado River Basin station app without reverse-engineering the repo.

## What This Project Is

The local app combines:

- NOAA station data preparation,
- a reusable C++ station proxy engine,
- a persistent C++ server process,
- a FastAPI backend,
- a browser frontend,
- Python research scripts for temperature reconstruction and model-run artifacts.

This cleanup branch is local-only. It should not be synced to Alpine until the
active or pending Alpine station-holdout jobs are finished and a new sync is
intentional.

## Review Path

For a fast review, use this order:

1. Read `PROJECT_MAP.md` for the top-level folder map and what to ignore.
2. Run `make check` from the project root.
3. Run `PYTHON=.venv/bin/python make test-python` after installing `.[dev]`.
4. Run `make run-backend` and open `http://127.0.0.1:8000/`.
5. Check `docs/artifact_quarantine_plan.md` and
   `docs/generated_artifact_audit.md` before staging anything.
6. Confirm no Alpine scratch paths were synced or reorganized.

## Cleanup Handoff Notes

This branch keeps the existing command entry points in place while moving reused
behavior behind named helpers. The most important helper boundaries are:

- backend app responsibilities are split across `engine_client.py`,
  `confidence_service.py`, `model_run_service.py`, `settings.py`, and
  `api_models.py`;
- frontend behavior is split under `station-proxy-backend/static/js/`;
- research-script reuse lives in `weather_reconstruction_model/scripts/common/`
  and `weather_reconstruction_model/scripts/pipeline/`;
- folder-level `README.md` files explain each major source collection;
- model-run manifests, feature selection, reporting HTML helpers, CSV/JSON
  utilities, training-data prep, station-holdout filtering, general-table row
  construction, and confidence support now have shared helper coverage.

Known remaining polish is narrower: the largest training/report scripts can
still be decomposed further. `build_general_training_table.py` now delegates
table row/field construction, but its data-loading and station-selection
orchestration is still intentionally local. Full research reproducibility still
depends on external NOAA/model artifacts and Alpine run context.

## First-Time Setup

From the project root:

```bash
make setup
```

For backend-only review:

```bash
make setup-backend
```

The app can run with the default repo layout. Use `.env.example` only when you
need to point the backend at alternate data, engine, confidence, or model-run
locations.

## Backend Config Reference

The backend reads these optional environment variables:

| Variable | Purpose |
| --- | --- |
| `STATION_PROXY_PROJECT_DIR` | Project root override. |
| `STATION_PROXY_ENGINE_SERVER_DIR` | Folder containing the persistent C++ server. |
| `STATION_PROXY_ENGINE_EXECUTABLE` | Exact C++ server executable path. |
| `STATION_PROXY_TARGET_FILE` | App-ready target station daily CSV. |
| `STATION_PROXY_HUB_FILE` | App-ready hub station daily CSV. |
| `STATION_PROXY_CONFIDENCE_TARGET_CANDIDATES` | Target station candidate metadata for confidence support. |
| `STATION_PROXY_CONFIDENCE_HUB_CANDIDATES` | Hub station candidate metadata for confidence support. |
| `STATION_PROXY_CONFIDENCE_TERRAIN_FEATURES` | Processed station terrain feature CSV. |
| `STATION_PROXY_CONFIDENCE_VALIDATION_METRICS` | Station validation metrics used by confidence support. |
| `STATION_PROXY_CONFIDENCE_MODEL_REFERENCE` | Human-readable confidence model label. |
| `STATION_PROXY_CONFIDENCE_SCORE_VERSION` | Optional score-version label override. |
| `STATION_PROXY_MODEL_RUN_ROOT` | Root folder for model-run artifacts. |
| `STATION_PROXY_ACTIVE_MODEL_RUN_ID` | Active model-run folder to serve in the UI. |

## One-Command Local Check

Run the practical reviewer validation set:

```bash
make check
```

This command runs:

- JavaScript syntax checks for `station-proxy-backend/static/js/*.js`,
- ruff lint over the Python sources,
- Python compile checks for the FastAPI backend and key scripts,
- the app-shell, engine-adapter, native-parity, and reliability-backend smoke
  tests,
- the fixture-backed C++ station engine test and the C++ unit tests,
- the C++ prediction-similarity validator build.

It intentionally does not run the full model-script pytest suite. Use
`make test-python` for that after installing the `dev` dependencies.

To run the model-script pytest suite in the project virtual environment:

```bash
.venv/bin/python -m pip install -e ".[dev]"
PYTHON=.venv/bin/python make test-python
```

The model-script suite covers shared helpers, variable-aware feature selection,
confidence support, remote command construction, and Paloma holdout helpers.

## Run The Local App

Build the persistent C++ server:

```bash
make server
```

Start FastAPI:

```bash
make run-backend
```

The first startup can be slow because the C++ server loads the target and hub
station CSVs into memory. Wait for the server log to show:

```text
READY
```

Then open:

```text
http://127.0.0.1:8000/
```

The frontend checks `/test` every few seconds. The Analyze button should become
available once the backend reports that the persistent C++ engine is running.

## Important Paths

Source and app code:

```text
station-proxy-backend/
station-proxy-backend/static/js/
C++_Weather_Station_Proxy_Engine/
Station_Engine_Server/
weather_reconstruction_model/scripts/
remote_jobs/
```

Small test fixtures:

```text
tests/fixtures/
```

Generated or bulky outputs:

```text
NOAA_Inventory_Sort/NOAA_GHCN_ByYear/
weather_reconstruction_model/cache/
weather_reconstruction_model/outputs/
weather_reconstruction_model/model_runs/
weather_reconstruction_artifacts/
terrain_data/processed/
Raw_DEM/
```

Generated data and model artifacts should stay out of source commits unless
they are intentionally curated fixtures or documentation assets.

See `docs/generated_artifact_audit.md` for the current ignore policy and tracked
data-file audit.

See `docs/artifact_quarantine_plan.md` for the conservative cleanup policy. The
safe workspace-calming command is:

```bash
make clean-local-artifacts
```

It removes rebuildable compiled/test byproducts only; it intentionally leaves
NOAA archives, model runs, DEM data, research outputs, and local artifact
shelves in place.

## Alpine Safety Boundary

Active or pending station-holdout jobs may be using the copied code under:

```text
/scratch/alpine/$USER/crb_weather_runs/current/weather_reconstruction_model/scripts
/scratch/alpine/$USER/crb_weather_runs/current/remote_jobs
```

Do not rsync, sync, rename, or reorganize that Alpine scratch copy while those
jobs are running. Local refactors are okay; Alpine scratch is frozen run code
until a new version is validated and intentionally synced.

## Expected Slow Parts

- `make server` and `make run-backend` can be slow the first time because large
  NOAA station CSVs are loaded into the C++ engine.
- `make test-engine` compiles a temporary one-shot C++ executable before running
  fixture assertions.
- The full Python model test suite requires dev dependencies and is separate
  from `make check`.

## Reviewer Checklist

Before approving a cleanup/refactor change, confirm:

- `make check` passes.
- `PYTHON=.venv/bin/python make test-python` passes when reviewing model-script
  changes.
- The working tree does not stage generated data, model files, caches, local
  virtual environments, compiled binaries, or scratch outputs.
- Frontend behavior still loads through FastAPI at `http://127.0.0.1:8000/`.
- Alpine scratch code has not been modified unless there is an explicit sync
  plan and the active jobs are no longer using the old copy.

---

## Archived Root README (Pre-Portfolio Polish)

The root `README.md` is now portfolio-first. The previous long-form root README is preserved verbatim below so reviewer/runbook material was relocated rather than deleted.



# Colorado River Basin Weather Station Proxy Finder

This project is a full-stack NOAA weather station analysis tool with multiple functionalities. The original and primary function finds the nearest weather station to a selected location and identifies the best long-record proxy stations for that location. The secondary and much larger function prepares NOAA GHCN data and DEM data, compiles it into large training tables, and trains a forest-based temperature reconstruction model that can estimate daily station temperatures using nearby long-record stations, terrain features, and historical similarity signals.

The main idea is simple:

```text
User enters or selects a latitude/longitude
→ the app finds the nearest target station
→ the C++ engine compares that station against long-record hub stations
→ the app returns ranked proxy stations with similarity scores
```

The project is built around decade-scale NOAA GHCN-Daily data and uses a hybrid architecture:

```text
Python preprocessing
→ app-ready NOAA CSV files
→ Python reconstruction and validation experiments
→ reusable C++ station proxy engine
→ persistent C++ server process
→ FastAPI backend
→ browser frontend
```

---

## Start Here / What To Ignore

If you are reviewing the project in Finder or a terminal, start with:

- `PROJECT_MAP.md` for the visual map of source folders, generated artifact
  shelves, and safe local commands.
- `docs/reviewer_runbook.md` for setup, validation, local run steps, and Alpine
  safety.
- `docs/research_script_inventory.md` for the research/model script map.
- folder-level `README.md` files for each major code collection.
- `docs/artifact_quarantine_plan.md` for what can be cleaned locally and what
  should be left in place.
- `docs/generated_artifact_audit.md` for the commit/staging policy.

The working folder may contain ignored generated artifacts, local virtual
environments, compiled binaries, NOAA data products, DEM products, model runs,
and scratch outputs beside the source. That visual clutter is expected in the
current local workspace. Review source and docs first; do not stage generated
data, model files, caches, local environments, compiled binaries, or Alpine run
outputs.

For the main reviewer validation path, run:

```bash
make check
```

For the Python research-script suite, use:

```bash
PYTHON=.venv/bin/python make test-python
```

For a fixture-first app bootstrap that works without full NOAA data:

```bash
make bootstrap-fixture
make run-backend-fixture
```

The fixture path builds the persistent C++ server, runs the fixture engine smoke
test, compiles backend Python entry points, and starts FastAPI against the tiny
tracked station files.

The Python backend still defaults to the persistent subprocess engine. An
optional pybind11 extension can be built with:

```bash
.venv/bin/python -m pip install -e ".[native]"
make native-engine PYTHON=.venv/bin/python
```

Set `STATION_PROXY_ENGINE_MODE=auto` to use that extension when available while
falling back to the subprocess engine on clean machines.

---

## Project Status

The current version is a working local web application.

The system can:

- preprocess NOAA GHCN-Daily yearly bulk files,
- generate app-ready target and hub station CSVs,
- train and validate station-temperature reconstruction models,
- independently score Python-generated predictions with the C++ engine,
- sample DEM-derived terrain features for stations,
- load decade-scale weather station data into a reusable C++ engine,
- keep that engine running persistently so data is loaded once,
- serve fast repeated location-analysis requests through FastAPI,
- display results in a browser frontend.

The first startup can take a while because the C++ engine loads large NOAA CSV files into memory. After startup, location requests are fast because the loaded station data is reused.

---

## Reviewer Quick Start

For most code reviews, start here:

```bash
cd colorado-river-basin-weather
make check
```

`make check` is the practical local validation set for the web app and C++
engine. It runs JavaScript syntax checks, ruff lint, backend Python compile
checks, the fixture-backed smoke tests (app shell, engine adapter, native
parity, reliability backend), the C++ engine and unit tests, and the prediction
similarity validator build.

To include the Python research-script pytest suite:

```bash
.venv/bin/python -m pip install -e ".[dev]"
PYTHON=.venv/bin/python make test-python
```

For a guided human review, use:

- `PROJECT_MAP.md` for a visual top-level folder guide and what to ignore.
- `docs/reviewer_runbook.md` for setup, validation, local run steps, and Alpine safety.
- `docs/research_script_inventory.md` for the research/model script map.
- `docs/artifact_quarantine_plan.md` for the local artifact cleanup policy.
- `docs/generated_artifact_audit.md` for what should and should not be committed.

Alpine safety note: local cleanup is safe, but the copied scratch code under
`/scratch/alpine/$USER/crb_weather_runs/current` should remain frozen while
active or pending station-holdout jobs are using it.

---

## High-Level Architecture

```text
colorado-river-basin-weather/
├── README.md
├── PROJECT_MAP.md
├── Makefile
├── docs/
│   ├── artifact_quarantine_plan.md
│   ├── generated_artifact_audit.md
│   ├── research_script_inventory.md
│   ├── reviewer_runbook.md
│   └── remote_runs/
├── NOAA_Inventory_Sort/
│   ├── README.md
│   ├── filter_ghcn_years.py
│   ├── ghcnd-inventory.txt
│   ├── ghcnd-stations.txt
│   ├── hub_station_candidates.csv
│   ├── target_station_candidates.csv
│   ├── hub_daily_app_ready.csv        (generated, ignored)
│   ├── target_daily_app_ready.csv     (generated, ignored)
│   └── NOAA_GHCN_ByYear/             (generated, ignored)
│       ├── 2016.csv.gz
│       ├── 2017.csv.gz
│       └── ...
├── C++_Weather_Station_Proxy_Engine/
│   ├── README.md
│   ├── STATION_PROXY_ENGINE.h
│   ├── STATION_PROXY_ENGINE.cpp
│   ├── api_main.cpp
│   ├── csv_filereader.cpp
│   ├── csv_filereader.h
│   ├── station_dataset.cpp
│   ├── station_dataset.h
│   ├── station_pair_score.cpp
│   ├── station_pair_score.h
│   ├── similarity_scores.cpp
│   ├── similarity_scores.h
│   ├── station_distance.cpp
│   ├── station_distance.h
│   ├── station_locator.cpp
│   ├── station_locator.h
│   ├── station_matcher.cpp
│   ├── station_matcher.h
│   ├── seasonal_analysis.cpp
│   └── seasonal_analysis.h
├── Station_Engine_Server/
│   ├── README.md
│   ├── station_engine_server.cpp
│   └── station_engine_server          (compiled, ignored)
├── weather_reconstruction_model/
│   ├── README.md
│   ├── scripts/
│   │   ├── README.md
│   │   ├── common/
│   │   ├── pipeline/
│   │   └── tests/
│   ├── model_runs/                    (generated, ignored)
│   └── outputs/                       (generated, ignored)
└── station-proxy-backend/
    ├── README.md
    ├── api_models.py
    ├── confidence_service.py
    ├── engine_client.py
    ├── main.py
    ├── model_run_service.py
    ├── settings.py
    ├── index.html
    └── static/
        ├── styles.css
        └── js/
            ├── README.md
            ├── api.js
            ├── charts.js
            ├── formatters.js
            ├── main.js
            ├── maps.js
            ├── results.js
            └── state.js
```

---

## Code Layout For Reviewers

Use this map when reviewing or extending the project:

- `docs/reviewer_runbook.md` is the shortest path for a human reviewer who wants setup, validation, local run instructions, generated-artifact boundaries, and Alpine safety notes.
- `docs/artifact_quarantine_plan.md` explains which ignored local artifacts can be cleaned safely and which should stay in place until path assumptions are audited.
- `docs/generated_artifact_audit.md` records what generated files are ignored and which small CSVs are intentionally tracked.
- `docs/research_script_inventory.md` maps the research script entry points and shared helper boundaries.
- Folder-level `README.md` files explain each major source collection before a
  reviewer opens individual files.
- `station-proxy-backend/` is the local web app. `main.py` wires FastAPI routes, while `engine_client.py`, `confidence_service.py`, `model_run_service.py`, `settings.py`, and `api_models.py` hold backend responsibilities.
- `station-proxy-backend/static/` is the browser app. `index.html` is structure, `styles.css` is presentation, and `static/js/main.js` is the frontend entry point.
- `C++_Weather_Station_Proxy_Engine/` is the reusable station matching core used by both command-line validation and the server.
- `Station_Engine_Server/` is the persistent stdin/stdout wrapper that lets FastAPI reuse one loaded C++ process.
- `weather_reconstruction_model/scripts/` is the research and model-building command layer. Shared logic belongs in `scripts/common/` or `scripts/pipeline/`; generated tables, reports, caches, and model files should stay out of source commits unless intentionally curated.
- `remote_jobs/` contains Alpine Slurm launch scripts. Treat these as run orchestration, not local application code.

Alpine safety note: active or pending Alpine station-holdout jobs may still be using the copied scratch code under `/scratch/alpine/$USER/crb_weather_runs/current`. Do not sync, rename, or reorganize that Alpine copy while those jobs are running.

---

## Data Pipeline

### 1. NOAA Station Inventory Filtering

The project uses NOAA GHCN-Daily metadata files:

- `ghcnd-inventory.txt`
- `ghcnd-stations.txt`

The inventory data is used to determine which stations have the required temperature variables and sufficient record length.

The station metadata file is used to attach:

- station name,
- station ID,
- latitude,
- longitude,
- elevation.

The pipeline separates stations into two categories:

### Target Stations

Target stations are stations with enough recent data to be evaluated for a user-selected location.

Example criteria used during development:

```text
minimum usable temperature history: 20 years
required variables: TMAX and TMIN
recent enough to include modern observations
inside the selected geographic study bounds
excluded from the hub station pool
```

### Hub Stations

Hub stations are long-record stations that can act as proxy options.

Current criteria used during development:

```text
minimum usable temperature history: 42 years
usable temperature record starts in 1960 or earlier
required variables: TMAX and TMIN
recent enough to include modern observations
inside the selected geographic study bounds
```

---

## App-Ready NOAA CSV Format

The preprocessing script creates two major app-ready data files:

```text
NOAA_Inventory_Sort/target_daily_app_ready.csv
NOAA_Inventory_Sort/hub_daily_app_ready.csv
```

Both files use this format:

```csv
station_id,station_name,latitude,longitude,elevation,date,tmax,tmin
```

Example row:

```csv
USC00052223,DENVER WATER DEPT,39.7294,-105.009,1592.6,2025-01-01,52.34,28.76
```

Temperatures are stored in degrees Fahrenheit.

The app-ready files are generated from NOAA GHCN-Daily yearly bulk files such as:

```text
2016.csv.gz
2017.csv.gz
2018.csv.gz
...
2025.csv.gz
```

These files are stored in:

```text
NOAA_Inventory_Sort/NOAA_GHCN_ByYear/
```

---

## C++ Engine

The reusable C++ core is implemented in:

```text
C++_Weather_Station_Proxy_Engine/STATION_PROXY_ENGINE.h
C++_Weather_Station_Proxy_Engine/STATION_PROXY_ENGINE.cpp
```

The main reusable class is:

```cpp
StationProxyEngine
```

This class owns the loaded station data and exposes methods such as:

```cpp
bool load(const std::string& target_file, const std::string& hub_file);
std::string analyze_location_json(double latitude, double longitude) const;
bool is_loaded() const;
int target_station_count() const;
int hub_station_count() const;
```

The purpose of this class is to keep the core analysis logic out of `main()` files.

This allows the same engine to be reused by:

- the one-shot command-line executable,
- the persistent C++ server,
- the prediction similarity validator,
- future Python bindings,
- future HTTP or cloud service wrappers.

The prediction validator is a small C++ executable that independently scores
Python-generated reconstruction results against actual station observations.
It is documented in:

```text
weather_reconstruction_model/README.md
```

---

## Weather Reconstruction Research Workflow

The `weather_reconstruction_model/` folder is the research side of the project.
It tests whether target station temperatures can be reconstructed from selected
long-record hub stations.

The core flow is:

```text
target station + candidate hubs
→ select eligible nearby hubs
→ build shared-date training table
→ train linear regression model
→ export predictions
→ independently validate predicted vs actual temperatures
→ summarize station-level success and failure cases
```

The Python research code is now split into:

```text
scripts/common/     low-level reusable helpers
scripts/pipeline/   shared station-selection and training-table logic
scripts/tests/      lightweight unit tests for common and pipeline code
```

This separation matters because the same hub-selection and shared-date rules are
used by both one-station validation and batch validation.

For details, see:

```text
weather_reconstruction_model/README.md
```

---

## Station Matching Workflow

For each requested latitude/longitude, the engine:

1. finds the nearest target station,
2. compares that target station against hub stations,
3. calculates similarity metrics,
4. ranks proxy station candidates,
5. returns JSON to the backend/frontend.

The scoring system currently uses temperature similarity and geography/elevation context.

Core comparison metrics include:

- daily average temperature correlation,
- daily mean absolute difference,
- daily RMSE,
- monthly correlation,
- monthly mean absolute difference,
- monthly RMSE,
- geographic distance,
- elevation difference,
- number of paired observations.

The result is returned as JSON with fields such as:

```json
{
  "status": "ok",
  "message": "Location analysis complete",
  "targetStationCount": 808,
  "hubStationCount": 438,
  "selectedLocation": {
    "latitude": 39.75,
    "longitude": -105.0
  },
  "nearestStation": {
    "stationID": "USC00052223",
    "stationName": "DENVER WATER DEPT"
  },
  "bestProxyStation": {...},
  "topProxyMatches": [...]
}
```

---

## Persistent C++ Server

The persistent server lives in:

```text
Station_Engine_Server/station_engine_server.cpp
```

It is intentionally a thin wrapper around `StationProxyEngine`.

The server does this:

```text
start process
→ load target and hub station CSVs once
→ wait for coordinate requests over stdin
→ return one JSON response per request over stdout
```

This avoids reloading the large NOAA CSV files for every website request.

The communication protocol is simple:

Input:

```text
39.75 -105.0
```

Output:

```json
{"status":"ok","message":"Location analysis complete",...}
```

Important rule:

```text
stdout = JSON only
stderr = logs and diagnostics
```

This prevents FastAPI from accidentally parsing debug output as JSON.

---

## FastAPI Backend

The FastAPI backend lives in:

```text
station-proxy-backend/main.py
```

FastAPI starts the persistent C++ server once using:

```python
subprocess.Popen(...)
```

Then each `/analyze-location` request sends latitude/longitude to the C++ process through stdin and reads one JSON response line from stdout.

Key routes:

```text
GET /
GET /test
GET /run-engine
GET /analyze-location?lat=39.75&lon=-105.0
```

The `/test` route reports whether the persistent C++ engine is running.

---

## Frontend

The frontend files live in:

```text
station-proxy-backend/index.html
station-proxy-backend/static/styles.css
station-proxy-backend/static/js/main.js
station-proxy-backend/static/js/api.js
station-proxy-backend/static/js/charts.js
station-proxy-backend/static/js/formatters.js
station-proxy-backend/static/js/maps.js
station-proxy-backend/static/js/results.js
station-proxy-backend/static/js/state.js
```

The split keeps the review surface predictable:

- `index.html` defines the page structure and data panels,
- `static/styles.css` owns the page layout and visual styling,
- `static/js/api.js` owns browser-to-backend requests,
- `static/js/maps.js` owns Leaflet setup and map overlays,
- `static/js/charts.js` owns SVG comparison charts,
- `static/js/results.js` owns analysis result cards and tables,
- `static/js/formatters.js` owns display helpers,
- `static/js/state.js` owns shared DOM references and browser state,
- `static/js/main.js` wires startup, tabs, engine status, and user events.

The interface provides:

- latitude and longitude inputs,
- an Analyze Location button,
- an engine status panel,
- nearest station display,
- best proxy station display,
- top proxy match results.

The frontend checks the backend status through:

```text
http://127.0.0.1:8000/test
```

The Analyze button is disabled until the backend reports that the engine is running.

---

## Build System

The project uses a root-level Makefile and `pyproject.toml`.

Install the local Python dependencies into your active environment:

```bash
make setup
```

Build both the persistent server and one-shot API executable:

```bash
make all
```

Build only the persistent server:

```bash
make server
```

Build only the one-shot API executable:

```bash
make api
```

Run the fixture-backed C++ engine test:

```bash
make test-engine
```

Run the practical reviewer validation set:

```bash
make check
```

Run the local FastAPI app-shell smoke test:

```bash
make test-app-shell
```

Run the Python model-pipeline tests after `make setup`:

```bash
make test-python
```

Run both test groups:

```bash
make test
```

Run the persistent server manually:

```bash
make run
```

Run the one-shot API test:

```bash
make run-api
```

Run the FastAPI backend from the project root:

```bash
make run-backend
```

Audit local readiness and expected data/artifact paths:

```bash
make doctor
```

Clean compiled outputs:

```bash
make clean
```

Clean only rebuildable local compiled/test byproducts:

```bash
make clean-local-artifacts
```

---

## Running the Project Locally

### 1. Build the C++ executables

From the project root:

```bash
make all
```

### 2. Start FastAPI

```bash
make run-backend
```

The first startup may take a while because the persistent C++ server loads large NOAA station CSVs into memory.

Wait for the server logs to show:

```text
READY
```

The backend derives project paths from its own location by default. These environment variables can override the defaults when running from a different layout or with test data:

```bash
STATION_PROXY_PROJECT_DIR
STATION_PROXY_ENGINE_SERVER_DIR
STATION_PROXY_ENGINE_EXECUTABLE
STATION_PROXY_TARGET_FILE
STATION_PROXY_HUB_FILE
```

See `.env.example` for the full set of backend, confidence, and model-run path
overrides.

### 3. Open the frontend

```bash
http://127.0.0.1:8000/
```

Once the engine status turns green, run an analysis.

---

## Manual Testing

### Test the one-shot executable

```bash
make run-api
```

Expected result:

```json
{"status":"ok",...}
```

### Run the fixture test

```bash
make test
```

This builds a temporary one-shot executable and runs it against small CSV fixtures in `tests/fixtures/`.

### Test the persistent server manually

```bash
make run
```

Wait for:

```text
READY
```

Then type:

```text
39.75 -105.0
```

The server should return one JSON response.

Try another coordinate without restarting:

```text
39.0639 -108.5506
```

To stop the persistent server:

```text
shutdown
```

---

## Current Performance Model

The project currently uses this performance model:

```text
slow startup once
→ station data remains loaded in memory
→ repeated location requests are fast
```

This replaced the original slower model:

```text
website request
→ launch C++ executable
→ reload giant CSV files
→ analyze one location
→ exit
```

The persistent server design makes the website feel interactive after startup.

---

## Future Improvements

Possible next steps:

- add a clickable map using Leaflet,
- improve frontend result explanations,
- join DEM terrain features into the general reconstruction model,
- compare terrain-aware and non-terrain general model performance,
- add technical documentation for the scoring system,
- add a fast loader that skips monthly/seasonal calculations when not needed,
- create a binary cache or SQLite database to reduce startup time,
- expose `StationProxyEngine` directly to Python using pybind11,
- replace stdin/stdout communication with a more standard C++ binding or service interface,
- add automated tests for station loading and scoring,
- add deployment instructions.

---

## Why This Project Matters

This project is not just a webpage. It combines:

- real NOAA climate/weather data,
- custom preprocessing,
- C++ data parsing and scoring,
- geographic nearest-station lookup,
- time-series similarity analysis,
- FastAPI backend integration,
- browser-based frontend display,
- persistent in-memory engine architecture.

The result is a working technical tool for identifying representative long-record weather stations for locations with shorter or less complete station histories.
