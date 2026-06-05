"""Train tree-based temperature models from generated training tables.

This script powers the stronger Paloma-style random forest workflows used for model artifacts."""

from pathlib import Path
import argparse
from time import perf_counter

import config
import train_general_temperature_model as general_model
from common.csv_utils import read_csv_rows, write_csv_rows
from common.metrics import calculate_metrics
from common.weather_cache import TEMPERATURE_VARIABLES, validate_temperature_variable
from pipeline.model_features import (
    require_training_columns,
    resolve_model_feature_selection,
)
from pipeline.training_data import (
    actual_temperature_values,
    add_baseline_to_offsets,
    build_temperature_prediction_rows,
    build_unscaled_features_and_labels,
    temperature_prediction_fieldnames,
)


PREDICTION_DIR = config.PREDICTION_DIR
REPORT_DIR = config.REPORT_DIR
DEFAULT_TRAIN_END_YEAR = config.DEFAULT_TRAIN_END_YEAR
DEFAULT_TEST_START_YEAR = config.DEFAULT_TEST_START_YEAR
ML_GOAL_MAX_MAE = config.ML_GOAL_MAX_MAE
ML_GOAL_MAX_RMSE = config.ML_GOAL_MAX_RMSE
ML_GOAL_MIN_CORRELATION = config.ML_GOAL_MIN_CORRELATION
ML_GOAL_PASS_RATE = config.ML_GOAL_PASS_RATE


def import_sklearn_models():
    try:
        from sklearn.ensemble import HistGradientBoostingRegressor
        from sklearn.ensemble import RandomForestRegressor
    except ModuleNotFoundError as error:
        raise SystemExit(
            "scikit-learn is required for tree-model training. "
            "Install it with: .venv/bin/python -m pip install scikit-learn"
        ) from error

    return RandomForestRegressor, HistGradientBoostingRegressor


def fit_and_predict(model, train_features, train_labels, test_features):
    model.fit(train_features, train_labels)
    train_predictions = list(model.predict(train_features))
    test_predictions = list(model.predict(test_features))
    return train_predictions, test_predictions


def metrics_by_station(rows, actual_values, predicted_values):
    return general_model.metrics_by_station(rows, actual_values, predicted_values)


def write_prediction_file(
    general_table,
    model_name,
    test_rows,
    actual_values,
    predicted_values,
    variable="tavg",
):
    variable = validate_temperature_variable(variable)
    prediction_file = PREDICTION_DIR / f"{general_table.stem}_{model_name}_predictions.csv"

    write_csv_rows(
        prediction_file,
        build_temperature_prediction_rows(
            test_rows,
            actual_values,
            predicted_values,
            variable,
        ),
        temperature_prediction_fieldnames(variable),
    )
    return prediction_file


def write_station_report(general_table, model_name, station_metrics):
    report_file = REPORT_DIR / f"{general_table.stem}_{model_name}_station_metrics.csv"
    rows = []

    for row in station_metrics:
        rows.append({
            "target_station_id": row["target_station_id"],
            "target_name": row["target_name"],
            "test_rows": row["test_rows"],
            "mae": f"{row['mae']:.4f}",
            "rmse": f"{row['rmse']:.4f}",
            "correlation": f"{row['correlation']:.6f}",
        })

    write_csv_rows(
        report_file,
        rows,
        [
            "target_station_id",
            "target_name",
            "test_rows",
            "mae",
            "rmse",
            "correlation",
        ],
    )
    return report_file


def print_metric_row(name, train_metrics, test_metrics):
    print(
        f"{name:<28} "
        f"{train_metrics['mae']:>9.2f} {train_metrics['rmse']:>10.2f} {train_metrics['correlation']:>10.3f} "
        f"{test_metrics['mae']:>9.2f} {test_metrics['rmse']:>10.2f} {test_metrics['correlation']:>10.3f}"
    )


def print_worst_stations(model_name, station_metrics, count):
    print()
    print(f"Worst test stations by MAE: {model_name}")
    print("----------------------------------------")
    print(f"{'Station':<12} {'MAE':>7} {'RMSE':>7} {'r':>8} {'Rows':>6}  Name")

    for row in station_metrics[:count]:
        print(
            f"{row['target_station_id']:<12} "
            f"{row['mae']:>7.2f} {row['rmse']:>7.2f} {row['correlation']:>8.3f} "
            f"{row['test_rows']:>6}  {row['target_name']}"
        )


def is_ml_goal_pass(station_metric):
    return (
        station_metric["mae"] <= ML_GOAL_MAX_MAE
        and station_metric["rmse"] <= ML_GOAL_MAX_RMSE
        and station_metric["correlation"] >= ML_GOAL_MIN_CORRELATION
    )


