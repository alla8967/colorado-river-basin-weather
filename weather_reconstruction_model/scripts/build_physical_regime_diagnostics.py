"""Summarize physical-regime patterns behind validation performance.

The report relates reconstruction quality to terrain, station spacing, and physical similarity signals."""

from __future__ import annotations

import argparse
import math
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

import config
from build_failure_diagnostics_report import (
    DEFAULT_GENERAL_TABLE,
    DEFAULT_MODEL_RUN_ID,
    SEASONS,
    collect_error_diagnostics,
    stream_predictor_metadata,
    worst_season,
)
from common.csv_utils import CsvRow, read_csv_rows, write_csv_rows
from common.model_runs import load_model_run, resolve_model_run
from common.number_utils import to_optional_float
from common.reporting import escape_html as escape
from common.reporting import render_html_table, render_metric_card, trusted_html

SCORE_FIELDNAMES = [
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
    "support_score",
    "representativeness_score",
    "worst_season",
    "worst_season_rows",
    "worst_season_confidence",
    "worst_season_mae_f",
    "worst_season_bias_f",
    "seasonal_confidence_warning",
    "winter_rows",
    "winter_mae_f",
    "winter_bias_f",
    "winter_confidence",
    "spring_rows",
    "spring_mae_f",
    "spring_bias_f",
    "spring_confidence",
    "summer_rows",
    "summer_mae_f",
    "summer_bias_f",
    "summer_confidence",
    "fall_rows",
    "fall_mae_f",
    "fall_bias_f",
    "fall_confidence",
    "cold_pool_index",
    "cold_pool_tpi_component",
    "cold_pool_slope_component",
    "cold_pool_relief_component",
    "cold_pool_elevation_component",
    "monsoon_region_flag",
    "arid_plateau_flag",
    "mean_abs_predictor_elevation_delta_m",
    "max_abs_predictor_elevation_delta_m",
    "mean_abs_predictor_dem_elevation_delta_m",
    "max_abs_predictor_dem_elevation_delta_m",
    "mean_abs_predictor_relief_delta_m",
    "max_abs_predictor_relief_delta_m",
    "mean_abs_predictor_tpi_delta_m",
    "max_abs_predictor_tpi_delta_m",
    "mean_predictor_distance_km",
    "max_predictor_distance_km",
    "elevation_mismatch_risk",
    "terrain_mismatch_risk",
    "high_support_physical_mismatch_failure",
    "likely_failure_regime",
]

REGIME_COLUMNS = [
    "winter_cold_pool",
    "high_elevation_reservoir_or_mesa",
    "monsoon_summer_bias",
    "arid_exposed_plateau",
    "predictor_physical_mismatch",
    "low_confidence_seasonal_artifact",
]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build all-station physical-regime diagnostics for a model run."
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
        help="General training table used to compute physical mismatch signals.",
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
        help="Optional CSV output path for physical-regime diagnostics.",
    )
    return parser.parse_args()


def fmt(value: object, decimals: int = 2, suffix: str = "") -> str:
    numeric_value = to_optional_float(value)
    if numeric_value is None or math.isnan(numeric_value):
        return ""
    return f"{numeric_value:.{decimals}f}{suffix}"


def bool_text(value: bool) -> str:
    return "yes" if value else "no"


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def seasonal_confidence(row_count: int) -> str:
    if row_count == 0:
        return "none"
    if row_count < 25:
        return "low"
    if row_count < 50:
        return "medium"
    return "high"


def monsoon_region_flag(latitude: float | None, longitude: float | None) -> bool:
    if latitude is None or longitude is None:
        return False
    return 31.0 <= latitude <= 38.0 and -115.0 <= longitude <= -107.0


def arid_plateau_flag(
    latitude: float | None,
    longitude: float | None,
    elevation_m: float | None,
) -> bool:
    if elevation_m is None:
        return False
    return monsoon_region_flag(latitude, longitude) and elevation_m >= 1000.0


