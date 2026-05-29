# Generated Artifacts

This project creates large model inputs, predictions, diagnostics, and smoke-test outputs. Keep source code in `ml_reconstruction/weather_reconstruction_model/`; keep bulky generated results out of the code path whenever possible.

## Active Outputs

`ml_reconstruction/weather_reconstruction_model/outputs/` is for the current working run: the latest training table, current predictions, current station metrics, and HTML reports you are actively reviewing.

Current active examples:

- `outputs/general_training_tables/option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain.csv`
- `outputs/predictions/option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain_offset_terrain_standard_random_forest_predictions.csv`
- `outputs/reports/option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain_offset_terrain_standard_random_forest_station_metrics.csv`
- `outputs/reports/offset_mode_station_holdout_report.html`

## Model Runs

`ml_reconstruction/weather_reconstruction_model/model_runs/<model_run_id>/` is the stable handoff
shape for calibrated model evidence and frontend-ready confidence grids. See
`MODEL_RUNS.md` for the artifact contract.

Adapt current working outputs into `model_runs/` before wiring calibrated
confidence into the backend or frontend.

## Archived Outputs

`../ml_reconstruction/weather_reconstruction_artifacts/archive/` is for older runs that are still worth preserving for comparison, but are not the current working target.

Examples include older full 97-target tables, previous option-C tables, and old validation CSVs.

## Scratch Outputs

`../ml_reconstruction/weather_reconstruction_artifacts/scratch/` is for smoke tests, small experiments, and exploratory reports. These files are useful for debugging but should not be treated as canonical results.

## Git Tracking

Generated artifacts are ignored by git:

- `ml_reconstruction/weather_reconstruction_model/outputs/`
- `ml_reconstruction/weather_reconstruction_model/cache/`
- `ml_reconstruction/weather_reconstruction_model/model_runs/`
- `ml_reconstruction/weather_reconstruction_artifacts/`
- DEM-derived terrain outputs

If a generated report becomes something you want to preserve permanently, summarize it in documentation rather than committing the full CSV artifact.
