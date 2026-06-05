"""Audit how representative station evidence is across the model domain.

The report helps explain where confidence is strong, sparse, or physically risky."""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import config
from common.confidence_data import load_confidence_support_inputs
from common.confidence_support import SupportStation
from common.csv_utils import CsvRow, read_csv_rows, write_csv_rows
from common.geo_utils import calculate_distance_km
from common.model_runs import load_model_run, resolve_model_run
from common.number_utils import to_optional_float
from common.reporting import escape_html as escape
from common.reporting import render_html_table, render_metric_card, trusted_html


DEFAULT_MODEL_RUN_ID = (
    "option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain_"
    "offset_terrain_standard_random_forest"
)

TOP_ANCHOR_COUNT = 8

FEATURE_DEFINITIONS = [
    {
        "name": "regional_proximity",
        "plain": "Continuous geographic/climate-region proximity. This is a decay curve, not a cutoff radius.",
        "weight": 0.25,
    },
    {
        "name": "elevation_similarity",
        "plain": "Similarity between the candidate point elevation and anchor-station elevation.",
        "weight": 0.25,
    },
    {
        "name": "terrain_relief_similarity",
        "plain": "Similarity in multi-scale local relief, especially the 3 km terrain neighborhood.",
        "weight": 0.15,
    },
    {
        "name": "terrain_position_similarity",
        "plain": "Similarity in ridge/valley position using terrain position index.",
        "weight": 0.12,
    },
    {
        "name": "slope_similarity",
        "plain": "Similarity in local terrain slope.",
        "weight": 0.08,
    },
    {
        "name": "aspect_similarity",
        "plain": "Similarity in slope-facing direction where aspect is meaningful.",
        "weight": 0.08,
    },
    {
        "name": "anchor_data_quality",
        "plain": "Longer and more recent station record support from the anchor station.",
        "weight": 0.07,
    },
]

REPRESENTATIVENESS_FIELDNAMES = [
    "target_station_id",
    "target_name",
    "observed_mae_f",
    "observed_rmse_f",
    "observed_correlation",
    "support_score",
    "representativeness_score",
    "top_anchor_station_id",
    "top_anchor_name",
    "top_anchor_role",
    "top_anchor_similarity",
    "top_anchor_distance_km",
    "top_anchor_elevation_delta_m",
    "top_anchor_relief_delta_m",
    "top_anchor_tpi_delta_m",
    "top_anchor_slope_delta_degrees",
    "top_anchor_aspect_similarity",
    "top_anchor_component_regional_proximity",
    "top_anchor_component_elevation_similarity",
    "top_anchor_component_terrain_relief_similarity",
    "top_anchor_component_terrain_position_similarity",
    "top_anchor_component_slope_similarity",
    "top_anchor_component_aspect_similarity",
    "top_anchor_component_anchor_data_quality",
    "mean_top3_similarity",
    "mean_top8_similarity",
    "top_anchor_ids",
]


@dataclass(frozen=True)
class AnchorMatch:
    station: SupportStation
    score: float
    components: dict[str, float]
    distance_km: float
    elevation_delta_m: float | None
    relief_delta_m: float | None
    tpi_delta_m: float | None
    slope_delta_degrees: float | None
    aspect_similarity: float | None


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a station-to-station representativeness audit for the current "
            "model-run calibration points."
        )
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
        "--target-candidates",
        type=Path,
        default=config.TARGET_CANDIDATE_FILE,
        help="Target station candidate metadata CSV.",
    )
    parser.add_argument(
        "--hub-candidates",
        type=Path,
        default=config.HUB_CANDIDATE_FILE,
        help="Hub station candidate metadata CSV.",
    )
    parser.add_argument(
        "--terrain-features",
        type=Path,
        default=config.TERRAIN_FEATURE_FILE,
        help="Processed station terrain feature CSV.",
    )
    parser.add_argument(
        "--output-html",
        type=Path,
        default=None,
        help="Optional HTML output path. Defaults to the selected model-run folder.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help="Optional CSV output path for representativeness scores.",
    )
    return parser.parse_args()


