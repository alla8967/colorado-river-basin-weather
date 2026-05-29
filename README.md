# Colorado River Basin Weather Station Proxy Finder

This repository contains a local NOAA weather-station proxy finder and the
research workflow behind a temperature reconstruction model for the Colorado
River Basin region.

The app answers two related questions:

1. Which long-record NOAA stations are plausible proxies for a selected
   location or nearby observed station?
2. How well supported is a temperature reconstruction model around that
   location, based on validation evidence and station support?

The codebase is intentionally mixed: it includes a browser/FastAPI app, a C++
station-scoring engine, Python data/modeling scripts, small test fixtures, and
Alpine Slurm run helpers. Large generated data and model artifacts are not
committed.

## Quick Review

For a fresh clone, the intended first check is:

```bash
python -m pip install -e ".[dev]"
make check
```

`make check` runs the clone-friendly validation path:

- frontend JavaScript syntax checks,
- backend Python compile checks,
- app-shell smoke tests,
- a fixture-backed C++ station-engine test,
- the C++ prediction-similarity validator build.

The heavier research-script pytest suite is useful for deeper review, but it is
not part of the fast CI path:

```bash
PYTHON=.venv/bin/python make test-python
```

## Current App Surface

The local web app lives in `web_app/station-proxy-backend/`.

It currently includes:

- a **Proxy Finder** tab with coordinate inputs, a Leaflet map, nearest-station
  lookup, ranked proxy stations, similarity metrics, and comparison charts;
- a **Model Support** tab with a confidence/support map loaded from the active
  model-run artifact contract;
- FastAPI endpoints for app health, proxy analysis, confidence scoring, and
  active model-run confidence grids.

Primary backend routes include:

```text
GET /
GET /test
GET /analyze-location
GET /analyze-confidence
GET /model-runs/current
GET /model-runs/current/confidence-grid
```

Running the full app requires generated NOAA/model artifacts described below.

## Repository Layout

| Path | Role |
| --- | --- |
| `web_app/` | FastAPI backend and browser frontend. |
| `cpp_scoring_engine/` | Reusable C++ station matching engine and persistent server wrapper. |
| `ml_reconstruction/NOAA_Inventory_Sort/` | NOAA inventory filtering code and small curated station candidate inputs. |
| `ml_reconstruction/weather_reconstruction_model/` | Python reconstruction, validation, confidence, and model-artifact scripts. |
| `ml_reconstruction/remote_jobs/` | Alpine Slurm scripts and result retrieval helpers. |
| `tests/` | Fast app/engine smoke tests and tiny CSV fixtures. |
| `docs/` | Reviewer runbooks, artifact policy, cleanup notes, and release checklist. |

Root-level files such as `Makefile`, `pyproject.toml`, `.env.example`,
`PROJECT_MAP.md`, and this README are the main command and orientation surface.

## Data And Artifact Policy

This public repo is designed to be reviewable without publishing bulky generated
data. It includes source code, docs, tests, tiny fixtures, and small curated
station-candidate CSVs.

It intentionally excludes:

- NOAA yearly bulk archives and full GHCN metadata snapshots,
- generated app-ready target and hub daily CSVs,
- model runs, training outputs, reports, caches, and serialized models,
- raw and processed DEM rasters,
- local virtual environments, compiled binaries, and scratch artifacts.

The most important excluded runtime files are:

```text
ml_reconstruction/NOAA_Inventory_Sort/target_daily_app_ready.csv
ml_reconstruction/NOAA_Inventory_Sort/hub_daily_app_ready.csv
ml_reconstruction/weather_reconstruction_model/model_runs/<active_run>/
ml_reconstruction/terrain_data/processed/station_terrain_features.csv
```

The small fixture files under `tests/fixtures/` are only for validation; they
are not scientific reproduction data.

See:

- `docs/artifact_quarantine_plan.md`
- `docs/generated_artifact_audit.md`
- `docs/local_artifact_inventory.md`

## Running The Local App

After supplying the generated NOAA/model artifacts, run:

```bash
make run-backend
```

Then open:

```text
http://127.0.0.1:8000/
```

The first startup can be slow because the C++ server loads the app-ready station
CSV files into memory. After startup, repeated location requests reuse the
loaded engine.

The backend derives paths from the repo layout by default. Use `.env.example`
if you need to point the app at alternate data, model-run, terrain, or engine
locations.

## Research Workflow

The modeling lane under `ml_reconstruction/weather_reconstruction_model/`
contains scripts for:

- building station/weather caches and training tables,
- joining geography, seasonality, terrain, station-neighbor, offset, and
  pairwise-skill features,
- training linear/ridge and random-forest temperature reconstruction models,
- running temporal validation and station-holdout validation,
- scoring predictions with the independent C++ similarity validator,
- generating diagnostics, calibration reports, confidence/support points, and
  model-run artifacts consumed by the app.

The current research code is not presented as a finished production ML package.
It is a documented research pipeline with shared helpers in:

```text
ml_reconstruction/weather_reconstruction_model/scripts/common/
ml_reconstruction/weather_reconstruction_model/scripts/pipeline/
```

For deeper context, start with:

- `ml_reconstruction/weather_reconstruction_model/README.md`
- `docs/research_script_inventory.md`
- `ml_reconstruction/weather_reconstruction_model/MODEL_RUNS.md`
- `ml_reconstruction/weather_reconstruction_model/CONFIDENCE_SUPPORT.md`

## C++ Station Proxy Engine

The reusable C++ core lives in:

```text
cpp_scoring_engine/C++_Weather_Station_Proxy_Engine/
```

The historical folder name is intentionally preserved for now. The core engine
loads target and hub station daily records, finds the nearest target station,
scores hub stations as proxies, and returns JSON used by the FastAPI backend.

The persistent wrapper lives in:

```text
cpp_scoring_engine/Station_Engine_Server/
```

It keeps the large station data loaded once and communicates with FastAPI over
stdin/stdout:

```text
stdin  = coordinate requests
stdout = JSON responses only
stderr = logs and diagnostics
```

## Useful Commands

```bash
make check                 # fast reviewer validation
make test-python           # heavier research-script pytest suite
make server                # build persistent C++ server
make api                   # build one-shot C++ API executable
make run-backend           # start FastAPI app after generated data is present
make clean-local-artifacts # remove rebuildable binaries/caches only
```

## Review Notes

This repository is being shared for critique. The most useful feedback is on:

- project organization and reviewer experience,
- FastAPI/frontend maintainability,
- C++ engine structure and testability,
- data-pipeline and artifact boundaries,
- validation design and modeling methodology,
- what tests would most improve confidence without requiring large local data.

Known limitations:

- full local app/model operation requires generated artifacts not committed here;
- the ML lane is still research-oriented and not fully productionized;
- Alpine scripts are run orchestration and assume an external HPC environment;
- the app is intended as a local technical tool, not a deployed public service.

See `REVIEWING.md` for a more direct critique guide.

## License

MIT. See `LICENSE`.
