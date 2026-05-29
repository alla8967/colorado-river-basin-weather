# Remote Run Manifest

This file describes the minimum project shape needed to run the weather reconstruction workflow on a larger remote machine.

The goal is to make a remote run boring: copy the required inputs, run an environment check, run a preset pipeline command, and retrieve the generated outputs.

## Expected Project Root

Run commands from the repository root:

```text
Colorado River Basin Project/
```

The root should contain:

```text
Makefile
README.md
ml_reconstruction/NOAA_Inventory_Sort/
ml_reconstruction/terrain_data/
ml_reconstruction/weather_reconstruction_model/
```

For the exact upload/exclude list, use `REMOTE_TRANSFER_CHECKLIST.md`.

## Python

Recommended:

```text
Python 3.10 or newer
```

Known Python package requirements:

```text
numpy
scikit-learn
```

Terrain rebuilds also require:

```text
rasterio
```

`rasterio` is not required if the processed station terrain file already exists.

## Required Input Files

These files are needed for normal model training:

```text
ml_reconstruction/NOAA_Inventory_Sort/target_station_candidates.csv
ml_reconstruction/NOAA_Inventory_Sort/hub_station_candidates.csv
ml_reconstruction/NOAA_Inventory_Sort/target_daily_app_ready.csv
ml_reconstruction/NOAA_Inventory_Sort/hub_daily_app_ready.csv
ml_reconstruction/terrain_data/processed/station_terrain_features.csv
ml_reconstruction/weather_reconstruction_model/cache/weather_data.sqlite
```

The SQLite cache is strongly preferred for remote runs because it avoids repeated full CSV scans.

## Optional Input Files

These are useful only if rebuilding derived data:

```text
ml_reconstruction/weather_reconstruction_artifacts/raw_dem_archive/Raw_DEM/*.tif
ml_reconstruction/weather_reconstruction_artifacts/noaa_year_archive/NOAA_GHCN_ByYear/*.csv.gz
```

Do not upload raw DEM files unless you plan to rebuild terrain features.

## Generated Output Locations

The main generated files land in:

```text
ml_reconstruction/weather_reconstruction_model/cache/*_pairwise_skill_train_through_*.csv
ml_reconstruction/weather_reconstruction_model/outputs/general_training_tables/
ml_reconstruction/weather_reconstruction_model/outputs/predictions/
ml_reconstruction/weather_reconstruction_model/outputs/reports/
```

These outputs are intentionally ignored by git.

## Preflight Check

Run this before starting a long job:

```bash
python ml_reconstruction/weather_reconstruction_model/scripts/check_remote_environment.py
```

For stricter checks:

```bash
python ml_reconstruction/weather_reconstruction_model/scripts/check_remote_environment.py --require-sklearn --check-cache-integrity
```

If you need to rebuild terrain features on the remote machine:

```bash
python ml_reconstruction/weather_reconstruction_model/scripts/check_remote_environment.py --require-rasterio
```

## Preset Pipeline Commands

Smoke test:

```bash
python ml_reconstruction/weather_reconstruction_model/scripts/run_remote_pipeline.py --preset smoke
```

For build presets, the runner first creates a pairwise historical skill CSV in
`ml_reconstruction/weather_reconstruction_model/cache/`, then passes that file into
`build_general_training_table.py`. Pairwise skill is calculated from same-date
training-window observations only, so it can improve station selection and
features without using the test period as evidence.

Medium run:

```bash
python ml_reconstruction/weather_reconstruction_model/scripts/run_remote_pipeline.py --preset medium
```

Full run:

```bash
python ml_reconstruction/weather_reconstruction_model/scripts/run_remote_pipeline.py --preset full
```

Wider remote experiments:

```bash
python ml_reconstruction/weather_reconstruction_model/scripts/run_remote_pipeline.py --preset wide-medium
python ml_reconstruction/weather_reconstruction_model/scripts/run_remote_pipeline.py --preset wide-large
python ml_reconstruction/weather_reconstruction_model/scripts/run_remote_pipeline.py --preset wide-full
```

The wide presets are intended for larger machines:

```text
wide-medium  200 targets, 10 hubs, 20 target-neighbor predictors
wide-large   400 targets, 15 hubs, 30 target-neighbor predictors
wide-full    all targets, 20 hubs, 40 target-neighbor predictors
```

Station-holdout validation:

```bash
python ml_reconstruction/weather_reconstruction_model/scripts/run_remote_pipeline.py --preset holdout-full --general-table ml_reconstruction/weather_reconstruction_model/outputs/general_training_tables/option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain.csv
```

Preview commands without running them:

```bash
python ml_reconstruction/weather_reconstruction_model/scripts/run_remote_pipeline.py --preset medium --dry-run
```

## Practical Hardware Notes

For the current random forest workflow:

- More CPU cores help, especially for `--jobs -1`.
- More RAM matters during training because the feature matrix is wide.
- Disk speed matters when reading large CSVs, but the SQLite cache reduces repeated scan cost.

On a remote machine, start with `smoke`, then `medium`, then `wide-medium`. Move to `wide-large` or `wide-full` only after the smaller wide run completes cleanly.
