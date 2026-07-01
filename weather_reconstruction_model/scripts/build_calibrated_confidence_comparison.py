"""Compare calibrated confidence scores against observed validation errors.

The output helps tune confidence-map scoring so frontend colors reflect expected reconstruction quality."""

from __future__ import annotations

import argparse
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import config
from common.csv_utils import CsvRow, read_csv_rows, write_csv_rows
from common.json_utils import write_json_file
from common.model_runs import load_model_run, resolve_model_run
from common.number_utils import to_optional_float
from common.reporting import escape_html as escape
from common.reporting import render_html_table, trusted_html

DEFAULT_MODEL_RUN_ID = (
    "option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain_"
    "offset_terrain_standard_random_forest"
)

SCORE_VERSION = "calibrated-confidence-physical-risk-v1"

BLEND_SUPPORT_WEIGHT = 0.75
BLEND_REPRESENTATIVENESS_WEIGHT = 0.25
ELEVATION_MISMATCH_PENALTY = 8.0
TERRAIN_MISMATCH_PENALTY = 6.0
ARID_PLATEAU_PENALTY = 4.0
MONSOON_REGION_PENALTY = 2.0
COLD_POOL_START = 0.40
COLD_POOL_FULL = 1.00
COLD_POOL_MAX_PENALTY = 6.0
SEASONAL_WARNING_PENALTY = 8.0

VERY_HIGH_CONFIDENCE_MIN = 85.0
HIGH_CONFIDENCE_MIN = 75.0
MODERATE_CONFIDENCE_MIN = 65.0
LOW_CONFIDENCE_MIN = 50.0
HIGH_ERROR_MAE_F = 2.5

CANDIDATE_FIELDNAMES = [
    "station_id",
    "station_name",
    "latitude",
    "longitude",
    "elevation_m",
    "observed_mae_f",
    "observed_rmse_f",
    "observed_correlation",
    "test_rows",
    "support_confidence",
    "support_representativeness_blend_confidence",
    "physical_adjusted_confidence",
    "physical_adjusted_expected_mae_f",
    "physical_adjusted_label",
    "physical_risk_penalty",
    "physical_risk_reasons",
    "support_score",
    "representativeness_score",
    "cold_pool_index",
    "monsoon_region_flag",
    "arid_plateau_flag",
    "elevation_mismatch_risk",
    "terrain_mismatch_risk",
    "seasonal_confidence_warning",
    "worst_season",
    "worst_season_confidence",
    "baseline_false_very_high_confidence",
    "candidate_false_very_high_confidence",
]


@dataclass(frozen=True)
class ScoreDefinition:
    name: str
    label: str
    column: str
    scorer: Callable[[Mapping[str, object]], float]


@dataclass(frozen=True)
class ExpectedMaeModel:
    intercept: float
    slope: float
    score_column: str

    def predict(self, score: float) -> float:
        return max(0.0, self.intercept + self.slope * score)

    def as_dict(self) -> dict[str, object]:
        return {
            "type": "ordinary_least_squares",
            "target": "observed_mae_f",
            "scoreColumn": self.score_column,
            "intercept": round(self.intercept, 6),
            "slope": round(self.slope, 6),
        }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare support-only confidence against a simple physical-risk-adjusted "
            "calibrated confidence candidate."
        )
    )
    parser.add_argument("--model-run-id", default=DEFAULT_MODEL_RUN_ID)
    parser.add_argument("--model-run-root", type=Path, default=config.MODEL_RUN_DIR)
    parser.add_argument("--physical-regime-scores", type=Path, default=None)
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--output-html", type=Path, default=None)
    parser.add_argument("--output-grid", type=Path, default=None)
    return parser.parse_args()


def fmt(value: object, decimals: int = 2, suffix: str = "") -> str:
    numeric_value = to_optional_float(value)
    if numeric_value is None or math.isnan(numeric_value):
        return ""
    return f"{numeric_value:.{decimals}f}{suffix}"


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def flag(row: Mapping[str, object], column: str) -> bool:
    return str(row.get(column, "")).strip().lower() == "yes"


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def numeric(row: Mapping[str, object], column: str) -> float | None:
    return to_optional_float(row.get(column))


