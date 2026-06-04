# Weather Reconstruction Model

This folder contains the experimental temperature reconstruction workflow.

The goal is to test whether nearby long-record weather stations can be used to reconstruct the daily average temperature history of a target station.

In plain English:

```text
Pretend we do not know a target station's temperature record.
Use nearby hub stations to estimate that record.
Compare the estimate against the real observed target station record.
Measure how close the reconstruction was.
```

This is a validation sandbox for the larger project goal: eventually letting a user click a point on the map and receive an estimated local climate history for that exact point.

---

## Folder Layout

```text
weather_reconstruction_model/
  README.md

  scripts/
    config.py
    count_stations.py
    build_training_table.py
    train_temperature_model.py
    batch_validate_models.py
    analyze_batch_results.py
    build_general_training_table.py
    train_general_temperature_model.py
    build_station_terrain_features.py
    validate_dem_alignment.py
    run_station_validation.py
    run_reference_cases.py
    common/
      csv_utils.py
      geo_utils.py
      metrics.py
      number_utils.py
    pipeline/
      station_selection.py
      training_tables.py
    tests/
      test_common_utils.py
      test_pipeline_utils.py

  outputs/
    training_tables/
    predictions/
    validation/
    reports/
    general_training_tables/
```

### `scripts/`

These are the Python tools that build, train, and validate the reconstruction model.

### `scripts/common/`

Small reusable helper modules:

```text
csv_utils.py      CSV reading and writing helpers
geo_utils.py      distance calculations
metrics.py        MAE, RMSE, correlation, and metric summaries
number_utils.py   safe numeric parsing
```

These exist so scripts do not carry separate copies of the same helper functions.

### `scripts/pipeline/`

Shared model-pipeline logic:

```text
station_selection.py   scores, filters, and ranks eligible hub stations
training_tables.py     builds shared-date target/hub training rows
```

These modules contain the core behavior that should stay consistent between the
one-station workflow and the batch workflow.

### `scripts/tests/`

Small dependency-free unit tests for the shared helper and pipeline modules.

### `outputs/`

These are generated CSV files. They are useful for inspection and validation, but they are outputs rather than source code.

### `outputs/general_training_tables/`

These are many-station training tables. They are meant for the next model phase, where one model can learn from many target stations instead of learning one separate formula per station.

---

## Important Terms

### Target Station

The station we are pretending to reconstruct.

Example:

```text
USC00052223 - DENVER WATER DEPT
```

During validation, the target station still has real observations. We use those real observations only to check whether the reconstruction worked.

### Hub Station

A long-record station that can help predict the target station.

Hub stations are selected because they have:

```text
longer observation records
TMAX and TMIN data
enough overlap with the target station
reasonable elevation similarity
```

### Training Table

A CSV where each row is one date shared by the target station and all selected hub stations.

It looks like this:

```csv
date,target_station_id,target_tavg,hub_1_station_id,hub_1_tavg,hub_2_station_id,hub_2_tavg
2016-01-02,USC00052223,22.46,USW00023062,21.02,USC00054452,25.52
```

This is the table the regression model learns from.

### Prediction File

A CSV that compares the real target temperature against the model's predicted temperature.

It looks like this:

```csv
date,target_station_id,actual_tavg,predicted_tavg,error
2024-01-01,USC00052223,28.49,29.12,-0.63
```

### Validation Station CSVs

These are special CSVs created so the existing C++ engine can independently score the prediction.

There are two files:

```text
USC00052223_5_hubs_actual.csv
USC00052223_5_hubs_predicted.csv
```

The Python model creates them. The C++ engine reads them as if they were two weather stations and calculates similarity between them.

This is useful because it means:

```text
Python predicts.
C++ independently scores.
```

---

## Current Model

The current model is ordinary linear regression.

It learns a formula like this:

```text
target_tavg =
    intercept
  + weight_1 * hub_1_tavg
  + weight_2 * hub_2_tavg
  + weight_3 * hub_3_tavg
  + weight_4 * hub_4_tavg
  + weight_5 * hub_5_tavg
```

The model is intentionally simple.

That is a feature, not a bug. A simple model is easier to inspect, validate, and explain. More complex models should eventually be tested against this baseline.

---

## Pipeline Structure

The cleaned pipeline has two layers:

```text
Command-line scripts
→ parse arguments, load files, print reports

Shared modules
→ hold reusable math, hub selection, and training-table logic
```

The most important shared pieces are:

### Hub Selection

Implemented in:

```text
weather_reconstruction_model/scripts/pipeline/station_selection.py
```

The selection process:

```text
1. Calculate each hub's distance from the target station.
2. Calculate how many dates overlap with the target station.
3. Calculate overlap percentage.
4. Calculate elevation difference.
5. Reject hubs with too little overlap, too few shared days, or too much elevation difference.
6. Score eligible hubs for physical representativeness.
7. Select the strongest physically representative hubs.
```

The physical representativeness score is intentionally practical rather than
perfect. It blends distance, elevation similarity, terrain-position similarity,
local-relief similarity, slope similarity, aspect similarity, and overlap
quality. Missing terrain values receive neutral component scores so older or
partial data can still run, but terrain-aware tables will prefer stations that
are physically more like the target instead of simply nearest.

When a pairwise historical skill file is available, selection also uses same-date
station agreement calculated only through the training window. These features
include overlap days, correlation, MAE, RMSE, mean bias, winter/summer MAE, and
an aggregate pair skill score. This lets the pipeline prefer stations that have
actually tracked the target well, not only stations that look similar on a map.

The key object is `ScoredHub`, which records:

```text
station ID
station name
distance from target
elevation difference
overlap days
overlap percentage
selection score
physical similarity score
component similarity scores
pairwise historical skill metrics
usable record period
```

### Shared-Date Training Tables

Implemented in:

```text
weather_reconstruction_model/scripts/pipeline/training_tables.py
```

This module finds the dates where the target station and every selected hub
all have valid daily average temperature data. Each row becomes one training
example.

Both `build_training_table.py` and `batch_validate_models.py` use this shared
logic, so the one-station and batch workflows are now using the same table rules.

---

## Current Default Rules

The shared settings live in:

```text
weather_reconstruction_model/scripts/config.py
```

Current defaults:

```text
Default target station: USC00052223
Default hub count: 5
Train through year: 2023
Test from year: 2024
Regression alpha: 0.0
```

Current hub eligibility rules:

```text
Minimum target overlap: 90%
Minimum overlap days: 1000
Maximum elevation difference: 500 m
```

Current batch validation rules:

```text
Minimum shared days: 1000
Minimum test days: 365
```

Proxy/batch development pass threshold:

```text
MAE <= 2.5 F
RMSE <= 3.5 F
correlation >= 0.95
```

Proxy/batch development borderline threshold:

```text
MAE <= 3.5 F
RMSE <= 4.5 F
correlation >= 0.90
```

These thresholds are not final scientific claims. They are working rules for
sorting strong, borderline, and weak results in the older per-station proxy
validation scripts.

Machine-learning reconstruction goal:

```text
At least 80% of withheld-station test cases should achieve:
MAE <= 1.5 F
RMSE <= 2.0 F
correlation >= 0.985
```

---

## How To Run The One-Station Pipeline

Run commands from the main project folder:

```bash
cd "/Users/alexanderlangley-valey/Desktop/Colorado River Basin Project"
```

Use the project virtual environment when available:

```bash
.venv/bin/python ...
```

Most reconstruction scripts use only the Python standard library. The terrain
scripts need Pillow and NumPy because they read DEM GeoTIFF files.

Then run:

```bash
.venv/bin/python weather_reconstruction_model/scripts/run_station_validation.py USC00052223
```

That one command does the full workflow:

```text
1. Build shared-date training table
2. Train the regression model
3. Export prediction CSV
4. Export actual/predicted validation station CSVs
5. Build the C++ validator
6. Run C++ similarity validation
```

To skip the C++ validation step:

```bash
.venv/bin/python weather_reconstruction_model/scripts/run_station_validation.py USC00052223 --skip-cpp
```

To test a different station:

```bash
.venv/bin/python weather_reconstruction_model/scripts/run_station_validation.py USC00025494
```

To change the number of hubs:

```bash
.venv/bin/python weather_reconstruction_model/scripts/run_station_validation.py USC00052223 --hub-count 8
```

---

## How To Run The Steps Manually

The wrapper above is easiest, but the individual steps can also be run manually.

### 1. Build A Training Table

```bash
.venv/bin/python weather_reconstruction_model/scripts/build_training_table.py USC00052223 5
```

