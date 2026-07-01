"""Train general temperature reconstruction models from wide training tables.

This is the main configurable trainer for multiscale, terrain, offset, and pairwise-skill feature sets."""

import argparse
from pathlib import Path

import config
import train_temperature_model as regression
from common.csv_utils import read_csv_rows, write_csv_rows
from common.metrics import calculate_metrics, mean
from common.number_utils import to_float
from common.pairwise_skill import PAIRWISE_SKILL_COLUMNS
from common.weather_cache import TEMPERATURE_VARIABLES, validate_temperature_variable

GENERAL_TABLE_DIR = config.GENERAL_TABLE_DIR
PREDICTION_DIR = config.PREDICTION_DIR
REPORT_DIR = config.REPORT_DIR
DEFAULT_TRAIN_END_YEAR = config.DEFAULT_TRAIN_END_YEAR
DEFAULT_TEST_START_YEAR = config.DEFAULT_TEST_START_YEAR


BASE_FEATURE_COLUMNS = [
    "season_sin",
    "season_cos",
    "target_latitude",
    "target_longitude",
    "target_elevation_m",
]
TARGET_TERRAIN_FEATURE_COLUMNS = [
    "target_dem_elevation_m",
    "target_dem_minus_noaa_elevation_m",
    "target_slope_degrees",
    "target_aspect_sin",
    "target_aspect_cos",
    "target_local_relief_m",
    "target_terrain_position_index_m",
]
MULTI_SCALE_TERRAIN_RADIUS_LABELS = [
    "r90m",
    "r300m",
    "r990m",
    "r3000m",
]
MULTI_SCALE_TERRAIN_FEATURE_STEMS = [
    "slope_degrees",
    "aspect_sin",
    "aspect_cos",
    "local_relief_m",
    "terrain_position_index_m",
]
TARGET_TERRAIN_FEATURE_COLUMNS.extend([
    f"target_{stem}_{radius_label}"
    for radius_label in MULTI_SCALE_TERRAIN_RADIUS_LABELS
    for stem in MULTI_SCALE_TERRAIN_FEATURE_STEMS
])
HUB_TERRAIN_FEATURE_SUFFIXES = [
    "dem_elevation_m",
    "dem_minus_noaa_elevation_m",
    "slope_degrees",
    "aspect_sin",
    "aspect_cos",
    "local_relief_m",
    "terrain_position_index_m",
]
HUB_TERRAIN_FEATURE_SUFFIXES.extend([
    f"{stem}_{radius_label}"
    for radius_label in MULTI_SCALE_TERRAIN_RADIUS_LABELS
    for stem in MULTI_SCALE_TERRAIN_FEATURE_STEMS
])
ENGINEERED_HUB_FEATURE_SUFFIXES = [
    "dem_elevation_delta_m",
    "abs_dem_elevation_delta_m",
    "slope_delta_degrees",
    "abs_slope_delta_degrees",
    "local_relief_delta_m",
    "abs_local_relief_delta_m",
    "terrain_position_delta_m",
    "abs_terrain_position_delta_m",
    "aspect_similarity",
    "distance_x_abs_dem_elevation_delta",
    "season_sin_x_dem_elevation_delta",
    "season_cos_x_dem_elevation_delta",
    "season_sin_x_terrain_position_delta",
    "season_cos_x_terrain_position_delta",
]
PREDICTOR_SELECTION_FEATURE_SUFFIXES = [
    "selection_score",
    "physical_similarity_score",
    "distance_score",
    "elevation_score",
    "terrain_position_score",
    "relief_score",
    "slope_score",
    "aspect_score",
]
PREDICTOR_PAIRWISE_FEATURE_SUFFIXES = PAIRWISE_SKILL_COLUMNS


def find_default_general_table():
    general_tables = sorted(GENERAL_TABLE_DIR.glob("general_*_targets_*_hubs.csv"))

    if not general_tables:
        raise FileNotFoundError(
            "No general training table was found. Run build_general_training_table.py first."
        )

    return general_tables[-1]


