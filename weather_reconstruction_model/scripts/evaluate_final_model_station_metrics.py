"""Evaluate final serialized model predictions at individual station locations.

The station metrics feed final-model reliability overlays and model-run artifact summaries."""

from __future__ import annotations

import argparse
import csv
import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from time import perf_counter

import config
from common.json_utils import write_json_file
from common.model_artifacts import project_relative_path
from common.model_runs import resolve_model_run
from common.number_utils import to_float
from common.weather_cache import TEMPERATURE_VARIABLES, validate_temperature_variable

DEFAULT_BATCH_ROWS = 5000
METRIC_FIELDNAMES = [
    "model_run_id",
    "variable",
    "target_station_id",
    "target_name",
    "evaluation_mode",
    "row_count",
    "start_date",
    "end_date",
    "mae",
    "rmse",
    "correlation",
    "bias",
    "actual_mean",
    "predicted_mean",
]


@dataclass
class StationAccumulator:
    station_id: str
    station_name: str
    count: int = 0
    start_date: str | None = None
    end_date: str | None = None
    sum_actual: float = 0.0
    sum_predicted: float = 0.0
    sum_actual_squared: float = 0.0
    sum_predicted_squared: float = 0.0
    sum_actual_predicted: float = 0.0
    sum_absolute_error: float = 0.0
    sum_squared_error: float = 0.0
    sum_error: float = 0.0

    def add(self, row_date: str, actual: float, predicted: float) -> None:
        error = actual - predicted
        self.count += 1
        self.start_date = row_date if self.start_date is None else min(self.start_date, row_date)
        self.end_date = row_date if self.end_date is None else max(self.end_date, row_date)
        self.sum_actual += actual
        self.sum_predicted += predicted
        self.sum_actual_squared += actual * actual
        self.sum_predicted_squared += predicted * predicted
        self.sum_actual_predicted += actual * predicted
        self.sum_absolute_error += abs(error)
        self.sum_squared_error += error * error
        self.sum_error += error

    def correlation(self) -> float:
        numerator = (
            self.count * self.sum_actual_predicted
            - self.sum_actual * self.sum_predicted
        )
        actual_term = self.count * self.sum_actual_squared - self.sum_actual * self.sum_actual
        predicted_term = (
            self.count * self.sum_predicted_squared
            - self.sum_predicted * self.sum_predicted
        )
        denominator = math.sqrt(max(actual_term, 0.0) * max(predicted_term, 0.0))
        if denominator == 0:
            return 0.0
        return numerator / denominator

    def as_row(self, model_run_id: str, variable: str) -> dict[str, object]:
        return {
            "model_run_id": model_run_id,
            "variable": variable,
            "target_station_id": self.station_id,
            "target_name": self.station_name,
            "evaluation_mode": "final_model_in_sample_fit",
            "row_count": self.count,
            "start_date": self.start_date or "",
            "end_date": self.end_date or "",
            "mae": round(self.sum_absolute_error / self.count, 6),
            "rmse": round(math.sqrt(self.sum_squared_error / self.count), 6),
            "correlation": round(self.correlation(), 8),
            "bias": round(self.sum_error / self.count, 6),
            "actual_mean": round(self.sum_actual / self.count, 6),
            "predicted_mean": round(self.sum_predicted / self.count, 6),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a final all-rows Paloma production model against observed "
            "station rows and write station-level in-sample fit metrics."
        )
    )
    parser.add_argument(
        "--variable",
        choices=sorted(TEMPERATURE_VARIABLES),
        default="tavg",
    )
    parser.add_argument("--model-run-id", default=None)
    parser.add_argument("--model-run-root", type=Path, default=config.MODEL_RUN_DIR)
    parser.add_argument("--model-file", type=Path, default=None)
    parser.add_argument("--general-table", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--report-file", type=Path, default=None)
    parser.add_argument("--batch-rows", type=int, default=DEFAULT_BATCH_ROWS)
    parser.add_argument("--progress-rows", type=int, default=100000)
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional smoke-test limit. Omit for the complete artifact.",
    )
    return parser.parse_args()


def import_prediction_dependencies():
    try:
        import joblib
        import numpy as np
    except ModuleNotFoundError as error:
        raise SystemExit(
            "joblib and numpy are required to evaluate final model metrics. "
            "Use the project .venv or install the model extras."
        ) from error

    return joblib, np