def cold_pool_components(
    tpi_m: float | None,
    slope_degrees: float | None,
    local_relief_3km_m: float | None,
    elevation_m: float | None,
) -> dict[str, float]:
    tpi_component = clamp((-(tpi_m or 0.0)) / 50.0)
    slope_component = (
        clamp((8.0 - slope_degrees) / 8.0)
        if slope_degrees is not None
        else 0.0
    )
    relief_component = (
        clamp(local_relief_3km_m / 500.0)
        if local_relief_3km_m is not None
        else 0.0
    )
    elevation_component = (
        clamp((elevation_m - 1200.0) / 1800.0)
        if elevation_m is not None
        else 0.0
    )

    return {
        "tpi": tpi_component,
        "slope": slope_component,
        "relief": relief_component,
        "elevation": elevation_component,
        "index": (
            0.35 * tpi_component
            + 0.20 * slope_component
            + 0.25 * relief_component
            + 0.20 * elevation_component
        ),
    }


def numeric_values(items: list[Mapping[str, object]], field_name: str) -> list[float]:
    output = []
    for item in items:
        value = to_optional_float(item.get(field_name))
        if value is not None:
            output.append(abs(value))
    return output


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def max_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return max(values)


def predictor_mismatch_metrics(
    predictor_metadata: Mapping[str, object],
) -> dict[str, float | bool | None]:
    predictors = [
        *predictor_metadata["hubs"],
        *predictor_metadata["target_neighbors"],
    ]
    elevation_deltas = numeric_values(predictors, "elevation_difference_m")
    dem_elevation_deltas = numeric_values(predictors, "abs_dem_elevation_delta_m")
    relief_deltas = numeric_values(predictors, "abs_local_relief_delta_m")
    tpi_deltas = numeric_values(predictors, "abs_terrain_position_delta_m")
    distances = numeric_values(predictors, "distance_km")
    mean_elevation_delta = mean(elevation_deltas)
    max_elevation_delta = max_or_none(elevation_deltas)
    mean_dem_delta = mean(dem_elevation_deltas)
    max_dem_delta = max_or_none(dem_elevation_deltas)
    mean_relief_delta = mean(relief_deltas)
    max_relief_delta = max_or_none(relief_deltas)
    mean_tpi_delta = mean(tpi_deltas)
    max_tpi_delta = max_or_none(tpi_deltas)

    elevation_mismatch = (
        (mean_elevation_delta is not None and mean_elevation_delta > 250.0)
        or (max_elevation_delta is not None and max_elevation_delta > 450.0)
        or (mean_dem_delta is not None and mean_dem_delta > 250.0)
        or (max_dem_delta is not None and max_dem_delta > 450.0)
    )
    terrain_mismatch = (
        (mean_relief_delta is not None and mean_relief_delta > 150.0)
        or (mean_tpi_delta is not None and mean_tpi_delta > 40.0)
    )

    return {
        "mean_abs_predictor_elevation_delta_m": mean_elevation_delta,
        "max_abs_predictor_elevation_delta_m": max_elevation_delta,
        "mean_abs_predictor_dem_elevation_delta_m": mean_dem_delta,
        "max_abs_predictor_dem_elevation_delta_m": max_dem_delta,
        "mean_abs_predictor_relief_delta_m": mean_relief_delta,
        "max_abs_predictor_relief_delta_m": max_relief_delta,
        "mean_abs_predictor_tpi_delta_m": mean_tpi_delta,
        "max_abs_predictor_tpi_delta_m": max_tpi_delta,
        "mean_predictor_distance_km": mean(distances),
        "max_predictor_distance_km": max_or_none(distances),
        "elevation_mismatch_risk": elevation_mismatch,
        "terrain_mismatch_risk": terrain_mismatch,
    }


def season_metric(
    diagnostics: Mapping[str, object],
    season: str,
    metric_name: str,
) -> float | int | None:
    return diagnostics["seasonal"][season].get(metric_name)


def seasonal_warning(diagnostics: Mapping[str, object], worst_season_name: str) -> str:
    warnings = []
    worst_rows = int(season_metric(diagnostics, worst_season_name, "rows") or 0)
    worst_confidence = seasonal_confidence(worst_rows)

    if worst_confidence in ("low", "none"):
        warnings.append(
            f"worst season has {worst_confidence} confidence ({worst_rows} rows)"
        )

    missing_seasons = [
        season
        for season in SEASONS
        if int(season_metric(diagnostics, season, "rows") or 0) == 0
    ]
    if missing_seasons:
        warnings.append("zero rows for " + ", ".join(missing_seasons))

    return "; ".join(warnings)


