"""Create an HTML diagnostics report for validation predictions and residuals.

Use it to inspect station failures, seasonal behavior, and error patterns after model validation."""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from pathlib import Path

from common.metrics import calculate_correlation, calculate_mae, calculate_rmse, mean
from common.number_utils import to_float
from common.reporting import escape_html as escape
from common.reporting import render_metric_card
from config import (
    GENERAL_TABLE_DIR,
    ML_GOAL_MAX_MAE,
    ML_GOAL_MAX_RMSE,
    ML_GOAL_MIN_CORRELATION,
    PREDICTION_DIR,
    REPORT_DIR,
)

STRICT_MAX_MAE = ML_GOAL_MAX_MAE
STRICT_MAX_RMSE = ML_GOAL_MAX_RMSE
STRICT_MIN_CORRELATION = ML_GOAL_MIN_CORRELATION

DEFAULT_MODEL_SLUG = "terrain_standard_random_forest"
DEFAULT_TABLE_NAME = "general_97_targets_5_hubs"
DEFAULT_REPORT_DIR = REPORT_DIR / "diagnostics"

SEASONS_BY_MONTH = {
    12: "Winter",
    1: "Winter",
    2: "Winter",
    3: "Spring",
    4: "Spring",
    5: "Spring",
    6: "Summer",
    7: "Summer",
    8: "Summer",
    9: "Fall",
    10: "Fall",
    11: "Fall",
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a readable HTML diagnostics report for model predictions."
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        default=PREDICTION_DIR
        / f"{DEFAULT_TABLE_NAME}_{DEFAULT_MODEL_SLUG}_predictions.csv",
        help="Prediction CSV produced by train_tree_temperature_model.py.",
    )
    parser.add_argument(
        "--station-metrics",
        type=Path,
        default=REPORT_DIR
        / f"{DEFAULT_TABLE_NAME}_{DEFAULT_MODEL_SLUG}_station_metrics.csv",
        help="Station-level metrics CSV produced by train_tree_temperature_model.py.",
    )
    parser.add_argument(
        "--general-table",
        type=Path,
        default=GENERAL_TABLE_DIR / f"{DEFAULT_TABLE_NAME}.csv",
        help="General training table used to add station terrain and hub metadata.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT_DIR
        / f"{DEFAULT_TABLE_NAME}_{DEFAULT_MODEL_SLUG}_diagnostics.html",
        help="HTML report path.",
    )
    parser.add_argument(
        "--detail-count",
        type=int,
        default=12,
        help="Number of best and worst stations to include in detail sections.",
    )
    return parser.parse_args()


def format_float(value: float | None, decimals: int = 2, suffix: str = "") -> str:
    if value is None or math.isnan(value):
        return "n/a"
    return f"{value:.{decimals}f}{suffix}"


def format_signed(value: float | None, decimals: int = 2, suffix: str = "") -> str:
    if value is None or math.isnan(value):
        return "n/a"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{decimals}f}{suffix}"


def parse_date(value: str) -> date:
    year, month, day = value.split("-")
    return date(int(year), int(month), int(day))


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None

    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * percentile_value
    lower_index = math.floor(index)
    upper_index = math.ceil(index)

    if lower_index == upper_index:
        return sorted_values[int(index)]

    lower = sorted_values[lower_index]
    upper = sorted_values[upper_index]
    return lower + (upper - lower) * (index - lower_index)


def load_station_metrics(file_path: Path) -> dict[str, dict[str, object]]:
    metrics: dict[str, dict[str, object]] = {}

    with file_path.open("r", newline="") as file:
        for row in csv.DictReader(file):
            station_id = row["target_station_id"]
            metrics[station_id] = {
                "target_station_id": station_id,
                "target_name": row["target_name"],
                "test_rows": int(row["test_rows"]),
                "mae": to_float(row["mae"]),
                "rmse": to_float(row["rmse"]),
                "correlation": to_float(row["correlation"]),
            }

    return metrics


