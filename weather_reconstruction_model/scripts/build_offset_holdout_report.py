"""Create a report for offset-feature holdout experiments.

It helps evaluate whether terrain and station offsets improve reconstruction reliability."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import config
from common.number_utils import to_float
from common.reporting import escape_html as escape
from common.reporting import render_metric_card


REPORT_DIR = config.REPORT_DIR
DEFAULT_TEMPORAL_DIRECT = (
    REPORT_DIR
    / "option_c_limit97_5_hubs_10_target_neighbors_offset_ready_direct_terrain_standard_random_forest_station_metrics.csv"
)
DEFAULT_TEMPORAL_OFFSET = (
    REPORT_DIR
    / "option_c_limit97_5_hubs_10_target_neighbors_offset_ready_offset_terrain_standard_random_forest_station_metrics.csv"
)
DEFAULT_HOLDOUT_DIRECT = (
    REPORT_DIR
    / "option_c_station_holdout_8_station_quick_random_forest_station_metrics.csv"
)
DEFAULT_HOLDOUT_OFFSET = (
    REPORT_DIR
    / "option_c_station_holdout_8_station_offset_quick_random_forest_station_metrics.csv"
)
DEFAULT_TEMPORAL_DIRECT_PREDICTIONS = (
    config.PREDICTION_DIR
    / "option_c_limit97_5_hubs_10_target_neighbors_offset_ready_direct_terrain_standard_random_forest_predictions.csv"
)
DEFAULT_TEMPORAL_OFFSET_PREDICTIONS = (
    config.PREDICTION_DIR
    / "option_c_limit97_5_hubs_10_target_neighbors_offset_ready_offset_terrain_standard_random_forest_predictions.csv"
)
DEFAULT_HOLDOUT_DIRECT_PREDICTIONS = (
    config.PREDICTION_DIR
    / "option_c_station_holdout_8_station_quick_random_forest_predictions.csv"
)
DEFAULT_HOLDOUT_OFFSET_PREDICTIONS = (
    config.PREDICTION_DIR
    / "option_c_station_holdout_8_station_offset_quick_random_forest_predictions.csv"
)
DEFAULT_OUTPUT = REPORT_DIR / "offset_mode_station_holdout_report.html"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an HTML report for direct vs offset model experiments."
    )
    parser.add_argument(
        "--temporal-direct",
        type=Path,
        default=DEFAULT_TEMPORAL_DIRECT,
        help="Temporal-validation station metrics for the direct model.",
    )
    parser.add_argument(
        "--temporal-offset",
        type=Path,
        default=DEFAULT_TEMPORAL_OFFSET,
        help="Temporal-validation station metrics for the offset model.",
    )
    parser.add_argument(
        "--holdout-direct",
        type=Path,
        default=DEFAULT_HOLDOUT_DIRECT,
        help="Station-holdout metrics for the direct model.",
    )
    parser.add_argument(
        "--holdout-offset",
        type=Path,
        default=DEFAULT_HOLDOUT_OFFSET,
        help="Station-holdout metrics for the offset model.",
    )
    parser.add_argument(
        "--temporal-direct-predictions",
        type=Path,
        default=DEFAULT_TEMPORAL_DIRECT_PREDICTIONS,
        help="Temporal-validation prediction rows for the direct model.",
    )
    parser.add_argument(
        "--temporal-offset-predictions",
        type=Path,
        default=DEFAULT_TEMPORAL_OFFSET_PREDICTIONS,
        help="Temporal-validation prediction rows for the offset model.",
    )
    parser.add_argument(
        "--holdout-direct-predictions",
        type=Path,
        default=DEFAULT_HOLDOUT_DIRECT_PREDICTIONS,
        help="Station-holdout prediction rows for the direct model.",
    )
    parser.add_argument(
        "--holdout-offset-predictions",
        type=Path,
        default=DEFAULT_HOLDOUT_OFFSET_PREDICTIONS,
        help="Station-holdout prediction rows for the offset model.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="HTML output path for the comparison report.",
    )
    return parser.parse_args()


def read_rows(file_path: Path) -> list[dict[str, str]]:
    with file_path.open("r", newline="") as file:
        return list(csv.DictReader(file))


def load_prediction_series(file_path: Path) -> dict[str, dict[str, object]]:
    series_by_station: dict[str, dict[str, object]] = {}

    with file_path.open("r", newline="") as file:
        for row in csv.DictReader(file):
            station_id = row["target_station_id"]
            station = series_by_station.setdefault(
                station_id,
                {
                    "station_id": station_id,
                    "station_name": row["target_name"],
                    "points": [],
                },
            )
            station["points"].append({
                "date": row["date"],
                "actual": round(to_float(row["actual_tavg"]), 2),
                "predicted": round(to_float(row["predicted_tavg"]), 2),
                "error": round(to_float(row["error"]), 2),
            })

    for station in series_by_station.values():
        station["points"].sort(key=lambda point: point["date"])

    return series_by_station


def build_chart_payload(
    temporal_direct_predictions: Path,
    temporal_offset_predictions: Path,
    holdout_direct_predictions: Path,
    holdout_offset_predictions: Path,
) -> dict[str, dict[str, dict[str, object]]]:
    return {
        "temporal": {
            "direct": load_prediction_series(temporal_direct_predictions),
            "offset": load_prediction_series(temporal_offset_predictions),
        },
        "holdout": {
            "direct": load_prediction_series(holdout_direct_predictions),
            "offset": load_prediction_series(holdout_offset_predictions),
        },
    }


def fmt(value: float, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}"


def strict_pass(row: dict[str, str]) -> bool:
    return (
        to_float(row["mae"]) <= config.ML_GOAL_MAX_MAE
        and to_float(row["rmse"]) <= config.ML_GOAL_MAX_RMSE
        and to_float(row["correlation"]) >= config.ML_GOAL_MIN_CORRELATION
    )


def compare_rows(
    direct_rows: list[dict[str, str]],
    offset_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    direct_by_station = {
        row["target_station_id"]: row
        for row in direct_rows
    }
    offset_by_station = {
        row["target_station_id"]: row
        for row in offset_rows
    }
    rows: list[dict[str, object]] = []

    for station_id in sorted(set(direct_by_station).intersection(offset_by_station)):
        direct = direct_by_station[station_id]
        offset = offset_by_station[station_id]
        direct_mae = to_float(direct["mae"])
        offset_mae = to_float(offset["mae"])
        direct_rmse = to_float(direct["rmse"])
        offset_rmse = to_float(offset["rmse"])
        direct_correlation = to_float(direct["correlation"])
        offset_correlation = to_float(offset["correlation"])

        rows.append({
            "target_station_id": station_id,
            "target_name": direct["target_name"],
            "test_rows": int(offset["test_rows"]),
            "direct_mae": direct_mae,
            "offset_mae": offset_mae,
            "mae_delta": offset_mae - direct_mae,
            "direct_rmse": direct_rmse,
            "offset_rmse": offset_rmse,
            "rmse_delta": offset_rmse - direct_rmse,
            "direct_correlation": direct_correlation,
            "offset_correlation": offset_correlation,
            "correlation_delta": offset_correlation - direct_correlation,
            "direct_strict": strict_pass(direct),
            "offset_strict": strict_pass(offset),
        })

    rows.sort(key=lambda row: row["mae_delta"])
    return rows


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    direct_mae = [row["direct_mae"] for row in rows]
    offset_mae = [row["offset_mae"] for row in rows]
    direct_rmse = [row["direct_rmse"] for row in rows]
    offset_rmse = [row["offset_rmse"] for row in rows]
    direct_correlation = [row["direct_correlation"] for row in rows]
    offset_correlation = [row["offset_correlation"] for row in rows]

    return {
        "station_count": len(rows),
        "direct_mean_mae": sum(direct_mae) / len(direct_mae),
        "offset_mean_mae": sum(offset_mae) / len(offset_mae),
        "direct_mean_rmse": sum(direct_rmse) / len(direct_rmse),
        "offset_mean_rmse": sum(offset_rmse) / len(offset_rmse),
        "direct_mean_correlation": sum(direct_correlation) / len(direct_correlation),
        "offset_mean_correlation": sum(offset_correlation) / len(offset_correlation),
        "improved_count": sum(1 for row in rows if row["mae_delta"] < 0),
        "regressed_count": sum(1 for row in rows if row["mae_delta"] > 0),
        "direct_strict_count": sum(1 for row in rows if row["direct_strict"]),
        "offset_strict_count": sum(1 for row in rows if row["offset_strict"]),
        "strict_gained_count": sum(
            1 for row in rows if not row["direct_strict"] and row["offset_strict"]
        ),
        "strict_lost_count": sum(
            1 for row in rows if row["direct_strict"] and not row["offset_strict"]
        ),
    }


def metric_card(label: str, value: str, note: str = "") -> str:
    return render_metric_card(
        label,
        value,
        note,
        label_class="card-label",
        value_class="card-value",
        note_class="note",
    )


def delta_class(value: float) -> str:
    if value < 0:
        return "good"
    if value > 0:
        return "bad"
    return "neutral"


def pass_text(value: bool) -> str:
    return "Pass" if value else "No"


def comparison_table(rows: list[dict[str, object]], limit: int | None = None) -> str:
    visible_rows = rows if limit is None else rows[:limit]
    body = []

    for row in visible_rows:
        body.append(f"""
        <tr>
          <td><code>{escape(row['target_station_id'])}</code></td>
          <td>{escape(row['target_name'])}</td>
          <td class="num">{escape(row['test_rows'])}</td>
          <td class="num">{fmt(row['direct_mae'])}</td>
          <td class="num">{fmt(row['offset_mae'])}</td>
          <td class="num {delta_class(row['mae_delta'])}">{fmt(row['mae_delta'], 3)}</td>
          <td class="num">{fmt(row['direct_rmse'])}</td>
          <td class="num">{fmt(row['offset_rmse'])}</td>
          <td class="num {delta_class(row['rmse_delta'])}">{fmt(row['rmse_delta'], 3)}</td>
          <td class="num">{fmt(row['direct_correlation'], 3)}</td>
          <td class="num">{fmt(row['offset_correlation'], 3)}</td>
          <td class="num good">{fmt(row['correlation_delta'], 4)}</td>
          <td>{pass_text(row['direct_strict'])}</td>
          <td>{pass_text(row['offset_strict'])}</td>
        </tr>
        """)

    return f"""
    <table>
      <thead>
        <tr>
          <th>Station</th>
          <th>Name</th>
          <th>Rows</th>
          <th>Direct MAE</th>
          <th>Offset MAE</th>
          <th>Delta</th>
          <th>Direct RMSE</th>
          <th>Offset RMSE</th>
          <th>Delta</th>
          <th>Direct r</th>
          <th>Offset r</th>
          <th>Delta</th>
          <th>Direct Strict</th>
          <th>Offset Strict</th>
        </tr>
      </thead>
      <tbody>
        {''.join(body)}
      </tbody>
    </table>
    """


def summary_cards(summary: dict[str, object]) -> str:
    mae_delta = summary["offset_mean_mae"] - summary["direct_mean_mae"]
    rmse_delta = summary["offset_mean_rmse"] - summary["direct_mean_rmse"]
    correlation_delta = (
        summary["offset_mean_correlation"] - summary["direct_mean_correlation"]
    )

    return f"""
    <div class="cards">
      {metric_card("Stations", str(summary["station_count"]))}
      {metric_card("Direct Mean MAE", f"{fmt(summary['direct_mean_mae'])} F")}
      {metric_card("Offset Mean MAE", f"{fmt(summary['offset_mean_mae'])} F", f"Delta {fmt(mae_delta, 3)} F")}
      {metric_card("Offset Improved", f"{summary['improved_count']}/{summary['station_count']}")}
      {metric_card("Direct Strict Passes", f"{summary['direct_strict_count']}/{summary['station_count']}")}
      {metric_card("Offset Strict Passes", f"{summary['offset_strict_count']}/{summary['station_count']}", f"+{summary['strict_gained_count']} gained, {summary['strict_lost_count']} lost")}
      {metric_card("RMSE Delta", f"{fmt(rmse_delta, 3)} F")}
      {metric_card("Mean r Delta", f"{fmt(correlation_delta, 4)}")}
    </div>
    """


def chart_panel(panel_id: str, title: str, note: str, default_mode: str) -> str:
    return f"""
    <div class="chart-panel" data-chart-panel="{escape(panel_id)}">
      <div class="chart-toolbar">
        <div>
          <h3>{escape(title)}</h3>
          <p>{escape(note)}</p>
        </div>
        <div class="chart-controls">
          <label>
            Model
            <select id="{escape(panel_id)}-model">
              <option value="offset" {"selected" if default_mode == "offset" else ""}>Offset mode</option>
              <option value="direct" {"selected" if default_mode == "direct" else ""}>Direct mode</option>
            </select>
          </label>
          <label>
            Station
            <select id="{escape(panel_id)}-station"></select>
          </label>
        </div>
      </div>
      <canvas id="{escape(panel_id)}-chart" width="1120" height="420"></canvas>
      <div class="chart-legend">
        <span><i class="legend-actual"></i> Actual recorded TAVG</span>
        <span><i class="legend-predicted"></i> Predicted TAVG</span>
      </div>
      <div id="{escape(panel_id)}-stats" class="chart-stats"></div>
    </div>
    """


def holdout_overlay_chart_panel() -> str:
    return """
    <div class="chart-panel" data-chart-panel="holdout-overlay">
      <div class="chart-toolbar">
        <div>
          <h3>8-Station Omission: Actual vs Direct vs Offset</h3>
          <p>Overlay the recorded daily average temperature against both prediction modes for each fully omitted station.</p>
        </div>
        <div class="chart-controls">
          <label>
            Station
            <select id="holdout-overlay-station"></select>
          </label>
        </div>
      </div>
      <canvas id="holdout-overlay-chart" width="1120" height="420"></canvas>
      <div class="chart-legend">
        <span><i class="legend-actual"></i> Actual recorded TAVG</span>
        <span><i class="legend-direct"></i> Direct prediction</span>
        <span><i class="legend-offset"></i> Offset prediction</span>
      </div>
      <div id="holdout-overlay-stats" class="chart-stats"></div>
    </div>
    """


def chart_script(chart_json: str) -> str:
    script = r"""
