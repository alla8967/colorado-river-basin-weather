# Artifact Quarantine Plan

The goal is to make the project easier for a human to browse without breaking
scripts that still expect generated files in their current locations.

## Policy

- Keep generated artifacts ignored and out of source commits.
- Do not move bulky data/model outputs during this cleanup pass unless the
  consuming scripts are updated and tested at the same time.
- Prefer documentation and conservative cleanup commands over a risky folder
  reshuffle.
- Treat Alpine scratch as frozen run code while active or pending jobs may be
  using it.

## Current Artifact Shelves

| Path | Contents | Handling |
| --- | --- | --- |
| `.venv/`, `station-proxy-backend/.venv/` | Local Python environments. | Ignore; recreate with `make setup` or `make setup-backend`. |
| `.pytest_cache/`, `build/`, `__pycache__/` | Local test/build caches. | Safe to remove when cleaning the workspace. |
| `station_engine_api`, `validate_prediction_similarity`, `Station_Engine_Server/station_engine_server` | Compiled C++ executables. | Rebuild with Makefile targets; do not commit. |
| `NOAA_Inventory_Sort/NOAA_GHCN_ByYear/` | NOAA yearly bulk archive. | Large generated/input data; keep ignored and do not move casually. |
| `NOAA_Inventory_Sort/*_daily_app_ready.csv` | App-ready station daily CSVs. | Generated but useful for local app runs; keep ignored. |
| `weather_reconstruction_model/cache/` | Research/model caches. | Keep ignored. |
| `weather_reconstruction_model/outputs/` | Research outputs and reports. | Keep ignored unless a small curated result is intentionally documented. |
| `weather_reconstruction_model/model_runs/` | Local model-run artifacts. | Keep ignored; production Paloma v1 artifacts live outside this local cleanup. |
| `alpine_outputs/` | Retrieved Alpine holdout metrics, predictions, and summary tables. | Keep ignored; useful for local reconstruction/reliability work, but too bulky and run-specific for source commits. |
| `model_runs/` | Local serialized Paloma model artifacts exported from remote/model runs. | Keep ignored; frontend defaults use `weather_reconstruction_model/model_runs/`, and serialized models stay local unless intentionally packaged. |
| `weather_reconstruction_artifacts/` | Local archive/scratch artifact shelf. | Keep ignored; browse only when investigating generated outputs. |
| `terrain_data/raw_dem/`, `terrain_data/processed/`, `Raw_DEM/*.tif` | DEM downloads and derived terrain rasters. | Keep ignored because these are large/regenerable data products. |
| `station-proxy-backend/assets/confidence-points.json` | Generated frontend/model handoff data. | Keep ignored; the app can fetch current confidence data from FastAPI. |

## Safe Cleanup

Use this when you want the folder to look calmer without deleting useful data:

```bash
make clean-local-artifacts
```

That target removes only rebuildable compiled binaries and local test/build
caches. It intentionally does not remove NOAA files, model runs, DEM data,
research outputs, local archives, or Alpine-related artifacts.

Before staging any cleanup commit, run:

```bash
git status --short
git status --ignored --short
```

Stage source code, tests, docs, small fixtures, and curated config examples
only.

## Future Reorganization

A stricter `src/`, `apps/`, `data_sources/`, and `artifacts/` split may make
sense later, but it should happen only after the active script entry points and
data-path assumptions are audited. For the current review-focused cleanup,
clear documentation is safer than moving data-heavy directories.