Output:

```text
weather_reconstruction_model/outputs/training_tables/USC00052223_5_hubs.csv
```

### 2. Train The Model

```bash
.venv/bin/python weather_reconstruction_model/scripts/train_temperature_model.py weather_reconstruction_model/outputs/training_tables/USC00052223_5_hubs.csv
```

Outputs:

```text
weather_reconstruction_model/outputs/predictions/USC00052223_5_hubs_predictions.csv
weather_reconstruction_model/outputs/validation/USC00052223_5_hubs_actual.csv
weather_reconstruction_model/outputs/validation/USC00052223_5_hubs_predicted.csv
```

### 3. Build The C++ Validator

```bash
make validate-prediction
```

### 4. Run Independent C++ Validation

```bash
./validate_prediction_similarity \
  weather_reconstruction_model/outputs/validation/USC00052223_5_hubs_actual.csv \
  weather_reconstruction_model/outputs/validation/USC00052223_5_hubs_predicted.csv
```

---

## What The C++ Validator Does

The C++ validator is:

```text
C++_Weather_Station_Proxy_Engine/validate_prediction_similarity.cpp
```

It is built with:

```bash
make validate-prediction
```

It compares two generated station CSVs:

```text
actual station CSV
predicted station CSV
```

Then it reports:

```text
paired days compared
daily correlation
daily MAD / MAE
daily RMSE
compared date range
```

### Why This Exists

The Python model does the regression.

The C++ validator does not trust the Python model's reported metrics. Instead, it reloads the exported actual and predicted CSV files using the existing C++ station-loading code, then runs the existing C++ daily similarity function:

```text
calculate_daily_tavg_similarity()
```

This gives us an independent check.

In plain English:

```text
Python makes the prediction.
C++ judges the prediction.
```

That separation is useful because a bug in the Python metric reporting is less likely to survive an independent C++ check.

### What It Proves

If Python reports:

```text
MAE: 1.48 F
RMSE: 1.88 F
correlation: 0.995
```

and C++ reports almost the same values, then we know:

```text
the exported prediction file matches the reported Python metrics
the actual and predicted dates are pairing correctly
the MAE/RMSE/correlation calculations agree across two code paths
```

### What It Does Not Prove

The C++ validator does not prove that the model is scientifically complete.

It does not check:

```text
whether the selected hub stations are ideal
whether terrain/geography is adequately represented
whether the model generalizes to every station
whether the target station data itself is perfect
```

It only answers this narrower question:

```text
Given these actual and predicted daily temperatures,
how similar are they according to the C++ engine's existing scoring logic?
```

That is still very useful. It is a validation guardrail, not the entire scientific argument.

### Why The Validation CSVs Use TMAX And TMIN

The C++ app-ready temperature loader expects files shaped like this:

```csv
station_id,station_name,latitude,longitude,elevation,date,tmax,tmin
```

The reconstruction model predicts daily average temperature, or `TAVG`.

To make predicted TAVG fit the existing C++ loader, the Python script writes:

```text
tmax = tavg
tmin = tavg
```

Then the C++ loader calculates:

```text
tavg = (tmax + tmin) / 2
```

Since both values are the same, the computed C++ `tavg` is exactly the predicted value.

This is a small adapter trick. It avoids creating a separate C++ file format just for predictions.

---

## How To Run Batch Validation

Batch validation runs the same reconstruction test across many target stations.

Example:

```bash
.venv/bin/python weather_reconstruction_model/scripts/batch_validate_models.py --limit 25
```

Output:

```text
weather_reconstruction_model/outputs/reports/batch_25_targets_5_hubs.csv
```

The batch report includes:

```text
target station ID
target name
target coordinates
target elevation
selected hub stations
shared days
train days
test days
MAE
RMSE
correlation
nearest hub distance
farthest hub distance
average elevation difference
PASS / BORDERLINE / FAIL status
```

This is the most important script for judging whether the method works broadly, not just for one station.

---

## How To Analyze Batch Results

After running a batch validation, summarize the results with:

```bash
.venv/bin/python weather_reconstruction_model/scripts/analyze_batch_results.py weather_reconstruction_model/outputs/reports/batch_100_targets_5_hubs.csv --write-markdown
```

This prints:

```text
current PASS / BORDERLINE / FAIL counts
strict end-goal pass rate
MAE/RMSE/correlation summaries
failure reasons
worst stations by MAE
simple error relationships
```

The strict end-goal check currently uses:

```text
MAE <= 1.5 F
RMSE <= 2.0 F
correlation >= 0.985
```

The `--write-markdown` flag also creates a compact report next to the batch CSV:

```text
weather_reconstruction_model/outputs/reports/batch_100_targets_5_hubs_analysis.md
```

This script is meant to answer:

```text
How often does the model meet the long-term goal?
Which stations are worst?
Are errors associated with distance, elevation, or data coverage?
```

---

## How To Build A General Training Table

The one-station model learns one formula for one target station.

The general training table is different. It combines many target stations into one larger CSV so a future model can learn broader patterns across stations.

Run:

```bash
.venv/bin/python weather_reconstruction_model/scripts/build_general_training_table.py --limit 25
```

Output:

```text
weather_reconstruction_model/outputs/general_training_tables/general_25_targets_5_hubs.csv
```

The exact target count in the filename may be lower than the limit if some stations fail the overlap, coverage, or elevation filters.

Each row represents:

```text
one target station
one shared date
the target station's observed daily average temperature
the selected hub stations' daily average temperatures
date and season features
target and hub metadata
distance, elevation difference, and coordinate offsets
target and hub DEM-derived terrain features when available
```

This is the bridge from the current per-station baseline toward a broader model that can eventually learn from many places at once.

---

## How To Train The General Model

After building a general training table, train the first many-station regression model with:

```bash
.venv/bin/python weather_reconstruction_model/scripts/train_general_temperature_model.py weather_reconstruction_model/outputs/general_training_tables/general_23_targets_5_hubs.csv
```

The script uses:

```text
hub temperatures
seasonality
target latitude, longitude, and elevation
hub distance
hub elevation difference
hub latitude and longitude offsets
hub overlap percentage
DEM-derived terrain features when they are present in the training table
```

It compares two models:

```text
Average of hubs
General linear regression
```

The first successful starter run used 23 target stations and produced:

```text
Average of hubs test MAE: 3.64 F
General linear regression test MAE: 2.26 F
General linear regression test RMSE: 2.96 F
General linear regression test correlation: 0.988
```

Outputs:

```text
weather_reconstruction_model/outputs/predictions/general_23_targets_5_hubs_terrain_general_predictions.csv
weather_reconstruction_model/outputs/reports/general_23_targets_5_hubs_terrain_general_station_metrics.csv
```

This is not the final clicked-point model yet. It is the first broader model that learns from many stations at once.

To train the same table while deliberately ignoring terrain features, use:

```bash
.venv/bin/python weather_reconstruction_model/scripts/train_general_temperature_model.py weather_reconstruction_model/outputs/general_training_tables/general_23_targets_5_hubs.csv --exclude-terrain
```

That writes separate comparison files:

```text
weather_reconstruction_model/outputs/predictions/general_23_targets_5_hubs_no_terrain_general_predictions.csv
weather_reconstruction_model/outputs/reports/general_23_targets_5_hubs_no_terrain_general_station_metrics.csv
```

This side-by-side mode is meant to answer whether terrain features are improving the model, not just whether they can be loaded.

---

## How To Train Tree-Based Models

The first nonlinear model script is:

```text
weather_reconstruction_model/scripts/train_tree_temperature_model.py
```

It trains two tabular machine learning models from the same general training table:

```text
RandomForestRegressor
HistGradientBoostingRegressor
```

Run:

```bash
.venv/bin/python weather_reconstruction_model/scripts/train_tree_temperature_model.py weather_reconstruction_model/outputs/general_training_tables/general_23_targets_5_hubs.csv
```

To compare the same table while ignoring terrain features:

```bash
.venv/bin/python weather_reconstruction_model/scripts/train_tree_temperature_model.py weather_reconstruction_model/outputs/general_training_tables/general_23_targets_5_hubs.csv --exclude-terrain
```

To test the dynamic daily-offset idea, build a fresh general training table and
then add:

```bash
--predict-offset-from-baseline
```

That mode trains the model to predict the target station's daily departure from
the selected-hub regional baseline, then adds the baseline back before scoring
the final daily average temperature. This keeps the existing direct-temperature
model intact while giving us a clean side-by-side test of whether local daily
offsets are easier to learn.

