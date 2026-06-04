from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import config
from common.csv_utils import CsvRow, read_csv_rows
from common.model_runs import load_model_run, resolve_model_run
from common.number_utils import to_optional_float
from common.reporting import escape_html as escape
from common.reporting import render_metric_card
from common.reporting import render_html_table, trusted_html


DEFAULT_MODEL_RUN_ID = (
    "option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain_"
    "offset_terrain_standard_random_forest"
)

RELATIONSHIPS = [
    {
        "column": "support_score",
        "label": "Support score",
        "expected": "negative",
        "plain": "Higher support should usually mean lower error.",
    },
    {
        "column": "component_station_coverage",
        "label": "Station coverage component",
        "expected": "negative",
        "plain": "More target-station coverage should usually mean lower error.",
    },
    {
        "column": "component_hub_support",
        "label": "Hub support component",
        "expected": "negative",
        "plain": "More hub support should usually mean lower error.",
    },
    {
        "column": "component_extrapolation_risk",
        "label": "Extrapolation support component",
        "expected": "negative",
        "plain": "Less extrapolation risk should usually mean lower error.",
    },
    {
        "column": "nearest_other_target_distance_km",
        "label": "Nearest other target station distance",
        "expected": "positive",
        "plain": "Farther station support should usually mean higher error.",
    },
    {
        "column": "nearest_hub_distance_km",
        "label": "Nearest hub distance",
        "expected": "positive",
        "plain": "Farther hub support should usually mean higher error.",
    },
    {
        "column": "nearest_validation_distance_km",
        "label": "Nearest validation station distance",
        "expected": "positive",
        "plain": "Farther validation evidence should usually mean higher uncertainty.",
    },
    {
        "column": "validation_stations_within_150km",
        "label": "Validation stations within 150 km",
        "expected": "negative",
        "plain": "More nearby validation evidence should usually mean lower uncertainty.",
    },
    {
        "column": "hubs_within_100km",
        "label": "Hubs within 100 km",
        "expected": "negative",
        "plain": "More nearby hubs should usually mean lower error.",
    },
    {
        "column": "local_relief_m_r3000m",
        "label": "3 km local relief",
        "expected": "positive",
        "plain": "More rugged terrain may mean higher error.",
    },
]

PLOT_COLUMNS = [
    "support_score",
    "nearest_validation_distance_km",
    "hubs_within_100km",
    "local_relief_m_r3000m",
]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a quick HTML audit report for model-run calibration points."
    )
    parser.add_argument(
        "--model-run-id",
        default=DEFAULT_MODEL_RUN_ID,
        help="Model-run directory name to audit.",
    )
    parser.add_argument(
        "--model-run-root",
        type=Path,
        default=config.MODEL_RUN_DIR,
        help="Root directory containing model-run folders.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional HTML output path. Defaults to the selected model-run folder.",
    )
    return parser.parse_args()


def fmt(value: float | None, decimals: int = 2, suffix: str = "") -> str:
    if value is None or math.isnan(value):
        return "N/A"
    return f"{value:.{decimals}f}{suffix}"


def numeric(row: CsvRow, column: str) -> float | None:
    return to_optional_float(row.get(column))


def numeric_pairs(rows: list[CsvRow], x_column: str, y_column: str) -> list[tuple[float, float]]:
    pairs = []

    for row in rows:
        x_value = numeric(row, x_column)
        y_value = numeric(row, y_column)
        if x_value is not None and y_value is not None:
            pairs.append((x_value, y_value))

    return pairs


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


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


