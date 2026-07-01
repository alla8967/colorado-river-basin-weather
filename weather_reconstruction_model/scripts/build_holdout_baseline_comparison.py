"""Compare station-holdout model predictions with simple hub baselines.

The comparison is intentionally row-locked: every baseline metric is calculated
on the exact prediction rows emitted by the held-out model run."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path

import config
from common.csv_utils import write_csv_rows
from common.geo_utils import calculate_distance_km
from common.metrics import calculate_metrics, mean
from common.number_utils import to_float
from common.reporting import escape_html as escape
from common.reporting import render_metric_card
from train_station_holdout_model import is_strict_pass

DEFAULT_MODEL_METRICS = (
    config.PROJECT_DIR
    / "alpine_outputs"
    / "paloma"
    / "paloma_v1_tavg_station_holdout_master.csv"
)
DEFAULT_PREDICTION_DIR = config.PROJECT_DIR / "alpine_outputs" / "predictions"
DEFAULT_OUTPUT_DIR = config.REPORT_DIR / "comparisons"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build nearest-hub and IDW-hub baselines on the same rows as "
            "station-holdout model predictions."
        )
    )
    parser.add_argument("--model-metrics", type=Path, default=DEFAULT_MODEL_METRICS)
    parser.add_argument("--prediction-dir", type=Path, default=DEFAULT_PREDICTION_DIR)
    parser.add_argument(
        "--prediction-pattern",
        default="paloma_v1_tavg_group_holdout_group_*_predictions.csv",
    )
    parser.add_argument("--hub-daily", type=Path, default=config.HUB_DAILY_FILE)
    parser.add_argument("--target-daily", type=Path, default=config.TARGET_DAILY_FILE)
    parser.add_argument("--hub-candidates", type=Path, default=config.HUB_CANDIDATE_FILE)
    parser.add_argument("--target-candidates", type=Path, default=config.TARGET_CANDIDATE_FILE)
    parser.add_argument("--terrain-features", type=Path, default=config.TERRAIN_FEATURE_FILE)
    parser.add_argument("--variable", default="tavg", choices=["tavg", "tmin", "tmax"])
    parser.add_argument("--idw-hub-count", type=int, default=5)
    parser.add_argument("--idw-power", type=float, default=2.0)
    parser.add_argument("--output-stem", default="paloma_v1_tavg_holdout_baseline_comparison")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--allow-incomplete-baseline",
        action="store_true",
        help=(
            "Write comparable rows even when some prediction rows have no hub "
            "baseline. By default missing baseline rows raise an error."
        ),
    )
    return parser.parse_args()


def read_csv_rows(file_path: Path) -> list[dict[str, str]]:
    with file_path.open("r", newline="") as file:
        return list(csv.DictReader(file))


def read_csv_rows_from_files(files: Iterable[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for file_path in sorted(files):
        rows.extend(read_csv_rows(file_path))
    return rows


def load_prediction_rows(prediction_dir: Path, pattern: str) -> list[dict[str, str]]:
    prediction_files = sorted(prediction_dir.glob(pattern))
    if not prediction_files:
        raise FileNotFoundError(
            f"No prediction files matched {prediction_dir / pattern}"
        )

    rows = read_csv_rows_from_files(prediction_files)
    if not rows:
        raise ValueError(f"Prediction files matched {pattern}, but had no rows.")

    return rows


def load_group_station_ids(model_metrics_file: Path) -> dict[str, set[str]]:
    groups: dict[str, set[str]] = defaultdict(set)
    for row in read_csv_rows(model_metrics_file):
        group_id = row.get("holdout_group_id") or row.get("target_station_id")
        station_id = row["target_station_id"]
        groups[group_id].add(station_id)
    return groups


def load_station_metrics(model_metrics_file: Path) -> dict[str, dict[str, str]]:
    return {
        row["target_station_id"]: row
        for row in read_csv_rows(model_metrics_file)
    }


def load_candidates(file_path: Path) -> dict[str, dict[str, str]]:
    rows = read_csv_rows(file_path)
    return {row["station_id"]: row for row in rows}


def temperature_value(row: Mapping[str, str], variable: str) -> float | None:
    if variable in row and row[variable] != "":
        return to_float(row[variable])

    if variable == "tavg":
        if row.get("tmax") == "" or row.get("tmin") == "":
            return None
        return (to_float(row.get("tmax")) + to_float(row.get("tmin"))) / 2.0

    if row.get(variable) in (None, ""):
        return None

    return to_float(row[variable])


def load_hub_daily_values(
    file_path: Path,
    needed_dates: set[str],
    hub_ids: set[str],
    variable: str,
) -> dict[str, dict[str, float]]:
    values_by_date: dict[str, dict[str, float]] = defaultdict(dict)

    with file_path.open("r", newline="") as file:
        for row in csv.DictReader(file):
            station_id = row["station_id"]
            date_text = row["date"]

            if station_id not in hub_ids or date_text not in needed_dates:
                continue

            value = temperature_value(row, variable)
            if value is not None:
                values_by_date[date_text][station_id] = value

    return values_by_date


def load_daily_metadata(
    file_path: Path,
    station_ids: set[str],
) -> dict[str, dict[str, str]]:
    metadata: dict[str, dict[str, str]] = {}

    if not file_path.exists() or not station_ids:
        return metadata

    with file_path.open("r", newline="") as file:
        for row in csv.DictReader(file):
            station_id = row["station_id"]
            if station_id not in station_ids or station_id in metadata:
                continue

            metadata[station_id] = {
                "station_name": row.get("station_name", ""),
                "latitude": row.get("latitude", ""),
                "longitude": row.get("longitude", ""),
                "elevation": row.get("elevation", ""),
            }

            if len(metadata) == len(station_ids):
                break

    return metadata


def load_terrain_features(file_path: Path, station_ids: set[str]) -> dict[str, dict[str, str]]:
    if not file_path.exists():
        return {}

    return {
        row["station_id"]: row
        for row in read_csv_rows(file_path)
        if row.get("station_id") in station_ids
    }


def target_location(
    station_id: str,
    target_candidates: Mapping[str, Mapping[str, str]],
    target_metadata: Mapping[str, Mapping[str, str]],
) -> tuple[float, float]:
    candidate = target_candidates.get(station_id, {})
    metadata = target_metadata.get(station_id, {})
    latitude = candidate.get("latitude") or metadata.get("latitude")
    longitude = candidate.get("longitude") or metadata.get("longitude")

    if latitude in (None, "") or longitude in (None, ""):
        raise ValueError(f"Missing target location for {station_id}")

    return to_float(latitude), to_float(longitude)


def ranked_hubs_for_targets(
    target_ids: set[str],
    hub_candidates: Mapping[str, Mapping[str, str]],
    target_candidates: Mapping[str, Mapping[str, str]],
    target_metadata: Mapping[str, Mapping[str, str]],
    group_station_ids: Mapping[str, set[str]],
    target_group_by_station: Mapping[str, str],
) -> dict[str, list[tuple[str, float]]]:
    ranked_by_target: dict[str, list[tuple[str, float]]] = {}

    for target_id in target_ids:
        target_latitude, target_longitude = target_location(
            target_id,
            target_candidates,
            target_metadata,
        )
        excluded_station_ids = group_station_ids.get(
            target_group_by_station.get(target_id, ""),
            {target_id},
        )
        ranked_hubs: list[tuple[str, float]] = []

        for hub_id, hub in hub_candidates.items():
            if hub_id in excluded_station_ids:
                continue

            distance_km = calculate_distance_km(
                target_latitude,
                target_longitude,
                to_float(hub["latitude"]),
                to_float(hub["longitude"]),
            )
            ranked_hubs.append((hub_id, distance_km))

        ranked_hubs.sort(key=lambda item: item[1])
        ranked_by_target[target_id] = ranked_hubs

    return ranked_by_target


def idw_prediction(
    ranked_hubs: list[tuple[str, float]],
    daily_values: Mapping[str, float],
    hub_count: int,
    power: float,
) -> tuple[float | None, list[str]]:
    weighted_sum = 0.0
    total_weight = 0.0
    used_hub_ids: list[str] = []

    for hub_id, distance_km in ranked_hubs:
        if hub_id not in daily_values:
            continue

        bounded_distance = max(distance_km, 0.1)
        weight = 1.0 / (bounded_distance ** power)
        weighted_sum += weight * daily_values[hub_id]
        total_weight += weight
        used_hub_ids.append(hub_id)

        if len(used_hub_ids) >= hub_count:
            break

    if total_weight == 0.0:
        return None, []

    return weighted_sum / total_weight, used_hub_ids


def build_row_locked_predictions(
    prediction_rows: list[dict[str, str]],
    ranked_hubs_by_target: Mapping[str, list[tuple[str, float]]],
    hub_values_by_date: Mapping[str, Mapping[str, float]],
    idw_hub_count: int,
    idw_power: float,
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    output_rows: list[dict[str, object]] = []
    missing_rows: list[dict[str, str]] = []

    for row in prediction_rows:
        target_id = row["target_station_id"]
        date_text = row["date"]
        ranked_hubs = ranked_hubs_by_target[target_id]
        daily_values = hub_values_by_date.get(date_text, {})
        nearest_hub_id = ""
        nearest_distance_km = None
        nearest_prediction = None

        for hub_id, distance_km in ranked_hubs:
            if hub_id in daily_values:
                nearest_hub_id = hub_id
                nearest_distance_km = distance_km
                nearest_prediction = daily_values[hub_id]
                break

        idw_value, idw_hub_ids = idw_prediction(
            ranked_hubs,
            daily_values,
            idw_hub_count,
            idw_power,
        )

        if nearest_prediction is None or idw_value is None:
            missing_rows.append(row)
            continue

        actual = to_float(row["actual_tavg"])
        model_prediction = to_float(row["predicted_tavg"])
        output_rows.append({
            "date": date_text,
            "target_station_id": target_id,
            "target_name": row["target_name"],
            "holdout_group_id": row.get("holdout_group_id", ""),
            "actual_tavg": f"{actual:.4f}",
            "model_predicted_tavg": f"{model_prediction:.4f}",
            "nearest_hub_predicted_tavg": f"{nearest_prediction:.4f}",
            "nearest_hub_id": nearest_hub_id,
            "nearest_hub_distance_km": f"{nearest_distance_km:.4f}",
            "idw_hubs_predicted_tavg": f"{idw_value:.4f}",
            "idw_hub_count": len(idw_hub_ids),
            "idw_hub_ids": "|".join(idw_hub_ids),
            "model_error": f"{actual - model_prediction:.4f}",
            "nearest_hub_error": f"{actual - nearest_prediction:.4f}",
            "idw_hubs_error": f"{actual - idw_value:.4f}",
        })

    return output_rows, missing_rows


def prediction_values(
    rows: list[dict[str, object]],
    field_name: str,
) -> list[float]:
    return [to_float(row[field_name]) for row in rows]


def calculate_bias(actual_values: list[float], predicted_values: list[float]) -> float:
    return mean([
        actual - predicted
        for actual, predicted in zip(actual_values, predicted_values)
    ])


def station_metrics_for_method(
    station_rows: list[dict[str, object]],
    predicted_field: str,
) -> dict[str, float]:
    actual_values = prediction_values(station_rows, "actual_tavg")
    predicted_values = prediction_values(station_rows, predicted_field)
    metrics = calculate_metrics(actual_values, predicted_values)
    metrics["bias"] = calculate_bias(actual_values, predicted_values)
    return metrics


def build_station_comparison_rows(
    row_locked_predictions: list[dict[str, object]],
    model_metrics_by_station: Mapping[str, Mapping[str, str]],
    target_metadata: Mapping[str, Mapping[str, str]],
    terrain_by_station: Mapping[str, Mapping[str, str]],
) -> list[dict[str, object]]:
    rows_by_station: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in row_locked_predictions:
        rows_by_station[str(row["target_station_id"])].append(row)

    comparison_rows: list[dict[str, object]] = []

    for station_id, station_rows in sorted(rows_by_station.items()):
        model_metrics = station_metrics_for_method(
            station_rows,
            "model_predicted_tavg",
        )
        nearest_metrics = station_metrics_for_method(
            station_rows,
            "nearest_hub_predicted_tavg",
        )
        idw_metrics = station_metrics_for_method(
            station_rows,
            "idw_hubs_predicted_tavg",
        )
        source_metrics = model_metrics_by_station.get(station_id, {})
        if source_metrics and int(source_metrics["test_rows"]) != len(station_rows):
            raise ValueError(
                f"Prediction row count for {station_id} ({len(station_rows)}) "
                f"does not match model metrics test_rows ({source_metrics['test_rows']})."
            )

        metadata = target_metadata.get(station_id, {})
        terrain = terrain_by_station.get(station_id, {})
        comparison_rows.append({
            "target_station_id": station_id,
            "target_name": station_rows[0]["target_name"],
            "test_rows": len(station_rows),
            "model_mae": model_metrics["mae"],
            "nearest_hub_mae": nearest_metrics["mae"],
            "idw_hubs_mae": idw_metrics["mae"],
            "model_mae_delta_vs_nearest": model_metrics["mae"] - nearest_metrics["mae"],
            "model_mae_delta_vs_idw": model_metrics["mae"] - idw_metrics["mae"],
            "model_rmse": model_metrics["rmse"],
            "nearest_hub_rmse": nearest_metrics["rmse"],
            "idw_hubs_rmse": idw_metrics["rmse"],
            "model_correlation": model_metrics["correlation"],
            "nearest_hub_correlation": nearest_metrics["correlation"],
            "idw_hubs_correlation": idw_metrics["correlation"],
            "model_bias": model_metrics["bias"],
            "nearest_hub_bias": nearest_metrics["bias"],
            "idw_hubs_bias": idw_metrics["bias"],
            "model_strict_pass": is_strict_pass(model_metrics),
            "nearest_hub_strict_pass": is_strict_pass(nearest_metrics),
            "idw_hubs_strict_pass": is_strict_pass(idw_metrics),
            "elevation_m": metadata.get("elevation", ""),
            "local_relief_m": terrain.get("local_relief_m", ""),
            "slope_degrees": terrain.get("slope_degrees", ""),
        })

    return comparison_rows


def mean_field(rows: list[Mapping[str, object]], field_name: str) -> float:
    return mean([to_float(row[field_name]) for row in rows])


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("Cannot calculate percentile of an empty list.")

    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return ordered[index]


def summarize_comparison_rows(rows: list[dict[str, object]]) -> dict[str, object]:
    model_mae_values = [to_float(row["model_mae"]) for row in rows]
    return {
        "station_count": len(rows),
        "row_count": sum(int(row["test_rows"]) for row in rows),
        "model_mean_station_mae": mean_field(rows, "model_mae"),
        "nearest_hub_mean_station_mae": mean_field(rows, "nearest_hub_mae"),
        "idw_hubs_mean_station_mae": mean_field(rows, "idw_hubs_mae"),
        "model_median_station_mae": percentile(model_mae_values, 0.50),
        "model_p90_station_mae": percentile(model_mae_values, 0.90),
        "model_strict_pass_count": sum(
            1 for row in rows if row["model_strict_pass"]
        ),
        "nearest_hub_strict_pass_count": sum(
            1 for row in rows if row["nearest_hub_strict_pass"]
        ),
        "idw_hubs_strict_pass_count": sum(
            1 for row in rows if row["idw_hubs_strict_pass"]
        ),
        "model_better_than_nearest_count": sum(
            1 for row in rows if to_float(row["model_mae_delta_vs_nearest"]) < 0
        ),
        "model_better_than_idw_count": sum(
            1 for row in rows if to_float(row["model_mae_delta_vs_idw"]) < 0
        ),
    }


def band_label(value: object, breakpoints: list[tuple[float, str]], fallback: str) -> str:
    if value in ("", None):
        return fallback

    number = to_float(value)
    for upper_bound, label in breakpoints:
        if number < upper_bound:
            return label

    return breakpoints[-1][1].replace("<", ">=")


def segment_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    segment_specs = {
        "elevation_band": (
            "elevation_m",
            [(1000.0, "<1000m"), (2000.0, "1000-1999m"), (math.inf, ">=2000m")],
        ),
        "relief_band": (
            "local_relief_m",
            [(250.0, "<250m relief"), (750.0, "250-749m relief"), (math.inf, ">=750m relief")],
        ),
        "slope_band": (
            "slope_degrees",
            [(5.0, "<5deg slope"), (15.0, "5-14deg slope"), (math.inf, ">=15deg slope")],
        ),
    }
    output_rows: list[dict[str, object]] = []

    for segment_name, (field_name, breakpoints) in segment_specs.items():
        grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            grouped[band_label(row.get(field_name), breakpoints, "unknown")].append(row)

        for label, segment in sorted(grouped.items()):
            output_rows.append({
                "segment": segment_name,
                "label": label,
                "station_count": len(segment),
                "model_mean_mae": mean_field(segment, "model_mae"),
                "nearest_hub_mean_mae": mean_field(segment, "nearest_hub_mae"),
                "idw_hubs_mean_mae": mean_field(segment, "idw_hubs_mae"),
                "model_better_than_nearest_count": sum(
                    1
                    for row in segment
                    if to_float(row["model_mae_delta_vs_nearest"]) < 0
                ),
                "model_better_than_idw_count": sum(
                    1
                    for row in segment
                    if to_float(row["model_mae_delta_vs_idw"]) < 0
                ),
            })

    return output_rows


def format_station_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    formatted_rows: list[dict[str, object]] = []
    for row in rows:
        formatted_rows.append({
            "target_station_id": row["target_station_id"],
            "target_name": row["target_name"],
            "test_rows": row["test_rows"],
            "model_mae": f"{row['model_mae']:.4f}",
            "nearest_hub_mae": f"{row['nearest_hub_mae']:.4f}",
            "idw_hubs_mae": f"{row['idw_hubs_mae']:.4f}",
            "model_mae_delta_vs_nearest": f"{row['model_mae_delta_vs_nearest']:.4f}",
            "model_mae_delta_vs_idw": f"{row['model_mae_delta_vs_idw']:.4f}",
            "model_rmse": f"{row['model_rmse']:.4f}",
            "nearest_hub_rmse": f"{row['nearest_hub_rmse']:.4f}",
            "idw_hubs_rmse": f"{row['idw_hubs_rmse']:.4f}",
            "model_correlation": f"{row['model_correlation']:.6f}",
            "nearest_hub_correlation": f"{row['nearest_hub_correlation']:.6f}",
            "idw_hubs_correlation": f"{row['idw_hubs_correlation']:.6f}",
            "model_bias": f"{row['model_bias']:.4f}",
            "nearest_hub_bias": f"{row['nearest_hub_bias']:.4f}",
            "idw_hubs_bias": f"{row['idw_hubs_bias']:.4f}",
            "model_strict_pass": row["model_strict_pass"],
            "nearest_hub_strict_pass": row["nearest_hub_strict_pass"],
            "idw_hubs_strict_pass": row["idw_hubs_strict_pass"],
            "elevation_m": row["elevation_m"],
            "local_relief_m": row["local_relief_m"],
            "slope_degrees": row["slope_degrees"],
        })

    return formatted_rows


def format_segment_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "segment": row["segment"],
            "label": row["label"],
            "station_count": row["station_count"],
            "model_mean_mae": f"{row['model_mean_mae']:.4f}",
            "nearest_hub_mean_mae": f"{row['nearest_hub_mean_mae']:.4f}",
            "idw_hubs_mean_mae": f"{row['idw_hubs_mean_mae']:.4f}",
            "model_better_than_nearest_count": row["model_better_than_nearest_count"],
            "model_better_than_idw_count": row["model_better_than_idw_count"],
        }
        for row in rows
    ]


def render_html_report(
    output_file: Path,
    station_rows: list[dict[str, object]],
    segment_summary_rows: list[dict[str, object]],
    summary: Mapping[str, object],
) -> None:
    worst_rows = sorted(
        station_rows,
        key=lambda row: to_float(row["model_mae_delta_vs_idw"]),
        reverse=True,
    )[:10]
    best_rows = sorted(
        station_rows,
        key=lambda row: to_float(row["model_mae_delta_vs_idw"]),
    )[:10]

    def station_table(rows: list[dict[str, object]]) -> str:
        table_rows = []
        for row in rows:
            table_rows.append(
                "<tr>"
                f"<td>{escape(str(row['target_station_id']))}</td>"
                f"<td>{escape(str(row['target_name']))}</td>"
                f"<td>{to_float(row['model_mae']):.2f}</td>"
                f"<td>{to_float(row['nearest_hub_mae']):.2f}</td>"
                f"<td>{to_float(row['idw_hubs_mae']):.2f}</td>"
                f"<td>{to_float(row['model_mae_delta_vs_idw']):+.2f}</td>"
                "</tr>"
            )
        return (
            "<table><thead><tr><th>Station</th><th>Name</th><th>Model MAE</th>"
            "<th>Nearest MAE</th><th>IDW MAE</th><th>Model-IDW</th></tr></thead>"
            f"<tbody>{''.join(table_rows)}</tbody></table>"
        )

    segment_rows_html = []
    for row in segment_summary_rows:
        segment_rows_html.append(
            "<tr>"
            f"<td>{escape(str(row['segment']))}</td>"
            f"<td>{escape(str(row['label']))}</td>"
            f"<td>{row['station_count']}</td>"
            f"<td>{to_float(row['model_mean_mae']):.2f}</td>"
            f"<td>{to_float(row['nearest_hub_mean_mae']):.2f}</td>"
            f"<td>{to_float(row['idw_hubs_mean_mae']):.2f}</td>"
            "</tr>"
        )

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Holdout Baseline Comparison</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #111827; }}
    .cards {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 20px 0; }}
    .metric-card {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 12px 14px; min-width: 160px; }}
    .label {{ color: #4b5563; font-size: 12px; text-transform: uppercase; }}
    .value {{ font-size: 24px; font-weight: 700; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0 28px; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 8px; text-align: left; }}
    th {{ background: #f9fafb; }}
    .note {{ color: #4b5563; max-width: 900px; }}
  </style>
</head>
<body>
  <h1>Holdout Baseline Comparison</h1>
  <p class="note">All model, nearest-hub, and IDW-hub metrics are evaluated on identical held-out prediction rows. The script fails by default if any baseline prediction is missing.</p>
  <div class="cards">
    {render_metric_card("Stations", str(summary["station_count"]))}
    {render_metric_card("Rows", str(summary["row_count"]))}
    {render_metric_card("Model mean MAE", f"{to_float(summary['model_mean_station_mae']):.2f} F")}
    {render_metric_card("Nearest mean MAE", f"{to_float(summary['nearest_hub_mean_station_mae']):.2f} F")}
    {render_metric_card("IDW mean MAE", f"{to_float(summary['idw_hubs_mean_station_mae']):.2f} F")}
  </div>
  <h2>Model Strongest vs IDW</h2>
  {station_table(best_rows)}
  <h2>Model Weakest vs IDW</h2>
  {station_table(worst_rows)}
  <h2>Terrain and Elevation Segments</h2>
  <table><thead><tr><th>Segment</th><th>Label</th><th>Stations</th><th>Model MAE</th><th>Nearest MAE</th><th>IDW MAE</th></tr></thead>
  <tbody>{''.join(segment_rows_html)}</tbody></table>
</body>
</html>
"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html)


def write_outputs(
    output_dir: Path,
    output_stem: str,
    row_locked_predictions: list[dict[str, object]],
    station_rows: list[dict[str, object]],
    segment_summary_rows: list[dict[str, object]],
    summary: Mapping[str, object],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv_rows(
        output_dir / f"{output_stem}_row_locked_predictions.csv",
        row_locked_predictions,
        list(row_locked_predictions[0].keys()),
    )
    formatted_station_rows = format_station_rows(station_rows)
    write_csv_rows(
        output_dir / f"{output_stem}_station_comparison.csv",
        formatted_station_rows,
        list(formatted_station_rows[0].keys()),
    )
    formatted_segment_rows = format_segment_rows(segment_summary_rows)
    write_csv_rows(
        output_dir / f"{output_stem}_segment_summary.csv",
        formatted_segment_rows,
        list(formatted_segment_rows[0].keys()),
    )
    (output_dir / f"{output_stem}_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    render_html_report(
        output_dir / f"{output_stem}.html",
        formatted_station_rows,
        formatted_segment_rows,
        summary,
    )


def build_holdout_baseline_comparison(arguments: argparse.Namespace) -> dict[str, object]:
    prediction_rows = load_prediction_rows(
        arguments.prediction_dir,
        arguments.prediction_pattern,
    )
    model_metrics_by_station = load_station_metrics(arguments.model_metrics)
    group_station_ids = load_group_station_ids(arguments.model_metrics)
    target_ids = {row["target_station_id"] for row in prediction_rows}
    needed_dates = {row["date"] for row in prediction_rows}
    target_group_by_station = {
        row["target_station_id"]: row.get("holdout_group_id", "")
        for row in prediction_rows
    }
    hub_candidates = load_candidates(arguments.hub_candidates)
    target_candidates = load_candidates(arguments.target_candidates)
    target_metadata = load_daily_metadata(arguments.target_daily, target_ids)
    terrain_by_station = load_terrain_features(arguments.terrain_features, target_ids)
    ranked_hubs_by_target = ranked_hubs_for_targets(
        target_ids,
        hub_candidates,
        target_candidates,
        target_metadata,
        group_station_ids,
        target_group_by_station,
    )
    hub_values_by_date = load_hub_daily_values(
        arguments.hub_daily,
        needed_dates,
        set(hub_candidates),
        arguments.variable,
    )
    row_locked_predictions, missing_rows = build_row_locked_predictions(
        prediction_rows,
        ranked_hubs_by_target,
        hub_values_by_date,
        arguments.idw_hub_count,
        arguments.idw_power,
    )

    if missing_rows and not arguments.allow_incomplete_baseline:
        examples = ", ".join(
            f"{row['target_station_id']}:{row['date']}"
            for row in missing_rows[:5]
        )
        raise ValueError(
            "Baseline predictions are missing for "
            f"{len(missing_rows)} of {len(prediction_rows)} model rows. "
            f"Examples: {examples}. Re-run with --allow-incomplete-baseline "
            "only for diagnostics, not for headline lift claims."
        )

    if not row_locked_predictions:
        raise ValueError("No row-locked baseline predictions were created.")

    station_rows = build_station_comparison_rows(
        row_locked_predictions,
        model_metrics_by_station,
        target_metadata,
        terrain_by_station,
    )
    segment_summary_rows = segment_rows(station_rows)
    summary = summarize_comparison_rows(station_rows)
    summary["source_prediction_rows"] = len(prediction_rows)
    summary["row_locked_prediction_rows"] = len(row_locked_predictions)
    summary["missing_baseline_rows"] = len(missing_rows)
    summary["comparison_guardrail"] = (
        "model, nearest-hub, and IDW-hub metrics use identical prediction rows"
    )

    write_outputs(
        arguments.output_dir,
        arguments.output_stem,
        row_locked_predictions,
        station_rows,
        segment_summary_rows,
        summary,
    )
    return summary


def main() -> None:
    summary = build_holdout_baseline_comparison(parse_arguments())
    print("Holdout baseline comparison complete")
    print(f"Stations: {summary['station_count']}")
    print(f"Rows: {summary['row_locked_prediction_rows']}")
    print(f"Missing baseline rows: {summary['missing_baseline_rows']}")
    print(f"Model mean station MAE: {summary['model_mean_station_mae']:.4f} F")
    print(f"Nearest-hub mean station MAE: {summary['nearest_hub_mean_station_mae']:.4f} F")
    print(f"IDW-hub mean station MAE: {summary['idw_hubs_mean_station_mae']:.4f} F")


if __name__ == "__main__":
    main()