The first 23-target comparison showed that tree models improved the general
model baseline:

```text
Linear regression test MAE:       about 2.26 F
Random forest test MAE:           about 2.12 F
Hist gradient boosting test MAE:  about 2.12 F
```

Terrain features were successfully included, but they did not yet create a
meaningful aggregate improvement in this first tree-model run. That means the
current win is mostly from nonlinear tabular learning rather than terrain
features alone.

The later 97-target table added engineered terrain relationship features such as:

```text
target/hub DEM elevation difference
target/hub slope difference
target/hub local relief difference
target/hub terrain position difference
aspect similarity
distance × elevation difference
season × elevation difference
season × terrain position difference
```

Those features improved the terrain-aware linear model:

```text
Linear no-terrain MAE:              about 2.89 F
Linear raw-terrain MAE:             about 2.52 F
Linear engineered-terrain MAE:      about 2.43 F
Random forest terrain MAE:          about 2.18 F
Hist gradient boosting engineered:  about 2.25 F
```

So engineered terrain relationships are useful, but the random forest remains
the strongest model in the current experiments.

The general table builder can also add nearby non-hub target stations as extra
temperature witnesses. This is useful for the machine-learning path because the
model is no longer restricted to only long-record proxy hubs:

```bash
.venv/bin/python weather_reconstruction_model/scripts/build_general_training_table.py --limit 10 --hub-count 5 --target-neighbor-count 10
```

That keeps 5 classic hub stations per target and adds 10 nearby target-neighbor
stations as additional predictor columns. The output filename includes the
extra predictor count:

```text
weather_reconstruction_model/outputs/general_training_tables/general_8_targets_5_hubs_10_target_neighbors.csv
```

Daily temperature data can be cached in SQLite with:

```bash
.venv/bin/python weather_reconstruction_model/scripts/build_weather_cache.py
```

That creates a local derived cache file:

```text
weather_reconstruction_model/cache/weather_data.sqlite
```

The general table builder can then read daily data from the cache:

```bash
.venv/bin/python weather_reconstruction_model/scripts/build_general_training_table.py --limit 25 --hub-count 5 --target-neighbor-count 10 --use-cache
```

The cache is most useful when a run needs a narrow set of station daily series.
For expanded target-neighbor experiments, the current selection algorithm still
checks date coverage across the full target-neighbor pool, so the cache is
functionally useful but not yet a guaranteed speedup for that mode.

Target-neighbor selection uses a geographic prefilter before the expensive
overlap checks:

```bash
.venv/bin/python weather_reconstruction_model/scripts/build_general_training_table.py \
  --limit 25 \
  --hub-count 5 \
  --target-neighbor-count 10 \
  --target-neighbor-prefilter-count 100 \
  --target-neighbor-max-distance-km 300
```

The default prefilter considers the nearest 100 target-neighbor candidates within
300 km, then applies the existing overlap and elevation rules. Use `0` for either
prefilter option to disable that specific limit.

Tree-model diagnostics can be turned into a readable HTML report with:

```bash
.venv/bin/python weather_reconstruction_model/scripts/build_diagnostics_report.py
```

By default, that command reads the latest 97-target standard random-forest
prediction files and writes:

```text
weather_reconstruction_model/outputs/reports/diagnostics/general_97_targets_5_hubs_terrain_standard_random_forest_diagnostics.html
```

The diagnostics report summarizes strict pass count, best and worst stations,
mean model bias, seasonal error spread, hub distance, elevation differences, and
target terrain context. It is meant to help answer why a model failed, not just
whether it failed.

Two station-metrics reports can be compared directly with:

```bash
.venv/bin/python weather_reconstruction_model/scripts/build_model_comparison_report.py \
  --baseline weather_reconstruction_model/outputs/reports/general_23_targets_5_hubs_terrain_quick_random_forest_station_metrics.csv \
  --candidate weather_reconstruction_model/outputs/reports/general_22_targets_5_hubs_10_target_neighbors_terrain_quick_random_forest_station_metrics.csv \
  --baseline-label "5 hubs" \
  --candidate-label "5 hubs + 10 target-neighbors" \
  --output-stem general_25_target_hub_only_vs_target_neighbors_quick_rf
```

That writes both CSV and HTML comparison reports under:

```text
weather_reconstruction_model/outputs/reports/comparisons/
```

