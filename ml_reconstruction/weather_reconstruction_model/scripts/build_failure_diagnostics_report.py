from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

import config
from common.csv_utils import CsvRow, read_csv_rows, write_csv_rows
from common.metrics import calculate_mae, calculate_rmse, mean
from common.model_runs import load_model_run, resolve_model_run
from common.number_utils import to_optional_float
from common.reporting import escape_html as escape
from common.reporting import render_html_table, render_metric_card, trusted_html


DEFAULT_MODEL_RUN_ID = (
    "option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain_"
    "offset_terrain_standard_random_forest"
)
DEFAULT_GENERAL_TABLE = (
    config.GENERAL_TABLE_DIR
    / "option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain.csv"
)

SEASON_BY_MONTH = {
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
SEASONS = ["Winter", "Spring", "Summer", "Fall"]
STATION_LIST_FIELDNAMES = [
    "station_id",
    "station_name",
    "latitude",
    "longitude",
    "elevation_m",
    "mae_f",
    "rmse_f",
    "correlation",
    "test_rows",
    "mean_bias_f",
    "bias_interpretation",
    "p90_abs_error_f",
    "max_abs_error_f",
    "worst_season",
    "worst_season_mae_f",
    "worst_month",
    "worst_month_mae_f",
    "support_score",
    "representativeness_score",
    "top_representative_anchor",
    "top_anchor_distance_km",
    "top_anchor_elevation_delta_m",
    "nearest_validation_station_id",
    "nearest_validation_distance_km",
    "research_focus",
]


@dataclass
class ErrorBucket:
    actual: list[float] = field(default_factory=list)
    predicted: list[float] = field(default_factory=list)
    errors: list[float] = field(default_factory=list)
    abs_errors: list[float] = field(default_factory=list)

    def add(self, actual: float, predicted: float) -> None:
        error = actual - predicted
        self.actual.append(actual)
        self.predicted.append(predicted)
        self.errors.append(error)
        self.abs_errors.append(abs(error))

    def summary(self) -> dict[str, float | int | None]:
        if not self.actual:
            return {
                "rows": 0,
                "mae": None,
                "rmse": None,
                "bias": None,
                "p90_abs_error": None,
                "max_abs_error": None,
                "actual_mean": None,
                "predicted_mean": None,
            }

        return {
            "rows": len(self.actual),
            "mae": calculate_mae(self.actual, self.predicted),
            "rmse": calculate_rmse(self.actual, self.predicted),
            "bias": mean(self.errors),
            "p90_abs_error": percentile(self.abs_errors, 0.90),
            "max_abs_error": max(self.abs_errors),
            "actual_mean": mean(self.actual),
            "predicted_mean": mean(self.predicted),
        }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build failure diagnostics for the worst model validation stations."
    )
    parser.add_argument(
        "--model-run-id",
        default=DEFAULT_MODEL_RUN_ID,
        help="Model-run directory name to inspect.",
    )
    parser.add_argument(
        "--model-run-root",
        type=Path,
        default=config.MODEL_RUN_DIR,
        help="Root directory containing model-run folders.",
    )
    parser.add_argument(
        "--general-table",
        type=Path,
        default=DEFAULT_GENERAL_TABLE,
        help="General training table used to recover predictor metadata.",
    )
    parser.add_argument(
        "--worst-count",
        type=int,
        default=10,
        help="Number of highest-MAE validation stations to include.",
    )
    parser.add_argument(
        "--output-html",
        type=Path,
        default=None,
        help="Optional HTML output path. Defaults to the selected model-run folder.",
    )
    parser.add_argument(
        "--output-stations",
        type=Path,
        default=None,
        help="Optional CSV output path for the selected research-station list.",
    )
    return parser.parse_args()


def fmt(value: object, decimals: int = 2, suffix: str = "") -> str:
    numeric_value = to_optional_float(value)
    if numeric_value is None or math.isnan(numeric_value):
        return "N/A"
    return f"{numeric_value:.{decimals}f}{suffix}"


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None

    sorted_values = sorted(values)
    position = (len(sorted_values) - 1) * percentile_value
    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return sorted_values[int(position)]

    lower_value = sorted_values[lower]
    upper_value = sorted_values[upper]
    fraction = position - lower
    return lower_value + (upper_value - lower_value) * fraction