def print_ml_goal_summary(model_name, station_metrics):
    strict_passes = [
        station_metric
        for station_metric in station_metrics
        if is_ml_goal_pass(station_metric)
    ]
    pass_rate = len(strict_passes) / len(station_metrics) if station_metrics else 0.0
    target_rate = ML_GOAL_PASS_RATE * 100
    print()
    print(f"Strict ML goal summary: {model_name}")
    print("----------------------------------------")
    print(
        f"Goal: MAE <= {ML_GOAL_MAX_MAE:g} F, "
        f"RMSE <= {ML_GOAL_MAX_RMSE:g} F, "
        f"r >= {ML_GOAL_MIN_CORRELATION:g}"
    )
    print(f"Strict passes: {len(strict_passes)}/{len(station_metrics)}")
    print(f"Strict pass rate: {pass_rate * 100:.1f}%")
    print(f"Target pass rate: {target_rate:.1f}%")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Train tree-based temperature reconstruction models from a general training table."
    )
    parser.add_argument(
        "general_table",
        nargs="?",
        type=Path,
        default=None,
        help="Path to a general_*_targets_*_hubs.csv file.",
    )
    parser.add_argument(
        "--train-end",
        type=int,
        default=DEFAULT_TRAIN_END_YEAR,
        help="Last year used for training.",
    )
    parser.add_argument(
        "--test-start",
        type=int,
        default=DEFAULT_TEST_START_YEAR,
        help="First year used for testing.",
    )
    parser.add_argument(
        "--exclude-terrain",
        action="store_true",
        help="Ignore DEM-derived terrain columns even if present.",
    )
    parser.add_argument(
        "--preset",
        choices=["custom", "quick", "standard", "heavy"],
        default="custom",
        help="Training preset. Explicit command-line values override preset defaults.",
    )
    parser.add_argument(
        "--forest-trees",
        type=int,
        default=None,
        help="Number of trees for RandomForestRegressor.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Maximum tree depth for RandomForestRegressor.",
    )
    parser.add_argument(
        "--min-samples-leaf",
        type=int,
        default=None,
        help="Minimum samples per leaf for RandomForestRegressor.",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.06,
        help="Learning rate for HistGradientBoostingRegressor.",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=None,
        help="Maximum boosting iterations for HistGradientBoostingRegressor.",
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
        default=None,
        help="Parallel jobs for RandomForestRegressor. Use -1 for all logical cores.",
    )
    parser.add_argument(
        "--model",
        choices=["both", "random-forest", "hist-gradient-boosting"],
        default=None,
        help="Which tree model to train.",
    )
    parser.add_argument(
        "--worst-count",
        type=int,
        default=10,
        help="Number of worst stations to print for each model.",
    )
    parser.add_argument(
        "--variable",
        choices=sorted(TEMPERATURE_VARIABLES),
        default="tavg",
        help="Daily temperature variable to train and score.",
    )
    parser.add_argument(
        "--predict-offset-from-baseline",
        action="store_true",
        help=(
            "Train models to predict target_<variable>_offset_from_baseline, "
            "then add regional_baseline_<variable> back before scoring and "
            "writing predictions."
        ),
    )
    return parser.parse_args()


def apply_training_preset(arguments):
    presets = {
        "custom": {
            "model": "both",
            "forest_trees": 250,
            "max_depth": 18,
            "min_samples_leaf": 5,
            "max_iter": 350,
            "jobs": -1,
        },
        "quick": {
            "model": "random-forest",
            "forest_trees": 80,
            "max_depth": 14,
            "min_samples_leaf": 10,
            "max_iter": 150,
            "jobs": -1,
        },
        "standard": {
            "model": "both",
            "forest_trees": 200,
            "max_depth": 18,
            "min_samples_leaf": 5,
            "max_iter": 350,
            "jobs": -1,
        },
        "heavy": {
            "model": "random-forest",
            "forest_trees": 300,
            "max_depth": 20,
            "min_samples_leaf": 5,
            "max_iter": 500,
            "jobs": -1,
        },
    }
    selected_preset = presets[arguments.preset]

    for name, value in selected_preset.items():
        if getattr(arguments, name) is None:
            setattr(arguments, name, value)

    if arguments.learning_rate is None:
        arguments.learning_rate = 0.06

    return arguments