def first_existing(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def default_model_candidates(model_run_root: Path, model_run_id: str) -> list[Path]:
    return [
        resolve_model_run(model_run_root, model_run_id).root / "model.joblib",
        config.PROJECT_DIR / "model_runs" / "paloma_v1" / model_run_id / "model.joblib",
    ]


def default_table_candidates(variable: str) -> list[Path]:
    filename = (
        "paloma_v1_full_all_targets_5_hubs_10_target_neighbors_"
        f"physical_selection_no_pairwise_{variable}.csv"
    )
    return [
        config.GENERAL_TABLE_DIR / filename,
        config.PROJECT_DIR / "alpine_outputs" / "general_training_tables" / filename,
    ]


def resolve_input_path(
    explicit_path: Path | None,
    candidates: list[Path],
    label: str,
) -> Path:
    if explicit_path is not None:
        path = explicit_path.resolve()
        if not path.exists():
            raise FileNotFoundError(f"{label} does not exist: {path}")
        return path

    path = first_existing(candidates)
    if path is None:
        formatted = "\n  ".join(str(candidate) for candidate in candidates)
        raise FileNotFoundError(f"Could not find {label}. Checked:\n  {formatted}")

    return path.resolve()


def validate_batch_size(batch_rows: int) -> None:
    if batch_rows <= 0:
        raise ValueError("--batch-rows must be positive.")


def validate_required_columns(
    fieldnames: list[str],
    required_columns: list[str],
    table_path: Path,
) -> None:
    missing = sorted(set(required_columns) - set(fieldnames))
    if missing:
        raise ValueError(
            f"Missing required column(s) in {table_path}: {', '.join(missing)}"
        )


def predict_batch(
    np,
    model,
    rows: list[dict[str, str]],
    feature_columns: list[str],
    baseline_column: str,
):
    features = np.empty((len(rows), len(feature_columns)), dtype=np.float32)
    baselines = np.empty(len(rows), dtype=np.float32)

    for row_index, row in enumerate(rows):
        for column_index, column in enumerate(feature_columns):
            features[row_index, column_index] = to_float(row.get(column, ""))
        baselines[row_index] = to_float(row.get(baseline_column, ""))

    return baselines + model.predict(features)


def update_station_metrics(
    accumulators: dict[str, StationAccumulator],
    rows: list[dict[str, str]],
    predicted_values,
    variable: str,
) -> None:
    actual_column = f"target_{variable}"

    for row, predicted in zip(rows, predicted_values):
        station_id = row["target_station_id"]
        accumulator = accumulators.get(station_id)
        if accumulator is None:
            accumulator = StationAccumulator(
                station_id=station_id,
                station_name=row.get("target_name") or station_id,
            )
            accumulators[station_id] = accumulator

        accumulator.add(
            row_date=row["date"],
            actual=to_float(row[actual_column]),
            predicted=float(predicted),
        )


def write_metrics(
    output_path: Path,
    accumulators: dict[str, StationAccumulator],
    model_run_id: str,
    variable: str,
) -> list[dict[str, object]]:
    rows = [
        accumulator.as_row(model_run_id, variable)
        for accumulator in sorted(
            accumulators.values(),
            key=lambda item: item.station_id,
        )
        if accumulator.count > 0
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=METRIC_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def build_report(
    *,
    model_run_id: str,
    variable: str,
    model_file: Path,
    general_table: Path,
    output_path: Path,
    metric_rows: list[dict[str, object]],
    total_rows: int,
    elapsed_seconds: float,
) -> dict[str, object]:
    mae_values = [float(row["mae"]) for row in metric_rows]
    rmse_values = [float(row["rmse"]) for row in metric_rows]
    correlation_values = [float(row["correlation"]) for row in metric_rows]
    return {
        "artifactVersion": "final-model-station-metrics-v1",
        "createdAt": date.today().isoformat(),
        "modelRunId": model_run_id,
        "variable": variable,
        "evaluationMode": "final_model_in_sample_fit",
        "importantCaveat": (
            "The production estimator was trained on all eligible rows. These "
            "station metrics measure in-sample final-model fit and are not "
            "out-of-sample validation evidence."
        ),
        "sourceFiles": {
            "model": project_relative_path(model_file, config.PROJECT_DIR),
            "generalTable": project_relative_path(general_table, config.PROJECT_DIR),
            "stationMetrics": project_relative_path(output_path, config.PROJECT_DIR),
        },
        "rowCount": total_rows,
        "stationCount": len(metric_rows),
        "summaryMetrics": {
            "meanMaeF": round(sum(mae_values) / len(mae_values), 6) if mae_values else None,
            "meanRmseF": round(sum(rmse_values) / len(rmse_values), 6) if rmse_values else None,
            "meanCorrelation": (
                round(sum(correlation_values) / len(correlation_values), 8)
                if correlation_values
                else None
            ),
        },
        "elapsedSeconds": round(elapsed_seconds, 1),
    }


def main() -> None:
    started_at = perf_counter()
    args = parse_args()
    variable = validate_temperature_variable(args.variable)
    model_run_id = args.model_run_id or f"paloma_v1_{variable}"
    validate_batch_size(args.batch_rows)
    joblib, np = import_prediction_dependencies()

    paths = resolve_model_run(args.model_run_root, model_run_id)
    model_file = resolve_input_path(
        args.model_file,
        default_model_candidates(args.model_run_root, model_run_id),
        "model file",
    )
    general_table = resolve_input_path(
        args.general_table,
        default_table_candidates(variable),
        "general training table",
    )
    output_path = (
        args.output.resolve()
        if args.output is not None
        else paths.root / "final_model_station_metrics.csv"
    )
    report_path = (
        args.report_file.resolve()
        if args.report_file is not None
        else paths.root / "final_model_station_metrics_manifest.json"
    )

    print("Final Model Station Metrics")
    print("===========================")
    print(f"Model run: {model_run_id}")
    print(f"Variable: {variable}")
    print(f"Model file: {model_file}")
    print(f"General table: {general_table}")
    print(f"Output: {output_path}")
    print(f"Batch rows: {args.batch_rows}")

    artifact = joblib.load(model_file)
    if not isinstance(artifact, dict) or "model" not in artifact:
        raise ValueError(f"Expected a Paloma model artifact dictionary in {model_file}.")

    artifact_variable = validate_temperature_variable(str(artifact.get("variable") or variable))
    if artifact_variable != variable:
        raise ValueError(
            f"Model artifact variable mismatch: {artifact_variable!r} != {variable!r}"
        )

    feature_columns = list(artifact.get("featureColumns") or [])
    if not feature_columns:
        raise ValueError("Model artifact does not include featureColumns.")
    baseline_column = str(artifact.get("baselineColumn") or f"regional_baseline_{variable}")
    actual_column = f"target_{variable}"

    with general_table.open("r", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames or []
        validate_required_columns(
            fieldnames,
            ["date", "target_station_id", "target_name", actual_column, baseline_column, *feature_columns],
            general_table,
        )

        accumulators: dict[str, StationAccumulator] = {}
        batch: list[dict[str, str]] = []
        total_rows = 0

        for row in reader:
            batch.append(row)
            if len(batch) < args.batch_rows:
                continue

            predictions = predict_batch(
                np,
                artifact["model"],
                batch,
                feature_columns,
                baseline_column,
            )
            update_station_metrics(accumulators, batch, predictions, variable)
            total_rows += len(batch)
            batch = []

            if args.progress_rows > 0 and total_rows % args.progress_rows == 0:
                print(f"Scored {total_rows:,} rows...", flush=True)

            if args.max_rows is not None and total_rows >= args.max_rows:
                break

        if batch and (args.max_rows is None or total_rows < args.max_rows):
            if args.max_rows is not None:
                batch = batch[: args.max_rows - total_rows]
            predictions = predict_batch(
                np,
                artifact["model"],
                batch,
                feature_columns,
                baseline_column,
            )
            update_station_metrics(accumulators, batch, predictions, variable)
            total_rows += len(batch)

    metric_rows = write_metrics(output_path, accumulators, model_run_id, variable)
    elapsed_seconds = perf_counter() - started_at
    report = build_report(
        model_run_id=model_run_id,
        variable=variable,
        model_file=model_file,
        general_table=general_table,
        output_path=output_path,
        metric_rows=metric_rows,
        total_rows=total_rows,
        elapsed_seconds=elapsed_seconds,
    )
    write_json_file(report_path, report)

    print(f"Rows scored: {total_rows:,}")
    print(f"Stations scored: {len(metric_rows):,}")
    print(f"Metrics file: {output_path}")
    print(f"Manifest: {report_path}")
    print(f"Elapsed: {elapsed_seconds:.1f} seconds")


if __name__ == "__main__":
    main()
