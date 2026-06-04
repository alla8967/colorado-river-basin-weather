# Model Run Artifact Contract

This contract gives each trained reconstruction model a stable folder shape so
calibration, confidence grids, backend endpoints, and frontend maps can all read
the same evidence without knowing which script produced it.

The first model run to adapt should be:

```text
option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain_offset_terrain_standard_random_forest
```

Current evidence for that run comes from out-of-sample station validation:

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
