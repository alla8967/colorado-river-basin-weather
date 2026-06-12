# NOAA Inventory Preparation

This folder contains NOAA GHCN-Daily station metadata, curated candidate station
lists, and the scripts used to turn yearly NOAA bulk files into app-ready CSVs.

## Why It Exists

The app and C++ engine need two prepared daily-temperature files:

- target stations near user-selected locations,
- long-record hub stations that can act as proxy candidates.

The raw NOAA yearly files are large and ignored by git. The tracked metadata and
candidate lists document which stations were selected.

## File Map

- `filter_ghcn_years.py` builds app-ready daily CSVs from NOAA yearly bulk
  files.
- `noaa_sort.*` and `main.cpp` filter station inventory metadata into target
  and hub candidate lists.
- `ghcnd-inventory.txt` and `ghcnd-stations.txt` are NOAA metadata inputs.
- `target_station_candidates.csv` and `hub_station_candidates.csv` are curated
  station candidate inputs.

Generated files such as `*_daily_app_ready.csv` and `NOAA_GHCN_ByYear/` are
ignored because they can be large and are local runtime artifacts.

## Full NOAA Data Path

The fixture app does not need the full NOAA files. For a full local run, place
GHCN-Daily yearly bulk CSVs under:

```text
NOAA_Inventory_Sort/NOAA_GHCN_ByYear/
```

NOAA publishes those files as yearly `.csv.gz` archives, for example:

```text
https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_year/2026.csv.gz
```

After the yearly files are present, build the app-ready target and hub CSVs:

```bash
STATION_PROXY_GHCN_YEAR_DIR=NOAA_Inventory_Sort/NOAA_GHCN_ByYear \
  .venv/bin/python NOAA_Inventory_Sort/filter_ghcn_years.py
```

That command writes `target_daily_app_ready.csv` and `hub_daily_app_ready.csv`
beside this README. Those outputs stay ignored by git.