def load_prediction_diagnostics(file_path: Path) -> dict[str, dict[str, object]]:
    actual_by_station: dict[str, list[float]] = defaultdict(list)
    predicted_by_station: dict[str, list[float]] = defaultdict(list)
    errors_by_station: dict[str, list[float]] = defaultdict(list)
    abs_errors_by_station: dict[str, list[float]] = defaultdict(list)
    seasonal_actual: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    seasonal_predicted: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )

    with file_path.open("r", newline="") as file:
        for row in csv.DictReader(file):
            station_id = row["target_station_id"]
            actual = to_float(row["actual_tavg"])
            predicted = to_float(row["predicted_tavg"])
            error = actual - predicted
            season = SEASONS_BY_MONTH[parse_date(row["date"]).month]

            actual_by_station[station_id].append(actual)
            predicted_by_station[station_id].append(predicted)
            errors_by_station[station_id].append(error)
            abs_errors_by_station[station_id].append(abs(error))
            seasonal_actual[station_id][season].append(actual)
            seasonal_predicted[station_id][season].append(predicted)

    diagnostics: dict[str, dict[str, object]] = {}
    for station_id, actual_values in actual_by_station.items():
        predicted_values = predicted_by_station[station_id]
        errors = errors_by_station[station_id]
        abs_errors = abs_errors_by_station[station_id]

        seasonal_metrics: dict[str, dict[str, float | None]] = {}
        for season in ("Winter", "Spring", "Summer", "Fall"):
            actual_season = seasonal_actual[station_id].get(season, [])
            predicted_season = seasonal_predicted[station_id].get(season, [])
            if actual_season:
                seasonal_metrics[season] = {
                    "mae": calculate_mae(actual_season, predicted_season),
                    "rmse": calculate_rmse(actual_season, predicted_season),
                    "bias": mean(
                        [
                            actual - predicted
                            for actual, predicted in zip(
                                actual_season,
                                predicted_season,
                            )
                        ]
                    ),
                    "rows": len(actual_season),
                }
            else:
                seasonal_metrics[season] = {
                    "mae": None,
                    "rmse": None,
                    "bias": None,
                    "rows": 0,
                }

        diagnostics[station_id] = {
            "mean_bias": mean(errors),
            "median_abs_error": percentile(abs_errors, 0.50),
            "p90_abs_error": percentile(abs_errors, 0.90),
            "max_abs_error": max(abs_errors),
            "seasonal": seasonal_metrics,
            "actual_mean": mean(actual_values),
            "predicted_mean": mean(predicted_values),
            "recomputed_correlation": calculate_correlation(
                actual_values,
                predicted_values,
            ),
        }

    return diagnostics


def load_general_table_metadata(file_path: Path) -> dict[str, dict[str, object]]:
    metadata: dict[str, dict[str, object]] = {}

    with file_path.open("r", newline="") as file:
        for row in csv.DictReader(file):
            station_id = row["target_station_id"]
            if station_id in metadata:
                continue

            hub_distances = collect_hub_values(row, "distance_km")
            abs_dem_deltas = collect_hub_values(row, "abs_dem_elevation_delta_m")
            abs_noaa_elevation_deltas = [
                abs(value) for value in collect_hub_values(row, "elevation_difference_m")
            ]
            hub_overlaps = collect_hub_values(row, "overlap_percent")

            metadata[station_id] = {
                "target_latitude": to_float(row.get("target_latitude")),
                "target_longitude": to_float(row.get("target_longitude")),
                "target_elevation_m": to_float(row.get("target_elevation_m")),
                "target_dem_elevation_m": to_float(
                    row.get("target_dem_elevation_m")
                ),
                "target_dem_minus_noaa_elevation_m": to_float(
                    row.get("target_dem_minus_noaa_elevation_m")
                ),
                "target_slope_degrees": to_float(row.get("target_slope_degrees")),
                "target_local_relief_m": to_float(row.get("target_local_relief_m")),
                "target_terrain_position_index_m": to_float(
                    row.get("target_terrain_position_index_m")
                ),
                "average_hub_distance_km": mean_or_none(hub_distances),
                "farthest_hub_distance_km": max(hub_distances)
                if hub_distances
                else None,
                "average_abs_dem_elevation_delta_m": mean_or_none(abs_dem_deltas),
                "average_abs_noaa_elevation_delta_m": mean_or_none(
                    abs_noaa_elevation_deltas
                ),
                "minimum_hub_overlap_percent": min(hub_overlaps)
                if hub_overlaps
                else None,
            }

    return metadata


