# Colorado River Basin Weather Station Proxy And Reconstruction Toolkit

This project is a full-stack NOAA weather station analysis tool with two connected
missions.

The original and primary function is an interactive station-proxy finder: a user
enters or selects a latitude/longitude, the app finds the nearest usable target
weather station, and a C++ engine ranks long-record hub stations that can act as
the best proxy stations for that location.

The secondary and much larger function is a research pipeline for temperature
reconstruction. It prepares NOAA GHCN-Daily data and DEM-derived terrain data,
builds large training tables, trains linear and tree-based reconstruction models,
validates those models with station-holdout experiments, and turns the resulting
metrics into confidence and reliability map products for the frontend.

In short:

```text
NOAA station metadata and daily observations
DEM terrain features
Python preprocessing and model pipelines
C++ station matching and scoring engine
FastAPI backend
Browser frontend with maps, charts, reliability, and confidence views
```

## What This Project Does

This repository contains several pieces that work together:

- Interactive browser app for station-proxy analysis.
- Persistent C++ engine for fast repeated station matching.
- NOAA GHCN-Daily station filtering and app-ready CSV generation.
- DEM terrain feature sampling for candidate stations.
- SQLite weather-cache support for faster modeling workflows.
- Linear baseline and tree-based temperature reconstruction training.
- General training-table builders for many-station model runs.
- Pairwise station skill features based on historical station agreement.
- Station-holdout validation workflows for measuring reconstruction reliability.
- Final-model artifact export and model-run manifest generation.
- Confidence-support scoring for user-selected map points.
- Reliability surface and station overlay generation for frontend map modes.
- HTML diagnostic, calibration, representativeness, and comparison reports.
- Alpine/Slurm remote job scripts for larger model runs.
- Lightweight tests and fixtures for reviewer validation without full local data.

## Why It Matters

Many climate and weather workflows need a representative long-record station for
a place with shorter, sparse, or incomplete observations. This project explores
that problem from both sides:

- a practical app that finds and explains proxy stations for a selected location,
- a validation pipeline that asks how reliable those proxy relationships are
  when reconstructing observed daily temperatures.

The result is not just a web page. It is a small research platform that connects
raw public weather data, physical terrain context, model validation, and an
interactive review interface.

## Current Status

The repository is organized as a public, reviewable source project. The polished
frontend lives in `station-proxy-backend/index.html` and is served by FastAPI.

The source code, tests, docs, small fixtures, station metadata, and curated
candidate station lists are tracked. Large generated artifacts are intentionally
ignored, including app-ready NOAA daily CSVs, DEM rasters, model runs, caches,
and generated report/output folders.

That means:

- `make check` works as the main reviewer validation path.
- The app code and tests are reviewable from a fresh clone.
- Some full runtime views require local generated NOAA/model artifacts that are
  documented but not committed.

## Main Application Workflow

```text
User selects a latitude/longitude
→ FastAPI sends coordinates to a persistent C++ engine
→ the engine finds the nearest target station
→ the engine ranks long-record hub stations by proxy suitability
→ the browser renders maps, station details, metrics, and comparison charts
```

The app is designed around repeated use. The expensive step is loading large
NOAA station CSVs into memory. After startup, the persistent C++ server keeps
that data loaded so location requests can be handled quickly.

## Frontend Features

The browser interface includes:

- latitude/longitude analysis controls,
- Leaflet map views,
- nearest target station summary,
- best proxy station summary,
- ranked proxy match results,
- station metadata and observation-period details,
- daily/monthly comparison charts,
- confidence-support map layer,
- model-run support summaries,
- reliability surface map modes,
- station overlay modes for holdout and fully trained model metrics.

Reliability map modes include:

- overall holdout quality,
- holdout correlation,
- holdout MAE,
- holdout RMSE,
- holdout bias,
- fully trained model correlation,
- fully trained model MAE,
- fully trained model RMSE,
- fully trained model bias.

## Backend Features

The FastAPI backend lives in `station-proxy-backend/`.

It serves:

- the browser frontend,
- static assets,
- engine health checks,
- location analysis responses,
- confidence-support scoring,
- current model-run summaries,
- confidence-grid artifacts,
- reliability surface JSON,
- reliability raster images,
- station overlay images,
- clicked-grid and station-detail reliability responses.

Important backend modules:

- `main.py` wires the routes.
- `engine_client.py` manages the persistent C++ engine process.
- `confidence_service.py` exposes confidence-support scoring.
- `model_run_service.py` reads generated model-run manifests and grids.
- `reliability_service.py` serves reliability surfaces, overlays, and station
  detail payloads.
