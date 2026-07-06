# Model Run Artifact Contract

This contract gives each trained reconstruction model a stable folder shape so
calibration, confidence grids, backend endpoints, and frontend maps can all read
the same evidence without knowing which script produced it.

The current broad station-holdout evidence source is:

```text
alpine_outputs/paloma/paloma_v1_tavg_station_holdout_master.csv
```

That Paloma TAVG grouped holdout covers:

```text
validation stations: 739
test rows: 416,892
mean station MAE: about 2.68 F
median station MAE: about 2.49 F
p90 station MAE: about 4.00 F
strict passes: 52 / 739
```

Use `build_holdout_baseline_comparison.py` before making lift claims. Its
nearest-hub and IDW-hub baselines are evaluated on the exact model prediction
rows and fail by default if any baseline row is missing.

Row-locked baseline comparison results (run 2026-06-11, all 739 stations,
416,892 rows, 0 missing baseline rows; artifacts in
`weather_reconstruction_model/outputs/reports/comparisons/`):

```text
mean station MAE:  model 2.68 F | IDW (5 hubs) 4.99 F | nearest hub 5.58 F
model beats IDW at 588 / 739 stations (80%)
model beats nearest hub at 631 / 739 stations (85%)
strict passes: model 52 | IDW 9 | nearest hub 8
```

Note: the local comparison run had no terrain feature file, so relief/slope
segment bands report "unknown"; elevation bands are populated.

## Independent C++ Re-Score (run 2026-07-06)

The row-locked model predictions were re-scored end to end by the C++
validator (`C++_Weather_Station_Proxy_Engine/validate_prediction_similarity.cpp`),
which reloads the exported actual/predicted values with the app engine's own
CSV loader and similarity code. This is a cross-language check on the holdout
metrics themselves: none of the numbers below depend on the Python metric
implementation.

```text
input: paloma_v1_tavg_holdout_baseline_comparison_row_locked_predictions.csv
stations re-scored: 739 (416,892 paired days)
mean station MAE:   2.6838 F   (Python master: 2.68 F)
median station MAE: 2.4855 F   (Python master: 2.49 F)
p90 station MAE:    3.9982 F   (Python master: 4.00 F)
hardest station:    9.6080 F   (Python master: 9.61 F)
strict passes:      52 / 739   (identical stations)
```

Per-station agreement between the two implementations: max MAE deviation
0.0024 F, max RMSE deviation 0.0026 F, max correlation deviation 0.0018,
consistent with the 4-decimal rounding in the exported CSV. The per-station
C++ results are committed at
`docs/evidence/paloma_v1_tavg_holdout_cpp_validation.csv`.

Two stations (USC00051743 COLLBRAN 1WSW, USC00052196 DELTA 3E) report a
correlation of exactly -1.0 in both implementations. Each has only 2 paired
holdout days, and two points always correlate at exactly plus or minus 1, so
this is a degenerate statistic rather than a model failure; their MAEs are
1.40 F and 0.98 F.

To reproduce:

```bash
cd weather_reconstruction_model/scripts
../../.venv/bin/python validate_predictions_with_cpp.py \
  ../outputs/reports/comparisons/paloma_v1_tavg_holdout_baseline_comparison_row_locked_predictions.csv \
  --predicted-column model_predicted_tavg
```

The older model-run contract example below remains useful history and schema
documentation. It should not be confused with the broader Paloma evidence above.

The first historical model run adapted to this contract was:

```text
option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain_offset_terrain_standard_random_forest
```

Historical evidence for that run came from an earlier out-of-sample station
validation subset:

```text
validation stations: 86
test rows: 40,890
mean MAE: about 1.86 F
mean RMSE: about 2.47 F
```

The support-score map is still a prototype until this contract contains
calibrated confidence outputs.

## Folder Layout

Each model run lives under:

```text
weather_reconstruction_model/model_runs/<model_run_id>/
  model_manifest.json
  feature_schema.json
  station_metrics.csv
  validation_predictions.csv
  calibration_points.csv
  confidence_grid.json
```

`<model_run_id>` should be a stable, filesystem-safe identifier. Prefer the
same slug used in prediction and report filenames.

## Required Files

### `model_manifest.json`

Describes the run, its provenance, and how its files were produced.

Required fields:

```json
{
  "modelRunId": "option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain_offset_terrain_standard_random_forest",
  "modelFamily": "random_forest",
  "predictionTarget": "daily_tavg_f",
  "trainingMode": "station_holdout",
  "validationMode": "out_of_sample_station_holdout",
  "createdAt": "2026-05-24",
  "sourceFiles": {
    "trainingTable": "weather_reconstruction_model/outputs/general_training_tables/...",
    "stationMetrics": "weather_reconstruction_model/outputs/reports/...",
    "validationPredictions": "weather_reconstruction_model/outputs/predictions/..."
  },
  "summaryMetrics": {
    "validationStationCount": 86,
    "testRows": 40890,
    "meanMaeF": 1.86,
    "meanRmseF": 2.47
  }
}
```

`validationMode` must describe out-of-sample evidence. A fully trained
mega-model can be used for production predictions, but it must not be used to
prove its own confidence.

### `feature_schema.json`

Defines model inputs in order, including units and nullable behavior.

Required fields:

```json
{
  "featureSchemaVersion": "feature-schema-v1",
  "targetColumn": "target_tavg",
  "features": [
    {
      "name": "hub_1_tavg",
      "type": "float",
      "unit": "F",
      "required": true
    }
  ]
}
```

### `station_metrics.csv`

Station-level validation summary. Minimum columns:

```csv
target_station_id,target_name,test_rows,mae,rmse,correlation
```

These values are calibration evidence and should come from held-out stations or
another out-of-sample validation design.

### `validation_predictions.csv`

Daily held-out predictions. Minimum columns:

```csv
date,target_station_id,target_name,actual_tavg,predicted_tavg,error
```

`error` is `actual_tavg - predicted_tavg`.

### `calibration_points.csv`

Point-level calibration training data. Minimum columns:

```csv
latitude,longitude,target_station_id,observed_mae_f,observed_rmse_f,observed_correlation,support_score
```

Additional explanatory features are encouraged, such as nearest-station
distance, hub density, elevation mismatch, terrain complexity, and validation
neighbor counts.

### `confidence_grid.json`

Frontend-ready calibrated confidence surface. Minimum shape:

```json
{
  "modelRunId": "option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain_offset_terrain_standard_random_forest",
  "scoreVersion": "calibrated-confidence-v1",
  "bounds": {
    "latMin": 31.0,
    "latMax": 43.0,
    "lonMin": -115.0,
    "lonMax": -102.0
  },
  "points": [
    {
      "latitude": 39.75,
      "longitude": -105.0,
      "confidence": 82.0,
      "expectedMaeF": 1.8,
      "label": "High confidence"
    }
  ]
}
```

## Calibration Rule

Confidence must be calibrated from validation error, not from the same fully
trained model's in-sample fit. The intended path is:

```text
station/spatial holdout predictions
-> station_metrics.csv and validation_predictions.csv
-> calibration_points.csv
-> calibrated confidence function
-> confidence_grid.json
```

The original support score can remain a component or prior, but it should not be
renamed to model confidence until calibrated outputs exist.