def collect_hub_values(row: dict[str, str], suffix: str) -> list[float]:
    values: list[float] = []
    for hub_number in range(1, 6):
        key = f"hub_{hub_number}_{suffix}"
        if key in row and row[key] != "":
            values.append(to_float(row[key]))
    return values


def mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return mean(values)


def merge_station_rows(
    station_metrics: dict[str, dict[str, object]],
    prediction_diagnostics: dict[str, dict[str, object]],
    metadata: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    for station_id, metric_row in station_metrics.items():
        row = dict(metric_row)
        row.update(prediction_diagnostics.get(station_id, {}))
        row.update(metadata.get(station_id, {}))
        row["strict_pass"] = (
            row["mae"] < STRICT_MAX_MAE
            and row["rmse"] < STRICT_MAX_RMSE
            and row["correlation"] >= STRICT_MIN_CORRELATION
        )
        row["bias_label"] = classify_bias(to_float(row.get("mean_bias")))
        row["seasonal_spread"] = calculate_seasonal_spread(row)
        rows.append(row)

    return rows


def classify_bias(mean_bias: float) -> str:
    if mean_bias >= 1.0:
        return "too cold"
    if mean_bias <= -1.0:
        return "too warm"
    return "low bias"


def calculate_seasonal_spread(row: dict[str, object]) -> float | None:
    seasonal = row.get("seasonal")
    if not isinstance(seasonal, dict):
        return None

    maes = [
        metrics["mae"]
        for metrics in seasonal.values()
        if isinstance(metrics, dict) and metrics.get("mae") is not None
    ]
    if not maes:
        return None
    return max(maes) - min(maes)


def sorted_rows(
    rows: Iterable[dict[str, object]],
    metric: str,
    reverse: bool = False,
) -> list[dict[str, object]]:
    return sorted(rows, key=lambda row: to_float(row.get(metric)), reverse=reverse)


def make_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    maes = [to_float(row["mae"]) for row in rows]
    rmses = [to_float(row["rmse"]) for row in rows]
    correlations = [to_float(row["correlation"]) for row in rows]
    biases = [to_float(row.get("mean_bias")) for row in rows]

    return {
        "station_count": len(rows),
        "strict_pass_count": sum(1 for row in rows if row["strict_pass"]),
        "mean_mae": mean(maes),
        "median_mae": percentile(maes, 0.50),
        "mean_rmse": mean(rmses),
        "mean_correlation": mean(correlations),
        "mean_bias": mean(biases),
    }


def build_html(
    rows: list[dict[str, object]],
    summary: dict[str, object],
    predictions_path: Path,
    station_metrics_path: Path,
    general_table_path: Path,
    detail_count: int,
) -> str:
    best_rows = sorted_rows(rows, "mae")[:detail_count]
    worst_rows = sorted_rows(rows, "mae", reverse=True)[:detail_count]
    bias_rows = sorted(rows, key=lambda row: abs(to_float(row.get("mean_bias"))), reverse=True)[
        :detail_count
    ]
    seasonal_rows = sorted_rows(rows, "seasonal_spread", reverse=True)[:detail_count]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Temperature Reconstruction Diagnostics</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #20242a;
      --muted: #667085;
      --line: #d9dee7;
      --accent: #176b87;
      --good: #177245;
      --warn: #9a5b00;
      --bad: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.45;
    }}
    header {{
      padding: 32px 40px 24px;
      background: #17212b;
      color: white;
    }}
    header h1 {{
      margin: 0 0 8px;
      font-size: 32px;
      letter-spacing: 0;
    }}
    header p {{
      max-width: 920px;
      margin: 0;
      color: #d5dce6;
    }}
    main {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 28px 28px 56px;
    }}
    h2 {{
      margin: 34px 0 12px;
      font-size: 22px;
    }}
    h3 {{
      margin: 0 0 12px;
      font-size: 17px;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: -8px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .metric-label {{
      font-size: 13px;
      color: var(--muted);
    }}
    .metric-value {{
      margin-top: 4px;
      font-size: 26px;
      font-weight: 700;
    }}
    .note {{
      color: var(--muted);
      font-size: 14px;
      max-width: 980px;
    }}
    .grid-two {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(440px, 1fr));
      gap: 16px;
    }}
    .section-panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      overflow: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      padding: 9px 8px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
    }}
    th {{
      color: #344054;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .04em;
      background: #f8fafc;
    }}
    .station-name {{
      white-space: normal;
      min-width: 170px;
    }}
    .pass {{
      color: var(--good);
      font-weight: 700;
    }}
    .fail {{
      color: var(--bad);
      font-weight: 700;
    }}
    .warm {{
      color: var(--bad);
    }}
    .cold {{
      color: var(--accent);
    }}
    .low {{
      color: var(--good);
    }}
    .details {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 14px;
    }}
    .station-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .station-header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 14px;
    }}
    .station-title {{
      font-weight: 700;
      font-size: 17px;
    }}
    .station-subtitle {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 2px;
    }}
    .mini-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 10px;
    }}
    .mini {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #fbfcfe;
    }}
    .mini span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
    }}
    .mini strong {{
      display: block;
      margin-top: 3px;
      font-size: 16px;
    }}
    .source-list {{
      margin: 8px 0 0;
      padding-left: 18px;
      color: var(--muted);
      font-size: 13px;
    }}
    @media (max-width: 700px) {{
      header {{ padding: 24px 20px; }}
      main {{ padding: 20px 14px 42px; }}
      .grid-two {{ grid-template-columns: 1fr; }}
      th, td {{ white-space: normal; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Temperature Reconstruction Diagnostics</h1>
    <p>This report looks beyond the headline score. It highlights bias, seasonal error, terrain context, and hub geometry so weak stations can be diagnosed rather than just labeled as failures.</p>
  </header>
  <main>
    <section>
      <div class="cards">
        {summary_card("Stations", str(summary["station_count"]))}
        {summary_card("Strict Passes", f"{summary['strict_pass_count']}/{summary['station_count']}")}
        {summary_card("Mean MAE", format_float(summary["mean_mae"], 2, " F"))}
        {summary_card("Median MAE", format_float(summary["median_mae"], 2, " F"))}
        {summary_card("Mean RMSE", format_float(summary["mean_rmse"], 2, " F"))}
        {summary_card("Mean r", format_float(summary["mean_correlation"], 3))}
        {summary_card("Mean Bias", format_signed(summary["mean_bias"], 2, " F"))}
      </div>
      <p class="note">Strict pass means MAE &lt; {STRICT_MAX_MAE} F, RMSE &lt; {STRICT_MAX_RMSE} F, and correlation &ge; {STRICT_MIN_CORRELATION}. Bias is actual minus predicted, so positive values mean the model predicted too cold.</p>
    </section>

    <section class="grid-two">
      <div class="section-panel">
        <h3>Best Stations By MAE</h3>
        {station_table(best_rows)}
      </div>
      <div class="section-panel">
        <h3>Worst Stations By MAE</h3>
        {station_table(worst_rows)}
      </div>
    </section>

    <section class="grid-two">
      <div class="section-panel">
        <h3>Largest Mean Bias</h3>
        <p class="note">These stations are most systematically too warm or too cold.</p>
        {bias_table(bias_rows)}
      </div>
      <div class="section-panel">
        <h3>Largest Seasonal Spread</h3>
        <p class="note">These stations change the most by season, which may point toward inversion, summer heat, snowpack, or local terrain effects.</p>
        {seasonal_spread_table(seasonal_rows)}
      </div>
    </section>

    <section>
      <h2>Worst-Station Detail</h2>
      <div class="details">
        {station_detail_cards(worst_rows)}
      </div>
    </section>

    <section>
      <h2>Source Files</h2>
      <div class="section-panel">
        <ul class="source-list">
          <li>Predictions: {escape(predictions_path)}</li>
          <li>Station metrics: {escape(station_metrics_path)}</li>
          <li>General table: {escape(general_table_path)}</li>
        </ul>
      </div>
    </section>
  </main>
</body>
</html>
"""


def summary_card(label: str, value: str) -> str:
    return render_metric_card(
        label,
        value,
        label_class="metric-label",
        value_class="metric-value",
    )


def station_table(rows: list[dict[str, object]]) -> str:
    body = "\n".join(
        f"""
        <tr>
          <td>{pass_label(row)}</td>
          <td>{escape(row["target_station_id"])}</td>
          <td class="station-name">{escape(row["target_name"])}</td>
          <td>{format_float(to_float(row["mae"]), 2)}</td>
          <td>{format_float(to_float(row["rmse"]), 2)}</td>
          <td>{format_float(to_float(row["correlation"]), 3)}</td>
          <td>{format_signed(to_float(row.get("mean_bias")), 2)}</td>
          <td>{escape(row["test_rows"])}</td>
        </tr>"""
        for row in rows
    )
    return f"""
    <table>
      <thead>
        <tr>
          <th>Goal</th>
          <th>Station</th>
          <th>Name</th>
          <th>MAE</th>
          <th>RMSE</th>
          <th>r</th>
          <th>Bias</th>
          <th>Rows</th>
        </tr>
      </thead>
      <tbody>{body}</tbody>
    </table>"""


def bias_table(rows: list[dict[str, object]]) -> str:
    body = "\n".join(
        f"""
        <tr>
          <td>{escape(row["target_station_id"])}</td>
          <td class="station-name">{escape(row["target_name"])}</td>
          <td>{bias_badge(row)}</td>
          <td>{format_signed(to_float(row.get("mean_bias")), 2)}</td>
          <td>{format_float(to_float(row["mae"]), 2)}</td>
          <td>{format_float(to_float(row["rmse"]), 2)}</td>
        </tr>"""
        for row in rows
    )
    return f"""
    <table>
      <thead>
        <tr>
          <th>Station</th>
          <th>Name</th>
          <th>Pattern</th>
          <th>Bias</th>
          <th>MAE</th>
          <th>RMSE</th>
        </tr>
      </thead>
      <tbody>{body}</tbody>
    </table>"""


def seasonal_spread_table(rows: list[dict[str, object]]) -> str:
    body = "\n".join(
        f"""
        <tr>
          <td>{escape(row["target_station_id"])}</td>
          <td class="station-name">{escape(row["target_name"])}</td>
          <td>{format_float(to_float(row.get("seasonal_spread")), 2)}</td>
          <td>{season_summary(row)}</td>
          <td>{format_float(to_float(row["mae"]), 2)}</td>
        </tr>"""
        for row in rows
    )
    return f"""
    <table>
      <thead>
        <tr>
          <th>Station</th>
          <th>Name</th>
          <th>Spread</th>
          <th>Season MAE</th>
          <th>Total MAE</th>
        </tr>
      </thead>
      <tbody>{body}</tbody>
    </table>"""


def station_detail_cards(rows: list[dict[str, object]]) -> str:
    return "\n".join(station_detail_card(row) for row in rows)


def station_detail_card(row: dict[str, object]) -> str:
    return f"""
    <article class="station-card">
      <div class="station-header">
        <div>
          <div class="station-title">{escape(row["target_name"])}</div>
          <div class="station-subtitle">{escape(row["target_station_id"])} · {escape(row["test_rows"])} test rows · {pass_label(row)}</div>
        </div>
        <div>{bias_badge(row)}</div>
      </div>
      <div class="mini-grid">
        {mini("MAE", format_float(to_float(row["mae"]), 2, " F"))}
        {mini("RMSE", format_float(to_float(row["rmse"]), 2, " F"))}
        {mini("Correlation", format_float(to_float(row["correlation"]), 3))}
        {mini("Mean Bias", format_signed(to_float(row.get("mean_bias")), 2, " F"))}
        {mini("Median Abs Error", format_float(to_float(row.get("median_abs_error")), 2, " F"))}
        {mini("90th Percentile Abs Error", format_float(to_float(row.get("p90_abs_error")), 2, " F"))}
        {mini("Max Abs Error", format_float(to_float(row.get("max_abs_error")), 2, " F"))}
        {mini("Seasonal Spread", format_float(to_float(row.get("seasonal_spread")), 2, " F"))}
        {mini("Avg Hub Distance", format_float(to_float(row.get("average_hub_distance_km")), 1, " km"))}
        {mini("Farthest Hub", format_float(to_float(row.get("farthest_hub_distance_km")), 1, " km"))}
        {mini("Avg DEM Elevation Delta", format_float(to_float(row.get("average_abs_dem_elevation_delta_m")), 0, " m"))}
        {mini("Target Slope", format_float(to_float(row.get("target_slope_degrees")), 1, " deg"))}
        {mini("Target Relief", format_float(to_float(row.get("target_local_relief_m")), 1, " m"))}
        {mini("Terrain Position", format_signed(to_float(row.get("target_terrain_position_index_m")), 1, " m"))}
        {mini("Season MAE", season_summary(row))}
      </div>
    </article>"""


def mini(label: str, value: str) -> str:
    return f"""
    <div class="mini">
      <span>{escape(label)}</span>
      <strong>{value}</strong>
    </div>"""


def pass_label(row: dict[str, object]) -> str:
    if row.get("strict_pass"):
        return '<span class="pass">Pass</span>'
    return '<span class="fail">Fail</span>'


def bias_badge(row: dict[str, object]) -> str:
    label = str(row.get("bias_label", "low bias"))
    css_class = "low"
    if label == "too warm":
        css_class = "warm"
    elif label == "too cold":
        css_class = "cold"
    return f'<span class="{css_class}">{escape(label)}</span>'


def season_summary(row: dict[str, object]) -> str:
    seasonal = row.get("seasonal")
    if not isinstance(seasonal, dict):
        return "n/a"

    parts = []
    for season in ("Winter", "Spring", "Summer", "Fall"):
        season_metrics = seasonal.get(season)
        if isinstance(season_metrics, dict):
            parts.append(
                f"{season[:3]} {format_float(season_metrics.get('mae'), 2)}"
            )
    return " · ".join(parts)


def main() -> None:
    arguments = parse_arguments()
    station_metrics = load_station_metrics(arguments.station_metrics)
    prediction_diagnostics = load_prediction_diagnostics(arguments.predictions)
    metadata = load_general_table_metadata(arguments.general_table)
    rows = merge_station_rows(station_metrics, prediction_diagnostics, metadata)
    summary = make_summary(rows)

    report_html = build_html(
        rows,
        summary,
        arguments.predictions,
        arguments.station_metrics,
        arguments.general_table,
        arguments.detail_count,
    )

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(report_html)

    print("Diagnostics report created")
    print(f"Stations: {summary['station_count']}")
    print(f"Strict passes: {summary['strict_pass_count']}/{summary['station_count']}")
    print(f"Mean MAE: {summary['mean_mae']:.2f} F")
    print(f"Output: {arguments.output}")


if __name__ == "__main__":
    main()
