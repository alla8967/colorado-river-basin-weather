# Public Review Notes

This repository is intended to be readable as a source and research artifact
without exposing the hosted demo's operating playbook.

## What Is Public

- application source for the station proxy UI and read-only API;
- C++ station-matching source;
- small fixture CSVs used by local smoke tests;
- research/model scripts and curated validation evidence;
- screenshots and explanatory diagrams;
- generated-artifact policy and cleanup guidance.

## What Is Not Public

- cloud project names and resource-management commands;
- production deploy, rollback, teardown, billing, or rate-limit runbooks;
- local `.env` files and machine-specific runtime overrides;
- full NOAA app-ready data products;
- model-run artifact shelves and serialized model files;
- DEM downloads and derived terrain rasters.

## Review Path

Use the top-level README for the project purpose, architecture, results, and
fixture demo. Use `PROJECT_MAP.md` for folder navigation, and use
`docs/generated_artifact_audit.md` before staging data-like files.

The fixture workflow exercises the public app path against tiny tracked files.
It is intentionally different from the hosted demo's production artifact shelf.

## Safety Posture

The public app surface is read-only and designed for anonymous use:

- all public API inputs are bounded or normalized;
- backend responses redact local filesystem paths;
- malformed public inputs return client errors rather than stack traces;
- browser-rendered data is escaped before insertion into markup;
- static and model-artifact responses use explicit cache policy;
- the hosted deployment uses scoped CORS and standard browser security headers.

## Artifact Boundary

The public repo should stay source-focused. Do not commit local runtime
overrides, generated model shelves, full NOAA data products, DEM rasters,
serialized estimators, scratch logs, or cloud operator notes.