def likely_regimes(
    station_name: str,
    elevation_m: float | None,
    support_score: float | None,
    mae_f: float | None,
    diagnostics: Mapping[str, object],
    worst_season_name: str,
    worst_season_confidence: str,
    cold_pool_index: float,
    monsoon_flag: bool,
    arid_flag: bool,
    elevation_mismatch_risk: bool,
    terrain_mismatch_risk: bool,
) -> list[str]:
    regimes = []
    winter_bias = to_optional_float(season_metric(diagnostics, "Winter", "bias"))
    winter_mae = to_optional_float(season_metric(diagnostics, "Winter", "mae"))
    spring_bias = to_optional_float(season_metric(diagnostics, "Spring", "bias"))
    spring_mae = to_optional_float(season_metric(diagnostics, "Spring", "mae"))
    summer_bias = to_optional_float(season_metric(diagnostics, "Summer", "bias"))
    summer_mae = to_optional_float(season_metric(diagnostics, "Summer", "mae"))
    station_name_upper = station_name.upper()

    if worst_season_confidence in ("low", "none"):
        regimes.append("low_confidence_seasonal_artifact")

    if (
        winter_mae is not None
        and winter_mae >= 3.0
        and winter_bias is not None
        and winter_bias <= -0.5
        and cold_pool_index >= 0.45
    ):
        regimes.append("winter_cold_pool")

    if (
        elevation_m is not None
        and elevation_m >= 2400.0
        and ("RSVR" in station_name_upper or "RESERVOIR" in station_name_upper)
        and worst_season_name in ("Winter", "Spring", "Fall")
    ):
        regimes.append("high_elevation_reservoir_or_mesa")

    if (
        monsoon_flag
        and summer_mae is not None
        and summer_mae >= 3.5
        and summer_bias is not None
        and summer_bias <= -1.5
    ):
        regimes.append("monsoon_summer_bias")

    if (
        arid_flag
        and (
            (spring_bias is not None and spring_bias >= 1.5)
            or (summer_bias is not None and summer_bias >= 1.5)
            or (
                spring_mae is not None
                and spring_mae >= 3.0
                and worst_season_name == "Spring"
            )
        )
    ):
        regimes.append("arid_exposed_plateau")

    high_support_failure = (
        support_score is not None
        and support_score >= 85.0
        and mae_f is not None
        and mae_f >= 2.5
    )
    if high_support_failure and (elevation_mismatch_risk or terrain_mismatch_risk):
        regimes.append("predictor_physical_mismatch")

    return regimes or ["unknown"]


def load_representativeness_by_station(model_run_root: Path) -> dict[str, CsvRow]:
    file_path = model_run_root / "representativeness_scores.csv"
    if not file_path.exists():
        return {}
    return {
        row["target_station_id"]: row
        for row in read_csv_rows(file_path)
    }


