# Website Backend And Frontend

This folder contains the local web product surface.

## Contents

| Path | Purpose |
| --- | --- |
| `station-proxy-backend/` | FastAPI backend, browser frontend, static assets, and frontend JavaScript. |

## Common Commands

From the project root:

```bash
make run-backend
make test-app-shell
```

Then open:

```text
http://127.0.0.1:8000/
```

The backend reads NOAA app data from `ml_reconstruction/NOAA_Inventory_Sort/`,
the C++ server from `cpp_scoring_engine/Station_Engine_Server/`, and active
model-run confidence grids from
`ml_reconstruction/weather_reconstruction_model/model_runs/`.
