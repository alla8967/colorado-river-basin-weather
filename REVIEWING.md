# Reviewing This Project

This repository is being published for critique of both the local application
architecture and the research workflow behind it.

## Most Useful Feedback

- Overall project organization: can a reviewer understand the app lane, C++
  engine lane, ML/reconstruction lane, and remote-run lane quickly?
- Backend/frontend maintainability: are responsibilities split clearly enough
  across FastAPI services, static JavaScript modules, and app state?
- C++ engine design: is the station scoring core understandable, testable, and
  reasonably separated from the persistent server wrapper?
- Data pipeline clarity: are NOAA preprocessing inputs, generated app-ready
  CSVs, terrain features, and model-run artifacts documented well enough?
- Modeling methodology: are the validation design, holdout workflow, feature
  choices, confidence/support surface, and failure diagnostics credible?
- Test strategy: does `make check` cover the right fast path, and what tests
  would most improve confidence without requiring large local data?

## Known Context

- The public repo intentionally excludes large/generated NOAA, DEM, model-run,
  cache, archive, and app-ready data artifacts.
- The tiny fixtures under `tests/fixtures/` are for clone-friendly validation,
  not scientific reproduction.
- `ml_reconstruction/weather_reconstruction_model/scripts/` is a research
  command layer. It has shared helpers and tests, but not every script is
  productionized.
- `cpp_scoring_engine/C++_Weather_Station_Proxy_Engine/` keeps a historical
  folder name.
- Alpine Slurm scripts are included for review, but active scratch runs should
  be treated as external runtime state, not source truth.

## Fast Local Check

```bash
python -m pip install -e ".[dev]"
make check
```

For the heavier research-script suite:

```bash
PYTHON=.venv/bin/python make test-python
```