- `settings.py` centralizes paths and environment overrides.
- `api_models.py` defines response models.

## C++ Station Proxy Engine

The C++ engine lives in `C++_Weather_Station_Proxy_Engine/`.

It is responsible for:

- loading app-ready target and hub station daily CSVs,
- organizing station metadata and daily observations,
- finding the nearest target station to a selected coordinate,
- comparing the target station against candidate hub stations,
- calculating similarity and physical-context metrics,
- ranking proxy stations,
- returning JSON for the backend and tests.

The scoring uses signals such as:

- daily temperature correlation,
- daily mean absolute difference,
- daily RMSE,
- monthly temperature similarity,
- geographic distance,
- elevation difference,
- number of paired observations.

The same C++ code is used by:

- a one-shot command-line executable,
- the persistent stdin/stdout server used by FastAPI,
- a prediction similarity validator for Python-generated reconstruction outputs,
- fixture-backed local tests.

## NOAA Data Preparation

The data-prep lane lives in `NOAA_Inventory_Sort/`.

It uses NOAA GHCN-Daily metadata files:

- `ghcnd-inventory.txt`,
- `ghcnd-stations.txt`.

The preprocessing work separates stations into:

- target stations, which are recent-enough stations used for location analysis
  and validation,
- hub stations, which are long-record stations that can act as proxy candidates.

Generated app-ready daily CSVs use this shape:

```csv
station_id,station_name,latitude,longitude,elevation,date,tmax,tmin
```

The full daily files are generated artifacts and are ignored:

```text
NOAA_Inventory_Sort/target_daily_app_ready.csv
NOAA_Inventory_Sort/hub_daily_app_ready.csv
NOAA_Inventory_Sort/NOAA_GHCN_ByYear/
```

## Terrain And Physical Features

The reconstruction pipeline can use DEM-derived terrain features to add physical
context to station selection and model training.

Terrain workflows include:

- downloading DEM tiles from a manifest,
- validating DEM alignment,
- sampling terrain features at station locations,
- joining terrain features into station-selection and training-table workflows.

Generated terrain rasters and processed terrain tables are local artifacts and
are intentionally not committed.

## Temperature Reconstruction Pipeline

The model pipeline lives in `weather_reconstruction_model/scripts/`.

At a high level:

```text
station candidate metadata
app-ready daily NOAA observations
terrain features
weather cache
pairwise station skill features
→ general training tables
→ model training
→ predictions
→ station-level metrics
→ reports, confidence products, reliability surfaces
```

The pipeline includes:

- baseline one-station linear regression workflows,
- many-station general training tables,
- variable-aware TAVG/TMIN/TMAX workflows,
- ridge/linear model support,
- random forest and histogram gradient boosting model support,
- station-holdout validation,
- final-model station metric evaluation,
- model-run artifact packaging.

The project uses simple linear models as explainable baselines and tree-based
models for stronger tabular reconstruction performance.

## Confidence And Reliability Products

The frontend reliability and confidence views are generated from model artifacts.

Confidence products answer:

```text
How much support does this location have from nearby validated station evidence?
```

Reliability products answer:

```text
Where did station-holdout reconstruction perform well, poorly, or with bias?
```

Generated products can include:

- confidence support points,
- continuous confidence grids,
- reliability raster surfaces,
- station overlay images,
- station-level holdout metrics,
- fully trained final-model station metrics,
- JSON manifests and summaries served by FastAPI.

These products are generated outputs, not source files, so the code documents how
to build and serve them while keeping bulky artifacts out of git.

## Reports And Audits

The research pipeline includes static report builders for:

- batch validation summaries,
- model comparisons,
- calibration audits,
- C++ prediction validation writeups,
- diagnostics and failure analysis,
- physical regime diagnostics,
- representativeness audits,
- offset holdout experiments,
- Alpine run summaries.

These reports help explain not just whether a model worked, but where it worked,
where it failed, and why the failure cases may be physically meaningful.

## Remote Alpine Workflows

The `remote_jobs/` folder contains Slurm scripts for CU Boulder Alpine runs.

Remote workflows support:

- smoke tests,
- medium and wide reconstruction runs,
- Paloma training-table builds,
- model export jobs,
- station-holdout arrays,
- grouped high-memory holdout jobs,
- holdout result merging,
- result retrieval.

Remote run documentation lives in `docs/remote_runs/`.

The local docs intentionally warn not to sync or reorganize active Alpine scratch
copies while jobs are running.

## Repository Layout