The older per-station batch validation script also supports the SQLite cache:

```bash
.venv/bin/python weather_reconstruction_model/scripts/batch_validate_models.py --limit 25 --hub-count 5 --use-cache
```

In that path, target daily rows are loaded by station ID. By default, cache mode
does not prefilter hubs, so it should preserve the same hub-selection behavior as
the CSV path while still avoiding repeated target CSV scans.

After confirming cache-mode equivalence, you can test the faster geographic
prefilter path:

```bash
.venv/bin/python weather_reconstruction_model/scripts/batch_validate_models.py \
  --limit 25 \
  --hub-count 5 \
  --use-cache \
  --hub-prefilter-count 100 \
  --hub-max-distance-km 500
```

Only the prefiltered hub candidates have date coverage loaded first, and full
hub temperature series are loaded only after hubs are selected for a target. If
the prefilter is too strict for a target, the script automatically retries with
the full hub list before marking that target as failed.

---

## How To Build Station Terrain Features

After downloading DEM GeoTIFF files into:

```text
Raw_DEM/
```

build terrain features for all target and hub stations with the project virtual environment:

```bash
.venv/bin/python weather_reconstruction_model/scripts/build_station_terrain_features.py
```

Output:

```text
terrain_data/processed/station_terrain_features.csv
```

The terrain feature table includes:

```text
DEM elevation
DEM minus NOAA station elevation
slope
aspect
aspect sine/cosine
local relief
terrain position index
QA status columns
```

The first full run produced:

```text
Rows written: 1246
Successful terrain rows: 1246
Missing/problem rows: 0
```

The `elevation_qa_status` column is important. The corrected DEM sampler now agrees closely with NOAA elevation for most stations:

```text
Median absolute DEM-vs-NOAA elevation difference: 4.39 m
Mean absolute DEM-vs-NOAA elevation difference: 23.45 m
Within 25 m: 78.3%
Within 50 m: 87.6%
Within 100 m: 95.2%
```

Large remaining differences should still be reviewed, but the earlier broad mismatch was caused by a tile-name interpretation bug. USGS DEM filenames use the tile's north edge: for example, `n34w112` covers roughly `33-34 N`, not `34-35 N`.

To validate the DEM tile/pixel alignment itself, run:

```bash
.venv/bin/python weather_reconstruction_model/scripts/validate_dem_alignment.py
```

Output:

```text
terrain_data/processed/dem_alignment_validation.csv
```

The first full alignment validation produced:

```text
ok: 1246
maximum coordinate round-trip error: 11.652 m
```

That means the station-to-tile and coordinate-to-pixel alignment appears sound for every target and hub station in the current candidate set.

---

## How To Interpret The Metrics

### MAE

Mean absolute error.

```text
MAE = average(abs(actual temperature - predicted temperature))
```

If MAE is `1.5 F`, then the model is off by about `1.5 F` on an average day.

Lower is better.

### RMSE

Root mean squared error.

```text
RMSE = sqrt(average((actual temperature - predicted temperature)^2))
```

RMSE punishes large misses more than MAE does.

If RMSE is much larger than MAE, the model probably has some bad individual days.

Lower is better.

### Correlation

Correlation measures whether the predicted and actual temperatures move together.

```text
1.0 = perfect movement together
0.0 = no relationship
-1.0 = perfect opposite movement
```

High correlation means the model understands the broad warm/cool pattern.

But high correlation alone is not enough. A model can move in the right direction and still be several degrees too warm or too cold.

Higher is better.

---

## Known Example Results

These examples are intentionally preserved as reference cases.

They are not meant to prove the whole method works. They are meant to keep one strong case and one weak case visible while the model evolves.

### Strong Case: Denver Water Department

Station:

```text
USC00052223 - DENVER WATER DEPT
```

Recent validation result:

```text
MAE: 1.4807 F
RMSE: 1.8801 F
correlation: 0.9951
```

This is a strong result. The model reconstructed unseen test dates very closely.

### Weak Case: Meteor Crater

Station:

```text
USC00025494 - METEOR CRATER
```

Recent validation result:

```text
MAE: 3.6020 F
RMSE: 4.5417 F
correlation: 0.9700
```

This is a useful failure case.

The model still tracks the broad temperature pattern, but the errors are too large. This suggests local geography and terrain context matter. Meteor Crater is one of the reasons future versions should include geospatial features such as elevation context, slope, aspect, and terrain position.

