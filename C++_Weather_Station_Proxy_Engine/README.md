# C++ Station Proxy Engine

This folder contains the reusable C++ engine that loads app-ready NOAA station
CSV files and ranks long-record hub stations as proxy candidates for a target
station.

## Why It Exists

The FastAPI app needs repeated station-proxy lookups to be fast after the large
station files are loaded. The C++ engine owns that performance-sensitive scoring
path, while Python remains responsible for data preparation and model research.

## File Map

- `STATION_PROXY_ENGINE.*` is the high-level engine API.
- `api_main.cpp` is a one-shot command-line wrapper used by tests and local
  checks; `main.cpp` is a local test runner.
- `station_dataset.*`, `csv_filereader.*`, and `seasonal_analysis.*` load and
  organize station observations.
- `station_distance.*`, `station_locator.*`, and `station_matcher.*` find the
  nearest target station and evaluate candidate matches.
- `similarity_scores.*` and `station_pair_score.*` calculate the station
  similarity metrics and weighted proxy score.
- `engine_unit_tests.cpp` holds the C++ unit tests run by `make test-cpp-unit`.
- `python_bindings.cpp` is the optional pybind11 extension built by
  `make native-engine`.
- `validate_prediction_similarity.cpp` independently scores Python-generated
  prediction files.

## Common Commands

From the project root:

```bash
make api
make test-engine
make test-cpp-unit
make validate-prediction
```

