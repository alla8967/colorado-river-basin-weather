# Model Input Boundaries

The reliability map boundary is a station-extent rectangle:

- furthest south station latitude
- furthest north station latitude
- furthest west station longitude
- furthest east station longitude
- plus 30 km of padding in each direction

```text
weather_reconstruction_model/inputs/colorado_river_basin_boundary.geojson
```

Generate it from the restored station coordinate files:

```bash
python3 weather_reconstruction_model/scripts/build_station_extent_boundary.py
```

Or let the reliability build create it automatically if it is missing:

```bash
python3 weather_reconstruction_model/scripts/build_reliability_surfaces.py
```

When Alpine holdout metric CSVs are available, normalize them into the expected
`model_runs/paloma_v1_<variable>/station_metrics.csv` folders with:

```bash
python3 weather_reconstruction_model/scripts/prepare_paloma_reliability_inputs.py \
  --tavg-metrics /path/to/tavg_station_metrics.csv \
  --tmin-metrics /path/to/tmin_station_metrics.csv \
  --tmax-metrics /path/to/tmax_station_metrics.csv
```
