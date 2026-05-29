# ML Reconstruction

This folder contains the data-prep, machine-learning, confidence-support, and
remote-run lanes.

## Contents

| Path | Purpose |
| --- | --- |
| `weather_reconstruction_model/` | Python reconstruction scripts, shared helpers, tests, outputs, and model-run artifacts. |
| `NOAA_Inventory_Sort/` | NOAA inventory filtering inputs and app-ready station CSVs. |
| `terrain_data/` | DEM-derived terrain feature inputs when present. |
| `remote_jobs/` | Alpine Slurm scripts and retrieval helpers. |
| `weather_reconstruction_artifacts/` | Ignored archive/scratch shelf for old outputs, snapshots, NOAA years, and DEM tiles. |

## Common Commands

From the project root:

```bash
PYTHON=.venv/bin/python make test-python
.venv/bin/python ml_reconstruction/weather_reconstruction_model/scripts/check_remote_environment.py
```

Keep generated caches, outputs, model runs, archives, and terrain rasters out of
source commits unless a small artifact is intentionally curated.

Remote transfer and run details live in:

```text
remote_jobs/REMOTE_RUN_MANIFEST.md
remote_jobs/REMOTE_TRANSFER_CHECKLIST.md
```