def bool_text(value: bool) -> str:
    return "yes" if value else "no"


def physical_risk_details(row: Mapping[str, object]) -> tuple[float, list[str]]:
    penalty = 0.0
    reasons = []

    if flag(row, "elevation_mismatch_risk"):
        penalty += ELEVATION_MISMATCH_PENALTY
        reasons.append("elevation mismatch")

    if flag(row, "terrain_mismatch_risk"):
        penalty += TERRAIN_MISMATCH_PENALTY
        reasons.append("terrain mismatch")

    if flag(row, "arid_plateau_flag"):
        penalty += ARID_PLATEAU_PENALTY
        reasons.append("arid plateau")
    elif flag(row, "monsoon_region_flag"):
        penalty += MONSOON_REGION_PENALTY
        reasons.append("monsoon region")

    cold_pool_index = numeric(row, "cold_pool_index") or 0.0
    if cold_pool_index > COLD_POOL_START:
        cold_pool_fraction = clamp(
            (cold_pool_index - COLD_POOL_START) / (COLD_POOL_FULL - COLD_POOL_START),
            0.0,
            1.0,
        )
        cold_pool_penalty = COLD_POOL_MAX_PENALTY * cold_pool_fraction
        penalty += cold_pool_penalty
        reasons.append(f"cold-pool risk {cold_pool_index:.3f}")

    if str(row.get("seasonal_confidence_warning", "")).strip():
        penalty += SEASONAL_WARNING_PENALTY
        reasons.append("thin seasonal validation evidence")

    return penalty, reasons


def support_confidence(row: Mapping[str, object]) -> float:
    return clamp(numeric(row, "support_score") or 0.0)


def support_representativeness_blend(row: Mapping[str, object]) -> float:
    support_score = numeric(row, "support_score") or 0.0
    representativeness = numeric(row, "representativeness_score")
    if representativeness is None:
        representativeness = support_score

    return clamp(
        BLEND_SUPPORT_WEIGHT * support_score
        + BLEND_REPRESENTATIVENESS_WEIGHT * representativeness
    )


def physical_adjusted_confidence(row: Mapping[str, object]) -> float:
    penalty, _reasons = physical_risk_details(row)
    return clamp(support_representativeness_blend(row) - penalty)


def confidence_label(score: float) -> str:
    if score >= VERY_HIGH_CONFIDENCE_MIN:
        return "Very high confidence"
    if score >= HIGH_CONFIDENCE_MIN:
        return "High confidence"
    if score >= MODERATE_CONFIDENCE_MIN:
        return "Moderate confidence"
    if score >= LOW_CONFIDENCE_MIN:
        return "Low confidence"
    return "Very low confidence"