def correlation(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 2:
        return None

    x_values = [pair[0] for pair in pairs]
    y_values = [pair[1] for pair in pairs]
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    numerator = sum(
        (x_value - x_mean) * (y_value - y_mean)
        for x_value, y_value in pairs
    )
    x_denominator = math.sqrt(sum((x_value - x_mean) ** 2 for x_value in x_values))
    y_denominator = math.sqrt(sum((y_value - y_mean) ** 2 for y_value in y_values))

    if x_denominator == 0 or y_denominator == 0:
        return None

    return numerator / (x_denominator * y_denominator)


def relationship_strength(correlation_value: float | None) -> str:
    if correlation_value is None:
        return "N/A"

    strength = abs(correlation_value)
    if strength >= 0.60:
        return "strong"
    if strength >= 0.35:
        return "moderate"
    if strength >= 0.15:
        return "weak"
    return "very weak"


def relationship_direction(correlation_value: float | None) -> str:
    if correlation_value is None:
        return "N/A"
    if correlation_value > 0.02:
        return "higher value, higher error"
    if correlation_value < -0.02:
        return "higher value, lower error"
    return "flat"


def matches_expected(correlation_value: float | None, expected: str) -> str:
    if correlation_value is None:
        return "unknown"
    if abs(correlation_value) < 0.15:
        return "weak/unclear"
    if expected == "positive" and correlation_value > 0:
        return "matches"
    if expected == "negative" and correlation_value < 0:
        return "matches"
    return "surprising"


def bucket_summary(rows: list[CsvRow], column: str) -> dict[str, object]:
    valid_rows = [
        row
        for row in rows
        if numeric(row, column) is not None and numeric(row, "observed_mae_f") is not None
    ]
    valid_rows.sort(key=lambda row: numeric(row, column) or 0.0)

    if len(valid_rows) < 8:
        return {}

    bucket_size = len(valid_rows) // 4
    low_bucket = valid_rows[:bucket_size]
    high_bucket = valid_rows[-bucket_size:]
    low_values = [numeric(row, "observed_mae_f") for row in low_bucket]
    high_values = [numeric(row, "observed_mae_f") for row in high_bucket]

    return {
        "lowFeatureMeanMae": mean([value for value in low_values if value is not None]),
        "highFeatureMeanMae": mean([value for value in high_values if value is not None]),
        "lowFeatureRange": (
            numeric(low_bucket[0], column),
            numeric(low_bucket[-1], column),
        ),
        "highFeatureRange": (
            numeric(high_bucket[0], column),
            numeric(high_bucket[-1], column),
        ),
    }


def missing_counts(rows: list[CsvRow]) -> list[tuple[str, int]]:
    if not rows:
        return []

    output = []
    for column in rows[0].keys():
        missing = sum(1 for row in rows if not str(row.get(column, "")).strip())
        if missing:
            output.append((column, missing))
    output.sort(key=lambda item: (-item[1], item[0]))
    return output


def station_table(rows: list[CsvRow]) -> str:
    table_rows = [
        [
            trusted_html(f"<code>{escape(row.get('target_station_id', ''))}</code>"),
            row.get("target_name", ""),
            row.get("observed_mae_f", ""),
            row.get("observed_rmse_f", ""),
            row.get("support_score", ""),
            row.get("nearest_validation_distance_km", ""),
            row.get("hubs_within_100km", ""),
            row.get("local_relief_m_r3000m", ""),
        ]
        for row in rows
    ]
    return render_html_table(
        [
            "Station",
            "Name",
            "MAE F",
            "RMSE F",
            "Support",
            "Nearest validation km",
            "Hubs 100 km",
            "Relief 3 km m",
        ],
        table_rows,
    )


def relationship_rows(rows: list[CsvRow]) -> tuple[str, list[dict[str, object]]]:
    summaries = []
    table_rows = []

    for relationship in RELATIONSHIPS:
        pairs = numeric_pairs(rows, relationship["column"], "observed_mae_f")
        r_value = correlation(pairs)
        bucket = bucket_summary(rows, relationship["column"])
        summaries.append({
            **relationship,
            "correlation": r_value,
            "strength": relationship_strength(r_value),
            "direction": relationship_direction(r_value),
            "matches": matches_expected(r_value, relationship["expected"]),
            "bucket": bucket,
            "pairs": len(pairs),
        })
        low_mean = bucket.get("lowFeatureMeanMae") if bucket else None
        high_mean = bucket.get("highFeatureMeanMae") if bucket else None
        table_rows.append([
            relationship["label"],
            fmt(r_value, 3),
            relationship_strength(r_value),
            relationship_direction(r_value),
            matches_expected(r_value, relationship["expected"]),
            fmt(low_mean, 2, " F"),
            fmt(high_mean, 2, " F"),
            len(pairs),
        ])

    html_table = render_html_table(
        [
            "Feature",
            "r with MAE",
            "Strength",
            "Direction",
            "Expected?",
            "Low feature MAE",
            "High feature MAE",
            "Rows",
        ],
        table_rows,
    )
    return html_table, summaries


def linear_fit(pairs: list[tuple[float, float]]) -> tuple[float, float] | None:
    if len(pairs) < 2:
        return None

    x_values = [pair[0] for pair in pairs]
    y_values = [pair[1] for pair in pairs]
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    denominator = sum((x_value - x_mean) ** 2 for x_value in x_values)

    if denominator == 0:
        return None

    slope = sum(
        (x_value - x_mean) * (y_value - y_mean)
        for x_value, y_value in pairs
    ) / denominator
    intercept = y_mean - slope * x_mean
    return slope, intercept


def scatter_plot(rows: list[CsvRow], x_column: str, label: str) -> str:
    pairs = numeric_pairs(rows, x_column, "observed_mae_f")
    if len(pairs) < 2:
        return "<p class=\"muted\">Not enough data for this plot.</p>"

    width = 520
    height = 320
    margin_left = 58
    margin_right = 18
    margin_top = 22
    margin_bottom = 54
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    x_values = [pair[0] for pair in pairs]
    y_values = [pair[1] for pair in pairs]
    x_min = min(x_values)
    x_max = max(x_values)
    y_min = min(y_values)
    y_max = max(y_values)
    y_padding = max((y_max - y_min) * 0.08, 0.2)
    y_min = max(0.0, y_min - y_padding)
    y_max += y_padding

    if x_min == x_max:
        x_min -= 1
        x_max += 1

    def x_scale(value: float) -> float:
        return margin_left + ((value - x_min) / (x_max - x_min)) * plot_width

    def y_scale(value: float) -> float:
        return margin_top + (1 - ((value - y_min) / (y_max - y_min))) * plot_height

    points = []
    for x_value, y_value in pairs:
        color = "#2563eb" if y_value <= 2.0 else "#dc2626" if y_value >= 3.0 else "#f59e0b"
        points.append(
            f"<circle cx=\"{x_scale(x_value):.1f}\" cy=\"{y_scale(y_value):.1f}\" "
            f"r=\"4\" fill=\"{color}\" fill-opacity=\"0.74\" />"
        )

    trend = ""
    fit = linear_fit(pairs)
    if fit is not None:
        slope, intercept = fit
        y_start = slope * x_min + intercept
        y_end = slope * x_max + intercept
        trend = (
            f"<line x1=\"{x_scale(x_min):.1f}\" y1=\"{y_scale(y_start):.1f}\" "
            f"x2=\"{x_scale(x_max):.1f}\" y2=\"{y_scale(y_end):.1f}\" "
            "stroke=\"#111827\" stroke-width=\"2\" stroke-dasharray=\"5 5\" />"
        )

    r_value = correlation(pairs)
    return f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label)} versus MAE">
      <rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />
      <line x1="{margin_left}" y1="{margin_top + plot_height}" x2="{margin_left + plot_width}" y2="{margin_top + plot_height}" stroke="#94a3b8" />
      <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_height}" stroke="#94a3b8" />
      <text x="{margin_left}" y="{height - 18}" font-size="12" fill="#475569">{escape(label)}</text>
      <text x="16" y="{margin_top + 12}" font-size="12" fill="#475569" transform="rotate(-90 16 {margin_top + 12})">Observed MAE F</text>
      <text x="{margin_left}" y="{margin_top - 6}" font-size="12" fill="#475569">r = {fmt(r_value, 3)}</text>
      <text x="{margin_left}" y="{margin_top + plot_height + 18}" font-size="11" fill="#64748b">{fmt(x_min, 1)}</text>
      <text x="{margin_left + plot_width - 34}" y="{margin_top + plot_height + 18}" font-size="11" fill="#64748b">{fmt(x_max, 1)}</text>
      <text x="14" y="{y_scale(y_min):.1f}" font-size="11" fill="#64748b">{fmt(y_min, 1)}</text>
      <text x="14" y="{y_scale(y_max):.1f}" font-size="11" fill="#64748b">{fmt(y_max, 1)}</text>
      {trend}
      {''.join(points)}
    </svg>
    """


def chart_grid(rows: list[CsvRow]) -> str:
    labels = {
        relationship["column"]: relationship["label"]
        for relationship in RELATIONSHIPS
    }
    charts = []
    for column in PLOT_COLUMNS:
        charts.append(
            "<section class=\"chart-card\">"
            f"<h3>{escape(labels[column])} vs MAE</h3>"
            f"{scatter_plot(rows, column, labels[column])}"
            "</section>"
        )
    return "<div class=\"chart-grid\">" + "".join(charts) + "</div>"


def high_level_takeaways(
    relationship_summaries: list[dict[str, object]],
) -> str:
    matched = [
        item
        for item in relationship_summaries
        if item["matches"] == "matches"
    ]
    surprising = [
        item
        for item in relationship_summaries
        if item["matches"] == "surprising"
    ]
    moderate_or_stronger = [
        item
        for item in relationship_summaries
        if item["strength"] in ("moderate", "strong")
    ]
    pieces = []

    if moderate_or_stronger:
        labels = ", ".join(item["label"] for item in moderate_or_stronger[:4])
        pieces.append(f"Moderate-or-strong signals found: {labels}.")
    else:
        pieces.append("No single feature has a moderate-or-strong linear relationship with MAE yet.")

    if matched:
        labels = ", ".join(item["label"] for item in matched[:4])
        pieces.append(f"Signals moving in the expected direction: {labels}.")

    if surprising:
        labels = ", ".join(item["label"] for item in surprising[:4])
        pieces.append(f"Signals to inspect carefully: {labels}.")

    pieces.append(
        "This suggests the v1 confidence function should stay conservative and explainable, "
        "using several weak signals together instead of trusting one magic score."
    )
    return "".join(f"<li>{escape(piece)}</li>" for piece in pieces)


def render_report(
    model_run_id: str,
    manifest: dict[str, object],
    rows: list[CsvRow],
) -> str:
    mae_values = [numeric(row, "observed_mae_f") for row in rows]
    rmse_values = [numeric(row, "observed_rmse_f") for row in rows]
    support_values = [numeric(row, "support_score") for row in rows]
    mae_values = [value for value in mae_values if value is not None]
    rmse_values = [value for value in rmse_values if value is not None]
    support_values = [value for value in support_values if value is not None]
    sorted_by_mae = sorted(rows, key=lambda row: numeric(row, "observed_mae_f") or 0.0)
    best_rows = sorted_by_mae[:10]
    worst_rows = sorted_by_mae[-10:][::-1]
    relationship_table, relationship_summaries = relationship_rows(rows)
    missing = missing_counts(rows)
    missing_html = (
        "<p class=\"good\">No missing values in calibration fields.</p>"
        if not missing
        else render_html_table(["Column", "Missing rows"], missing)
    )
    summary = manifest.get("summaryMetrics", {})
    summary_cards = "\n      ".join([
        render_metric_card("Calibration stations", len(rows)),
        render_metric_card(
            "Prediction rows",
            summary.get("validationPredictionRows", "N/A"),
        ),
        render_metric_card("Mean MAE", fmt(mean(mae_values), 2, " F")),
        render_metric_card("Median MAE", fmt(percentile(mae_values, 0.50), 2, " F")),
        render_metric_card("Mean RMSE", fmt(mean(rmse_values), 2, " F")),
        render_metric_card(
            "Support range",
            f"{fmt(min(support_values), 1)}-{fmt(max(support_values), 1)}",
        ),
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Calibration Audit - {escape(model_run_id)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f8fafc;
      --text: #111827;
      --muted: #64748b;
      --line: #dbe3ef;
      --panel: #ffffff;
      --blue: #2563eb;
      --green: #059669;
      --amber: #d97706;
      --red: #dc2626;
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
      padding: 24px 36px 42px;
      max-width: 1440px;
      margin: 0 auto;
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
      margin: 0 0 12px;
      font-size: 16px;
      letter-spacing: 0;
    }}
    p {{
      line-height: 1.5;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.92em;
    }}
    .muted {{
      color: var(--muted);
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 12px;
      margin: 18px 0 8px;
    }}
    .card, .chart-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    .label {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 5px;
    }}
    .value {{
      font-size: 22px;
      font-weight: 700;
      line-height: 1.2;
    }}
    .note {{
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      border-radius: 8px;
      padding: 14px 16px;
      margin: 18px 0;
    }}
    .good {{
      color: var(--green);
      font-weight: 700;
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
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      font-size: 13px;
      line-height: 1.35;
    }}
    th {{
      background: #f1f5f9;
      color: #334155;
      font-weight: 700;
    }}
    tr:last-child td {{
      border-bottom: 0;
    }}
    .two-col {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(520px, 1fr));
      gap: 18px;
      align-items: start;
    }}
    .chart-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
      gap: 16px;
    }}
    svg {{
      width: 100%;
      height: auto;
      display: block;
    }}
    ul {{
      line-height: 1.55;
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px 18px 14px 34px;
    }}
    @media (max-width: 720px) {{
      header, main {{
        padding-left: 16px;
        padding-right: 16px;
      }}
      .two-col, .chart-grid {{
        grid-template-columns: 1fr;
      }}
      th, td {{
        font-size: 12px;
        padding: 8px;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Calibration Audit</h1>
    <p class="muted"><code>{escape(model_run_id)}</code></p>
  </header>
  <main>
    <section class="note">
      <strong>What this is:</strong> a quick check of whether the 86 held-out validation stations give us a believable basis for calibrated confidence. This is not the final confidence formula.
    </section>

    <section class="cards">
      {summary_cards}
    </section>

    <h2>Initial Read</h2>
    <ul>{high_level_takeaways(relationship_summaries)}</ul>

    <h2>Relationship Checks</h2>
    <p class="muted">Correlation is shown against observed MAE. For error, negative is good when the feature is a support score; positive is expected when the feature is distance or ruggedness.</p>
    {relationship_table}

    <h2>Scatter Plots</h2>
    {chart_grid(rows)}

    <h2>Best And Worst Stations</h2>
    <div class="two-col">
      <section>
        <h3>Best 10 by MAE</h3>
        {station_table(best_rows)}
      </section>
      <section>
        <h3>Worst 10 by MAE</h3>
        {station_table(worst_rows)}
      </section>
    </div>

    <h2>Missing Data Check</h2>
    {missing_html}

    <h2>Manifest Summary</h2>
    <pre>{escape(json.dumps(summary, indent=2))}</pre>
  </main>
</body>
</html>
"""


def main() -> None:
    arguments = parse_arguments()
    paths = resolve_model_run(arguments.model_run_root, arguments.model_run_id)
    model_run = load_model_run(paths)
    output = arguments.output or (paths.root / "calibration_audit.html")
    output.write_text(
        render_report(
            arguments.model_run_id,
            model_run["manifest"],
            model_run["calibration_points"],
        )
    )
    print(f"Calibration audit report: {output}")


if __name__ == "__main__":
    main()
