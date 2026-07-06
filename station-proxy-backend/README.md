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

## Public Review Scope

The public repository keeps this folder reviewable as application source while
leaving production operating details out of tree. The fixture workflow in the
top-level README is the intended public smoke path.

Some views depend on generated NOAA/model artifacts that are intentionally
ignored by git. Those artifacts are described at a high level in
`../docs/public_review_notes.md` and `../docs/generated_artifact_audit.md`.
