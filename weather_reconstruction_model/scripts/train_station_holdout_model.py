"""Train and validate models while holding out selected stations.

This workflow estimates how well the model reconstructs stations with no direct training evidence."""

from __future__ import annotations

import argparse
import csv
import gc
from pathlib import Path
from time import perf_counter

import config
from common.csv_utils import read_csv_rows
from common.metrics import calculate_metrics
from common.weather_cache import TEMPERATURE_VARIABLES, validate_temperature_variable
from pipeline.model_features import (
    require_training_columns,
    resolve_model_feature_selection,
)
from pipeline.station_holdouts import (
    training_rows_for_station_holdout,
)
from pipeline.training_data import (
    actual_temperature_values,
    add_baseline_to_offsets,
    build_temperature_prediction_rows,
    build_unscaled_features_and_labels,
    calculate_prediction_bias,
    temperature_prediction_fieldnames,
)
from train_tree_temperature_model import (
    import_sklearn_models,
)

PREDICTION_DIR = config.PREDICTION_DIR
REPORT_DIR = config.REPORT_DIR
DEFAULT_TRAIN_END_YEAR = config.DEFAULT_TRAIN_END_YEAR
DEFAULT_TEST_START_YEAR = config.DEFAULT_TEST_START_YEAR
DEFAULT_STATION_IDS = [
    "USC00052223",  # strong Option C strict pass
    "USC00022782",  # became strict pass
    "USC00051539",  # strong station
    "USC00025494",  # weak station
    "USC00050825",  # weak station
    "USC00027880",  # regressed from strict pass
    "USC00051060",  # large Option C improvement
    "USC00050263",  # seasonal spread / difficult station
]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run station-holdout validation. For each held-out station, "
            "the model trains without any row where that station appears as a "
            "target, hub, or target-neighbor predictor."
        )
    )
    parser.add_argument(
        "general_table",
        type=Path,
        help="General training table with hub and target-neighbor features.",
    )
    parser.add_argument(
        "--station-ids",
        nargs="+",
        default=DEFAULT_STATION_IDS,
        help="Station IDs to hold out one at a time.",
    )
    parser.add_argument(
        "--station-list",
        type=Path,
        default=None,
        help="CSV with station_id/station_name columns. Overrides --station-ids.",
    )
    parser.add_argument(
        "--station-group-list",
        type=Path,
        default=None,
        help=(
            "CSV with group_id and station_id columns. Each group is trained once "
            "with all group stations omitted, then scored station-by-station."
        ),
    )
    parser.add_argument(
        "--variable",
        choices=sorted(TEMPERATURE_VARIABLES),
        default="tavg",
        help="Daily temperature variable to train and score.",
    )
    parser.add_argument(
        "--train-end",
        type=int,
        default=DEFAULT_TRAIN_END_YEAR,
        help="Last year used for training rows.",
    )
    parser.add_argument(
        "--test-start",
        type=int,
        default=DEFAULT_TEST_START_YEAR,
        help="First year used for held-out station test rows.",
    )
    parser.add_argument(
        "--forest-trees",
        type=int,
        default=80,
        help="Random forest tree count for each held-out station model.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=14,
        help="Random forest max depth for each held-out station model.",
    )
    parser.add_argument(
        "--min-samples-leaf",
        type=int,
        default=10,
        help="Random forest minimum samples per leaf for each held-out station model.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for reproducible model training.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=-1,
        help="Parallel jobs for RandomForestRegressor.",
    )
    parser.add_argument(
        "--output-stem",
        default=None,
        help="Optional output filename stem.",
    )
    parser.add_argument(
        "--model-id",
        default=None,
        help="Model identifier to write into station metrics.",
    )
    parser.add_argument(
        "--predict-offset-from-baseline",
        action="store_true",
        help=(
            "Train each holdout model to predict target_<variable>_offset_from_baseline, "
            "then add regional_baseline_<variable> back before scoring."
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Append to existing output files and skip station IDs already present in the station metrics file.",
    )
    return parser.parse_args()


def is_strict_pass(metrics: dict[str, float]) -> bool:
    return (
        metrics["mae"] <= config.ML_GOAL_MAX_MAE
        and metrics["rmse"] <= config.ML_GOAL_MAX_RMSE
        and metrics["correlation"] >= config.ML_GOAL_MIN_CORRELATION
    )


def prediction_rows_for_station(
    test_rows: list[dict[str, str]],
    actual_values: list[float],
    predicted_values: list[float],
    variable: str,
    holdout_group_id: str,
    holdout_group_size: int,
) -> list[dict[str, object]]:
    return build_temperature_prediction_rows(
        test_rows,
        actual_values,
        predicted_values,
        variable,
        {
            "holdout_group_id": holdout_group_id,
            "holdout_group_size": holdout_group_size,
        },
    )


def existing_station_ids(report_file: Path) -> set[str]:
    if not report_file.exists():
        return set()

    with report_file.open("r", newline="") as file:
        return {
            row.get("STATION_ID") or row.get("target_station_id", "")
            for row in csv.DictReader(file)
            if row.get("STATION_ID") or row.get("target_station_id")
        }


def read_existing_summary_rows(report_file: Path) -> list[dict[str, str]]:
    if not report_file.exists():
        return []

    with report_file.open("r", newline="") as file:
        return list(csv.DictReader(file))


def open_csv_writer(file_path: Path, fieldnames: list[str], append: bool):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = file_path.exists()

    if append and file_exists:
        with file_path.open("r", newline="") as existing_file:
            existing_fieldnames = csv.DictReader(existing_file).fieldnames or []

        if existing_fieldnames != fieldnames:
            raise ValueError(
                f"Cannot resume into {file_path} because its CSV header does not "
                "match the current Paloma holdout format. Use a new --output-stem "
                "or remove the stale partial output after archiving it."
            )

    file = file_path.open("a" if append else "w", newline="")
    writer = csv.DictWriter(file, fieldnames=fieldnames)

    if not append or not file_exists:
        writer.writeheader()

    return file, writer


def load_station_ids(arguments: argparse.Namespace) -> list[str]:
    if arguments.station_list is None:
        return arguments.station_ids

    rows = read_csv_rows(arguments.station_list)
    station_ids = []

    for row in rows:
        station_id = row.get("station_id") or row.get("STATION_ID")

        if station_id:
            station_ids.append(station_id)

    if not station_ids:
        raise ValueError(
            f"Station list has no station_id/STATION_ID values: {arguments.station_list}"
        )

    return station_ids


def load_station_groups(arguments: argparse.Namespace) -> list[dict[str, object]]:
    if arguments.station_group_list is None:
        return [
            {
                "group_id": station_id,
                "station_ids": [station_id],
            }
            for station_id in load_station_ids(arguments)
        ]

    rows = read_csv_rows(arguments.station_group_list)
    grouped_station_ids: dict[str, list[str]] = {}

    for row in rows:
        group_id = row.get("group_id") or row.get("GROUP_ID")
        station_id = row.get("station_id") or row.get("STATION_ID")

        if not group_id or not station_id:
            continue

        grouped_station_ids.setdefault(group_id, []).append(station_id)

    if not grouped_station_ids:
        raise ValueError(
            f"Station group list has no usable group_id/station_id rows: "
            f"{arguments.station_group_list}"
        )

    return [
        {
            "group_id": group_id,
            "station_ids": station_ids,
        }
        for group_id, station_ids in sorted(grouped_station_ids.items())
    ]


def main() -> None:
    started_at = perf_counter()
    arguments = parse_arguments()
    variable = validate_temperature_variable(arguments.variable)
    station_groups = load_station_groups(arguments)
    RandomForestRegressor, _ = import_sklearn_models()
    rows = read_csv_rows(arguments.general_table)

    if not rows:
        raise ValueError("The general training table is empty.")

    feature_selection = resolve_model_feature_selection(
        rows[0].keys(),
        variable=variable,
        include_terrain=True,
        include_offset_features=arguments.predict_offset_from_baseline,
    )
    target_column = feature_selection.target_column
    baseline_column = feature_selection.baseline_column
    offset_label_column = feature_selection.label_column

    if target_column not in rows[0]:
        raise ValueError(
            f"Training table is missing {target_column}. "
            f"Build it with --variable {variable}."
        )

    hub_count = feature_selection.hub_count
    target_neighbor_count = feature_selection.target_neighbor_count
    feature_columns = feature_selection.feature_columns
    if arguments.predict_offset_from_baseline:
        require_training_columns(
            rows[0].keys(),
            feature_selection,
            "Offset holdout requires a training table with these columns",
        )

    output_stem = arguments.output_stem or (
        f"{arguments.general_table.stem}_"
        f"{'offset' if arguments.predict_offset_from_baseline else 'direct'}_"
        "station_holdout_quick_random_forest"
    )
    model_id = arguments.model_id or output_stem
    prediction_file = PREDICTION_DIR / f"{output_stem}_predictions.csv"
    report_file = REPORT_DIR / f"{output_stem}_station_metrics.csv"
    existing_summary_rows = read_existing_summary_rows(report_file) if arguments.resume else []
    completed_station_ids = {
        row.get("STATION_ID") or row.get("target_station_id")
        for row in existing_summary_rows
        if row.get("STATION_ID") or row.get("target_station_id")
    }
    prediction_fieldnames = temperature_prediction_fieldnames(
        variable,
        ["holdout_group_id", "holdout_group_size"],
    )
    report_fieldnames = [
        "model_id",
        "variable",
        "holdout_group_id",
        "holdout_group_size",
        "target_station_id",
        "target_name",
        "train_rows",
        "test_rows",
        "mae",
        "rmse",
        "correlation",
        "bias",
        "strict_pass",
        "elapsed_seconds",
    ]
    prediction_handle, prediction_writer = open_csv_writer(
        prediction_file,
        prediction_fieldnames,
        append=arguments.resume,
    )
    report_handle, report_writer = open_csv_writer(
        report_file,
        report_fieldnames,
        append=arguments.resume,
    )
    summary_rows = list(existing_summary_rows)

    print("Station-holdout random forest validation")
    print("========================================")
    print(f"General table: {arguments.general_table}")
    print(f"Rows: {len(rows)}")
    print(f"Hubs per target: {hub_count}")
    print(f"Target-neighbor stations per target: {target_neighbor_count}")
    print(f"Temperature variable: {variable}")
    print(f"Feature inputs: {len(feature_columns)}")
    print(
        "Prediction target: "
        + (
            "daily offset from regional baseline"
            if arguments.predict_offset_from_baseline
            else f"direct daily {variable} temperature"
        )
    )
    print(f"Model ID: {model_id}")
    if arguments.station_group_list is not None:
        print(f"Station group list: {arguments.station_group_list}")
    if arguments.station_list is not None:
        print(f"Station list: {arguments.station_list}")
    print(f"Holdout groups: {len(station_groups)}")
    print(
        "Stations to hold out: "
        f"{sum(len(group['station_ids']) for group in station_groups)}"
    )
    if arguments.resume:
        print(f"Resume mode: skipping {len(completed_station_ids)} completed stations")
    print(
        "Holdout rule: excluded from training when station appears as "
        "target, hub, or target-neighbor"
    )
    print()

    try:
        for index, group in enumerate(station_groups, start=1):
            group_id = str(group["group_id"])
            station_ids = [
                str(station_id)
                for station_id in group["station_ids"]
            ]
            pending_station_ids = [
                station_id
                for station_id in station_ids
                if station_id not in completed_station_ids
            ]

            if not pending_station_ids:
                print(
                    f"[{index}/{len(station_groups)}] {group_id} "
                    "SKIP: already complete"
                )
                continue

            station_started_at = perf_counter()
            heldout_station_ids = set(station_ids)
            train_rows = training_rows_for_station_holdout(
                rows,
                heldout_station_ids,
                arguments.train_end,
                hub_count,
                target_neighbor_count,
            )

            print(
                f"[{index}/{len(station_groups)}] {group_id} "
                f"({len(station_ids)} stations)",
                end=" ",
                flush=True,
            )

            if not train_rows:
                print("SKIP: no training rows", flush=True)
                continue

            label_column = (
                offset_label_column
                if arguments.predict_offset_from_baseline
                else target_column
            )
            train_features, train_labels = build_unscaled_features_and_labels(
                train_rows,
                feature_columns,
                label_column,
            )
            model = RandomForestRegressor(
                n_estimators=arguments.forest_trees,
                max_depth=arguments.max_depth,
                min_samples_leaf=arguments.min_samples_leaf,
                random_state=arguments.random_state,
                n_jobs=arguments.jobs,
            )
            model.fit(train_features, train_labels)
            modeled_station_count = 0

            for station_id in pending_station_ids:
                test_rows = [
                    row
                    for row in rows
                    if row["target_station_id"] == station_id
                    and int(row["year"]) >= arguments.test_start
                ]

                if not test_rows:
                    print(f"{station_id} SKIP no test rows", end=" ", flush=True)
                    continue

                test_features, test_labels = build_unscaled_features_and_labels(
                    test_rows,
                    feature_columns,
                    label_column,
                )
                actual_test_values = actual_temperature_values(test_rows, variable)
                predictions = list(model.predict(test_features))
                if arguments.predict_offset_from_baseline:
                    predictions = add_baseline_to_offsets(
                        test_rows,
                        predictions,
                        baseline_column,
                    )

                metrics = calculate_metrics(actual_test_values, predictions)
                bias = calculate_prediction_bias(actual_test_values, predictions)
                prediction_writer.writerows(
                    prediction_rows_for_station(
                        test_rows,
                        actual_test_values,
                        predictions,
                        variable,
                        group_id,
                        len(station_ids),
                    )
                )
                prediction_handle.flush()
                strict_pass = is_strict_pass(metrics)
                summary_row = {
                    "model_id": model_id,
                    "variable": variable,
                    "holdout_group_id": group_id,
                    "holdout_group_size": len(station_ids),
                    "target_station_id": station_id,
                    "target_name": test_rows[0]["target_name"],
                    "train_rows": len(train_rows),
                    "test_rows": len(test_rows),
                    "mae": f"{metrics['mae']:.4f}",
                    "rmse": f"{metrics['rmse']:.4f}",
                    "correlation": f"{metrics['correlation']:.6f}",
                    "bias": f"{bias:.4f}",
                    "strict_pass": str(strict_pass),
                    "elapsed_seconds": f"{perf_counter() - station_started_at:.1f}",
                }
                report_writer.writerow(summary_row)
                report_handle.flush()
                summary_rows.append(summary_row)
                modeled_station_count += 1
                print(
                    f"{station_id} MAE {metrics['mae']:.4f} F, "
                    f"RMSE {metrics['rmse']:.4f} F, "
                    f"r {metrics['correlation']:.5f}, "
                    f"strict {strict_pass};",
                    end=" ",
                    flush=True,
                )

            print(
                f"modeled {modeled_station_count}/{len(pending_station_ids)} "
                "pending stations",
                flush=True,
            )

            del train_rows
            del train_features
            del train_labels
            del model
            gc.collect()
    finally:
        prediction_handle.close()
        report_handle.close()

    strict_count = sum(
        1
        for row in summary_rows
        if (row.get("STRICT_PASS") or row.get("strict_pass")) == "True"
    )

    print()
    print("Station-holdout validation complete")
    print("-----------------------------------")
    print(f"Stations modeled: {len(summary_rows)}")
    print(f"Strict passes: {strict_count}/{len(summary_rows)}")
    print(f"Prediction file: {prediction_file}")
    print(f"Station metrics: {report_file}")
    print(f"Elapsed time: {perf_counter() - started_at:.1f} seconds")


if __name__ == "__main__":
    main()
