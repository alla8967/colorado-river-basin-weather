# V1 Release Checklist

Use this checklist before calling the local station proxy finder a polished v1.

## Product Boundary

- The primary v1 surface is the local browser app served by FastAPI.
- The C++ station proxy engine and persistent server are part of the product.
- `ml_reconstruction/weather_reconstruction_model/model_runs/` is a generated artifact shelf, but
  the active model-run folder is part of the v1 app evidence path because the
  Model Support tab reads its confidence grid through FastAPI.
- `ml_reconstruction/weather_reconstruction_model/outputs/` is working research output. Keep only
  current evidence locally; do not treat it as source.
- `ml_reconstruction/weather_reconstruction_artifacts/` is an archive/scratch shelf. Keep it out
  of git and avoid making app behavior depend on it.

## Required Checks

Run from the project root:

```bash
make check
```

For model or confidence-support changes, also run:

```bash
PYTHON=.venv/bin/python make test-python
```

For model-run artifact or confidence-grid changes, run focused tests:

```bash
.venv/bin/python -m pytest \
  ml_reconstruction/weather_reconstruction_model/scripts/tests/test_model_runs.py \
  ml_reconstruction/weather_reconstruction_model/scripts/tests/test_build_confidence_points.py
```

## Manual App Smoke Test

1. Start the backend:

   ```bash
   make run-backend
   ```

2. Open:

   ```text
   http://127.0.0.1:8000/
   ```

3. Confirm:

- the engine status becomes ready after the C++ server loads the NOAA CSVs;
- Proxy Finder can analyze a known location such as `39.75, -105.0`;
- Model Support loads the calibrated confidence layer from
  `/model-runs/current/confidence-grid`;
- clicked-point support scoring returns a result from `/analyze-confidence`;
- unavailable-engine and unavailable-confidence states are readable.

## Artifact Check

Before staging or handing off:

```bash
git status --short
git status --ignored --short
```

Confirm that staged files do not include:

- generated NOAA daily CSVs;
- Python environments or caches;
- compiled C++ binaries;
- `ml_reconstruction/weather_reconstruction_model/outputs/`;
- `ml_reconstruction/weather_reconstruction_model/cache/`;
- `ml_reconstruction/weather_reconstruction_model/model_runs/`;
- `ml_reconstruction/weather_reconstruction_artifacts/`;
- DEM tiles or processed terrain rasters.

## Alpine Boundary

Do not sync, rename, or reorganize the Alpine scratch copy under:

```text
/scratch/alpine/$USER/crb_weather_runs/current
```

until active or pending jobs are complete and a new sync is intentional.