def fmt(value: object, decimals: int = 2, suffix: str = "") -> str:
    numeric_value = to_optional_float(value)
    if numeric_value is None or math.isnan(numeric_value):
        return ""
    return f"{numeric_value:.{decimals}f}{suffix}"


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def decay_score(delta: float, scale: float) -> float:
    if scale <= 0:
        raise ValueError("scale must be positive.")
    return clamp(100.0 * math.exp(-abs(delta) / scale))


def terrain_value(station: SupportStation, name: str) -> float | None:
    if station.terrain is None:
        return None
    return getattr(station.terrain, name)


def first_available(*values: float | None) -> float | None:
    for value in values:
        if value is not None:
            return value
    return None


def station_elevation(station: SupportStation) -> float | None:
    return first_available(
        station.elevation_m,
        terrain_value(station, "dem_elevation_m"),
    )


def station_relief(station: SupportStation) -> float | None:
    return first_available(
        terrain_value(station, "local_relief_m_r3000m"),
        terrain_value(station, "local_relief_m_r990m"),
        terrain_value(station, "local_relief_m"),
    )


def station_tpi(station: SupportStation) -> float | None:
    return first_available(
        terrain_value(station, "terrain_position_index_m_r990m"),
        terrain_value(station, "terrain_position_index_m_r300m"),
        terrain_value(station, "terrain_position_index_m"),
    )


def station_slope(station: SupportStation) -> float | None:
    return first_available(
        terrain_value(station, "slope_degrees_r990m"),
        terrain_value(station, "slope_degrees_r300m"),
        terrain_value(station, "slope_degrees"),
    )


def aspect_score(point: SupportStation, anchor: SupportStation) -> tuple[float, float | None]:
    point_slope = station_slope(point)
    anchor_slope = station_slope(anchor)
    if point_slope is None or anchor_slope is None:
        return 50.0, None
    if point_slope < 1.0 or anchor_slope < 1.0:
        return 75.0, None
    if point.terrain is None or anchor.terrain is None:
        return 50.0, None

    point_sin = first_available(
        point.terrain.aspect_sin_r990m,
        point.terrain.aspect_sin_r300m,
        point.terrain.aspect_sin,
    )
    point_cos = first_available(
        point.terrain.aspect_cos_r990m,
        point.terrain.aspect_cos_r300m,
        point.terrain.aspect_cos,
    )
    anchor_sin = first_available(
        anchor.terrain.aspect_sin_r990m,
        anchor.terrain.aspect_sin_r300m,
        anchor.terrain.aspect_sin,
    )
    anchor_cos = first_available(
        anchor.terrain.aspect_cos_r990m,
        anchor.terrain.aspect_cos_r300m,
        anchor.terrain.aspect_cos,
    )

    if None in (point_sin, point_cos, anchor_sin, anchor_cos):
        return 50.0, None

    dot_product = point_sin * anchor_sin + point_cos * anchor_cos
    normalized = clamp((dot_product + 1.0) * 50.0)
    return normalized, dot_product


def data_quality_score(station: SupportStation) -> float:
    pieces = []

    if station.usable_years is not None:
        pieces.append(clamp(100.0 * station.usable_years / 50.0))

    if station.usable_end_year is not None:
        pieces.append(clamp(100.0 * (station.usable_end_year - 2000.0) / 25.0))

    if not pieces:
        return 50.0

    return sum(pieces) / len(pieces)


def weighted_average(values: Mapping[str, float], weights: Mapping[str, float]) -> float:
    total = 0.0
    weight_total = 0.0

    for name, value in values.items():
        weight = weights.get(name, 0.0)
        if weight <= 0:
            continue
        total += clamp(value) * weight
        weight_total += weight

    if weight_total == 0:
        return 0.0

    return clamp(total / weight_total)


