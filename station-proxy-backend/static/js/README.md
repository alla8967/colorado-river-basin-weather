# Frontend JavaScript Modules

This folder contains the browser-side modules for the station proxy app.

## File Map

- `main.js` wires page controls, tabs, maps, and form behavior.
- `api.js` wraps backend `fetch` calls.
- `state.js` stores shared DOM references and browser state.
- `maps.js` manages the Leaflet analysis and confidence maps.
- `confidence.js` renders confidence-support points and map interactions.
- `reliability.js` renders reliability surfaces, station overlays, and legends.
- `results.js` renders station analysis results and proxy rankings.
- `charts.js` renders SVG comparison charts.
- `formatters.js` holds display, numeric, station, and map helper functions.

These modules are loaded by `../index.html` through `main.js`.

