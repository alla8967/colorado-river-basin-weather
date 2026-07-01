# App Screenshot Capture

The README embeds these assets, all captured from the running app at a viewport of at least 1280 px wide with map tiles fully rendered:

| File | View |
| --- | --- |
| `docs/assets/demo.gif` | Four-frame walkthrough: analysis map, results, reliability map, station holdout detail. |
| `docs/assets/app_analysis.png` | Proxy Finder tab after clicking the Grand Junction preset. |
| `docs/assets/app_results.png` | Nearest station / proxy ranking results panels. |
| `docs/assets/app_reliability.png` | Reliability Map zoomed to the basin with a station selected. |
| `docs/assets/app_prediction_chart.png` | Holdout prediction-vs-actual daily chart from the station detail panel. |

## Recapture steps

1. Run the app. Fixture mode works (`make demo`), but full local NOAA data produces real station names and richer results:

   ```bash
   make run-backend
   ```

2. Open `http://127.0.0.1:8000` at a viewport at least 1280 px wide.
3. Click a preset location and wait for map tiles and analysis panels to finish rendering; capture the analysis and results views.
4. Switch to the Reliability Map, zoom to the basin, click a station point, and wait for the detail panel; capture the map and the prediction chart.
5. Downscale large captures to about 1600 px wide before committing.

Do not commit half-loaded map tiles, small mobile captures, or screenshots where the analysis panels are not visible.