def calculate_anchor_match(point: SupportStation, anchor: SupportStation) -> AnchorMatch:
    distance_km = calculate_distance_km(
        point.latitude,
        point.longitude,
        anchor.latitude,
        anchor.longitude,
    )
    point_elevation = station_elevation(point)
    anchor_elevation = station_elevation(anchor)
    elevation_delta = (
        abs(point_elevation - anchor_elevation)
        if point_elevation is not None and anchor_elevation is not None
        else None
    )
    point_relief = station_relief(point)
    anchor_relief = station_relief(anchor)
    relief_delta = (
        abs(point_relief - anchor_relief)
        if point_relief is not None and anchor_relief is not None
        else None
    )
    point_tpi = station_tpi(point)
    anchor_tpi = station_tpi(anchor)
    tpi_delta = (
        abs(point_tpi - anchor_tpi)
        if point_tpi is not None and anchor_tpi is not None
        else None
    )
    point_slope = station_slope(point)
    anchor_slope = station_slope(anchor)
    slope_delta = (
        abs(point_slope - anchor_slope)
        if point_slope is not None and anchor_slope is not None
        else None
    )
    aspect_component, aspect_similarity = aspect_score(point, anchor)
    components = {
        "regional_proximity": decay_score(distance_km, 150.0),
        "elevation_similarity": (
            decay_score(elevation_delta, 350.0)
            if elevation_delta is not None
            else 50.0
        ),
        "terrain_relief_similarity": (
            decay_score(relief_delta, 300.0)
            if relief_delta is not None
            else 50.0
        ),
        "terrain_position_similarity": (
            decay_score(tpi_delta, 120.0)
            if tpi_delta is not None
            else 50.0
        ),
        "slope_similarity": (
            decay_score(slope_delta, 8.0)
            if slope_delta is not None
            else 50.0
        ),
        "aspect_similarity": aspect_component,
        "anchor_data_quality": data_quality_score(anchor),
    }
    weights = {
        definition["name"]: definition["weight"]
        for definition in FEATURE_DEFINITIONS
    }

    return AnchorMatch(
        station=anchor,
        score=weighted_average(components, weights),
        components=components,
        distance_km=distance_km,
        elevation_delta_m=elevation_delta,
        relief_delta_m=relief_delta,
        tpi_delta_m=tpi_delta,
        slope_delta_degrees=slope_delta,
        aspect_similarity=aspect_similarity,
    )


def aggregate_representativeness(matches: list[AnchorMatch]) -> float:
    if not matches:
        return 0.0

    top_one = matches[0].score
    top_three = mean([match.score for match in matches[:3]]) or top_one
    top_eight = mean([match.score for match in matches[:TOP_ANCHOR_COUNT]]) or top_three
    return 0.55 * top_one + 0.30 * top_three + 0.15 * top_eight


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def build_station_lookup(stations: list[SupportStation]) -> dict[str, SupportStation]:
    return {station.station_id: station for station in stations}