def get_hub_count(fieldnames, variable="tavg"):
    variable = validate_temperature_variable(variable)
    count = 0

    for fieldname in fieldnames:
        if fieldname.startswith("hub_") and fieldname.endswith(f"_{variable}"):
            count += 1

    return count


def get_target_neighbor_count(fieldnames, variable="tavg"):
    variable = validate_temperature_variable(variable)
    count = 0

    for fieldname in fieldnames:
        if fieldname.startswith("target_neighbor_") and fieldname.endswith(f"_{variable}"):
            count += 1

    return count


def build_feature_columns(hub_count, fieldnames, include_terrain=True, variable="tavg"):
    variable = validate_temperature_variable(variable)
    available_fieldnames = set(fieldnames)
    feature_columns = [
        column
        for column in BASE_FEATURE_COLUMNS
        if column in available_fieldnames
    ]

    if include_terrain:
        feature_columns.extend([
            column
            for column in TARGET_TERRAIN_FEATURE_COLUMNS
            if column in available_fieldnames
        ])

    add_predictor_feature_columns(
        feature_columns,
        available_fieldnames,
        "hub",
        hub_count,
        include_terrain,
        variable,
    )
    add_predictor_feature_columns(
        feature_columns,
        available_fieldnames,
        "target_neighbor",
        get_target_neighbor_count(fieldnames, variable),
        include_terrain,
        variable,
    )

    return feature_columns


def add_predictor_feature_columns(
    feature_columns,
    available_fieldnames,
    prefix,
    count,
    include_terrain,
    variable="tavg",
):
    variable = validate_temperature_variable(variable)

    for index in range(1, count + 1):
        indexed_prefix = f"{prefix}_{index}"
        predictor_columns = [
            f"{indexed_prefix}_{variable}",
            f"{indexed_prefix}_distance_km",
            f"{indexed_prefix}_elevation_difference_m",
            f"{indexed_prefix}_latitude_offset",
            f"{indexed_prefix}_longitude_offset",
            f"{indexed_prefix}_overlap_percent",
        ]
        predictor_columns.extend([
            f"{indexed_prefix}_{suffix}"
            for suffix in PREDICTOR_SELECTION_FEATURE_SUFFIXES
        ])
        predictor_columns.extend([
            f"{indexed_prefix}_{suffix}"
            for suffix in PREDICTOR_PAIRWISE_FEATURE_SUFFIXES
        ])
        if include_terrain:
            predictor_columns.extend([
                f"{indexed_prefix}_{suffix}"
                for suffix in HUB_TERRAIN_FEATURE_SUFFIXES
            ])
            predictor_columns.extend([
                f"{indexed_prefix}_{suffix}"
                for suffix in ENGINEERED_HUB_FEATURE_SUFFIXES
            ])
        feature_columns.extend([
            column
            for column in predictor_columns
            if column in available_fieldnames
        ])


def split_rows_by_year(rows, train_end_year, test_start_year):
    train_rows = []
    test_rows = []

    for row in rows:
        year = int(row["year"])

        if year <= train_end_year:
            train_rows.append(row)
        elif year >= test_start_year:
            test_rows.append(row)

    return train_rows, test_rows


def calculate_feature_stats(rows, feature_columns):
    stats = {}

    for column in feature_columns:
        values = [to_float(row.get(column, "")) for row in rows]
        mean_value = mean(values)
        variance = mean([
            (value - mean_value) ** 2
            for value in values
        ])
        scale = variance ** 0.5

        if scale == 0:
            scale = 1.0

        stats[column] = {
            "mean": mean_value,
            "scale": scale,
        }

    return stats


def build_features_and_labels(
    rows,
    feature_columns,
    feature_stats,
    label_column="target_tavg",
):
    features = []
    labels = []

    for row in rows:
        feature_row = [1.0]

        for column in feature_columns:
            value = to_float(row.get(column, ""))
            mean_value = feature_stats[column]["mean"]
            scale = feature_stats[column]["scale"]
            feature_row.append((value - mean_value) / scale)

        features.append(feature_row)
        labels.append(to_float(row[label_column]))

    return features, labels


