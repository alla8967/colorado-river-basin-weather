# V1 Cleanup Plan

This project is already functional and reviewable. The remaining cleanup should
make the product boundary clearer, reduce browsing friction, and turn the local
workspace into a polished v1 handoff without disturbing data-heavy research
paths.

## V1 Product Boundary

The v1 product is the local station proxy finder:

- FastAPI backend in `web_app/station-proxy-backend/`
- Browser frontend in `web_app/station-proxy-backend/index.html` and
  `web_app/station-proxy-backend/static/`
- C++ matching engine in `cpp_scoring_engine/C++_Weather_Station_Proxy_Engine/`
- Persistent engine wrapper in `cpp_scoring_engine/Station_Engine_Server/`
- Small local validation fixtures in `tests/`
- App-ready generated station CSVs in `ml_reconstruction/NOAA_Inventory_Sort/`, kept ignored but
  expected for local app runs

The research/modeling system is supporting infrastructure, not the primary v1
surface. Keep it available and documented, but do not let it dominate the first
experience for a human reviewer.

## Whole-Project Aim

The broad project goal is to let a user choose a location in the Colorado River
Basin region and understand both:

- which observed NOAA stations can act as good proxies for that location; and
- how well supported a future reconstructed local temperature history would be.

The app lane currently answers the proxy-finder question. The model lane tests
the next step: reconstructing daily average temperature histories by learning
from long-record hub stations, nearby target-neighbor stations, terrain
features, seasonality, offsets, and pairwise station skill. Holdout validation
then measures real error, and model-run artifacts convert that evidence into a
confidence/support surface for the app.

## Cleanup Priorities

### 1. Clarify The First Five Minutes

The top-level `README.md` is comprehensive, but it is long enough that a new
human has to work to find the shortest path. For v1, keep the current detail but
add or preserve a compact opening path:

```text
1. What this app does.
2. What folders matter for the app.
3. How to run `make check`.
4. How to start the backend.
5. What generated files to ignore.
```

Avoid sending first-time readers into model-run, Alpine, or research-script
details before they understand the app.

### 2. Keep Top-Level Folders Stable

Do not do a broad `src/`, `apps/`, `data/`, or `artifacts/` reshuffle for v1.
The current scripts and docs already encode the existing path assumptions, and
`make check` passes with the current layout.

Use documentation to explain the lanes:

- app lane
- data-prep lane
- research/model lane
- remote-run lane

Save large physical moves for a later version after every data path has an
explicit config hook or test.

### 3. Make The App Feel Like The Product

The frontend is usable, but it should be the most polished part of v1. The next
UI pass should focus on:

- replacing generic page language with concise product language;
- making the initial screen denser and more operational;
- checking mobile layout for map, tabs, controls, and result cards;
- making loading, unavailable-engine, and no-result states feel intentional;
- keeping methodology details accessible but secondary.

The app should open directly into the working tool. The research explanation
should support confidence in the result, not compete with the workflow.

### 4. Separate Source From Local Artifacts Visually

The ignore policy is solid. Keep generated data, model outputs, DEM products,
compiled binaries, caches, and virtual environments ignored.

Recommended v1 behavior:

- keep `make clean-local-artifacts` conservative;
- do not delete NOAA archives, model runs, or DEM products automatically;
- keep `.DS_Store`, build outputs, and generated handoff files ignored;
- before a release commit, run `git status --ignored --short` and check for
  surprising unignored artifacts.

### 5. Add Release-Facing Checks

`make check` is the right local review command and currently passes. Before v1,
add a short release checklist that records:

- `make check`
- optional model-script tests with `PYTHON=.venv/bin/python make test-python`
- a manual browser smoke test at `http://127.0.0.1:8000/`
- confirmation that generated artifacts are not staged
- confirmation that Alpine scratch paths were not changed

Keep this checklist human-readable; it is a handoff aid, not a CI replacement.
The current checklist lives in `docs/release_checklist.md`.

## Artifact Audit Findings

Current cleanup recommendations:

- `ml_reconstruction/weather_reconstruction_model/model_runs/` should stay locally for v1. It is
  ignored/generated, but the backend reads the active run to serve
  `/model-runs/current` and `/model-runs/current/confidence-grid`.
- `ml_reconstruction/weather_reconstruction_model/outputs/` is small enough to keep during v1
  polish, but it should remain clearly labeled as working research output.
- `web_app/station-proxy-backend/assets/confidence-points.json` appears to be a stale
  generated handoff file. The current frontend loads confidence points from the
  model-run endpoint instead of this static JSON.
- `ml_reconstruction/weather_reconstruction_artifacts/` is an archive/scratch shelf and should
  remain ignored. Do not wire app behavior to files in that shelf.
- NOAA app-ready daily CSVs should stay in place locally because the persistent
  C++ engine uses them for normal app runs.

## Lower Priority Cleanup

These are useful after the product handoff is smooth:

- continue decomposing the largest research scripts only when shared behavior is
  obvious;
- add report-render smoke tests if static HTML reports become deliverables;
- consider renaming C++ directories to simpler lowercase names only after
  Makefile, docs, scripts, and user expectations are updated together;
- consider moving app code under an `app/` or `services/` namespace in a future
  major cleanup, not as a v1 polish task.

## Current Recommendation

For v1, polish the product narrative and frontend first, then freeze the current
layout with clear docs and passing checks. The project does not need a risky
directory reorganization to be understandable; it needs a stronger distinction
between the finished app and the research machinery that produced it.
