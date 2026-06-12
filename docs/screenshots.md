# App Screenshot Capture

Capture screenshots only after the fixture app is running, map tiles are fully rendered, and the browser viewport is at least 1280 px wide.

1. Run the fixture demo from the repository root:

   ```bash
   make demo
   ```

2. Open `http://127.0.0.1:8000`.
3. Click a preset location.
4. Capture the analysis/results view as `docs/assets/app_analysis.png`.
5. Switch to the Reliability Map.
6. Capture the reliability map/inspector view as `docs/assets/app_reliability.png`.

Do not commit half-loaded map tiles, small mobile captures, or screenshots where the analysis panels are not visible.
