# Generated Artifact Audit

This audit describes what should and should not be committed while the project is
being cleaned up for review.

For the human-facing cleanup policy and conservative local cleanup command, see
`docs/artifact_quarantine_plan.md`.

## Current Tracked Data Files

The repository intentionally tracks only small or source-like CSV files:

```text
NOAA_Inventory_Sort/hub_station_candidates.csv
NOAA_Inventory_Sort/target_station_candidates.csv
tests/fixtures/hub_daily_app_ready.csv
tests/fixtures/target_daily_app_ready.csv
```

The station candidate files are source inputs. The fixture CSVs are tiny test
inputs for the C++ engine smoke test.

## Ignored Generated Outputs

These categories are ignored and should remain out of source commits:

- macOS finder files and Python bytecode: `.DS_Store`, `__pycache__/`,
  `*.pyc`.
- local environment override files: `.env`, `.env.*`, except `.env.example`.
- local virtual environments, editable-install metadata, and tool caches:
  `.venv/`, `venv/`, `env/`, `*.egg-info/`, `.pytest_cache/`,
  `.mypy_cache/`, `.ruff_cache/`.
- compiled C++ binaries: `station_engine_api`, `station_engine_api_test`,
  `validate_prediction_similarity`, `Station_Engine_Server/station_engine_server`.
- generated NOAA/app-ready data: `NOAA_Inventory_Sort/NOAA_GHCN_ByYear/`,
  `NOAA_Inventory_Sort/*_daily_app_ready.csv`,
  `NOAA_Inventory_Sort/*_daily_recent_long_format.csv`.
- model caches, model runs, reports, and training outputs:
  `weather_reconstruction_model/cache/`,
  `weather_reconstruction_model/outputs/`,
  `weather_reconstruction_model/model_runs/`.
- local Alpine and exported Paloma model shelves:
  `alpine_outputs/`,
  `model_runs/`.
- local DEM downloads and terrain rasters: `Raw_DEM/*.tif`,
  `terrain_data/raw_dem/`, `terrain_data/processed/`.
- serialized model/data artifacts: `*.sqlite`, `*.sqlite3`, `*.db`, `*.pkl`,
  `*.joblib`, `*.parquet`, `*.npy`, `*.npz`.
- local Slurm/log output: `*.log`, `*.out`, `*.err`, `slurm-*.out`.

## Commit Rule

Before staging a cleanup change, run:

```bash
git status --short
git status --ignored --short
```

Stage only source code, tests, docs, small fixtures, and intentionally curated
configuration examples. Do not stage generated outputs, scratch data, local
environments, compiled binaries, model files, or Alpine run results.
