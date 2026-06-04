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
- Python compile checks for the FastAPI backend and app-shell smoke test,
- the local app-shell smoke test,
- the fixture-backed C++ station engine test,
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