def parse_month(date_text: str) -> int:
    return int(date_text.split("-")[1])


def bias_interpretation(bias: float | None) -> str:
    if bias is None:
        return "unknown"
    if bias > 0.25:
        return "predicted too cold"
    if bias < -0.25:
        return "predicted too warm"
    return "low net bias"


def load_worst_station_rows(
    calibration_rows: list[CsvRow],
    worst_count: int,
) -> list[CsvRow]:
    rows = sorted(
        calibration_rows,
        key=lambda row: to_optional_float(row.get("observed_mae_f")) or 0.0,
        reverse=True,
    )
    return rows[:worst_count]


def load_representativeness_by_station(model_run_root: Path) -> dict[str, CsvRow]:
    file_path = model_run_root / "representativeness_scores.csv"
    if not file_path.exists():
        return {}

    return {
        row["target_station_id"]: row
        for row in read_csv_rows(file_path)
    }


def collect_error_diagnostics(
    prediction_rows: list[CsvRow],
    station_ids: set[str],
) -> dict[str, dict[str, object]]:
    station_buckets = {station_id: ErrorBucket() for station_id in station_ids}
    seasonal_buckets = {
        station_id: {season: ErrorBucket() for season in SEASONS}
        for station_id in station_ids
    }
    monthly_buckets = {
        station_id: {month: ErrorBucket() for month in range(1, 13)}
        for station_id in station_ids
    }

    for row in prediction_rows:
        station_id = row["target_station_id"]
        if station_id not in station_ids:
            continue

        actual = float(row["actual_tavg"])
        predicted = float(row["predicted_tavg"])
        month = parse_month(row["date"])
        season = SEASON_BY_MONTH[month]
        station_buckets[station_id].add(actual, predicted)
        seasonal_buckets[station_id][season].add(actual, predicted)
        monthly_buckets[station_id][month].add(actual, predicted)

    output = {}
    for station_id in station_ids:
        seasonal = {
            season: seasonal_buckets[station_id][season].summary()
            for season in SEASONS
        }
        monthly = {
            month: monthly_buckets[station_id][month].summary()
            for month in range(1, 13)
        }
        output[station_id] = {
            "overall": station_buckets[station_id].summary(),
            "seasonal": seasonal,
            "monthly": monthly,
        }

    return output