def build_physical_rows(
    calibration_rows: list[CsvRow],
    diagnostics_by_station: Mapping[str, Mapping[str, object]],
    representativeness_by_station: Mapping[str, CsvRow],
    predictor_metadata_by_station: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    rows = []

    for calibration_row in calibration_rows:
        station_id = calibration_row["target_station_id"]
        diagnostics = diagnostics_by_station[station_id]
        representativeness = representativeness_by_station.get(station_id, {})
        predictor_metadata = predictor_metadata_by_station[station_id]
        station_name = calibration_row.get("target_name", "")
        latitude = to_optional_float(calibration_row.get("latitude"))
        longitude = to_optional_float(calibration_row.get("longitude"))
        elevation_m = to_optional_float(calibration_row.get("elevation_m"))
        mae_f = to_optional_float(calibration_row.get("observed_mae_f"))
        support_score = to_optional_float(calibration_row.get("support_score"))
        worst_season_name, worst_season_mae = worst_season(diagnostics["seasonal"])
        worst_rows = int(season_metric(diagnostics, worst_season_name, "rows") or 0)
        worst_confidence = seasonal_confidence(worst_rows)
        warning = seasonal_warning(diagnostics, worst_season_name)
        cold_pool = cold_pool_components(
            to_optional_float(calibration_row.get("terrain_position_index_m")),
            to_optional_float(calibration_row.get("slope_degrees")),
            to_optional_float(calibration_row.get("local_relief_m_r3000m")),
            elevation_m,
        )
        monsoon_flag = monsoon_region_flag(latitude, longitude)
        arid_flag = arid_plateau_flag(latitude, longitude, elevation_m)
        mismatch = predictor_mismatch_metrics(predictor_metadata)
        regimes = likely_regimes(
            station_name=station_name,
            elevation_m=elevation_m,
            support_score=support_score,
            mae_f=mae_f,
            diagnostics=diagnostics,
            worst_season_name=worst_season_name,
            worst_season_confidence=worst_confidence,
            cold_pool_index=cold_pool["index"],
            monsoon_flag=monsoon_flag,
            arid_flag=arid_flag,
            elevation_mismatch_risk=bool(mismatch["elevation_mismatch_risk"]),
            terrain_mismatch_risk=bool(mismatch["terrain_mismatch_risk"]),
        )
        high_support_physical_mismatch_failure = (
            support_score is not None
            and support_score >= 85.0
            and mae_f is not None
            and mae_f >= 2.5
            and (
                cold_pool["index"] >= 0.45
                or monsoon_flag
                or arid_flag
                or bool(mismatch["elevation_mismatch_risk"])
                or bool(mismatch["terrain_mismatch_risk"])
            )
        )
        row = {
            "station_id": station_id,
            "station_name": station_name,
            "latitude": calibration_row.get("latitude", ""),
            "longitude": calibration_row.get("longitude", ""),
            "elevation_m": calibration_row.get("elevation_m", ""),
            "mae_f": calibration_row.get("observed_mae_f", ""),
            "rmse_f": calibration_row.get("observed_rmse_f", ""),
            "correlation": calibration_row.get("observed_correlation", ""),
            "test_rows": calibration_row.get("test_rows", ""),
            "mean_bias_f": fmt(diagnostics["overall"].get("bias"), 3),
            "support_score": calibration_row.get("support_score", ""),
            "representativeness_score": representativeness.get(
                "representativeness_score",
                "",
            ),
            "worst_season": worst_season_name,
            "worst_season_rows": worst_rows,
            "worst_season_confidence": worst_confidence,
            "worst_season_mae_f": fmt(worst_season_mae, 3),
            "worst_season_bias_f": fmt(
                season_metric(diagnostics, worst_season_name, "bias"),
                3,
            ),
            "seasonal_confidence_warning": warning,
            "cold_pool_index": fmt(cold_pool["index"], 3),
            "cold_pool_tpi_component": fmt(cold_pool["tpi"], 3),
            "cold_pool_slope_component": fmt(cold_pool["slope"], 3),
            "cold_pool_relief_component": fmt(cold_pool["relief"], 3),
            "cold_pool_elevation_component": fmt(cold_pool["elevation"], 3),
            "monsoon_region_flag": bool_text(monsoon_flag),
            "arid_plateau_flag": bool_text(arid_flag),
            "elevation_mismatch_risk": bool_text(
                bool(mismatch["elevation_mismatch_risk"])
            ),
            "terrain_mismatch_risk": bool_text(
                bool(mismatch["terrain_mismatch_risk"])
            ),
            "high_support_physical_mismatch_failure": bool_text(
                high_support_physical_mismatch_failure
            ),
            "likely_failure_regime": "; ".join(regimes),
        }

        for season in SEASONS:
            key = season.lower()
            season_rows = int(season_metric(diagnostics, season, "rows") or 0)
            row[f"{key}_rows"] = season_rows
            row[f"{key}_mae_f"] = fmt(season_metric(diagnostics, season, "mae"), 3)
            row[f"{key}_bias_f"] = fmt(season_metric(diagnostics, season, "bias"), 3)
            row[f"{key}_confidence"] = seasonal_confidence(season_rows)

        for key, value in mismatch.items():
            if key.endswith("_risk"):
                continue
            row[key] = fmt(value, 3)

        rows.append(row)

    rows.sort(key=lambda row: to_optional_float(row.get("mae_f")) or 0.0, reverse=True)
    return rows


def flag_value(row: Mapping[str, object], column: str) -> bool:
    return str(row.get(column, "")).strip().lower() == "yes"


def regime_counter(rows: list[Mapping[str, object]]) -> Counter:
    counts: Counter = Counter()
    for row in rows:
        regimes = [
            item.strip()
            for item in str(row.get("likely_failure_regime", "")).split(";")
            if item.strip()
        ]
        counts.update(regimes)
    return counts


def mean_mae(rows: list[Mapping[str, object]]) -> float | None:
    values = [
        value
        for row in rows
        if (value := to_optional_float(row.get("mae_f"))) is not None
    ]
    return mean(values)


def grouped_signal_table(rows: list[Mapping[str, object]]) -> str:
    checks = [
        ("cold_pool_index", "Cold-pool index >= 0.45", lambda row: (to_optional_float(row.get("cold_pool_index")) or 0.0) >= 0.45),
        ("monsoon_region_flag", "Monsoon region", lambda row: flag_value(row, "monsoon_region_flag")),
        ("arid_plateau_flag", "Arid plateau", lambda row: flag_value(row, "arid_plateau_flag")),
        ("elevation_mismatch_risk", "Elevation mismatch risk", lambda row: flag_value(row, "elevation_mismatch_risk")),
        ("terrain_mismatch_risk", "Terrain mismatch risk", lambda row: flag_value(row, "terrain_mismatch_risk")),
        ("seasonal_confidence_warning", "Seasonal confidence warning", lambda row: bool(row.get("seasonal_confidence_warning"))),
    ]
    table_rows = []

    for _column, label, predicate in checks:
        yes_rows = [row for row in rows if predicate(row)]
        no_rows = [row for row in rows if not predicate(row)]
        yes_mean = mean_mae(yes_rows)
        no_mean = mean_mae(no_rows)
        delta = (
            yes_mean - no_mean
            if yes_mean is not None and no_mean is not None
            else None
        )
        table_rows.append([
            label,
            len(yes_rows),
            fmt(yes_mean, 2, " F"),
            fmt(no_mean, 2, " F"),
            fmt(delta, 2, " F"),
        ])

    return render_html_table(
        ["Flag", "Flagged stations", "Flagged mean MAE", "Other mean MAE", "Delta"],
        table_rows,
    )


def regime_table(rows: list[Mapping[str, object]]) -> str:
    counts = regime_counter(rows)
    table_rows = []

    for regime, count in counts.most_common():
        regime_rows = [
            row
            for row in rows
            if regime in str(row.get("likely_failure_regime", "")).split("; ")
        ]
        table_rows.append([
            trusted_html(f"<code>{escape(regime)}</code>"),
            count,
            fmt(mean_mae(regime_rows), 2, " F"),
        ])

    return render_html_table(["Regime", "Stations", "Mean MAE"], table_rows)


def row_table(rows: list[Mapping[str, object]], limit: int | None = None) -> str:
    selected_rows = rows[:limit] if limit is not None else rows
    return render_html_table(
        [
            "Station",
            "Name",
            "Worst season",
            "Season confidence",
            "MAE F",
            "Bias F",
            "Support",
            "Represent.",
            "Cold pool",
            "Monsoon",
            "Arid plateau",
            "Elev mismatch",
            "Terrain mismatch",
            "Likely regime",
        ],
        [
            [
                trusted_html(f"<code>{escape(row.get('station_id', ''))}</code>"),
                row.get("station_name", ""),
                row.get("worst_season", ""),
                row.get("worst_season_confidence", ""),
                row.get("mae_f", ""),
                row.get("mean_bias_f", ""),
                row.get("support_score", ""),
                row.get("representativeness_score", ""),
                row.get("cold_pool_index", ""),
                row.get("monsoon_region_flag", ""),
                row.get("arid_plateau_flag", ""),
                row.get("elevation_mismatch_risk", ""),
                row.get("terrain_mismatch_risk", ""),
                row.get("likely_failure_regime", ""),
            ]
            for row in selected_rows
        ],
    )


def warning_table(rows: list[Mapping[str, object]]) -> str:
    warning_rows = [
        row
        for row in rows
        if row.get("seasonal_confidence_warning")
    ]
    if not warning_rows:
        return "<p class=\"good\">No seasonal confidence warnings.</p>"

    return render_html_table(
        ["Station", "Name", "Worst season", "Rows", "Confidence", "Warning"],
        [
            [
                trusted_html(f"<code>{escape(row.get('station_id', ''))}</code>"),
                row.get("station_name", ""),
                row.get("worst_season", ""),
                row.get("worst_season_rows", ""),
                row.get("worst_season_confidence", ""),
                row.get("seasonal_confidence_warning", ""),
            ]
            for row in warning_rows
        ],
    )


def render_report(model_run_id: str, rows: list[Mapping[str, object]]) -> str:
    high_support_physical = [
        row
        for row in rows
        if flag_value(row, "high_support_physical_mismatch_failure")
    ]
    low_confidence_warnings = [
        row
        for row in rows
        if row.get("seasonal_confidence_warning")
    ]
    likely_failure_rows = [
        row
        for row in rows
        if row.get("likely_failure_regime") != "unknown"
    ]
    summary_cards = "".join(
        [
            render_metric_card("Validation stations", len(rows)),
            render_metric_card("Regime-labeled stations", len(likely_failure_rows)),
            render_metric_card(
                "High-support physical failures",
                len(high_support_physical),
            ),
            render_metric_card("Seasonal warnings", len(low_confidence_warnings)),
            render_metric_card("Mean MAE", fmt(mean_mae(rows), 2, " F")),
        ]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Physical Regime Diagnostics - {escape(model_run_id)}</title>
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
    p, li {{
      line-height: 1.5;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.92em;
    }}
    .muted {{ color: var(--muted); }}
    .good {{ color: #047857; font-weight: 700; }}
    .note, .card {{
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
    <h1>Physical Regime Diagnostics</h1>
    <p class="muted"><code>{escape(model_run_id)}</code></p>
  </header>
  <main>
    <section class="note">
      <strong>Purpose:</strong> convert the station-failure research into measurable diagnostics across all 86 validation stations. This is diagnostic-only; it does not change the trained model.
    </section>

    <section class="cards">
      {summary_cards}
    </section>

    <h2>Regime Counts</h2>
    {regime_table(rows)}

    <h2>Do The Flags Separate Higher-Error Stations?</h2>
    <p class="muted">A useful diagnostic flag should often have higher mean MAE than unflagged stations. This is not proof, but it tells us what is worth turning into model features later.</p>
    {grouped_signal_table(rows)}

    <h2>Physical Failure Regime Summary</h2>
    {row_table(rows)}

    <h2>Seasonal Confidence Warnings</h2>
    {warning_table(rows)}

    <h2>High-Support Physical Mismatch Failures</h2>
    <p class="muted">These are the cases most relevant to confidence calibration: the model looked well-supported, but physical-regime diagnostics suggest transfer risk.</p>
    {row_table(high_support_physical)}
  </main>
</body>
</html>
"""


def main() -> None:
    arguments = parse_arguments()
    paths = resolve_model_run(arguments.model_run_root, arguments.model_run_id)
    model_run = load_model_run(paths)
    representativeness_by_station = load_representativeness_by_station(paths.root)
    station_ids = {
        row["target_station_id"]
        for row in model_run["calibration_points"]
    }
    diagnostics = collect_error_diagnostics(
        model_run["validation_predictions"],
        station_ids,
    )
    predictor_metadata = stream_predictor_metadata(
        arguments.general_table,
        station_ids,
    )
    rows = build_physical_rows(
        model_run["calibration_points"],
        diagnostics,
        representativeness_by_station,
        predictor_metadata,
    )
    output_csv = arguments.output_csv or (paths.root / "physical_regime_scores.csv")
    output_html = arguments.output_html or (paths.root / "physical_regime_diagnostics.html")

    write_csv_rows(output_csv, rows, SCORE_FIELDNAMES)
    output_html.write_text(render_report(arguments.model_run_id, rows))

    print(f"Physical regime scores: {output_csv}")
    print(f"Physical regime diagnostics: {output_html}")
    print("Regime counts:")
    for regime, count in regime_counter(rows).most_common():
        print(f"- {regime}: {count}")


if __name__ == "__main__":
    main()