<script>
const chartData = __CHART_DATA__;

function stationLabel(station) {
  return `${station.station_id} | ${station.station_name}`;
}

function sortedStationIds(panelId, modelName) {
  return Object.keys(chartData[panelId][modelName]).sort((left, right) => {
    const leftStation = chartData[panelId][modelName][left];
    const rightStation = chartData[panelId][modelName][right];
    return stationLabel(leftStation).localeCompare(stationLabel(rightStation));
  });
}

function resizeCanvas(canvas) {
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(600, Math.floor(rect.width * ratio));
  canvas.height = Math.floor(420 * ratio);
  const context = canvas.getContext("2d");
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { width: rect.width, height: 420, context };
}

function mean(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function rmse(errors) {
  return Math.sqrt(mean(errors.map((error) => error * error)));
}

function correlation(actual, predicted) {
  if (actual.length < 2) return 0;
  const actualMean = mean(actual);
  const predictedMean = mean(predicted);
  let numerator = 0;
  let actualDenominator = 0;
  let predictedDenominator = 0;

  for (let index = 0; index < actual.length; index += 1) {
    const actualDelta = actual[index] - actualMean;
    const predictedDelta = predicted[index] - predictedMean;
    numerator += actualDelta * predictedDelta;
    actualDenominator += actualDelta * actualDelta;
    predictedDenominator += predictedDelta * predictedDelta;
  }

  if (actualDenominator === 0 || predictedDenominator === 0) return 0;
  return numerator / Math.sqrt(actualDenominator * predictedDenominator);
}

function drawLine(context, points, xScale, yScale, color, width) {
  context.beginPath();
  points.forEach((point, index) => {
    const x = xScale(index);
    const y = yScale(point);
    if (index === 0) context.moveTo(x, y);
    else context.lineTo(x, y);
  });
  context.strokeStyle = color;
  context.lineWidth = width;
  context.lineJoin = "round";
  context.lineCap = "round";
  context.stroke();
}

function drawChart(panelId) {
  const modelSelect = document.getElementById(`${panelId}-model`);
  const stationSelect = document.getElementById(`${panelId}-station`);
  const canvas = document.getElementById(`${panelId}-chart`);
  const stats = document.getElementById(`${panelId}-stats`);
  const modelName = modelSelect.value;
  const station = chartData[panelId][modelName][stationSelect.value];
  const points = station.points;
  const actual = points.map((point) => point.actual);
  const predicted = points.map((point) => point.predicted);
  const errors = points.map((point) => point.actual - point.predicted);
  const allValues = actual.concat(predicted);
  const minValue = Math.floor(Math.min(...allValues) - 4);
  const maxValue = Math.ceil(Math.max(...allValues) + 4);
  const { context, width, height } = resizeCanvas(canvas);
  const padding = { top: 26, right: 22, bottom: 48, left: 58 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const xScale = (index) => {
    if (points.length === 1) return padding.left + plotWidth / 2;
    return padding.left + (index / (points.length - 1)) * plotWidth;
  };
  const yScale = (value) => {
    return padding.top + ((maxValue - value) / (maxValue - minValue)) * plotHeight;
  };

  context.clearRect(0, 0, width, height);
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, width, height);

  context.strokeStyle = "#e1e7ef";
  context.lineWidth = 1;
  context.fillStyle = "#596475";
  context.font = "12px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
  context.textAlign = "right";
  context.textBaseline = "middle";

  const yTicks = 6;
  for (let tick = 0; tick <= yTicks; tick += 1) {
    const value = minValue + ((maxValue - minValue) * tick) / yTicks;
    const y = yScale(value);
    context.beginPath();
    context.moveTo(padding.left, y);
    context.lineTo(width - padding.right, y);
    context.stroke();
    context.fillText(`${value.toFixed(0)} F`, padding.left - 8, y);
  }

  context.textAlign = "center";
  context.textBaseline = "top";
  const xTickCount = Math.min(6, points.length);
  for (let tick = 0; tick < xTickCount; tick += 1) {
    const index = Math.round((tick / Math.max(1, xTickCount - 1)) * (points.length - 1));
    const x = xScale(index);
    context.beginPath();
    context.moveTo(x, padding.top);
    context.lineTo(x, height - padding.bottom);
    context.stroke();
    context.fillText(points[index].date, x, height - padding.bottom + 12);
  }

  drawLine(context, actual, xScale, yScale, "#1f2937", 2.2);
  drawLine(context, predicted, xScale, yScale, "#d1493f", 2.2);

  context.fillStyle = "#17202a";
  context.textAlign = "left";
  context.textBaseline = "top";
  context.font = "600 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
  context.fillText(stationLabel(station), padding.left, 8);

  const mae = mean(errors.map((error) => Math.abs(error)));
  const stationRmse = rmse(errors);
  const stationCorrelation = correlation(actual, predicted);
  const meanError = mean(errors);
  stats.innerHTML = [
    ["Rows", points.length],
    ["MAE", `${mae.toFixed(2)} F`],
    ["RMSE", `${stationRmse.toFixed(2)} F`],
    ["Correlation", stationCorrelation.toFixed(3)],
    ["Mean Error", `${meanError.toFixed(2)} F`],
  ].map(([label, value]) => `
    <div class="chart-stat">
      <div class="chart-stat-label">${label}</div>
      <div class="chart-stat-value">${value}</div>
    </div>
  `).join("");
}

function findMatchingPoint(pointsByDate, date) {
  return pointsByDate.get(date) || null;
}

function drawHoldoutOverlayChart() {
  const stationSelect = document.getElementById("holdout-overlay-station");
  const canvas = document.getElementById("holdout-overlay-chart");
  const stats = document.getElementById("holdout-overlay-stats");
  const stationId = stationSelect.value;
  const directStation = chartData.holdout.direct[stationId];
  const offsetStation = chartData.holdout.offset[stationId];
  const offsetByDate = new Map(offsetStation.points.map((point) => [point.date, point]));
  const points = directStation.points
    .map((directPoint) => {
      const offsetPoint = findMatchingPoint(offsetByDate, directPoint.date);
      if (!offsetPoint) return null;
      return {
        date: directPoint.date,
        actual: directPoint.actual,
        direct: directPoint.predicted,
        offset: offsetPoint.predicted,
      };
    })
    .filter(Boolean);
  const actual = points.map((point) => point.actual);
  const direct = points.map((point) => point.direct);
  const offset = points.map((point) => point.offset);
  const directErrors = points.map((point) => point.actual - point.direct);
  const offsetErrors = points.map((point) => point.actual - point.offset);
  const allValues = actual.concat(direct, offset);
  const minValue = Math.floor(Math.min(...allValues) - 4);
  const maxValue = Math.ceil(Math.max(...allValues) + 4);
  const { context, width, height } = resizeCanvas(canvas);
  const padding = { top: 26, right: 22, bottom: 48, left: 58 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const xScale = (index) => {
    if (points.length === 1) return padding.left + plotWidth / 2;
    return padding.left + (index / (points.length - 1)) * plotWidth;
  };
  const yScale = (value) => {
    return padding.top + ((maxValue - value) / (maxValue - minValue)) * plotHeight;
  };

  context.clearRect(0, 0, width, height);
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, width, height);
  context.strokeStyle = "#e1e7ef";
  context.lineWidth = 1;
  context.fillStyle = "#596475";
  context.font = "12px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
  context.textAlign = "right";
  context.textBaseline = "middle";

  const yTicks = 6;
  for (let tick = 0; tick <= yTicks; tick += 1) {
    const value = minValue + ((maxValue - minValue) * tick) / yTicks;
    const y = yScale(value);
    context.beginPath();
    context.moveTo(padding.left, y);
    context.lineTo(width - padding.right, y);
    context.stroke();
    context.fillText(`${value.toFixed(0)} F`, padding.left - 8, y);
  }

  context.textAlign = "center";
  context.textBaseline = "top";
  const xTickCount = Math.min(6, points.length);
  for (let tick = 0; tick < xTickCount; tick += 1) {
    const index = Math.round((tick / Math.max(1, xTickCount - 1)) * (points.length - 1));
    const x = xScale(index);
    context.beginPath();
    context.moveTo(x, padding.top);
    context.lineTo(x, height - padding.bottom);
    context.stroke();
    context.fillText(points[index].date, x, height - padding.bottom + 12);
  }

  drawLine(context, actual, xScale, yScale, "#1f2937", 2.4);
  drawLine(context, direct, xScale, yScale, "#2c7fb8", 2.0);
  drawLine(context, offset, xScale, yScale, "#d1493f", 2.0);

  context.fillStyle = "#17202a";
  context.textAlign = "left";
  context.textBaseline = "top";
  context.font = "600 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
  context.fillText(stationLabel(directStation), padding.left, 8);

  const directMae = mean(directErrors.map((error) => Math.abs(error)));
  const offsetMae = mean(offsetErrors.map((error) => Math.abs(error)));
  const directRmse = rmse(directErrors);
  const offsetRmse = rmse(offsetErrors);
  const directCorrelation = correlation(actual, direct);
  const offsetCorrelation = correlation(actual, offset);
  stats.innerHTML = [
    ["Rows", points.length],
    ["Direct MAE", `${directMae.toFixed(2)} F`],
    ["Offset MAE", `${offsetMae.toFixed(2)} F`],
    ["MAE Delta", `${(offsetMae - directMae).toFixed(2)} F`],
    ["Direct RMSE", `${directRmse.toFixed(2)} F`],
    ["Offset RMSE", `${offsetRmse.toFixed(2)} F`],
    ["Direct r", directCorrelation.toFixed(3)],
    ["Offset r", offsetCorrelation.toFixed(3)],
  ].map(([label, value]) => `
    <div class="chart-stat">
      <div class="chart-stat-label">${label}</div>
      <div class="chart-stat-value">${value}</div>
    </div>
  `).join("");
}

function initializeHoldoutOverlayPanel() {
  const stationSelect = document.getElementById("holdout-overlay-station");
  const stationIds = sortedStationIds("holdout", "offset");
  stationSelect.innerHTML = "";

  stationIds.forEach((stationId) => {
    const station = chartData.holdout.offset[stationId];
    const option = document.createElement("option");
    option.value = stationId;
    option.textContent = stationLabel(station);
    stationSelect.appendChild(option);
  });

  stationSelect.addEventListener("change", drawHoldoutOverlayChart);
  drawHoldoutOverlayChart();
}

function populateStations(panelId) {
  const modelSelect = document.getElementById(`${panelId}-model`);
  const stationSelect = document.getElementById(`${panelId}-station`);
  const currentStation = stationSelect.value;
  const stationIds = sortedStationIds(panelId, modelSelect.value);
  stationSelect.innerHTML = "";

  stationIds.forEach((stationId) => {
    const station = chartData[panelId][modelSelect.value][stationId];
    const option = document.createElement("option");
    option.value = stationId;
    option.textContent = stationLabel(station);
    stationSelect.appendChild(option);
  });

  if (stationIds.includes(currentStation)) {
    stationSelect.value = currentStation;
  } else if (stationIds.length > 0) {
    stationSelect.value = stationIds[0];
  }

  drawChart(panelId);
}

function initializePanel(panelId) {
  const modelSelect = document.getElementById(`${panelId}-model`);
  const stationSelect = document.getElementById(`${panelId}-station`);
  modelSelect.addEventListener("change", () => populateStations(panelId));
  stationSelect.addEventListener("change", () => drawChart(panelId));
  populateStations(panelId);
}

window.addEventListener("load", () => {
  initializePanel("temporal");
  initializePanel("holdout");
  initializeHoldoutOverlayPanel();
});

window.addEventListener("resize", () => {
  drawChart("temporal");
  drawChart("holdout");
  drawHoldoutOverlayChart();
});
</script>
"""
    return script.replace("__CHART_DATA__", chart_json)


def build_html(
    temporal_rows: list[dict[str, object]],
    temporal_summary: dict[str, object],
    holdout_rows: list[dict[str, object]],
    holdout_summary: dict[str, object],
    chart_payload: dict[str, dict[str, dict[str, object]]],
) -> str:
    temporal_worst = sorted(temporal_rows, key=lambda row: row["mae_delta"], reverse=True)
    holdout_worst = sorted(holdout_rows, key=lambda row: row["mae_delta"], reverse=True)
    chart_json = json.dumps(chart_payload)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Offset Mode Validation Report</title>
  <style>
    :root {{
      --ink: #17202a;
      --muted: #596475;
      --line: #d8dee8;
      --panel: #ffffff;
      --bg: #f5f7fb;
      --good: #126b45;
      --bad: #a43d31;
      --accent: #275f8f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
      line-height: 1.45;
    }}
    header {{
      padding: 32px 40px 20px;
      background: #ffffff;
      border-bottom: 1px solid var(--line);
    }}
    main {{
      max-width: 1380px;
      margin: 0 auto;
      padding: 28px 32px 48px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 30px;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 32px 0 12px;
      font-size: 22px;
      letter-spacing: 0;
    }}
    h3 {{
      margin: 24px 0 10px;
      font-size: 17px;
      letter-spacing: 0;
    }}
    p {{
      max-width: 980px;
      margin: 0 0 12px;
      color: var(--muted);
    }}
    .section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 22px;
      margin-bottom: 24px;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin: 16px 0 20px;
    }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: #fbfcff;
      min-height: 92px;
    }}
    .card-label {{
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 7px;
    }}
    .card-value {{
      font-size: 24px;
      font-weight: 700;
    }}
    .note {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 12px;
    }}
    .callout {{
      border-left: 4px solid var(--accent);
      background: #edf5fb;
      padding: 14px 16px;
      margin: 16px 0;
      border-radius: 0 8px 8px 0;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 1100px;
      background: white;
    }}
    th, td {{
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      white-space: nowrap;
      font-size: 13px;
    }}
    th {{
      position: sticky;
      top: 0;
      background: #eef2f7;
      color: #344054;
      font-weight: 700;
      z-index: 1;
    }}
    td.num, th.num {{
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}
    code {{
      font-family: "SFMono-Regular", Consolas, monospace;
      font-size: 12px;
    }}
    .good {{ color: var(--good); font-weight: 700; }}
    .bad {{ color: var(--bad); font-weight: 700; }}
    .neutral {{ color: var(--muted); }}
    .two-col {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 18px;
    }}
    .chart-panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      background: #fbfcff;
      margin: 18px 0 24px;
    }}
    .chart-toolbar {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 18px;
      align-items: end;
      margin-bottom: 12px;
    }}
    .chart-toolbar h3 {{
      margin-top: 0;
    }}
    .chart-controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      justify-content: flex-end;
    }}
    .chart-controls label {{
      display: grid;
      gap: 4px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }}
    .chart-controls select {{
      min-width: 190px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      background: white;
      color: var(--ink);
      font-size: 14px;
    }}
    canvas {{
      display: block;
      width: 100%;
      height: 420px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: white;
    }}
    .chart-legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      margin-top: 10px;
      color: var(--muted);
      font-size: 13px;
    }}
    .chart-legend i {{
      display: inline-block;
      width: 24px;
      height: 3px;
      margin-right: 6px;
      vertical-align: middle;
      border-radius: 999px;
    }}
    .legend-actual {{ background: #1f2937; }}
    .legend-predicted {{ background: #d1493f; }}
    .legend-direct {{ background: #2c7fb8; }}
    .legend-offset {{ background: #d1493f; }}
    .chart-stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
      margin-top: 12px;
    }}
    .chart-stat {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: white;
    }}
    .chart-stat-label {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }}
    .chart-stat-value {{
      font-size: 17px;
      font-weight: 700;
      font-variant-numeric: tabular-nums;
    }}
    @media (max-width: 900px) {{
      header {{ padding: 24px; }}
      main {{ padding: 20px; }}
      .two-col {{ grid-template-columns: 1fr; }}
      .chart-toolbar {{ grid-template-columns: 1fr; }}
      .chart-controls {{ justify-content: stretch; }}
      .chart-controls label {{ width: 100%; }}
      .chart-controls select {{ width: 100%; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Direct vs Offset Temperature Reconstruction</h1>
    <p>
      This report compares the original direct-temperature random forest against
      the new regional-baseline offset mode. Lower MAE/RMSE is better. Higher
      correlation is better.
    </p>
  </header>
  <main>
    <section class="section">
      <h2>Read This First</h2>
      <div class="callout">
        The offset model clearly improved the normal temporal validation, where
        the target station has historical training rows. It did not improve the
        much harder true station-omission test overall. That means offset mode
        helps calibration for known stations, but does not yet solve click-to-predict
        behavior for totally unseen stations.
      </div>
      <div class="two-col">
        <div>
          <h3>Temporal validation</h3>
          <p>
            Same stations appear in training through 2023, then the model predicts
            2024 onward. This asks whether the model can extend known stations
            into a later time period.
          </p>
        </div>
        <div>
          <h3>Station omission validation</h3>
          <p>
            Each test station is removed from all training roles: target, hub,
            and target-neighbor. This asks whether the model can predict a station
            it has never seen before.
          </p>
        </div>
      </div>
    </section>

    <section class="section">
      <h2>Temporal Validation: Direct vs Offset</h2>
      {summary_cards(temporal_summary)}
      <p>
        Offset mode improved MAE for most stations and increased strict ML goal
        passes without losing any stations that were already strict passes.
      </p>
      {chart_panel(
        "temporal",
        "Actual vs Predicted Temperature",
        "Compare 2024+ recorded daily average temperature against the selected model prediction for any temporal-validation station.",
        "offset",
      )}
      <h3>Best MAE Improvements</h3>
      <div class="table-wrap">{comparison_table(temporal_rows, 12)}</div>
      <h3>Largest MAE Regressions</h3>
      <div class="table-wrap">{comparison_table(temporal_worst, 12)}</div>
      <h3>All Temporal Stations</h3>
      <div class="table-wrap">{comparison_table(temporal_rows)}</div>
    </section>

    <section class="section">
      <h2>True Station-Omission Validation: Direct vs Offset</h2>
      {summary_cards(holdout_summary)}
      <p>
        This is the more important long-term test for click-to-predict. The offset
        model improved four held-out stations and regressed four held-out stations.
        Correlation increased across the board, but absolute MAE still failed the
        strict goal for every held-out station.
      </p>
      {chart_panel(
        "holdout",
        "Actual vs Predicted Temperature",
        "Compare recorded daily average temperature against predictions for stations that were fully omitted from model training.",
        "offset",
      )}
      {holdout_overlay_chart_panel()}
      <h3>All Held-Out Stations, Sorted By MAE Change</h3>
      <div class="table-wrap">{comparison_table(holdout_rows)}</div>
      <h3>Largest Holdout Regressions</h3>
      <div class="table-wrap">{comparison_table(holdout_worst)}</div>
    </section>

    <section class="section">
      <h2>Interpretation</h2>
      <p>
        The offset model is useful, but mostly for stations the model has already
        learned something about. In true station omission, the model often captures
        the day-to-day shape of temperature changes, but it still misses the local
        absolute calibration for unusual terrain or microclimate settings.
      </p>
      <p>
        The next improvement target is not simply more daily pattern recognition.
        It is learning the site-specific correction: how warm or cool the clicked
        point should be relative to the regional weather signal.
      </p>
    </section>
  </main>
  {chart_script(chart_json)}
</body>
</html>
"""


def main() -> None:
    arguments = parse_arguments()
    temporal_rows = compare_rows(
        read_rows(arguments.temporal_direct),
        read_rows(arguments.temporal_offset),
    )
    holdout_rows = compare_rows(
        read_rows(arguments.holdout_direct),
        read_rows(arguments.holdout_offset),
    )
    temporal_summary = summarize(temporal_rows)
    holdout_summary = summarize(holdout_rows)
    chart_payload = build_chart_payload(
        arguments.temporal_direct_predictions,
        arguments.temporal_offset_predictions,
        arguments.holdout_direct_predictions,
        arguments.holdout_offset_predictions,
    )

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        build_html(
            temporal_rows,
            temporal_summary,
            holdout_rows,
            holdout_summary,
            chart_payload,
        )
    )

    print("Offset mode report complete")
    print("---------------------------")
    print(f"Temporal stations: {temporal_summary['station_count']}")
    print(f"Temporal improved: {temporal_summary['improved_count']}")
    print(f"Temporal strict passes: {temporal_summary['offset_strict_count']}")
    print(f"Holdout stations: {holdout_summary['station_count']}")
    print(f"Holdout improved: {holdout_summary['improved_count']}")
    print(f"Holdout strict passes: {holdout_summary['offset_strict_count']}")
    print(f"HTML: {arguments.output}")


if __name__ == "__main__":
    main()
