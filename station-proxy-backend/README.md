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

Some views depend on generated NOAA/model artifacts that are intentionally
ignored by git; see `../docs/reviewer_runbook.md` for the practical review path.

