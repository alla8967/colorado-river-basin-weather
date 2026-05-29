# Colorado River Basin Weather Station Proxy Finder

This project is a local NOAA weather-station analysis app plus the research
workflow behind it. The app lets a user choose a latitude/longitude, finds the
nearest observed station, and ranks long-record proxy stations with a reusable
C++ scoring engine. The research lane trains and validates temperature
reconstruction models whose support/confidence artifacts can be surfaced in the
app.

## Reviewer Quick Start

From a fresh clone, the source and fixture-backed checks are the intended first
review path:

```bash
python -m pip install -e ".[dev]"
make check
```

To run the local web app after supplying the generated NOAA/model artifacts
described below:

```bash
make run-backend
# open http://127.0.0.1:8000/
```

The heavier Python research-script suite is useful, but it is not part of the
fast CI path:

```bash
PYTHON=.venv/bin/python make test-python
```

## Folder Layout

The repository is organized around three main lanes:

| Folder | What it is |
| --- | --- |
| `cpp_scoring_engine/` | C++ station scoring engine and persistent server wrapper. |
| `ml_reconstruction/` | NOAA data-prep, ML reconstruction, confidence artifacts, terrain inputs, and remote jobs. |
| `web_app/` | FastAPI backend and browser frontend. |

Supporting files at the root (`README.md`, `PROJECT_MAP.md`, `Makefile`,
`pyproject.toml`, `.env.example`, `docs/`, and `tests/`) exist to explain,
validate, and run those three lanes.

Remote-run manifests live with the ML lane:

```text
ml_reconstruction/remote_jobs/REMOTE_RUN_MANIFEST.md
ml_reconstruction/remote_jobs/REMOTE_TRANSFER_CHECKLIST.md
```

## Data And Artifact Policy

This public source repo is designed to be reviewable without committing bulky
generated data. It intentionally includes source code, docs, tests, tiny
fixtures, and small curated station-candidate CSVs. It intentionally excludes:

- NOAA yearly bulk archives and full GHCN metadata snapshots,
- app-ready target and hub daily CSVs,
- model runs, training outputs, reports, caches, and serialized models,
- raw/processed DEM rasters,
- local virtual environments, compiled binaries, and scratch artifacts.

The excluded files are documented in `docs/artifact_quarantine_plan.md`,
`docs/generated_artifact_audit.md`, and `docs/local_artifact_inventory.md`.
Full local app/model runs require regenerating or supplying the ignored NOAA,
DEM, and model-run artifacts at the paths documented there.

## Critique Welcome

This repo is being prepared for outside critique. The most useful feedback is
on architecture, maintainability, data-pipeline clarity, validation strategy,
and modeling methodology. Known rough edges are intentionally documented rather
than hidden:

- `cpp_scoring_engine/C++_Weather_Station_Proxy_Engine/` keeps a historical
  folder name.
- The ML lane is research-oriented; not every script is productionized.
- Full app behavior depends on generated NOAA/model/DEM artifacts that are not
  committed.
- Alpine remote-run scripts are included for review, but scratch copies should
  be treated as separate run artifacts.

## Start Here / What To Ignore

If you are reviewing the project in a terminal or file browser, start with:

- `PROJECT_MAP.md` for the visual map of source folders, generated artifact
  shelves, and safe local commands.
- `docs/reviewer_runbook.md` for setup, validation, local run steps, and Alpine
  safety.
- `docs/research_script_inventory.md` for the research/model script map.
- `docs/artifact_quarantine_plan.md` for what can be cleaned locally and what
  should be left in place.
- `docs/generated_artifact_audit.md` for the commit/staging policy.
- `docs/v1_cleanup_plan.md` for the remaining product-polish priorities.
- `docs/release_checklist.md` for the v1 validation and handoff checklist.
- `docs/local_artifact_inventory.md` before deleting ignored local data.

Local development folders may contain ignored generated artifacts beside the
source. Review source and docs first; do not stage generated data, model files,
caches, local environments, compiled binaries, or Alpine run outputs.

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

## Validation Details

For most code reviews, the fast validation command is:

```bash
cd /path/to/colorado-river-basin-weather
make check
```

`make check` is the practical local validation set for the web app and C++
engine. It runs JavaScript syntax checks, backend Python compile checks, the app
shell smoke test, the fixture-backed C++ engine test, and the prediction
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
- `docs/v1_cleanup_plan.md` for the recommended v1 cleanup sequence.
- `docs/release_checklist.md` for the final v1 validation checklist.
- `docs/local_artifact_inventory.md` for the local generated-data inventory.