def build_representativeness_rows(
    calibration_points: list[CsvRow],
    station_lookup: dict[str, SupportStation],
    anchor_pool: list[SupportStation],
) -> list[dict[str, object]]:
    rows = []

    for calibration_row in calibration_points:
        station_id = calibration_row["target_station_id"]
        point_station = station_lookup.get(station_id)
        if point_station is None:
            raise ValueError(f"Could not find station metadata for {station_id}.")

        matches = [
            calculate_anchor_match(point_station, anchor)
            for anchor in anchor_pool
            if anchor.station_id != station_id
        ]
        matches.sort(key=lambda match: match.score, reverse=True)
        top_match = matches[0]
        top_ids = [
            {
                "stationId": match.station.station_id,
                "role": match.station.station_role,
                "similarity": round(match.score, 2),
                "distanceKm": round(match.distance_km, 2),
                "elevationDeltaM": (
                    round(match.elevation_delta_m, 2)
                    if match.elevation_delta_m is not None
                    else None
                ),
            }
            for match in matches[:TOP_ANCHOR_COUNT]
        ]

        row = {
            "target_station_id": station_id,
            "target_name": calibration_row.get("target_name", point_station.station_name),
            "observed_mae_f": calibration_row.get("observed_mae_f", ""),
            "observed_rmse_f": calibration_row.get("observed_rmse_f", ""),
            "observed_correlation": calibration_row.get("observed_correlation", ""),
            "support_score": calibration_row.get("support_score", ""),
            "representativeness_score": fmt(aggregate_representativeness(matches), 2),
            "top_anchor_station_id": top_match.station.station_id,
            "top_anchor_name": top_match.station.station_name,
            "top_anchor_role": top_match.station.station_role,
            "top_anchor_similarity": fmt(top_match.score, 2),
            "top_anchor_distance_km": fmt(top_match.distance_km, 3),
            "top_anchor_elevation_delta_m": fmt(top_match.elevation_delta_m, 2),
            "top_anchor_relief_delta_m": fmt(top_match.relief_delta_m, 2),
            "top_anchor_tpi_delta_m": fmt(top_match.tpi_delta_m, 2),
            "top_anchor_slope_delta_degrees": fmt(top_match.slope_delta_degrees, 3),
            "top_anchor_aspect_similarity": fmt(top_match.aspect_similarity, 4),
            "mean_top3_similarity": fmt(mean([match.score for match in matches[:3]]), 2),
            "mean_top8_similarity": fmt(
                mean([match.score for match in matches[:TOP_ANCHOR_COUNT]]),
                2,
            ),
            "top_anchor_ids": json.dumps(top_ids, separators=(",", ":")),
        }
        for component_name, value in top_match.components.items():
            row[f"top_anchor_component_{component_name}"] = fmt(value, 2)

        rows.append(row)

    rows.sort(key=lambda row: row["target_station_id"])
    return rows


def numeric(row: Mapping[str, object], column: str) -> float | None:
    return to_optional_float(row.get(column))


def numeric_pairs(rows: list[Mapping[str, object]], x_column: str, y_column: str) -> list[tuple[float, float]]:
    pairs = []
    for row in rows:
        x_value = numeric(row, x_column)
        y_value = numeric(row, y_column)
        if x_value is not None and y_value is not None:
            pairs.append((x_value, y_value))
    return pairs


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


def relationship_row(rows: list[Mapping[str, object]], column: str, label: str) -> list[object]:
    pairs = numeric_pairs(rows, column, "observed_mae_f")
    r_value = correlation(pairs)
    return [label, fmt(r_value, 3), relationship_direction(r_value), len(pairs)]


def relationship_direction(value: float | None) -> str:
    if value is None:
        return "N/A"
    if value <= -0.35:
        return "good inverse signal"
    if value < -0.15:
        return "weak inverse signal"
    if value < 0.15:
        return "flat/unclear"
    return "higher value, higher error"


def station_table(rows: list[Mapping[str, object]]) -> str:
    return render_html_table(
        [
            "Station",
            "Name",
            "MAE F",
            "Support",
            "Represent.",
            "Top anchor",
            "Role",
            "Anchor km",
            "Elev delta m",
        ],
        [
            [
                trusted_html(
                    f"<code>{escape(row.get('target_station_id', ''))}</code>"
                ),
                row.get("target_name", ""),
                row.get("observed_mae_f", ""),
                row.get("support_score", ""),
                row.get("representativeness_score", ""),
                trusted_html(
                    f"<code>{escape(row.get('top_anchor_station_id', ''))}</code>"
                ),
                row.get("top_anchor_role", ""),
                row.get("top_anchor_distance_km", ""),
                row.get("top_anchor_elevation_delta_m", ""),
            ]
            for row in rows
        ],
    )


def component_table() -> str:
    return render_html_table(
        ["Feature", "Starting weight", "Meaning"],
        [
            [
                trusted_html(f"<code>{escape(definition['name'])}</code>"),
                f"{definition['weight']:.2f}",
                definition["plain"],
            ]
            for definition in FEATURE_DEFINITIONS
        ],
    )


