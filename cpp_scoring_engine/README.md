# C++ Scoring Engine

This folder contains the station-matching engine used by the local app.

## Contents

| Path | Purpose |
| --- | --- |
| `C++_Weather_Station_Proxy_Engine/` | Reusable C++ scoring core, one-shot API executable, and validation helpers. |
| `Station_Engine_Server/` | Persistent stdin/stdout wrapper used by FastAPI so NOAA data loads once and is reused. |

## Common Commands

From the project root:

```bash
make server
make api
make test-engine
```

The persistent server expects app-ready NOAA daily CSVs under:

```text
ml_reconstruction/NOAA_Inventory_Sort/
```