Alpine safety note: local cleanup is safe, but the copied scratch code under
`/scratch/alpine/$USER/crb_weather_runs/current` should remain frozen while
active or pending station-holdout jobs are using it.

---

## High-Level Architecture

```text
Colorado River Basin Project/
├── README.md
├── PROJECT_MAP.md
├── Makefile
├── docs/
│   ├── artifact_quarantine_plan.md
│   ├── generated_artifact_audit.md
│   ├── research_script_inventory.md
│   └── reviewer_runbook.md
├── ml_reconstruction/NOAA_Inventory_Sort/
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
├── cpp_scoring_engine/C++_Weather_Station_Proxy_Engine/
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
├── cpp_scoring_engine/Station_Engine_Server/
│   ├── station_engine_server.cpp
│   └── station_engine_server          (compiled, ignored)
├── ml_reconstruction/weather_reconstruction_model/
│   ├── README.md
│   ├── scripts/
│   │   ├── common/
│   │   ├── pipeline/
│   │   ├── tests/
│   │   └── README.md
│   ├── model_runs/                    (generated, ignored)
│   └── outputs/                       (generated, ignored)
└── web_app/station-proxy-backend/
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
            ├── api.js
            ├── charts.js
            ├── confidence.js
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
- `web_app/station-proxy-backend/` is the local web app. `main.py` wires FastAPI routes, while `engine_client.py`, `confidence_service.py`, `model_run_service.py`, `settings.py`, and `api_models.py` hold backend responsibilities.
- `web_app/station-proxy-backend/static/` is the browser app. `index.html` is structure, `styles.css` is presentation, and `static/js/main.js` is the frontend entry point.
- `cpp_scoring_engine/C++_Weather_Station_Proxy_Engine/` is the reusable station matching core used by both command-line validation and the server.
- `cpp_scoring_engine/Station_Engine_Server/` is the persistent stdin/stdout wrapper that lets FastAPI reuse one loaded C++ process.
- `ml_reconstruction/weather_reconstruction_model/scripts/` is the research and model-building command layer. Shared logic belongs in `scripts/common/` or `scripts/pipeline/`; generated tables, reports, caches, and model files should stay out of source commits unless intentionally curated.
- `ml_reconstruction/remote_jobs/` contains Alpine Slurm launch scripts. Treat these as run orchestration, not local application code.

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
ml_reconstruction/NOAA_Inventory_Sort/target_daily_app_ready.csv
ml_reconstruction/NOAA_Inventory_Sort/hub_daily_app_ready.csv
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
ml_reconstruction/NOAA_Inventory_Sort/NOAA_GHCN_ByYear/
```

---

## C++ Engine

The reusable C++ core is implemented in:

```text
cpp_scoring_engine/C++_Weather_Station_Proxy_Engine/STATION_PROXY_ENGINE.h
cpp_scoring_engine/C++_Weather_Station_Proxy_Engine/STATION_PROXY_ENGINE.cpp
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
ml_reconstruction/weather_reconstruction_model/README.md
```

---

## Weather Reconstruction Research Workflow

The `ml_reconstruction/weather_reconstruction_model/` folder is the research side of the project.
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
ml_reconstruction/weather_reconstruction_model/README.md
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
cpp_scoring_engine/Station_Engine_Server/station_engine_server.cpp
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
web_app/station-proxy-backend/main.py
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
web_app/station-proxy-backend/index.html
web_app/station-proxy-backend/static/styles.css
web_app/station-proxy-backend/static/js/main.js
web_app/station-proxy-backend/static/js/api.js
web_app/station-proxy-backend/static/js/charts.js
web_app/station-proxy-backend/static/js/confidence.js
web_app/station-proxy-backend/static/js/formatters.js
web_app/station-proxy-backend/static/js/maps.js
web_app/station-proxy-backend/static/js/results.js
web_app/station-proxy-backend/static/js/state.js
```

The split keeps the review surface predictable:

- `index.html` defines the page structure and data panels,
- `static/styles.css` owns the page layout and visual styling,
- `static/js/api.js` owns browser-to-backend requests,
- `static/js/maps.js` owns Leaflet setup and map overlays,
- `static/js/charts.js` owns SVG comparison charts,
- `static/js/confidence.js` owns model-support layer rendering,
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
cd /path/to/colorado-river-basin-weather
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
