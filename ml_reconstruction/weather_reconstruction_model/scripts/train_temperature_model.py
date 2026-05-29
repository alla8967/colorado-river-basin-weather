from pathlib import Path
import argparse
import csv

import config
from common.metrics import calculate_metrics, mean
from common.number_utils import to_float

PROJECT_DIR = config.PROJECT_DIR
TRAINING_TABLE_DIR = config.TRAINING_TABLE_DIR
PREDICTION_DIR = config.PREDICTION_DIR
VALIDATION_DIR = config.VALIDATION_DIR
DEFAULT_TRAIN_END_YEAR = config.DEFAULT_TRAIN_END_YEAR
DEFAULT_TEST_START_YEAR = config.DEFAULT_TEST_START_YEAR


def find_default_training_table():
    training_tables = sorted(TRAINING_TABLE_DIR.glob("*_hubs.csv"))

    if not training_tables:
        raise FileNotFoundError(
            "No training table was found. Run build_training_table.py first."
        )

    return training_tables[-1]


def read_training_rows(file_path):
    with file_path.open("r", newline="") as file:
        return list(csv.DictReader(file))


def get_hub_temperature_columns(fieldnames):
    return [
        fieldname
        for fieldname in fieldnames
        if fieldname.startswith("hub_") and fieldname.endswith("_tavg")
    ]


def year_from_date(date_text):
    return int(date_text[:4])


def build_features_and_labels(rows, hub_temperature_columns):
    features = []
    labels = []

    for row in rows:
        # The leading 1.0 is the intercept term. It lets the model learn a
        # constant temperature offset instead of forcing the line through zero.
        feature_row = [1.0]

        for column in hub_temperature_columns:
            feature_row.append(to_float(row[column]))

        features.append(feature_row)
        labels.append(to_float(row["target_tavg"]))

    return features, labels


def split_rows_by_year(rows, train_end_year, test_start_year):
    train_rows = []
    test_rows = []

    for row in rows:
        row_year = year_from_date(row["date"])

        if row_year <= train_end_year:
            train_rows.append(row)
        elif row_year >= test_start_year:
            test_rows.append(row)

    return train_rows, test_rows


def transpose(matrix):
    return list(map(list, zip(*matrix)))


def multiply_matrix_vector(matrix, vector):
    return [
        sum(value * vector[index] for index, value in enumerate(row))
        for row in matrix
    ]


def build_normal_equations(features, labels, alpha):
    feature_count = len(features[0])
    xtx = [[0.0 for _ in range(feature_count)] for _ in range(feature_count)]
    xty = [0.0 for _ in range(feature_count)]

    for feature_row, label in zip(features, labels):
        for row_index in range(feature_count):
            xty[row_index] += feature_row[row_index] * label

            for column_index in range(feature_count):
                xtx[row_index][column_index] += (
                    feature_row[row_index] * feature_row[column_index]
                )

    # Alpha is optional ridge regularization. We skip the intercept so the
    # model can still learn the overall temperature offset naturally.
    for index in range(1, feature_count):
        xtx[index][index] += alpha

    return xtx, xty


def solve_linear_system(matrix, values):
    size = len(values)
    augmented = [
        [*matrix[row_index], values[row_index]]
        for row_index in range(size)
    ]

    for pivot_index in range(size):
        best_row = max(
            range(pivot_index, size),
            key=lambda row_index: abs(augmented[row_index][pivot_index]),
        )

        if abs(augmented[best_row][pivot_index]) < 1e-12:
            raise ValueError(
                "The regression math became unstable. Try running with --alpha 1.0."
            )

        augmented[pivot_index], augmented[best_row] = (
            augmented[best_row],
            augmented[pivot_index],
        )

        pivot_value = augmented[pivot_index][pivot_index]

        for column_index in range(pivot_index, size + 1):
            augmented[pivot_index][column_index] /= pivot_value

        for row_index in range(size):
            if row_index == pivot_index:
                continue

            scale = augmented[row_index][pivot_index]

            for column_index in range(pivot_index, size + 1):
                augmented[row_index][column_index] -= (
                    scale * augmented[pivot_index][column_index]
                )

    return [augmented[row_index][size] for row_index in range(size)]


def train_linear_regression(features, labels, alpha):
    normal_matrix, normal_values = build_normal_equations(features, labels, alpha)
    return solve_linear_system(normal_matrix, normal_values)


def predict(features, coefficients):
    return multiply_matrix_vector(features, coefficients)


def average_hub_predictions(rows, hub_temperature_columns):
    predictions = []

    for row in rows:
        hub_values = [to_float(row[column]) for column in hub_temperature_columns]
        predictions.append(mean(hub_values))

    return predictions


def single_hub_predictions(rows, hub_temperature_column):
    return [to_float(row[hub_temperature_column]) for row in rows]


def print_metric_row(name, train_metrics, test_metrics):
    print(
        f"{name:<24} "
        f"{train_metrics['mae']:>9.2f} {train_metrics['rmse']:>10.2f} {train_metrics['correlation']:>10.3f} "
        f"{test_metrics['mae']:>9.2f} {test_metrics['rmse']:>10.2f} {test_metrics['correlation']:>10.3f}"
    )