def scatter_plot(rows: list[Mapping[str, object]], x_column: str, label: str) -> str:
    pairs = numeric_pairs(rows, x_column, "observed_mae_f")
    if len(pairs) < 2:
        return "<p class=\"muted\">Not enough points.</p>"

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
    y_min = max(0.0, min(y_values) - 0.2)
    y_max = max(y_values) + 0.2

    if x_min == x_max:
        x_min -= 1.0
        x_max += 1.0

    def x_scale(value: float) -> float:
        return margin_left + ((value - x_min) / (x_max - x_min)) * plot_width

    def y_scale(value: float) -> float:
        return margin_top + (1.0 - ((value - y_min) / (y_max - y_min))) * plot_height

    point_html = []
    for x_value, y_value in pairs:
        color = "#2563eb" if y_value <= 2.0 else "#dc2626" if y_value >= 3.0 else "#d97706"
        point_html.append(
            f"<circle cx=\"{x_scale(x_value):.1f}\" cy=\"{y_scale(y_value):.1f}\" "
            f"r=\"4\" fill=\"{color}\" fill-opacity=\"0.74\" />"
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
      {''.join(point_html)}
    </svg>
    """


def render_report(
    model_run_id: str,
    representativeness_rows: list[dict[str, object]],
) -> str:
    mae_values = [
        value
        for row in representativeness_rows
        if (value := numeric(row, "observed_mae_f")) is not None
    ]
    support_r = correlation(numeric_pairs(
        representativeness_rows,
        "support_score",
        "observed_mae_f",
    ))
    representativeness_r = correlation(numeric_pairs(
        representativeness_rows,
        "representativeness_score",
        "observed_mae_f",
    ))
    sorted_by_mae = sorted(
        representativeness_rows,
        key=lambda row: numeric(row, "observed_mae_f") or 0.0,
    )
    worst_rows = sorted_by_mae[-10:][::-1]
    best_rows = sorted_by_mae[:10]
    high_support_failures = [
        row
        for row in representativeness_rows
        if (
            (numeric(row, "support_score") or 0.0) >= 85.0
            and (numeric(row, "observed_mae_f") or 0.0) >= 2.5
        )
    ]
    high_support_failures.sort(
        key=lambda row: numeric(row, "observed_mae_f") or 0.0,
        reverse=True,
    )

    relationship_table = render_html_table(
        ["Score / Feature", "r with MAE", "Read", "Rows"],
        [
            relationship_row(
                representativeness_rows,
                "support_score",
                "Existing support score",
            ),
            relationship_row(
                representativeness_rows,
                "representativeness_score",
                "Environmental representativeness",
            ),
            relationship_row(
                representativeness_rows,
                "top_anchor_distance_km",
                "Top anchor distance",
            ),
            relationship_row(
                representativeness_rows,
                "top_anchor_elevation_delta_m",
                "Top anchor elevation delta",
            ),
            relationship_row(
                representativeness_rows,
                "top_anchor_relief_delta_m",
                "Top anchor relief delta",
            ),
            relationship_row(
                representativeness_rows,
                "mean_top8_similarity",
                "Mean top-8 anchor similarity",
            ),
        ],
    )

    takeaways = [
        (
            "Representativeness is built from environmental similarity, not a fixed radius. "
            "Distance is only one component."
        ),
        (
            f"The existing support score has r={fmt(support_r, 3)} with MAE. "
            f"This prototype representativeness score has r={fmt(representativeness_r, 3)} with MAE."
        ),
        (
            "If representativeness is not stronger yet, that is still useful: it tells us "
            "which feature weights or missing inputs need attention before map generation."
        ),
    ]
    summary_cards = "".join(
        [
            render_metric_card("Validation stations", len(representativeness_rows)),
            render_metric_card("Mean MAE", fmt(mean(mae_values), 2, " F")),
            render_metric_card(
                "Median MAE",
                fmt(percentile(mae_values, 0.50), 2, " F"),
            ),
            render_metric_card("Support r with MAE", fmt(support_r, 3)),
            render_metric_card("Represent. r with MAE", fmt(representativeness_r, 3)),
        ]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Representativeness Audit - {escape(model_run_id)}</title>
  <style>
    :root {{
      --bg: #f8fafc;
      --text: #111827;
      --muted: #64748b;
      --line: #dbe3ef;
      --panel: #ffffff;
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
      margin: 0 0 12px;
      font-size: 16px;
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
    .note, .card, .chart-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    .note {{
      background: #eff6ff;
      border-color: #bfdbfe;
      margin: 18px 0;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 12px;
      margin: 18px 0 8px;
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
    tr:last-child td {{ border-bottom: 0; }}
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
    <h1>Representativeness Audit</h1>
    <p class="muted"><code>{escape(model_run_id)}</code></p>
  </header>
  <main>
    <section class="note">
      <strong>Question:</strong> If a validation station were unknown, how well would the other real stations environmentally represent it?
    </section>

    <section class="cards">
      {summary_cards}
    </section>

    <h2>How To Read This</h2>
    <ul>{"".join(f"<li>{escape(item)}</li>" for item in takeaways)}</ul>

    <h2>Step 1: Feature Definition</h2>
    <p class="muted">These are starting weights for a transparent prototype, not final calibrated weights.</p>
    {component_table()}

    <h2>Step 2-3: Station-To-Station Prototype</h2>
    <p class="muted">For each validation station, the script excludes that station and finds the most environmentally representative anchors from the remaining target and hub stations.</p>
    {relationship_table}

    <h2>Step 4: Visual Audit</h2>
    <div class="chart-grid">
      <section class="chart-card">
        <h3>Existing support score vs MAE</h3>
        {scatter_plot(representativeness_rows, "support_score", "Support score")}
      </section>
      <section class="chart-card">
        <h3>Representativeness score vs MAE</h3>
        {scatter_plot(representativeness_rows, "representativeness_score", "Representativeness score")}
      </section>
      <section class="chart-card">
        <h3>Top anchor distance vs MAE</h3>
        {scatter_plot(representativeness_rows, "top_anchor_distance_km", "Top anchor distance km")}
      </section>
      <section class="chart-card">
        <h3>Top anchor elevation delta vs MAE</h3>
        {scatter_plot(representativeness_rows, "top_anchor_elevation_delta_m", "Top anchor elevation delta m")}
      </section>
    </div>

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

    <h2>High-Support Failures</h2>
    <p class="muted">These are the most important stations to understand before calling anything calibrated confidence.</p>
    {station_table(high_support_failures[:12]) if high_support_failures else "<p>No high-support failures by the current threshold.</p>"}
  </main>
</body>
</html>
"""


def main() -> None:
    arguments = parse_arguments()
    paths = resolve_model_run(arguments.model_run_root, arguments.model_run_id)
    model_run = load_model_run(paths)
    inputs = load_confidence_support_inputs(
        target_candidate_file=arguments.target_candidates,
        hub_candidate_file=arguments.hub_candidates,
        terrain_file=arguments.terrain_features,
        validation_metrics_file=paths.station_metrics,
        model_reference=arguments.model_run_id,
    )
    all_stations = [*inputs.target_stations, *inputs.hub_stations]
    station_by_id = build_station_lookup(all_stations)
    output_rows = build_representativeness_rows(
        model_run["calibration_points"],
        station_by_id,
        all_stations,
    )
    output_csv = arguments.output_csv or (paths.root / "representativeness_scores.csv")
    output_html = arguments.output_html or (paths.root / "representativeness_audit.html")

    write_csv_rows(output_csv, output_rows, REPRESENTATIVENESS_FIELDNAMES)
    output_html.write_text(render_report(arguments.model_run_id, output_rows))

    support_r = correlation(numeric_pairs(output_rows, "support_score", "observed_mae_f"))
    representativeness_r = correlation(numeric_pairs(
        output_rows,
        "representativeness_score",
        "observed_mae_f",
    ))
    print(f"Representativeness scores: {output_csv}")
    print(f"Representativeness audit: {output_html}")
    print(f"Support r with MAE: {fmt(support_r, 3)}")
    print(f"Representativeness r with MAE: {fmt(representativeness_r, 3)}")


if __name__ == "__main__":
    main()
