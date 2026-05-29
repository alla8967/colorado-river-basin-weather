# Local Artifact Inventory

This inventory describes ignored local artifacts that may be present in the
working folder. It helps a human clean the project view without accidentally
deleting inputs or evidence needed by the app, model work, or active
station-holdout runs.

## Size Note

On this machine, APFS cloning/sparse storage can make disk usage and apparent
file size differ sharply. Use both views when deciding what to clean:

```bash
du -sh <path>      # disk blocks currently used
du -A -sh <path>   # apparent file size
```

The apparent size is often the better signal for how large a file will look to
copy, archive, or sync.

## Keep For V1 App Runs

| Path | Why it stays |
| --- | --- |
| `ml_reconstruction/NOAA_Inventory_Sort/target_daily_app_ready.csv` | C++ engine target-station daily input. |
| `ml_reconstruction/NOAA_Inventory_Sort/hub_daily_app_ready.csv` | C++ engine hub-station daily input. |
| `ml_reconstruction/NOAA_Inventory_Sort/target_station_candidates.csv` | Confidence/support station metadata input. |
| `ml_reconstruction/NOAA_Inventory_Sort/hub_station_candidates.csv` | Confidence/support station metadata input. |
| `ml_reconstruction/weather_reconstruction_model/model_runs/<active_run>/` | FastAPI serves the active confidence grid and model-run summary from here. |
| `ml_reconstruction/terrain_data/processed/` | Terrain feature inputs for confidence support when present. |

These files and folders are ignored by git, but they are part of a useful local
v1 workspace.

## Keep Until Holdout Runs Finish

| Path | Contents | Cleanup note |
| --- | --- | --- |
| `ml_reconstruction/weather_reconstruction_model/outputs/` | Current working training tables, predictions, station metrics, validation files, and reports. | Keep during current cleanup. Revisit after active station-holdout runs finish and current evidence has been exported to `model_runs/`. |
| `ml_reconstruction/weather_reconstruction_artifacts/alpine_results_snapshot_2026_05_25/` | Retrieved Alpine result snapshot, logs, pairwise skill cache, and remote outputs. | Treat as comparison evidence. Archive externally before deleting locally. |
| `ml_reconstruction/weather_reconstruction_artifacts/archive/` | Older full and option-C training tables, predictions, reports, validation files, and handoff notes. | Large apparent size. Do not delete until deciding which older experiments are superseded. |
| `ml_reconstruction/weather_reconstruction_artifacts/noaa_year_archive/` | NOAA yearly `.csv.gz` archive. | Keep unless there is another confirmed local or remote copy. |
| `ml_reconstruction/weather_reconstruction_artifacts/raw_dem_archive/` | Raw DEM tile archive. | Keep unless DEM regeneration/download path is confirmed. |
| `ml_reconstruction/weather_reconstruction_artifacts/scratch/` | Smoke-test and exploratory model outputs. | Best candidate for later deletion, but wait until current holdout work is complete. |

## Safe To Remove Locally

These are safe cleanup targets because they are rebuildable or stale:

- `.DS_Store` files outside `.git/`
- `.pytest_cache/`
- `build/pycache/`
- compiled C++ binaries created by Makefile targets
- `web_app/station-proxy-backend/assets/confidence-points.json`

`web_app/station-proxy-backend/assets/confidence-points.json` is an older generated
handoff file. The current app loads the confidence layer from:

```text
/model-runs/current/confidence-grid
```

## Current Cleanup Position

For now, keep source structure stable and do not move data-heavy shelves into a
new folder. Once station-holdout runs finish, the next cleanup pass should:

1. Export any current evidence that belongs in the active `model_runs/` folder.
2. Decide whether `ml_reconstruction/weather_reconstruction_model/outputs/` can be cleared or
   narrowed to current reports only.
3. Decide whether `ml_reconstruction/weather_reconstruction_artifacts/scratch/` can be deleted.
4. Move any long-term archive copies outside the source workspace if Finder
   clutter or sync cost is still a problem.