def average_hub_predictions(rows, hub_count, variable="tavg"):
    variable = validate_temperature_variable(variable)
    predictions = []

    for row in rows:
        hub_values = [
            to_float(row[f"hub_{index}_{variable}"])
            for index in range(1, hub_count + 1)
        ]
        predictions.append(mean(hub_values))

    return predictions


def print_metric_row(name, train_metrics, test_metrics):
    print(
        f"{name:<28} "
        f"{train_metrics['mae']:>9.2f} {train_metrics['rmse']:>10.2f} {train_metrics['correlation']:>10.3f} "
        f"{test_metrics['mae']:>9.2f} {test_metrics['rmse']:>10.2f} {test_metrics['correlation']:>10.3f}"
    )


def metrics_by_station(rows, actual_values, predicted_values):
    grouped = {}

    for row, actual, predicted in zip(rows, actual_values, predicted_values):
        station_id = row["target_station_id"]

        if station_id not in grouped:
            grouped[station_id] = {
                "target_name": row["target_name"],
                "actual": [],
                "predicted": [],
            }

        grouped[station_id]["actual"].append(actual)
        grouped[station_id]["predicted"].append(predicted)

    station_metrics = []

    for station_id, values in grouped.items():
        metrics = calculate_metrics(values["actual"], values["predicted"])
        station_metrics.append({
            "target_station_id": station_id,
            "target_name": values["target_name"],
            "test_rows": len(values["actual"]),
            "mae": metrics["mae"],
            "rmse": metrics["rmse"],
            "correlation": metrics["correlation"],
        })

    station_metrics.sort(key=lambda row: row["mae"], reverse=True)
    return station_metrics


def write_prediction_file(
    general_table,
    model_variant,
    test_rows,
    actual_values,
    predicted_values,
    variable="tavg",
):
    variable = validate_temperature_variable(variable)
    prediction_file = PREDICTION_DIR / f"{general_table.stem}_{model_variant}_predictions.csv"
    rows = []
    actual_column = f"actual_{variable}"
    predicted_column = f"predicted_{variable}"

    for row, actual, predicted in zip(test_rows, actual_values, predicted_values):
        rows.append({
            "date": row["date"],
            "target_station_id": row["target_station_id"],
            "target_name": row["target_name"],
            actual_column: f"{actual:.2f}",
            predicted_column: f"{predicted:.2f}",
            "error": f"{actual - predicted:.2f}",
        })

    write_csv_rows(
        prediction_file,
        rows,
        [
            "date",
            "target_station_id",
            "target_name",
            actual_column,
            predicted_column,
            "error",
        ],
    )

    return prediction_file


def write_station_report(general_table, model_variant, station_metrics):
    report_file = REPORT_DIR / f"{general_table.stem}_{model_variant}_station_metrics.csv"
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


