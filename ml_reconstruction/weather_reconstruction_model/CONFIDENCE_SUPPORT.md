# Confidence Support Score Contract

This contract defines the first version of the confidence/support result used by
the click-to-estimate map workflow.

The score answers this question:

```text
How well supported is this clicked point by nearby weather stations, terrain
similarity, and prior model validation evidence?
```

It does not answer this stronger question yet:

```text
What is the formal probability that the model prediction is correct?
```

The confidence score is an explainable support index. It should be calibrated
against holdout errors later, but version 1 should stay transparent and
conservative.

## Output Shape

Every point evaluation should return a result shaped like this:

```json
{
  "scoreVersion": "confidence-support-v1",
  "modelReference": "optional-model-or-run-id",
  "status": "ok",
  "latitude": 39.75,
  "longitude": -105.0,
  "score": 82.4,
  "label": "High support",
  "components": {
    "stationCoverage": 91.0,
    "hubSupport": 84.0,
    "dataQuality": 77.0,
    "elevationMatch": 88.0,
    "terrainSimilarity": 74.0,
    "terrainComplexity": 69.0,
    "validationEvidence": 80.0,
    "extrapolationRisk": 92.0
  },
  "reasons": [
    "Nearest station is 4.2 km away.",
    "Six hub stations are within 100 km.",
    "Nearby stations have similar elevation."
  ],
  "warnings": [
    "Terrain is moderately complex, so nearby station support matters more."
  ],
  "nearestStations": [
    {
      "stationId": "USC00052223",
      "stationName": "DENVER WATER DEPT",
      "stationRole": "target",
      "distanceKm": 4.2,
      "elevationDifferenceM": 82.0
    }
  ]
}
```

`scoreVersion` identifies the scoring rules and thresholds. `modelReference`
identifies the model, experiment, or validation run that supplied model-specific
evidence. Either value can change independently.

## Component Scores

All component scores use the same scale:

```text
0   very weak support
50  moderate support
100 very strong support
```

The first score version should include these components:

- `stationCoverage`: nearby target/weather station distance and density.
- `hubSupport`: nearby long-record hub distance and density.
- `dataQuality`: record length, recency, and completeness of useful neighbors.
- `elevationMatch`: elevation agreement between the clicked point and nearby stations.
- `terrainSimilarity`: similarity between clicked-point terrain and nearby stations.
- `terrainComplexity`: whether local terrain is simple enough for broader station support.
- `validationEvidence`: nearby holdout/model validation performance.
- `extrapolationRisk`: whether the point sits outside the known station/terrain support.

## Default Weights

Initial weights should sum to 1.0:

```text
stationCoverage      0.20
hubSupport           0.15
dataQuality          0.10
elevationMatch       0.15
terrainSimilarity    0.15
terrainComplexity    0.10
validationEvidence   0.10
extrapolationRisk    0.05
```

The total score is:

```text
weighted average of available component scores
```

If a component cannot be calculated yet, omit it from the weighted average and
add a warning. Do not silently treat missing evidence as strong evidence.

## Reusability Contract

The confidence scorer must remain separate from the learning model.

Learning-model code should answer:

```text
What temperature do we predict?
```

Confidence-support code should answer:

```text
How well supported is this prediction location by data, terrain, and validation evidence?
```

Future models should adapt through loaders and configuration, not by rewriting
the scoring core. The pure scorer should receive normalized in-memory objects:

```text
SupportPoint
SupportStation
TerrainFeatures
ValidationEvidence
ConfidenceSupportConfig
```

Any future command-line executable should load model-specific files, convert
them into these generic objects, pass a `ConfidenceSupportConfig`, and write the
standard result shape. This keeps the same confidence evaluator usable with a
random forest, gradient boosting model, regression model, ensemble, or future
calibrated uncertainty model.

Model-specific assumptions belong in:

```text
ConfidenceSupportConfig
loader/adaptor scripts
ValidationEvidence fields
```

They should not be hardcoded into the map, backend endpoint, or component
scoring functions.

## Labels

Use these label bands:

```text
85-100  Very high support
70-84   High support
50-69   Moderate support
30-49   Low support
0-29    Very low support
```

## Design Rules

- The score must produce reasons, not just a number.
- Terrain complexity should not automatically punish mountain locations.
- Rugged locations should require closer and more terrain-similar station support.
- The score should be conservative near sparse stations, unusual elevation, or weak validation evidence.
- The clicked-point result should be computed directly, even if the map also shows sampled confidence points.
- Map-wide visualization should be treated as an approximate confidence surface, not an exact value for every possible coordinate.