---

## How To Rerun Reference Cases

Use:

```bash
.venv/bin/python weather_reconstruction_model/scripts/run_reference_cases.py
```

This reruns the one-station validation workflow for:

```text
USC00052223 - DENVER WATER DEPT
USC00025494 - METEOR CRATER
```

Then it reads the generated prediction files and reports whether the results are still close to the expected baseline behavior.

The reference cases serve two purposes:

```text
Denver should remain a strong case.
Meteor Crater should remain a visible weak case until terrain-aware features improve it.
```

To check existing prediction files without rerunning the full pipeline:

```bash
.venv/bin/python weather_reconstruction_model/scripts/run_reference_cases.py --skip-rerun
```

To include the independent C++ validator for both reference cases:

```bash
.venv/bin/python weather_reconstruction_model/scripts/run_reference_cases.py --with-cpp
```

If a future model improves Meteor Crater, that is a good sign. The point is not to keep the weak case weak forever. The point is to keep the weakness visible so improvements are measurable.

---

## How To Run The Lightweight Tests

The shared helper and pipeline modules have small direct tests.

Run:

```bash
.venv/bin/python weather_reconstruction_model/scripts/tests/test_common_utils.py
.venv/bin/python weather_reconstruction_model/scripts/tests/test_pipeline_utils.py
```

These tests do not read the large NOAA files. They use tiny in-memory examples
to check the behavior of:

```text
CSV helpers
number parsing
distance calculations
MAE/RMSE/correlation calculations
hub scoring and eligibility rules
shared-date row construction
```

These tests are different from reference cases:

```text
unit tests       = small checks of individual helper/pipeline functions
reference cases  = end-to-end reconstruction checks on real station outputs
batch validation = broad performance check across many target stations
```

---

## Current Code Organization Notes

The project intentionally keeps command-line scripts thin enough for a human to
run and inspect, while moving reusable logic into shared modules.

Current division of responsibility:

```text
build_training_table.py
  loads one target's data, calls shared hub selection, writes one training table

batch_validate_models.py
  loads many targets, calls shared hub selection and shared table construction,
  trains and scores each target

build_general_training_table.py
  builds a many-target table for a future general model

common/
  owns low-level helpers that should not know about weather stations

pipeline/
  owns reusable weather-reconstruction logic
```

This is why scripts import from `common` and `pipeline`, but `common` and
`pipeline` should not import the command-line scripts.

---

## What This Model Can Claim Right Now

It is fair to say:

```text
This is a validated baseline temperature reconstruction model.
It can reconstruct some target stations very well using nearby hub stations.
It can identify where simple station-temperature regression is not enough.
```

It is not yet fair to say:

```text
This can reconstruct the climate of any clicked point.
This fully accounts for local geography.
This is a finished scientific climate reconstruction product.
```

The current model is a baseline. Its job is to establish what can be achieved with station temperatures alone before adding more complex geography.

---

## Intended Next Direction

The longer-term goal is point-scale climate reconstruction.

That means the user clicks a point on a map, and the program estimates local climate history using:

```text
nearby station observations
station metadata
distance
elevation
latitude and longitude offsets
seasonality
slope
aspect
ridge or valley position
other terrain features
```

The target validation goal is:

```text
At least 80% of withheld-station test cases should achieve:
MAE <= 1.5 F
RMSE <= 2.0 F
correlation >= 0.985
```

That target may change as more batch validation results come in.

The next practical modeling step is to join the DEM-derived station terrain
features into the general training table, then compare:

```text
general model without terrain features
vs.
general model with DEM elevation, slope, aspect, relief, and terrain position
```

That comparison should answer the next important research question:

```text
Does terrain context measurably improve reconstruction accuracy?
```

---

## Practical Notes

Run scripts from the project root unless you have a specific reason not to:

```bash
cd "/Users/alexanderlangley-valey/Desktop/Colorado River Basin Project"
```

Most reconstruction scripts use only the Python standard library. The DEM
terrain scripts require Pillow and NumPy. No `pandas` or `scikit-learn` is
required for the current baseline regression workflow.

The C++ validator is separate from the Python model on purpose:

```text
Python is used for fast experimentation.
C++ is used as an independent scoring check.
```

That separation makes the validation story stronger.
