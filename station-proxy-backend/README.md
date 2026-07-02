# Station Proxy Backend And Frontend

This folder contains the local FastAPI app, polished browser frontend, and
backend services that connect the UI to the C++ engine and model artifacts.

## Why It Exists

This is the main reviewable application surface. It serves `index.html`, static
assets, location analysis routes, confidence-support routes, reliability-map
routes, and model-run summary routes.

## File Map

- `main.py` wires FastAPI routes and static file serving.
- `engine_client.py` manages the persistent C++ engine process.
- `engine_adapter.py` and `native_engine_client.py` dispatch between the
  subprocess engine and the optional pybind11 native extension.
- `confidence_service.py`, `model_run_service.py`, and
  `reliability_service.py` load generated research/model artifacts for the UI.
- `settings.py` centralizes default paths and environment-variable overrides.
- `api_models.py` defines JSON response shapes shared by backend routes.
- `index.html` is the polished application shell.
- `static/` contains CSS, JavaScript modules, and small documentation images.

## Local Run

From the project root:

```bash
make server
make run-backend
```

Then open `http://127.0.0.1:8000/`.

For a clean fixture-only run that does not require the full NOAA CSVs:

```bash
make bootstrap-fixture
make run-backend-fixture
```

The fixture app uses the tiny tracked station files in `tests/fixtures/`, so it
is the safest first check on a new machine.

## Engine Modes

The backend defaults to the persistent subprocess engine:

```text
STATION_PROXY_ENGINE_MODE=process
```

An optional pybind11 path is available for local experiments:

```bash
.venv/bin/python -m pip install -e ".[native]"
make native-engine PYTHON=.venv/bin/python
STATION_PROXY_ENGINE_MODE=auto make run-backend-fixture PYTHON=.venv/bin/python
```

`auto` uses the native extension only when it is importable; otherwise it falls
back to the subprocess engine. `native` requires the extension and reports
`native-unavailable` in `/test` if it has not been built.

Some views depend on generated NOAA/model artifacts that are intentionally
ignored by git; see `../docs/reviewer_runbook.md` for the practical review path.
