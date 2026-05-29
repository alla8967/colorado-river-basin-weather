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
| `.venv/`, `web_app/station-proxy-backend/.venv/` | Local Python environments. | Ignore; recreate with `make setup` or `make setup-backend`. |
| `.pytest_cache/`, `build/`, `__pycache__/` | Local test/build caches. | Safe to remove when cleaning the workspace. |
| `station_engine_api`, `validate_prediction_similarity`, `cpp_scoring_engine/Station_Engine_Server/station_engine_server` | Compiled C++ executables. | Rebuild with Makefile targets; do not commit. |
| `ml_reconstruction/NOAA_Inventory_Sort/NOAA_GHCN_ByYear/` | NOAA yearly bulk archive. | Large generated/input data; keep ignored and do not move casually. |
| `ml_reconstruction/NOAA_Inventory_Sort/ghcnd-inventory.txt`, `ml_reconstruction/NOAA_Inventory_Sort/ghcnd-stations.txt` | NOAA full metadata snapshots. | Public source repo excludes these larger NOAA inputs; regenerate/download locally when needed. |
| `ml_reconstruction/NOAA_Inventory_Sort/*_daily_app_ready.csv` | App-ready station daily CSVs. | Generated but useful for local app runs; keep ignored. |
| `ml_reconstruction/weather_reconstruction_model/cache/` | Research/model caches. | Keep ignored. |
| `ml_reconstruction/weather_reconstruction_model/outputs/` | Research outputs and reports. | Keep ignored unless a small curated result is intentionally documented. |
| `ml_reconstruction/weather_reconstruction_model/model_runs/` | Local model-run artifacts and active confidence grid contract. | Keep ignored, but keep the active v1 run locally because FastAPI serves it to the Model Support tab. |
| `ml_reconstruction/weather_reconstruction_artifacts/` | Local archive/scratch artifact shelf. | Keep ignored; browse only when investigating generated outputs. |
| `ml_reconstruction/terrain_data/raw_dem/`, `ml_reconstruction/terrain_data/processed/`, `Raw_DEM/*.tif` | DEM downloads and derived terrain rasters. | Keep ignored because these are large/regenerable data products. |
| `web_app/station-proxy-backend/assets/confidence-points.json` | Older generated frontend/model handoff data. | Keep ignored; current frontend confidence layers come from `/model-runs/current/confidence-grid`. Safe deletion should be paired with a quick app smoke test. |

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

For a more detailed local generated-data inventory, including what should stay
until active station-holdout work finishes, see `docs/local_artifact_inventory.md`.

## Future Reorganization

A stricter `src/`, `apps/`, `data_sources/`, and `artifacts/` split may make
sense later, but it should happen only after the active script entry points and
data-path assumptions are audited. For the current review-focused cleanup,
clear documentation is safer than moving data-heavy directories.