def write_predictions(file_path, test_rows, actual_values, predicted_values):
    PREDICTION_DIR.mkdir(parents=True, exist_ok=True)
    prediction_file = PREDICTION_DIR / f"{file_path.stem}_predictions.csv"

    with prediction_file.open("w", newline="") as file:
        fieldnames = [
            "date",
            "target_station_id",
            "actual_tavg",
            "predicted_tavg",
            "error",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for row, actual, predicted in zip(test_rows, actual_values, predicted_values):
            writer.writerow({
                "date": row["date"],
                "target_station_id": row["target_station_id"],
                "actual_tavg": f"{actual:.2f}",
                "predicted_tavg": f"{predicted:.2f}",
                "error": f"{actual - predicted:.2f}",
            })

    return prediction_file


def write_validation_station_csvs(file_path, test_rows, actual_values, predicted_values):
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    actual_file = VALIDATION_DIR / f"{file_path.stem}_actual.csv"
    predicted_file = VALIDATION_DIR / f"{file_path.stem}_predicted.csv"
    fieldnames = [
        "station_id",
        "station_name",
        "latitude",
        "longitude",
        "elevation",
        "date",
        "tmax",
        "tmin",
    ]

    with actual_file.open("w", newline="") as actual_output, predicted_file.open("w", newline="") as predicted_output:
        actual_writer = csv.DictWriter(actual_output, fieldnames=fieldnames)
        predicted_writer = csv.DictWriter(predicted_output, fieldnames=fieldnames)
        actual_writer.writeheader()
        predicted_writer.writeheader()

        for row, actual, predicted in zip(test_rows, actual_values, predicted_values):
            actual_writer.writerow({
                "station_id": row["target_station_id"],
                "station_name": "ACTUAL_TARGET_TAVG",
                "latitude": "0",
                "longitude": "0",
                "elevation": "0",
                "date": row["date"],
                "tmax": f"{actual:.2f}",
                "tmin": f"{actual:.2f}",
            })
            predicted_writer.writerow({
                "station_id": "PREDICTED_TARGET",
                "station_name": "PREDICTED_TARGET_TAVG",
                "latitude": "0",
                "longitude": "0",
                "elevation": "0",
                "date": row["date"],
                "tmax": f"{predicted:.2f}",
                "tmin": f"{predicted:.2f}",
            })

    return actual_file, predicted_file


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Train a simple temperature reconstruction model from a shared-date training table."
    )
    parser.add_argument(
        "training_table",
        nargs="?",
        type=Path,
        default=None,
        help="Path to a *_hubs.csv training table file.",
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
        default=0.0,
        help="Optional ridge regularization strength. Use 0.0 for ordinary linear regression.",
    )
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    training_table = arguments.training_table or find_default_training_table()

    rows = read_training_rows(training_table)

    if not rows:
        raise ValueError("The training table is empty.")

    hub_temperature_columns = get_hub_temperature_columns(rows[0].keys())

    if not hub_temperature_columns:
        raise ValueError("No hub temperature columns were found in the training table.")

    train_rows, test_rows = split_rows_by_year(
        rows,
        arguments.train_end,
        arguments.test_start,
    )

    if not train_rows:
        raise ValueError("No training rows were found. Try changing --train-end.")

    if not test_rows:
        raise ValueError("No test rows were found. Try changing --test-start.")

    train_features, train_labels = build_features_and_labels(
        train_rows,
        hub_temperature_columns,
    )
    test_features, test_labels = build_features_and_labels(
        test_rows,
        hub_temperature_columns,
    )

    coefficients = train_linear_regression(
        train_features,
        train_labels,
        arguments.alpha,
    )
    train_predictions = predict(train_features, coefficients)
    test_predictions = predict(test_features, coefficients)
    train_metrics = calculate_metrics(train_labels, train_predictions)
    test_metrics = calculate_metrics(test_labels, test_predictions)

    print()
    print("Linear temperature reconstruction")
    print("================================")
    print(f"Training table: {training_table}")
    print(f"Rows: {len(rows)}")
    print(f"Training rows: {len(train_rows)} through {arguments.train_end}")
    print(f"Testing rows: {len(test_rows)} from {arguments.test_start} onward")
    print(f"Hub inputs: {len(hub_temperature_columns)}")
    print(f"Alpha: {arguments.alpha}")
    print()

    print("Model comparison")
    print("----------------")
    print(
        f"{'Model':<24} "
        f"{'Train MAE':>9} {'Train RMSE':>10} {'Train r':>10} "
        f"{'Test MAE':>9} {'Test RMSE':>10} {'Test r':>10}"
    )

    average_train_predictions = average_hub_predictions(
        train_rows,
        hub_temperature_columns,
    )
    average_test_predictions = average_hub_predictions(
        test_rows,
        hub_temperature_columns,
    )
    print_metric_row(
        "Average of hubs",
        calculate_metrics(train_labels, average_train_predictions),
        calculate_metrics(test_labels, average_test_predictions),
    )

    for index, hub_column in enumerate(hub_temperature_columns, start=1):
        hub_train_predictions = single_hub_predictions(train_rows, hub_column)
        hub_test_predictions = single_hub_predictions(test_rows, hub_column)
        print_metric_row(
            f"Hub {index} only",
            calculate_metrics(train_labels, hub_train_predictions),
            calculate_metrics(test_labels, hub_test_predictions),
        )

    print_metric_row("Linear regression", train_metrics, test_metrics)

    print()
    print("Learned formula")
    print("---------------")
    print(f"target_tavg = {coefficients[0]:.3f}")

    for coefficient, hub_column in zip(coefficients[1:], hub_temperature_columns):
        print(f"            + {coefficient:.3f} * {hub_column}")

    prediction_file = write_predictions(
        training_table,
        test_rows,
        test_labels,
        test_predictions,
    )
    actual_station_file, predicted_station_file = write_validation_station_csvs(
        training_table,
        test_rows,
        test_labels,
        test_predictions,
    )

    print()
    print(f"Prediction file: {prediction_file}")
    print(f"Actual station validation CSV: {actual_station_file}")
    print(f"Predicted station validation CSV: {predicted_station_file}")


if __name__ == "__main__":
    main()