def pearson_correlation(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 2:
        return None

    xs = [pair[0] for pair in pairs]
    ys = [pair[1] for pair in pairs]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    denominator_x = sum((x - mean_x) ** 2 for x in xs)
    denominator_y = sum((y - mean_y) ** 2 for y in ys)

    if denominator_x <= 0 or denominator_y <= 0:
        return None

    return numerator / math.sqrt(denominator_x * denominator_y)


def ranks(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranked = [0.0] * len(values)
    index = 0

    while index < len(ordered):
        end = index
        while end + 1 < len(ordered) and ordered[end + 1][1] == ordered[index][1]:
            end += 1

        rank = (index + end) / 2.0 + 1.0
        for ordered_index in range(index, end + 1):
            ranked[ordered[ordered_index][0]] = rank
        index = end + 1

    return ranked


def spearman_correlation(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 2:
        return None

    x_ranks = ranks([pair[0] for pair in pairs])
    y_ranks = ranks([pair[1] for pair in pairs])
    return pearson_correlation(list(zip(x_ranks, y_ranks)))


def score_pairs(rows: list[Mapping[str, object]], score_column: str) -> list[tuple[float, float]]:
    pairs = []
    for row in rows:
        score = numeric(row, score_column)
        observed_mae = numeric(row, "observed_mae_f")
        if score is not None and observed_mae is not None:
            pairs.append((score, observed_mae))
    return pairs


def fit_expected_mae_model(
    rows: list[Mapping[str, object]],
    score_column: str,
) -> ExpectedMaeModel:
    pairs = score_pairs(rows, score_column)
    if len(pairs) < 2:
        raise ValueError("Need at least two score/MAE pairs to fit expected MAE.")

    mean_score = sum(score for score, _mae in pairs) / len(pairs)
    mean_mae = sum(mae for _score, mae in pairs) / len(pairs)
    denominator = sum((score - mean_score) ** 2 for score, _mae in pairs)

    if denominator <= 0:
        raise ValueError(f"Cannot fit expected MAE; {score_column} has no variation.")

    slope = sum(
        (score - mean_score) * (mae - mean_mae)
        for score, mae in pairs
    ) / denominator
    intercept = mean_mae - slope * mean_score

    return ExpectedMaeModel(
        intercept=intercept,
        slope=slope,
        score_column=score_column,
    )


def high_error(row: Mapping[str, object]) -> bool:
    observed_mae = numeric(row, "observed_mae_f")
    return observed_mae is not None and observed_mae >= HIGH_ERROR_MAE_F


def build_candidate_rows(
    physical_rows: list[CsvRow],
    expected_mae_model: ExpectedMaeModel | None = None,
) -> list[dict[str, object]]:
    rows = []

    for physical_row in physical_rows:
        support = support_confidence(physical_row)
        blend = support_representativeness_blend(physical_row)
        physical_score = physical_adjusted_confidence(physical_row)
        penalty, reasons = physical_risk_details(physical_row)
        observed_mae = numeric(physical_row, "mae_f")
        candidate_expected_mae = (
            expected_mae_model.predict(physical_score)
            if expected_mae_model is not None
            else None
        )

        rows.append({
            "station_id": physical_row.get("station_id", ""),
            "station_name": physical_row.get("station_name", ""),
            "latitude": physical_row.get("latitude", ""),
            "longitude": physical_row.get("longitude", ""),
            "elevation_m": physical_row.get("elevation_m", ""),
            "observed_mae_f": physical_row.get("mae_f", ""),
            "observed_rmse_f": physical_row.get("rmse_f", ""),
            "observed_correlation": physical_row.get("correlation", ""),
            "test_rows": physical_row.get("test_rows", ""),
            "support_confidence": fmt(support, 2),
            "support_representativeness_blend_confidence": fmt(blend, 2),
            "physical_adjusted_confidence": fmt(physical_score, 2),
            "physical_adjusted_expected_mae_f": fmt(candidate_expected_mae, 3),
            "physical_adjusted_label": confidence_label(physical_score),
            "physical_risk_penalty": fmt(penalty, 2),
            "physical_risk_reasons": "; ".join(reasons),
            "support_score": physical_row.get("support_score", ""),
            "representativeness_score": physical_row.get("representativeness_score", ""),
            "cold_pool_index": physical_row.get("cold_pool_index", ""),
            "monsoon_region_flag": physical_row.get("monsoon_region_flag", ""),
            "arid_plateau_flag": physical_row.get("arid_plateau_flag", ""),
            "elevation_mismatch_risk": physical_row.get("elevation_mismatch_risk", ""),
            "terrain_mismatch_risk": physical_row.get("terrain_mismatch_risk", ""),
            "seasonal_confidence_warning": physical_row.get(
                "seasonal_confidence_warning",
                "",
            ),
            "worst_season": physical_row.get("worst_season", ""),
            "worst_season_confidence": physical_row.get("worst_season_confidence", ""),
            "baseline_false_very_high_confidence": bool_text(
                support >= VERY_HIGH_CONFIDENCE_MIN
                and observed_mae is not None
                and observed_mae >= HIGH_ERROR_MAE_F
            ),
            "candidate_false_very_high_confidence": bool_text(
                physical_score >= VERY_HIGH_CONFIDENCE_MIN
                and observed_mae is not None
                and observed_mae >= HIGH_ERROR_MAE_F
            ),
        })

    rows.sort(key=lambda row: numeric(row, "observed_mae_f") or 0.0, reverse=True)
    return rows


def score_definitions() -> list[ScoreDefinition]:
    return [
        ScoreDefinition(
            name="support",
            label="Support only",
            column="support_confidence",
            scorer=support_confidence,
        ),
        ScoreDefinition(
            name="support_representativeness_blend",
            label="Support plus representativeness",
            column="support_representativeness_blend_confidence",
            scorer=support_representativeness_blend,
        ),
        ScoreDefinition(
            name="physical_adjusted",
            label="Physical-risk adjusted",
            column="physical_adjusted_confidence",
            scorer=physical_adjusted_confidence,
        ),
    ]


def score_metric_rows(rows: list[Mapping[str, object]]) -> list[dict[str, object]]:
    output = []

    for definition in score_definitions():
        pairs = score_pairs(rows, definition.column)
        scores = [score for score, _mae in pairs]
        high_85_rows = [
            row
            for row in rows
            if (numeric(row, definition.column) or 0.0) >= VERY_HIGH_CONFIDENCE_MIN
        ]
        high_80_rows = [
            row
            for row in rows
            if (numeric(row, definition.column) or 0.0) >= 80.0
        ]
        false_85_rows = [
            row
            for row in high_85_rows
            if high_error(row)
        ]
        false_80_rows = [
            row
            for row in high_80_rows
            if high_error(row)
        ]

        output.append({
            "label": definition.label,
            "column": definition.column,
            "pearson_r": pearson_correlation(pairs),
            "spearman_r": spearman_correlation(pairs),
            "score_min": min(scores) if scores else None,
            "score_max": max(scores) if scores else None,
            "score_mean": mean(scores),
            "very_high_count": len(high_85_rows),
            "false_very_high_count": len(false_85_rows),
            "false_very_high_rate": (
                len(false_85_rows) / len(high_85_rows)
                if high_85_rows
                else None
            ),
            "very_high_mean_mae_f": mean([
                numeric(row, "observed_mae_f") or 0.0
                for row in high_85_rows
            ]),
            "score_80_plus_count": len(high_80_rows),
            "false_score_80_plus_count": len(false_80_rows),
            "score_80_plus_mean_mae_f": mean([
                numeric(row, "observed_mae_f") or 0.0
                for row in high_80_rows
            ]),
        })

    return output


def confidence_bins() -> list[tuple[str, float, float]]:
    return [
        ("Very high", 85.0, 101.0),
        ("High", 75.0, 85.0),
        ("Moderate", 65.0, 75.0),
        ("Low", 50.0, 65.0),
        ("Very low", 0.0, 50.0),
    ]


def binned_rows(
    rows: list[Mapping[str, object]],
    score_column: str,
) -> list[dict[str, object]]:
    output = []

    for label, minimum, maximum in confidence_bins():
        selected = [
            row
            for row in rows
            if minimum <= (numeric(row, score_column) or -1.0) < maximum
        ]
        output.append({
            "label": label,
            "minimum": minimum,
            "maximum": maximum,
            "count": len(selected),
            "mean_mae_f": mean([
                numeric(row, "observed_mae_f") or 0.0
                for row in selected
            ]),
            "high_error_count": len([
                row
                for row in selected
                if high_error(row)
            ]),
        })

    return output


def table(headers: list[str], rows: list[list[object]]) -> str:
    return render_html_table(headers, rows)


def score_metrics_table(metric_rows: list[Mapping[str, object]]) -> str:
    rows = []
    for row in metric_rows:
        rows.append([
            row["label"],
            fmt(row["pearson_r"], 3),
            fmt(row["spearman_r"], 3),
            fmt(row["score_mean"], 1),
            row["very_high_count"],
            row["false_very_high_count"],
            fmt(row["very_high_mean_mae_f"], 2, " F"),
            row["score_80_plus_count"],
            row["false_score_80_plus_count"],
            fmt(row["score_80_plus_mean_mae_f"], 2, " F"),
        ])

    return table(
        [
            "Score",
            "Pearson r vs MAE",
            "Spearman r vs MAE",
            "Mean score",
            ">=85 count",
            ">=85 high-error count",
            ">=85 mean MAE",
            ">=80 count",
            ">=80 high-error count",
            ">=80 mean MAE",
        ],
        rows,
    )


def bins_table(
    rows: list[Mapping[str, object]],
    score_column: str,
    title: str,
) -> str:
    table_rows = []
    for row in binned_rows(rows, score_column):
        table_rows.append([
            row["label"],
            row["count"],
            fmt(row["mean_mae_f"], 2, " F"),
            row["high_error_count"],
        ])

    return (
        f"<h3>{escape(title)}</h3>"
        + table(["Bin", "Stations", "Mean observed MAE", "MAE >= 2.5 F"], table_rows)
    )


def station_table(rows: list[Mapping[str, object]], limit: int | None = None) -> str:
    selected = rows[:limit] if limit is not None else rows
    table_rows = []

    for row in selected:
        table_rows.append([
            trusted_html(f"<code>{escape(row.get('station_id', ''))}</code>"),
            row.get("station_name", ""),
            row.get("observed_mae_f", ""),
            row.get("support_confidence", ""),
            row.get("support_representativeness_blend_confidence", ""),
            row.get("physical_adjusted_confidence", ""),
            row.get("physical_adjusted_expected_mae_f", ""),
            row.get("physical_risk_penalty", ""),
            row.get("physical_risk_reasons", ""),
        ])

    head = [
        "Station",
        "Name",
        "Observed MAE",
        "Support",
        "Support + rep.",
        "Physical adjusted",
        "Expected MAE",
        "Penalty",
        "Penalty reasons",
    ]
    return render_html_table(head, table_rows)


def false_high_rows(
    rows: list[Mapping[str, object]],
    score_column: str,
    cutoff: float,
) -> list[Mapping[str, object]]:
    return [
        row
        for row in rows
        if (numeric(row, score_column) or 0.0) >= cutoff and high_error(row)
    ]


def render_report(
    model_run_id: str,
    rows: list[Mapping[str, object]],
    expected_mae_model: ExpectedMaeModel,
) -> str:
    metric_rows = score_metric_rows(rows)
    support_metrics = next(row for row in metric_rows if row["column"] == "support_confidence")
    candidate_metrics = next(
        row
        for row in metric_rows
        if row["column"] == "physical_adjusted_confidence"
    )
    baseline_false_very_high = false_high_rows(
        rows,
        "support_confidence",
        VERY_HIGH_CONFIDENCE_MIN,
    )
    candidate_false_very_high = false_high_rows(
        rows,
        "physical_adjusted_confidence",
        VERY_HIGH_CONFIDENCE_MIN,
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Calibrated Confidence Comparison - {escape(model_run_id)}</title>
  <style>
    :root {{
      --bg: #f8fafc;
      --text: #111827;
      --muted: #64748b;
      --line: #dbe3ef;
      --panel: #ffffff;
      --blue: #1d4ed8;
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
      margin: 30px 0 12px;
      font-size: 20px;
      letter-spacing: 0;
    }}
    h3 {{
      margin: 16px 0 8px;
      font-size: 15px;
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
      padding: 14px;
      margin: 18px 0;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 12px;
      margin: 18px 0 8px;
    }}
    .card {{
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
      overflow-wrap: anywhere;
    }}
    .two-col {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(520px, 1fr));
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
    <h1>Calibrated Confidence Comparison</h1>
    <p class="muted"><code>{escape(model_run_id)}</code></p>
  </header>
  <main>
    <section class="note">
      <strong>Purpose:</strong> test whether the physical-risk adjustment makes high-confidence claims line up better with out-of-sample station validation error. Observed MAE is used only for evaluation and expected-MAE calibration, not as a direct input to the confidence score.
    </section>

    <section class="cards">
      <div class="card"><div class="label">Validation stations</div><div class="value">{len(rows)}</div></div>
      <div class="card"><div class="label">Baseline r vs MAE</div><div class="value">{fmt(support_metrics["pearson_r"], 3)}</div></div>
      <div class="card"><div class="label">Candidate r vs MAE</div><div class="value">{fmt(candidate_metrics["pearson_r"], 3)}</div></div>
      <div class="card"><div class="label">Baseline false >=85</div><div class="value">{support_metrics["false_very_high_count"]}</div></div>
      <div class="card"><div class="label">Candidate false >=85</div><div class="value">{candidate_metrics["false_very_high_count"]}</div></div>
      <div class="card"><div class="label">Candidate score version</div><div class="value">{escape(SCORE_VERSION)}</div></div>
    </section>

    <h2>Score Comparison</h2>
    <p class="muted">More negative correlation is better because confidence should fall as observed validation MAE rises. The practical test is the false high-confidence count.</p>
    {score_metrics_table(metric_rows)}

    <h2>Confidence Bins</h2>
    <div class="two-col">
      <div>{bins_table(rows, "support_confidence", "Support only")}</div>
      <div>{bins_table(rows, "physical_adjusted_confidence", "Physical-risk adjusted")}</div>
    </div>

    <h2>False Very-High Confidence Misses</h2>
    <p class="muted">These are stations with confidence >= 85 but observed MAE >= {HIGH_ERROR_MAE_F:.1f} F.</p>
    <div class="two-col">
      <div>
        <h3>Before: support only</h3>
        {station_table(baseline_false_very_high) if baseline_false_very_high else "<p>No false very-high confidence misses.</p>"}
      </div>
      <div>
        <h3>After: physical adjusted</h3>
        {station_table(candidate_false_very_high) if candidate_false_very_high else "<p>No false very-high confidence misses.</p>"}
      </div>
    </div>

    <h2>Expected MAE Calibration</h2>
    <p class="muted">Expected MAE is a simple linear fit from physical-adjusted confidence to observed validation MAE: <code>MAE = {expected_mae_model.intercept:.4f} + ({expected_mae_model.slope:.4f} * confidence)</code>.</p>

    <h2>All Stations, Sorted By Observed MAE</h2>
    {station_table(rows)}

    <h2>Interpretation</h2>
    <p>The selected candidate is intentionally simple: support and representativeness stay as the base, then physically interpretable risk penalties reduce confidence where the held-out validation failures suggest transfer risk. This does not retrain the weather model. It improves the confidence layer by reducing misleading high-confidence claims.</p>
  </main>
</body>
</html>
"""


def grid_bounds(rows: list[Mapping[str, object]]) -> dict[str, float]:
    latitudes = [
        value
        for row in rows
        if (value := numeric(row, "latitude")) is not None
    ]
    longitudes = [
        value
        for row in rows
        if (value := numeric(row, "longitude")) is not None
    ]

    if not latitudes or not longitudes:
        raise ValueError("Cannot build confidence grid bounds without coordinates.")

    return {
        "latMin": round(min(latitudes), 6),
        "latMax": round(max(latitudes), 6),
        "lonMin": round(min(longitudes), 6),
        "lonMax": round(max(longitudes), 6),
    }


def build_grid_payload(
    model_run_id: str,
    rows: list[Mapping[str, object]],
    expected_mae_model: ExpectedMaeModel,
) -> dict[str, object]:
    metric_rows = score_metric_rows(rows)
    support_metrics = next(row for row in metric_rows if row["column"] == "support_confidence")
    candidate_metrics = next(
        row
        for row in metric_rows
        if row["column"] == "physical_adjusted_confidence"
    )
    points = []

    for row in rows:
        confidence = numeric(row, "physical_adjusted_confidence")
        latitude = numeric(row, "latitude")
        longitude = numeric(row, "longitude")
        expected_mae = numeric(row, "physical_adjusted_expected_mae_f")

        if confidence is None or latitude is None or longitude is None:
            continue

        points.append({
            "latitude": round(latitude, 6),
            "longitude": round(longitude, 6),
            "confidence": round(confidence, 2),
            "expectedMaeF": round(expected_mae or expected_mae_model.predict(confidence), 3),
            "label": confidence_label(confidence),
            "stationId": row.get("station_id", ""),
            "stationName": row.get("station_name", ""),
            "observedMaeF": to_optional_float(row.get("observed_mae_f")),
            "supportScore": to_optional_float(row.get("support_score")),
            "representativenessScore": to_optional_float(row.get("representativeness_score")),
            "physicalRiskPenalty": to_optional_float(row.get("physical_risk_penalty")),
            "physicalRiskReasons": [
                reason.strip()
                for reason in str(row.get("physical_risk_reasons", "")).split(";")
                if reason.strip()
            ],
        })

    return {
        "schemaVersion": "confidence-grid-v1",
        "modelRunId": model_run_id,
        "scoreVersion": SCORE_VERSION,
        "status": "ok",
        "calibrationStatus": "calibrated_from_out_of_sample_station_holdout",
        "pointType": "validation_station_anchor",
        "pointCount": len(points),
        "bounds": grid_bounds(rows),
        "formula": {
            "base": (
                f"{BLEND_SUPPORT_WEIGHT:.2f} * support_score + "
                f"{BLEND_REPRESENTATIVENESS_WEIGHT:.2f} * representativeness_score"
            ),
            "penalties": {
                "elevationMismatchRisk": ELEVATION_MISMATCH_PENALTY,
                "terrainMismatchRisk": TERRAIN_MISMATCH_PENALTY,
                "aridPlateauFlag": ARID_PLATEAU_PENALTY,
                "monsoonRegionFlagWhenNotArid": MONSOON_REGION_PENALTY,
                "coldPoolPenaltyStart": COLD_POOL_START,
                "coldPoolMaxPenalty": COLD_POOL_MAX_PENALTY,
                "seasonalConfidenceWarning": SEASONAL_WARNING_PENALTY,
            },
        },
        "expectedMaeModel": expected_mae_model.as_dict(),
        "calibrationSummary": {
            "validationStationCount": len(rows),
            "highErrorMaeThresholdF": HIGH_ERROR_MAE_F,
            "supportPearsonRVsMae": round(support_metrics["pearson_r"], 6),
            "physicalAdjustedPearsonRVsMae": round(candidate_metrics["pearson_r"], 6),
            "supportFalseVeryHighConfidenceCount": support_metrics["false_very_high_count"],
            "physicalAdjustedFalseVeryHighConfidenceCount": candidate_metrics["false_very_high_count"],
            "supportVeryHighMeanMaeF": round(support_metrics["very_high_mean_mae_f"], 4),
            "physicalAdjustedVeryHighMeanMaeF": round(
                candidate_metrics["very_high_mean_mae_f"],
                4,
            ),
        },
        "points": points,
        "notes": [
            "This is the first calibrated station-anchor confidence grid for the model run.",
            "It is calibrated against out-of-sample station validation, not in-sample fit.",
            "The points are validation-station anchors, not a continuous DEM-derived surface yet.",
            "Observed MAE is included for auditability and is not used directly as a score input.",
        ],
    }


def main() -> None:
    arguments = parse_arguments()
    paths = resolve_model_run(arguments.model_run_root, arguments.model_run_id)
    load_model_run(paths)

    physical_scores_path = (
        arguments.physical_regime_scores
        or paths.root / "physical_regime_scores.csv"
    )
    physical_rows = read_csv_rows(physical_scores_path)
    preliminary_rows = build_candidate_rows(physical_rows)
    expected_mae_model = fit_expected_mae_model(
        preliminary_rows,
        "physical_adjusted_confidence",
    )
    rows = build_candidate_rows(physical_rows, expected_mae_model)

    output_csv = arguments.output_csv or paths.root / "calibrated_confidence_candidates.csv"
    output_html = arguments.output_html or paths.root / "calibrated_confidence_comparison.html"
    output_grid = arguments.output_grid or paths.confidence_grid

    write_csv_rows(output_csv, rows, CANDIDATE_FIELDNAMES)
    output_html.write_text(render_report(arguments.model_run_id, rows, expected_mae_model))
    write_json_file(
        output_grid,
        build_grid_payload(arguments.model_run_id, rows, expected_mae_model),
    )

    metric_rows = score_metric_rows(rows)
    support_metrics = next(row for row in metric_rows if row["column"] == "support_confidence")
    candidate_metrics = next(
        row
        for row in metric_rows
        if row["column"] == "physical_adjusted_confidence"
    )

    print(f"Calibrated confidence candidates: {output_csv}")
    print(f"Calibrated confidence comparison: {output_html}")
    print(f"Updated confidence grid: {output_grid}")
    print(
        "Pearson r vs MAE: "
        f"support={support_metrics['pearson_r']:.3f}, "
        f"physical_adjusted={candidate_metrics['pearson_r']:.3f}"
    )
    print(
        "False very-high confidence misses: "
        f"support={support_metrics['false_very_high_count']}, "
        f"physical_adjusted={candidate_metrics['false_very_high_count']}"
    )


if __name__ == "__main__":
    main()