```text
colorado-river-basin-weather/
├── README.md                         main overview
├── PROJECT_MAP.md                    visual review map
├── Makefile                          build, run, test, cleanup commands
├── pyproject.toml                    Python package/dependency metadata
├── docs/                             runbooks, audits, remote-run docs
├── NOAA_Inventory_Sort/              NOAA metadata and data-prep tools
├── C++_Weather_Station_Proxy_Engine/ reusable C++ station matching engine
├── Station_Engine_Server/            persistent C++ server wrapper
├── station-proxy-backend/            FastAPI backend and browser frontend
├── weather_reconstruction_model/     Python modeling and validation pipeline
├── remote_jobs/                      Alpine/Slurm orchestration scripts
└── tests/                            lightweight local smoke tests and fixtures
```

Each major source folder has its own `README.md` with a focused explanation.

## Where To Start

For project orientation:

- `PROJECT_MAP.md` gives a quick folder-by-folder guide.
- `docs/reviewer_runbook.md` gives setup, validation, and local run steps.
- `docs/research_script_inventory.md` maps the modeling scripts.
- `docs/generated_artifact_audit.md` explains what is intentionally ignored.
- `docs/artifact_quarantine_plan.md` explains local artifact cleanup policy.

For code review:

- start with `station-proxy-backend/` for the app,
- then `C++_Weather_Station_Proxy_Engine/` for the station matching core,
- then `weather_reconstruction_model/scripts/` for the modeling pipeline,
- then `remote_jobs/` if reviewing Alpine execution.

## Quick Validation

From the project root:

```bash
make check
```

`make check` runs:

- JavaScript syntax checks,
- backend Python compile checks,
- FastAPI app-shell smoke test,
- reliability backend tests,
- fixture-backed C++ engine test,
- C++ prediction validator build.

To run the Python research-script test suite:

```bash
.venv/bin/python -m pip install -e ".[dev]"
PYTHON=.venv/bin/python make test-python
```

## Running The Local App

Install dependencies into your active Python environment:

```bash
make setup-backend
```

Build the persistent C++ server:

```bash
make server
```

Start FastAPI:

```bash
make run-backend
```

Then open:

```text
http://127.0.0.1:8000/
```

The first startup can be slow because the C++ engine loads large station CSVs
into memory. After that, repeated location requests are fast.

## Common Commands

```bash
make check                 # main reviewer validation set
make test-python           # Python research-script pytest suite
make server                # build persistent C++ server
make api                   # build one-shot C++ API executable
make run-backend           # run FastAPI app
make run-api               # run one-shot coordinate analysis
make doctor                # audit local readiness and expected artifacts
make clean                 # remove compiled outputs
make clean-local-artifacts # remove conservative rebuildable byproducts
```

## Artifact Policy

This repo intentionally does not commit large generated data or local runtime
artifacts.

Ignored examples include:

- app-ready NOAA daily CSVs,
- yearly NOAA bulk files,
- DEM rasters,
- processed terrain products,
- SQLite weather caches,
- generated training tables,
- model runs,
- model files,
- reports,
- compiled C++ binaries,
- local virtual environments.

Small fixtures and curated metadata are tracked when they help review or testing.

## Environment Overrides

The backend works with the default repo layout, but `.env.example` documents
optional path overrides for:

- project root,
- C++ engine executable,
- target and hub daily CSVs,
- confidence support inputs,
- model-run roots,
- active model-run IDs.

Use these when running against alternate artifact locations.

## Engineering Highlights

This project demonstrates:

- full-stack app development with FastAPI and browser JavaScript,
- C++ engine design for reusable, performance-sensitive station scoring,
- process orchestration between Python/FastAPI and a persistent C++ service,
- NOAA data preparation and metadata filtering,
- geospatial station selection,
- DEM-derived terrain feature integration,
- model training and validation workflow design,
- reliability and confidence visualization pipelines,
- remote Slurm workflow management,
- source/artifact boundary discipline,
- practical test coverage for a mixed Python/C++/frontend project.

## Known Constraints

- Full app runtime depends on generated NOAA/model artifacts that are too large
  or too local to commit.
- Some modeling reports document active research workflows rather than polished
  package APIs.
- Alpine scratch copies should remain frozen while active jobs are running.
- The project is optimized for local review and research iteration, not hosted
  production deployment yet.

## Project Summary

The project began as a station proxy finder and grew into a broader weather
reconstruction toolkit. The polished app lets a reviewer inspect station matches
interactively. The modeling pipeline explains how those matches can be validated,
where they are reliable, and where the physical evidence is weaker.

Together, the app, C++ engine, Python pipeline, reports, and remote workflows
show a complete path from raw public weather data to an interactive analytical
tool.