def main():
    started_at = perf_counter()
    arguments = apply_training_preset(parse_arguments())
    variable = validate_temperature_variable(arguments.variable)
    RandomForestRegressor, HistGradientBoostingRegressor = import_sklearn_models()
    general_table = arguments.general_table or general_model.find_default_general_table()
    rows = read_csv_rows(general_table)

    if not rows:
        raise ValueError("The general training table is empty.")

    feature_selection = resolve_model_feature_selection(
        rows[0].keys(),
        variable=variable,
        include_terrain=not arguments.exclude_terrain,
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
    include_terrain = not arguments.exclude_terrain
    feature_columns = feature_selection.feature_columns
    if arguments.predict_offset_from_baseline:
        require_training_columns(
            rows[0].keys(),
            feature_selection,
            "Offset prediction requires a training table with these columns",
        )

    train_rows, test_rows = general_model.split_rows_by_year(
        rows,
        arguments.train_end,
        arguments.test_start,
    )

    if not train_rows:
        raise ValueError("No training rows were found. Try changing --train-end.")

    if not test_rows:
        raise ValueError("No test rows were found. Try changing --test-start.")

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
    test_features, test_labels = build_unscaled_features_and_labels(
        test_rows,
        feature_columns,
        label_column,
    )
    actual_train_values = actual_temperature_values(train_rows, variable)
    actual_test_values = actual_temperature_values(test_rows, variable)
    average_train_predictions = general_model.average_hub_predictions(
        train_rows,
        hub_count,
        variable,
    )
    average_test_predictions = general_model.average_hub_predictions(
        test_rows,
        hub_count,
        variable,
    )
    average_train_metrics = calculate_metrics(actual_train_values, average_train_predictions)
    average_test_metrics = calculate_metrics(actual_test_values, average_test_predictions)

    models = []

    if arguments.model in ("both", "random-forest"):
        models.append((
            "random_forest",
            "Random Forest",
            RandomForestRegressor(
                n_estimators=arguments.forest_trees,
                max_depth=arguments.max_depth,
                min_samples_leaf=arguments.min_samples_leaf,
                random_state=arguments.random_state,
                n_jobs=arguments.jobs,
            ),
        ))

    if arguments.model in ("both", "hist-gradient-boosting"):
        models.append((
            "hist_gradient_boosting",
            "Hist Gradient Boosting",
            HistGradientBoostingRegressor(
                learning_rate=arguments.learning_rate,
                max_iter=arguments.max_iter,
                l2_regularization=0.05,
                random_state=arguments.random_state,
            ),
        ))
    model_results = []

    for model_slug, model_label, model in models:
        train_predictions, test_predictions = fit_and_predict(
            model,
            train_features,
            train_labels,
            test_features,
        )
        if arguments.predict_offset_from_baseline:
            train_predictions = add_baseline_to_offsets(
                train_rows,
                train_predictions,
                baseline_column,
            )
            test_predictions = add_baseline_to_offsets(
                test_rows,
                test_predictions,
                baseline_column,
            )

        train_metrics = calculate_metrics(actual_train_values, train_predictions)
        test_metrics = calculate_metrics(actual_test_values, test_predictions)
        station_metrics = metrics_by_station(test_rows, actual_test_values, test_predictions)
        output_parts = [
            *([variable] if variable != "tavg" else []),
            "offset" if arguments.predict_offset_from_baseline else "direct",
            "terrain" if include_terrain else "no_terrain",
            arguments.preset,
            model_slug,
        ]
        output_slug = "_".join(output_parts)
        prediction_file = write_prediction_file(
            general_table,
            output_slug,
            test_rows,
            actual_test_values,
            test_predictions,
            variable,
        )
        station_report_file = write_station_report(
            general_table,
            output_slug,
            station_metrics,
        )
        model_results.append({
            "label": model_label,
            "slug": output_slug,
            "train_metrics": train_metrics,
            "test_metrics": test_metrics,
            "station_metrics": station_metrics,
            "prediction_file": prediction_file,
            "station_report_file": station_report_file,
        })

    unique_train_targets = len(set(row["target_station_id"] for row in train_rows))
    unique_test_targets = len(set(row["target_station_id"] for row in test_rows))

    print()
    print("Tree-based temperature reconstruction")
    print("=====================================")
    print(f"General table: {general_table}")
    print(f"Rows: {len(rows)}")
    print(f"Training rows: {len(train_rows)} through {arguments.train_end}")
    print(f"Testing rows: {len(test_rows)} from {arguments.test_start} onward")
    print(f"Training target stations: {unique_train_targets}")
    print(f"Testing target stations: {unique_test_targets}")
    print(f"Hubs per target: {hub_count}")
    print(f"Target-neighbor stations per target: {target_neighbor_count}")
    print(f"Temperature variable: {variable}")
    print(f"Feature inputs: {len(feature_columns)}")
    print(f"Terrain features: {'included' if include_terrain else 'excluded'}")
    print(
        "Prediction target: "
        + (
            "daily offset from regional baseline"
            if arguments.predict_offset_from_baseline
            else f"direct daily {variable} temperature"
        )
    )
    print(f"Preset: {arguments.preset}")

    print()
    print("Model comparison")
    print("----------------")
    print(
        f"{'Model':<28} "
        f"{'Train MAE':>9} {'Train RMSE':>10} {'Train r':>10} "
        f"{'Test MAE':>9} {'Test RMSE':>10} {'Test r':>10}"
    )
    print_metric_row("Average of hubs", average_train_metrics, average_test_metrics)

    for result in model_results:
        print_metric_row(
            result["label"],
            result["train_metrics"],
            result["test_metrics"],
        )

    for result in model_results:
        print_ml_goal_summary(
            result["label"],
            result["station_metrics"],
        )
        print_worst_stations(
            result["label"],
            result["station_metrics"],
            arguments.worst_count,
        )

    print()
    print("Output files")
    print("------------")

    for result in model_results:
        print(f"{result['label']} predictions: {result['prediction_file']}")
        print(f"{result['label']} station report: {result['station_report_file']}")

    print()
    print(f"Elapsed time: {perf_counter() - started_at:.1f} seconds")


if __name__ == "__main__":
    main()