def print_top_coefficients(coefficients, feature_columns, limit):
    coefficient_rows = [
        {
            "feature": feature,
            "coefficient": coefficient,
            "absolute_coefficient": abs(coefficient),
        }
        for feature, coefficient in zip(feature_columns, coefficients[1:])
    ]
    coefficient_rows.sort(key=lambda row: row["absolute_coefficient"], reverse=True)

    print()
    print("Largest standardized coefficients")
    print("---------------------------------")
    print(f"Intercept: {coefficients[0]:.3f}")

    for row in coefficient_rows[:limit]:
        print(f"{row['feature']:<36} {row['coefficient']:>9.3f}")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Train a general temperature model from a many-station training table."
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
        "--alpha",
        type=float,
        default=1.0,
        help="Ridge regularization strength. Use 0.0 for ordinary linear regression.",
    )
    parser.add_argument(
        "--coefficient-limit",
        type=int,
        default=20,
        help="Number of largest coefficients to print.",
    )
    parser.add_argument(
        "--exclude-terrain",
        action="store_true",
        help="Ignore DEM-derived terrain columns even if they are present in the table.",
    )
    parser.add_argument(
        "--variable",
        choices=sorted(TEMPERATURE_VARIABLES),
        default="tavg",
        help="Daily temperature variable to train and score.",
    )
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    variable = validate_temperature_variable(arguments.variable)
    general_table = arguments.general_table or find_default_general_table()
    rows = read_csv_rows(general_table)

    if not rows:
        raise ValueError("The general training table is empty.")

    target_column = f"target_{variable}"

    if target_column not in rows[0]:
        raise ValueError(
            f"Training table is missing {target_column}. "
            f"Build it with --variable {variable}."
        )

    hub_count = get_hub_count(rows[0].keys(), variable)
    target_neighbor_count = get_target_neighbor_count(rows[0].keys(), variable)
    include_terrain = not arguments.exclude_terrain
    feature_columns = build_feature_columns(
        hub_count,
        rows[0].keys(),
        include_terrain,
        variable,
    )
    model_variant = "terrain_general" if include_terrain else "no_terrain_general"
    if variable != "tavg":
        model_variant = f"{variable}_{model_variant}"

    train_rows, test_rows = split_rows_by_year(
        rows,
        arguments.train_end,
        arguments.test_start,
    )

    if not train_rows:
        raise ValueError("No training rows were found. Try changing --train-end.")

    if not test_rows:
        raise ValueError("No test rows were found. Try changing --test-start.")

    feature_stats = calculate_feature_stats(train_rows, feature_columns)
    train_features, train_labels = build_features_and_labels(
        train_rows,
        feature_columns,
        feature_stats,
        target_column,
    )
    test_features, test_labels = build_features_and_labels(
        test_rows,
        feature_columns,
        feature_stats,
        target_column,
    )

    coefficients = regression.train_linear_regression(
        train_features,
        train_labels,
        arguments.alpha,
    )
    train_predictions = regression.predict(train_features, coefficients)
    test_predictions = regression.predict(test_features, coefficients)
    train_metrics = calculate_metrics(train_labels, train_predictions)
    test_metrics = calculate_metrics(test_labels, test_predictions)

    average_train_predictions = average_hub_predictions(train_rows, hub_count, variable)
    average_test_predictions = average_hub_predictions(test_rows, hub_count, variable)
    average_train_metrics = calculate_metrics(
        train_labels,
        average_train_predictions,
    )
    average_test_metrics = calculate_metrics(
        test_labels,
        average_test_predictions,
    )

    unique_train_targets = len(set(row["target_station_id"] for row in train_rows))
    unique_test_targets = len(set(row["target_station_id"] for row in test_rows))

    print()
    print("General temperature reconstruction")
    print("==================================")
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
    print(f"Alpha: {arguments.alpha}")

    print()
    print("Model comparison")
    print("----------------")
    print(
        f"{'Model':<28} "
        f"{'Train MAE':>9} {'Train RMSE':>10} {'Train r':>10} "
        f"{'Test MAE':>9} {'Test RMSE':>10} {'Test r':>10}"
    )
    print_metric_row("Average of hubs", average_train_metrics, average_test_metrics)
    print_metric_row("General linear regression", train_metrics, test_metrics)

    print_top_coefficients(
        coefficients,
        feature_columns,
        arguments.coefficient_limit,
    )

    station_metrics = metrics_by_station(test_rows, test_labels, test_predictions)

    print()
    print("Worst test stations by MAE")
    print("--------------------------")
    print(f"{'Station':<12} {'MAE':>7} {'RMSE':>7} {'r':>8} {'Rows':>6}  Name")

    for row in station_metrics[:10]:
        print(
            f"{row['target_station_id']:<12} "
            f"{row['mae']:>7.2f} {row['rmse']:>7.2f} {row['correlation']:>8.3f} "
            f"{row['test_rows']:>6}  {row['target_name']}"
        )

    prediction_file = write_prediction_file(
        general_table,
        model_variant,
        test_rows,
        test_labels,
        test_predictions,
        variable,
    )
    station_report_file = write_station_report(general_table, model_variant, station_metrics)

    print()
    print(f"Prediction file: {prediction_file}")
    print(f"Station metrics report: {station_report_file}")


if __name__ == "__main__":
    main()
