# Research Script Inventory

This inventory gives reviewers a map of `ml_reconstruction/weather_reconstruction_model/scripts`
without requiring them to inspect every script first.

## Shared Modules

```text
common/       CSV, JSON, metrics, number parsing, model-run, weather-cache,
              reporting, confidence, and pairwise-skill helpers
pipeline/     station selection, feature selection, training-data prep,
              station-holdout filtering, and training-table logic
tests/        pytest-style and direct-call tests for shared helpers and script
              contracts
```

Shared behavior should move into `common/` or `pipeline/` before being copied
between entry-point scripts.

## Entry Point Groups

Build inputs and caches:

```text
build_weather_cache.py
build_training_table.py
build_general_training_table.py
build_station_terrain_features.py
build_pairwise_station_skill_features.py
download_dem_tiles.py
validate_dem_alignment.py
count_stations.py
```

Train and validate models:

```text
train_temperature_model.py
train_tree_temperature_model.py
train_general_temperature_model.py
train_station_holdout_model.py
run_station_validation.py
batch_validate_models.py
validate_predictions_with_cpp.py
run_reference_cases.py
```

Model-run artifacts and confidence products:

```text
build_model_run_artifacts.py
export_final_model_artifact.py
build_confidence_points.py
score_confidence_point.py
build_calibrated_confidence_comparison.py
build_continuous_confidence_grid.py
```

Reports and audits:

```text
analyze_batch_results.py
audit_project_readiness.py
check_remote_environment.py
build_alpine_run_summary.py
build_calibration_audit_report.py
build_cpp_validation_writeup.py
build_diagnostics_report.py
build_failure_diagnostics_report.py
build_model_comparison_report.py
build_offset_holdout_report.py
build_physical_regime_diagnostics.py
build_representativeness_audit_report.py
```

Remote and Paloma orchestration:

```text
run_remote_pipeline.py
create_station_holdout_chunks.py
create_station_holdout_groups.py
merge_station_holdout_results.py
```

## Current Shared Boundaries

Reusable behavior belongs in these helper modules:

- `common.csv_utils.read_csv_fieldnames`
- `common.csv_utils.count_csv_rows`
- `common.json_utils.write_json_file`
- `common.model_artifacts.project_relative_path`
- `common.model_artifacts.infer_feature_unit`
- `common.model_artifacts.build_feature_schema_payload`
- `common.model_artifacts.build_validation_model_run_manifest`
- `common.model_artifacts.build_production_model_run_manifest`
- `common.model_artifacts.build_serialized_model_artifact_manifest`
- `common.model_artifacts.merge_serialized_model_run_manifest`
- `common.reporting.escape_html`
- `common.reporting.render_html_table`
- `common.reporting.render_metric_card`
- `pipeline.model_features.resolve_model_feature_selection`
- `pipeline.model_features.add_offset_feature_columns`
- `pipeline.model_features.require_training_columns`
- `pipeline.training_data.build_unscaled_features_and_labels`
- `pipeline.training_data.actual_temperature_values`
- `pipeline.training_data.add_baseline_to_offsets`
- `pipeline.training_data.build_temperature_prediction_rows`
- `pipeline.station_holdouts.row_uses_station`
- `pipeline.station_holdouts.row_uses_any_station`
- `pipeline.station_holdouts.training_rows_for_station_holdout`
- `pipeline.training_tables.build_general_rows_for_target`
- `pipeline.training_tables.fieldnames_for_hub_count`
- `pipeline.training_tables.open_streaming_general_table_writer`

These helpers are already used by model-run artifact scripts, confidence-grid
builders, Paloma feature-selection paths, station-holdout training scripts, and
general-table/reporting scripts with repeated static structure:

```text
build_model_run_artifacts.py
export_final_model_artifact.py
build_calibrated_confidence_comparison.py
build_continuous_confidence_grid.py
build_calibration_audit_report.py
build_cpp_validation_writeup.py
build_model_comparison_report.py
build_offset_holdout_report.py
build_diagnostics_report.py
build_failure_diagnostics_report.py
build_physical_regime_diagnostics.py
build_representativeness_audit_report.py
train_tree_temperature_model.py
train_station_holdout_model.py
build_general_training_table.py
```

Tests in `scripts/tests/test_common_utils.py` cover the new shared helpers.
Tests in `scripts/tests/test_temperature_trainer_variables.py` cover the
variable-aware feature-selection helpers used by Paloma artifact exports.
Tests in `scripts/tests/test_training_pipeline_helpers.py` cover the shared
training-data and station-holdout helpers.
Tests in `scripts/tests/test_general_training_table_variables.py` cover
variable-aware general-table rows, fieldnames, terrain columns, predictor
sections, and pairwise-skill columns.

Keep command-line entry points focused on arguments, paths, and orchestration.
When a script starts to duplicate feature selection, model-run artifact shape,
CSV/JSON writing, confidence support, or report rendering, move that behavior
into `common/` or `pipeline/`.

## Report Helper Inventory

The main static-report scripts now use `common.reporting` for repeated HTML
escaping, simple table rendering, trusted `<code>` cells, and label/value metric
cards. Keep using these helpers for report-wide structure and small tables.

Complex station-detail tables, chart SVGs, and tables with report-specific cell
classes can stay local until there is a clear shared shape. The goal is readable
reports, not a clever template framework.

## Next Cleanup Targets

Good next refactor candidates:

- keep report-specific tables local when they need custom classes, badges, or
  chart markup, but avoid recreating escape/table/card helpers,
- continue moving model training and holdout entry points onto
  `pipeline.model_features` where it keeps the script easier to read,
- keep `train_general_temperature_model.py` stable until the standardized
  feature-scaling helpers can move without creating a circular dependency,
- keep `build_general_training_table.py` focused on data loading, station
  selection, streaming output, and CLI orchestration; move new reusable table
  row/field behavior into `pipeline.training_tables`,
- add focused report-render smoke tests if these HTML reports become review
  deliverables rather than research-only diagnostics,
- keep CLI parsing in scripts, but move reusable data transforms into
  `common/` or `pipeline/`.
