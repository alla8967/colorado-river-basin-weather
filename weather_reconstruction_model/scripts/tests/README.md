# Reconstruction Script Tests

This folder contains the Python tests for shared helpers, pipeline contracts,
and command-line script behavior.

## What They Cover

- common CSV, JSON, metric, reporting, confidence, and model-run helpers,
- station selection and training-table helper behavior,
- Paloma variable-aware table, trainer, holdout, and remote pipeline contracts,
- reliability-surface and confidence-point artifact generation with temporary
  fixtures.

Run them from the project root after installing dev dependencies:

```bash
PYTHON=.venv/bin/python make test-python
```

