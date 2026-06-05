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

