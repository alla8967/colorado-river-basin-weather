# Weather Reconstruction Scripts

This folder contains the command-line tools and shared Python modules for the
temperature reconstruction workflow.

## Safety Boundary

The Alpine scratch copy used by active or pending station-holdout jobs should be
treated as frozen run code until a new version is intentionally validated and
synced. Local cleanup in this repository is fine, but do not rsync, rename, or
reorganize the Alpine copy while those jobs are running.

## Folder Map

```text
scripts/
├── common/      reusable data, metric, model-run, reporting, and confidence helpers
├── pipeline/    station selection, feature selection, holdout, and table logic
├── tests/       pytest coverage for helpers, pipelines, and run-script contracts
└── *.py         command-line entry points for building, training, validating,
                exporting, auditing, and reporting
```

For a reviewer-oriented inventory of the entry-point scripts and shared helper
boundaries, see `../../docs/research_script_inventory.md`.

The subfolders also have local READMEs:

- `common/README.md` explains general-purpose shared helpers.
- `pipeline/README.md` explains training and station-selection helpers.
- `tests/README.md` explains the reconstruction script test coverage.

## Entry-Point Groups

- Build inputs and caches: `build_weather_cache.py`, `build_training_table.py`,
  `build_general_training_table.py`, `build_station_terrain_features.py`,
  `build_pairwise_station_skill_features.py`.
- Train models: `train_temperature_model.py`,
  `train_tree_temperature_model.py`, `train_general_temperature_model.py`,
  `train_station_holdout_model.py`.
- Validate and score: `run_station_validation.py`,
  `batch_validate_models.py`, `validate_predictions_with_cpp.py`,
  `score_confidence_point.py`.
- Build model-run artifacts and confidence products:
  `build_model_run_artifacts.py`, `build_confidence_points.py`,
  `build_continuous_confidence_grid.py`,
  `build_calibrated_confidence_comparison.py`.
- Summarize and audit: `analyze_batch_results.py`,
  `build_alpine_run_summary.py`, `build_diagnostics_report.py`,
  `build_failure_diagnostics_report.py`,
  `build_model_comparison_report.py`, `build_calibration_audit_report.py`,
  `build_holdout_baseline_comparison.py`,
  `build_physical_regime_diagnostics.py`,
  `build_representativeness_audit_report.py`,
  `audit_project_readiness.py`, `check_remote_environment.py`.
- Alpine/run orchestration helpers: `run_remote_pipeline.py`,
  `create_station_holdout_chunks.py`, `create_station_holdout_groups.py`,
  `merge_station_holdout_results.py`, `export_final_model_artifact.py`.

## Review Rules

- Keep command-line scripts thin: argument parsing, path setup, and orchestration.
- Put reused behavior in `common/` or `pipeline/` before copying logic between
  scripts.
- Put repeated static-report escaping and table rendering in `common/reporting.py`.
- Keep generated outputs, model files, caches, scratch data, and large training
  tables out of source commits unless they are intentionally curated fixtures.
- Add or update tests in `tests/` when changing shared helpers, run-script
  contracts, model-run artifact schemas, or confidence scoring logic.
