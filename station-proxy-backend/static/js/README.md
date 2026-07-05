# Frontend JavaScript Modules

This folder contains the browser-side modules for the station proxy app.

## File Map

- `main.js` wires page controls, tabs, maps, and form behavior.
- `api.js` wraps backend `fetch` calls.
- `state.js` stores shared DOM references and browser state.
- `maps.js` manages the Leaflet station-analysis map.
- `reliability.js` renders reliability surfaces, station overlays, legends, and
  the station detail panel with holdout metrics and daily prediction-vs-actual
  charts.
- `results.js` renders station analysis results and proxy rankings.
- `methodology.js` renders the proxy-scoring methodology copy.
- `model-testing.js` renders the Model & Testing tab (validation design,
  Alpine HPC hardware, and measured run timings).
- `charts.js` renders SVG comparison charts.
- `formatters.js` holds display, numeric, station, and map helper functions.

These modules are loaded by `../index.html` through `main.js`.