def stream_predictor_metadata(
    general_table: Path,
    station_ids: set[str],
) -> dict[str, dict[str, object]]:
    metadata = {}

    with general_table.open("r", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            station_id = row["target_station_id"]
            if station_id not in station_ids or station_id in metadata:
                continue

            metadata[station_id] = {
                "target": {
                    "latitude": row.get("target_latitude", ""),
                    "longitude": row.get("target_longitude", ""),
                    "elevation_m": row.get("target_elevation_m", ""),
                    "dem_elevation_m": row.get("target_dem_elevation_m", ""),
                    "slope_degrees": row.get("target_slope_degrees", ""),
                    "local_relief_m": row.get("target_local_relief_m", ""),
                    "local_relief_m_r3000m": row.get(
                        "target_local_relief_m_r3000m",
                        "",
                    ),
                    "terrain_position_index_m": row.get(
                        "target_terrain_position_index_m",
                        "",
                    ),
                },
                "hubs": collect_predictors(row, "hub", 5),
                "target_neighbors": collect_predictors(row, "target_neighbor", 10),
            }

            if len(metadata) == len(station_ids):
                break

    missing = sorted(station_ids - set(metadata))
    if missing:
        raise ValueError(
            "Could not find selected predictor metadata for station(s): "
            + ", ".join(missing)
        )

    return metadata


def collect_predictors(row: CsvRow, prefix: str, count: int) -> list[dict[str, object]]:
    predictors = []

    for index in range(1, count + 1):
        key = f"{prefix}_{index}"
        station_id = row.get(f"{key}_station_id", "").strip()
        if not station_id:
            continue

        predictors.append({
            "rank": index,
            "station_id": station_id,
            "name": row.get(f"{key}_name", ""),
            "distance_km": row.get(f"{key}_distance_km", ""),
            "elevation_difference_m": row.get(f"{key}_elevation_difference_m", ""),
            "overlap_percent": row.get(f"{key}_overlap_percent", ""),
            "dem_elevation_delta_m": row.get(f"{key}_dem_elevation_delta_m", ""),
            "abs_dem_elevation_delta_m": row.get(f"{key}_abs_dem_elevation_delta_m", ""),
            "local_relief_delta_m": row.get(f"{key}_local_relief_delta_m", ""),
            "abs_local_relief_delta_m": row.get(f"{key}_abs_local_relief_delta_m", ""),
            "terrain_position_delta_m": row.get(f"{key}_terrain_position_delta_m", ""),
            "abs_terrain_position_delta_m": row.get(
                f"{key}_abs_terrain_position_delta_m",
                "",
            ),
            "aspect_similarity": row.get(f"{key}_aspect_similarity", ""),
        })

    return predictors


def worst_season(seasonal: Mapping[str, Mapping[str, object]]) -> tuple[str, float | None]:
    candidates = [
        (season, to_optional_float(values.get("mae")))
        for season, values in seasonal.items()
    ]
    candidates = [(season, mae) for season, mae in candidates if mae is not None]
    if not candidates:
        return "N/A", None
    return max(candidates, key=lambda item: item[1])


def worst_month(monthly: Mapping[int, Mapping[str, object]]) -> tuple[int | None, float | None]:
    candidates = [
        (month, to_optional_float(values.get("mae")))
        for month, values in monthly.items()
    ]
    candidates = [(month, mae) for month, mae in candidates if mae is not None]
    if not candidates:
        return None, None
    return max(candidates, key=lambda item: item[1])


def research_focus(
    station_row: CsvRow,
    diagnostics: Mapping[str, object],
    representativeness_row: CsvRow | None,
) -> str:
    overall = diagnostics["overall"]
    seasonal = diagnostics["seasonal"]
    worst_season_name, worst_season_mae = worst_season(seasonal)
    bias = to_optional_float(overall.get("bias"))
    notes = []

    if bias is not None and abs(bias) >= 1.0:
        notes.append(bias_interpretation(bias))

    if worst_season_mae is not None:
        notes.append(f"{worst_season_name.lower()} error peak")

    support_score = to_optional_float(station_row.get("support_score"))
    if support_score is not None and support_score >= 85:
        notes.append("high-support failure")

    if representativeness_row is not None:
        representativeness_score = to_optional_float(
            representativeness_row.get("representativeness_score")
        )
        if representativeness_score is not None and representativeness_score >= 80:
            notes.append("high-representativeness failure")

    return "; ".join(notes) if notes else "general hard case"


def build_station_list_rows(
    worst_rows: list[CsvRow],
    diagnostics_by_station: Mapping[str, Mapping[str, object]],
    representativeness_by_station: Mapping[str, CsvRow],
) -> list[dict[str, object]]:
    rows = []

    for station_row in worst_rows:
        station_id = station_row["target_station_id"]
        diagnostics = diagnostics_by_station[station_id]
        overall = diagnostics["overall"]
        seasonal = diagnostics["seasonal"]
        monthly = diagnostics["monthly"]
        worst_season_name, worst_season_mae = worst_season(seasonal)
        worst_month_number, worst_month_mae = worst_month(monthly)
        representativeness = representativeness_by_station.get(station_id, {})
        bias = to_optional_float(overall.get("bias"))

        rows.append({
            "station_id": station_id,
            "station_name": station_row.get("target_name", ""),
            "latitude": station_row.get("latitude", ""),
            "longitude": station_row.get("longitude", ""),
            "elevation_m": station_row.get("elevation_m", ""),
            "mae_f": station_row.get("observed_mae_f", ""),
            "rmse_f": station_row.get("observed_rmse_f", ""),
            "correlation": station_row.get("observed_correlation", ""),
            "test_rows": station_row.get("test_rows", ""),
            "mean_bias_f": fmt(bias, 3),
            "bias_interpretation": bias_interpretation(bias),
            "p90_abs_error_f": fmt(overall.get("p90_abs_error"), 3),
            "max_abs_error_f": fmt(overall.get("max_abs_error"), 3),
            "worst_season": worst_season_name,
            "worst_season_mae_f": fmt(worst_season_mae, 3),
            "worst_month": worst_month_number or "",
            "worst_month_mae_f": fmt(worst_month_mae, 3),
            "support_score": station_row.get("support_score", ""),
            "representativeness_score": representativeness.get(
                "representativeness_score",
                "",
            ),
            "top_representative_anchor": representativeness.get(
                "top_anchor_station_id",
                "",
            ),
            "top_anchor_distance_km": representativeness.get(
                "top_anchor_distance_km",
                "",
            ),
            "top_anchor_elevation_delta_m": representativeness.get(
                "top_anchor_elevation_delta_m",
                "",
            ),
            "nearest_validation_station_id": station_row.get(
                "nearest_validation_station_id",
                "",
            ),
            "nearest_validation_distance_km": station_row.get(
                "nearest_validation_distance_km",
                "",
            ),
            "research_focus": research_focus(
                station_row,
                diagnostics,
                representativeness if representativeness else None,
            ),
        })

    return rows


def metrics_cards(station_row: CsvRow, diagnostics: Mapping[str, object], representativeness: CsvRow) -> str:
    overall = diagnostics["overall"]
    bias = to_optional_float(overall.get("bias"))
    cards = [
        ("MAE", fmt(station_row.get("observed_mae_f"), 2, " F")),
        ("RMSE", fmt(station_row.get("observed_rmse_f"), 2, " F")),
        ("Mean Bias", f"{fmt(bias, 2, ' F')} ({bias_interpretation(bias)})"),
        ("P90 Abs Error", fmt(overall.get("p90_abs_error"), 2, " F")),
        ("Support", fmt(station_row.get("support_score"), 1)),
        ("Represent.", fmt(representativeness.get("representativeness_score"), 1)),
    ]
    return (
        "<div class=\"mini-grid\">"
        + "".join(
            render_metric_card(
                label,
                value,
                card_class="mini",
                label_class="mini-label",
                value_class="mini-value",
            )
            for label, value in cards
        )
        + "</div>"
    )


def season_table(diagnostics: Mapping[str, object]) -> str:
    seasonal = diagnostics["seasonal"]
    rows = []
    for season in SEASONS:
        values = seasonal[season]
        rows.append([
            season,
            values.get("rows"),
            fmt(values.get("mae"), 2),
            fmt(values.get("rmse"), 2),
            fmt(values.get("bias"), 2),
        ])
    return render_html_table(["Season", "Rows", "MAE F", "RMSE F", "Bias F"], rows)


def month_table(diagnostics: Mapping[str, object]) -> str:
    monthly = diagnostics["monthly"]
    rows = []
    for month in range(1, 13):
        values = monthly[month]
        rows.append([
            month,
            values.get("rows"),
            fmt(values.get("mae"), 2),
            fmt(values.get("bias"), 2),
        ])
    return render_html_table(["Month", "Rows", "MAE F", "Bias F"], rows)


def predictor_table(predictors: list[Mapping[str, object]], title: str) -> str:
    rows = []
    for predictor in predictors:
        rows.append([
            predictor.get("rank"),
            trusted_html(f"<code>{escape(predictor.get('station_id', ''))}</code>"),
            predictor.get("name", ""),
            fmt(predictor.get("distance_km"), 1),
            fmt(predictor.get("elevation_difference_m"), 1),
            fmt(predictor.get("overlap_percent"), 1),
            fmt(predictor.get("abs_dem_elevation_delta_m"), 1),
            fmt(predictor.get("abs_local_relief_delta_m"), 1),
            fmt(predictor.get("abs_terrain_position_delta_m"), 1),
        ])
    return (
        f"<h4>{escape(title)}</h4>"
        + render_html_table(
            [
                "#",
                "Station",
                "Name",
                "Dist km",
                "Elev diff m",
                "Overlap %",
                "DEM elev delta m",
                "Relief delta m",
                "TPI delta m",
            ],
            rows,
        )
    )


def top_anchor_block(representativeness: CsvRow) -> str:
    top_anchor_json = representativeness.get("top_anchor_ids", "[]")
    try:
        anchors = json.loads(top_anchor_json)
    except json.JSONDecodeError:
        anchors = []

    rows = []
    for anchor in anchors[:5]:
        rows.append([
            trusted_html(f"<code>{escape(anchor.get('stationId', ''))}</code>"),
            anchor.get("role", ""),
            fmt(anchor.get("similarity"), 1),
            fmt(anchor.get("distanceKm"), 1),
            fmt(anchor.get("elevationDeltaM"), 1),
        ])

    return (
        "<h4>Top Representative Anchors</h4>"
        + render_html_table(
            ["Anchor", "Role", "Similarity", "Distance km", "Elev delta m"],
            rows,
        )
    )


def target_terrain_table(target: Mapping[str, object]) -> str:
    return render_html_table(
        ["Terrain feature", "Value"],
        [
            ["DEM elevation m", target.get("dem_elevation_m", "")],
            ["Slope degrees", target.get("slope_degrees", "")],
            ["Local relief m", target.get("local_relief_m", "")],
            ["3 km local relief m", target.get("local_relief_m_r3000m", "")],
            ["Terrain position index m", target.get("terrain_position_index_m", "")],
        ],
    )


def station_panel(
    station_row: CsvRow,
    diagnostics: Mapping[str, object],
    representativeness: CsvRow,
    predictor_metadata: Mapping[str, object],
) -> str:
    station_id = station_row["target_station_id"]
    target = predictor_metadata["target"]
    focus = research_focus(station_row, diagnostics, representativeness)

    return f"""
    <section class="station-panel">
      <h3><code>{escape(station_id)}</code> - {escape(station_row.get("target_name", ""))}</h3>
      <p class="muted">
        Location: {escape(station_row.get("latitude", ""))}, {escape(station_row.get("longitude", ""))};
        elevation {escape(station_row.get("elevation_m", ""))} m.
        Research focus: <strong>{escape(focus)}</strong>.
      </p>
      {metrics_cards(station_row, diagnostics, representativeness)}
      <div class="two-col">
        <div>
          <h4>Seasonal Error</h4>
          {season_table(diagnostics)}
        </div>
        <div>
          <h4>Monthly Error</h4>
          {month_table(diagnostics)}
        </div>
      </div>
      <div class="two-col">
        <div>
          <h4>Target Terrain Snapshot</h4>
          {target_terrain_table(target)}
        </div>
        <div>
          {top_anchor_block(representativeness)}
        </div>
      </div>
      {predictor_table(predictor_metadata["hubs"], "Selected Hub Predictors")}
      {predictor_table(predictor_metadata["target_neighbors"][:5], "Nearest Target-Neighbor Predictors")}
    </section>
    """


def station_list_table(rows: list[Mapping[str, object]]) -> str:
    return render_html_table(
        [
            "Station",
            "Name",
            "Lat",
            "Lon",
            "MAE F",
            "Bias F",
            "Worst season",
            "Support",
            "Represent.",
            "Research focus",
        ],
        [
            [
                trusted_html(f"<code>{escape(row['station_id'])}</code>"),
                row["station_name"],
                row["latitude"],
                row["longitude"],
                row["mae_f"],
                row["mean_bias_f"],
                row["worst_season"],
                row["support_score"],
                row["representativeness_score"],
                row["research_focus"],
            ]
            for row in rows
        ],
    )


def render_html(
    model_run_id: str,
    station_list_rows: list[Mapping[str, object]],
    worst_rows: list[CsvRow],
    diagnostics_by_station: Mapping[str, Mapping[str, object]],
    representativeness_by_station: Mapping[str, CsvRow],
    predictor_metadata_by_station: Mapping[str, Mapping[str, object]],
) -> str:
    panels = []
    for station_row in worst_rows:
        station_id = station_row["target_station_id"]
        panels.append(
            station_panel(
                station_row,
                diagnostics_by_station[station_id],
                representativeness_by_station.get(station_id, {}),
                predictor_metadata_by_station[station_id],
            )
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Failure Diagnostics - {escape(model_run_id)}</title>
  <style>
    :root {{
      --bg: #f8fafc;
      --text: #111827;
      --muted: #64748b;
      --line: #dbe3ef;
      --panel: #ffffff;
      --accent: #2563eb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    header {{
      padding: 28px 36px 22px;
      background: #ffffff;
      border-bottom: 1px solid var(--line);
    }}
    main {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 24px 36px 42px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 28px;
      line-height: 1.2;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 28px 0 12px;
      font-size: 20px;
      letter-spacing: 0;
    }}
    h3 {{
      margin: 0 0 10px;
      font-size: 18px;
      letter-spacing: 0;
    }}
    h4 {{
      margin: 16px 0 8px;
      font-size: 14px;
      letter-spacing: 0;
    }}
    p, li {{
      line-height: 1.5;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.92em;
    }}
    .muted {{ color: var(--muted); }}
    .note {{
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      border-radius: 8px;
      padding: 14px 16px;
      margin: 18px 0;
    }}
    .station-panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      margin: 18px 0;
    }}
    .mini-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
      margin: 12px 0 14px;
    }}
    .mini {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #f8fafc;
    }}
    .mini-label {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }}
    .mini-value {{
      font-size: 16px;
      font-weight: 700;
      line-height: 1.25;
    }}
    .two-col {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
      gap: 16px;
      align-items: start;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    th, td {{
      padding: 8px 9px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      font-size: 12px;
      line-height: 1.35;
    }}
    th {{
      background: #f1f5f9;
      color: #334155;
      font-weight: 700;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    @media (max-width: 720px) {{
      header, main {{
        padding-left: 16px;
        padding-right: 16px;
      }}
      .two-col {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Failure Diagnostics</h1>
    <p class="muted"><code>{escape(model_run_id)}</code></p>
  </header>
  <main>
    <section class="note">
      <strong>What this report does:</strong> zooms into the worst validation stations and asks why they failed despite station support. It shows seasonal error, bias, selected predictors, terrain context, and representative anchors.
    </section>

    <h2>Research Station List</h2>
    {station_list_table(station_list_rows)}

    <h2>Station Diagnostics</h2>
    {"".join(panels)}
  </main>
</body>
</html>
"""


def main() -> None:
    arguments = parse_arguments()
    paths = resolve_model_run(arguments.model_run_root, arguments.model_run_id)
    model_run = load_model_run(paths)
    output_html = arguments.output_html or (paths.root / "failure_diagnostics.html")
    output_stations = arguments.output_stations or (paths.root / "failure_station_list.csv")
    worst_rows = load_worst_station_rows(
        model_run["calibration_points"],
        arguments.worst_count,
    )
    station_ids = {row["target_station_id"] for row in worst_rows}
    diagnostics = collect_error_diagnostics(
        model_run["validation_predictions"],
        station_ids,
    )
    representativeness_by_station = load_representativeness_by_station(paths.root)
    predictor_metadata = stream_predictor_metadata(
        arguments.general_table,
        station_ids,
    )
    station_list_rows = build_station_list_rows(
        worst_rows,
        diagnostics,
        representativeness_by_station,
    )

    write_csv_rows(output_stations, station_list_rows, STATION_LIST_FIELDNAMES)
    output_html.write_text(
        render_html(
            arguments.model_run_id,
            station_list_rows,
            worst_rows,
            diagnostics,
            representativeness_by_station,
            predictor_metadata,
        )
    )

    print(f"Failure diagnostics report: {output_html}")
    print(f"Research station list: {output_stations}")
    print("Worst stations:")
    for row in station_list_rows:
        print(
            f"- {row['station_id']} {row['station_name']}: "
            f"MAE {row['mae_f']} F, bias {row['mean_bias_f']} F, "
            f"focus {row['research_focus']}"
        )


if __name__ == "__main__":
    main()
