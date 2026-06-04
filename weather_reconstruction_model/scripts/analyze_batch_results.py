from pathlib import Path
import argparse

import config
from common.csv_utils import read_csv_rows
from common.metrics import calculate_correlation as calculate_pearson_correlation
from common.metrics import mean
from common.number_utils import to_optional_float


REPORT_DIR = config.REPORT_DIR

STRICT_MAX_MAE = config.ML_GOAL_MAX_MAE
STRICT_MAX_RMSE = config.ML_GOAL_MAX_RMSE
STRICT_MIN_CORRELATION = config.ML_GOAL_MIN_CORRELATION


def find_default_batch_report():
    reports = sorted(REPORT_DIR.glob("batch_*_targets_*_hubs.csv"))

    if not reports:
        raise FileNotFoundError(
            "No batch report was found. Run batch_validate_models.py first."
        )

    return reports[-1]


def has_value(row, column_name):
    return row.get(column_name, "") != ""


def optional_row_float(row, column_name):
    return to_optional_float(row.get(column_name, ""))


def to_int(row, column_name):
    if not has_value(row, column_name):
        return None

    return int(float(row[column_name]))


def median(values):
    sorted_values = sorted(values)
    middle = len(sorted_values) // 2

    if len(sorted_values) % 2 == 1:
        return sorted_values[middle]

    return (sorted_values[middle - 1] + sorted_values[middle]) / 2


def percentile(values, percentile_value):
    sorted_values = sorted(values)
    index = round((len(sorted_values) - 1) * percentile_value)
    return sorted_values[index]


def calculate_column_correlation(rows, x_column, y_column):
    pairs = []

    for row in rows:
        x_value = optional_row_float(row, x_column)
        y_value = optional_row_float(row, y_column)

        if x_value is None or y_value is None:
            continue

        pairs.append((x_value, y_value))

    if len(pairs) < 2:
        return None

    x_values = [pair[0] for pair in pairs]
    y_values = [pair[1] for pair in pairs]

    if len(set(x_values)) == 1 or len(set(y_values)) == 1:
        return None

    return calculate_pearson_correlation(x_values, y_values)


def metric_values(rows, column_name):
    values = []

    for row in rows:
        value = optional_row_float(row, column_name)

        if value is not None:
            values.append(value)

    return values


def summarize_metric(rows, column_name):
    values = metric_values(rows, column_name)

    if not values:
        return None

    return {
        "count": len(values),
        "mean": mean(values),
        "median": median(values),
        "p75": percentile(values, 0.75),
        "p90": percentile(values, 0.90),
        "minimum": min(values),
        "maximum": max(values),
    }


def is_strict_goal_pass(row):
    mae = optional_row_float(row, "test_mae_f")
    rmse = optional_row_float(row, "test_rmse_f")
    correlation = optional_row_float(row, "test_correlation")

    if mae is None or rmse is None or correlation is None:
        return False

    return (
        mae <= STRICT_MAX_MAE
        and rmse <= STRICT_MAX_RMSE
        and correlation >= STRICT_MIN_CORRELATION
    )


def model_rows(rows):
    return [
        row
        for row in rows
        if has_value(row, "test_mae_f")
        and has_value(row, "test_rmse_f")
        and has_value(row, "test_correlation")
    ]


def count_by_value(rows, column_name):
    counts = {}

    for row in rows:
        value = row.get(column_name, "")

        if value == "":
            value = "(blank)"

        counts[value] = counts.get(value, 0) + 1

    return counts


def print_counts(title, counts):
    print(title)
    print("-" * len(title))

    for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"{key}: {value}")

    print()


def print_metric_summary(label, summary, unit=""):
    if summary is None:
        print(f"{label}: no data")
        return

    suffix = f" {unit}" if unit else ""
    print(f"{label}")
    print("-" * len(label))
    print(f"count:  {summary['count']}")
    print(f"mean:   {summary['mean']:.4f}{suffix}")
    print(f"median: {summary['median']:.4f}{suffix}")
    print(f"p75:    {summary['p75']:.4f}{suffix}")
    print(f"p90:    {summary['p90']:.4f}{suffix}")
    print(f"min:    {summary['minimum']:.4f}{suffix}")
    print(f"max:    {summary['maximum']:.4f}{suffix}")
    print()


def print_worst_rows(rows, count):
    scored_rows = [
        row
        for row in rows
        if has_value(row, "test_mae_f")
    ]
    scored_rows.sort(key=lambda row: optional_row_float(row, "test_mae_f"), reverse=True)

    print(f"Worst {min(count, len(scored_rows))} Model Results By MAE")
    print("--------------------------------")
    print(
        f"{'Station':<12} {'Name':<24} {'MAE':>7} {'RMSE':>7} {'r':>8} "
        f"{'AvgDist':>8} {'AvgElev':>8} {'Status':>10}"
    )

    for row in scored_rows[:count]:
        print(
            f"{row['target_station_id']:<12} "
            f"{row['target_name'][:24]:<24} "
            f"{optional_row_float(row, 'test_mae_f'):>7.2f} "
            f"{optional_row_float(row, 'test_rmse_f'):>7.2f} "
            f"{optional_row_float(row, 'test_correlation'):>8.3f} "
            f"{optional_row_float(row, 'average_hub_distance_km'):>8.1f} "
            f"{optional_row_float(row, 'average_elevation_difference_m'):>8.1f} "
            f"{row['status']:>10}"
        )

    print()


def print_relationships(rows):
    relationships = [
        ("average_hub_distance_km", "test_mae_f", "Average hub distance vs MAE"),
        ("farthest_hub_km", "test_mae_f", "Farthest hub distance vs MAE"),
        ("average_elevation_difference_m", "test_mae_f", "Average elevation difference vs MAE"),
        ("target_elevation_m", "test_mae_f", "Target elevation vs MAE"),
        ("minimum_selected_overlap_percent", "test_mae_f", "Minimum selected overlap vs MAE"),
        ("test_days", "test_mae_f", "Test days vs MAE"),
    ]

    print("Simple Error Relationships")
    print("--------------------------")
    print("These are Pearson correlations. They show broad tendencies, not proof of cause.")

    for x_column, y_column, label in relationships:
        correlation = calculate_column_correlation(rows, x_column, y_column)

        if correlation is None:
            print(f"{label}: no data")
        else:
            print(f"{label}: {correlation:.3f}")

    print()


def print_strict_goal_summary(rows):
    modeled_rows = model_rows(rows)
    strict_passes = [row for row in modeled_rows if is_strict_goal_pass(row)]

    print("Strict End-Goal Check")
    print("---------------------")
    print(
        f"Goal: MAE <= {STRICT_MAX_MAE:.1f} F, "
        f"RMSE <= {STRICT_MAX_RMSE:.1f} F, "
        f"r >= {STRICT_MIN_CORRELATION:.3f}"
    )
    print(f"Modeled stations: {len(modeled_rows)}")
    print(f"Strict passes: {len(strict_passes)}")

    if modeled_rows:
        print(f"Strict pass rate among modeled stations: {len(strict_passes) / len(modeled_rows) * 100:.1f}%")

    print()


def write_markdown_report(output_file, batch_file, rows):
    modeled_rows = model_rows(rows)
    strict_passes = [row for row in modeled_rows if is_strict_goal_pass(row)]
    mae_summary = summarize_metric(modeled_rows, "test_mae_f")
    rmse_summary = summarize_metric(modeled_rows, "test_rmse_f")
    correlation_summary = summarize_metric(modeled_rows, "test_correlation")
    status_counts = count_by_value(rows, "status")
    reason_counts = count_by_value([row for row in rows if row.get("reason", "")], "reason")

    lines = [
        "# Batch Validation Analysis",
        "",
        f"Source report: `{batch_file}`",
        "",
        "## Overview",
        "",
        f"- Total rows: {len(rows)}",
        f"- Modeled stations: {len(modeled_rows)}",
        f"- Strict goal passes: {len(strict_passes)}",
    ]

    if modeled_rows:
        lines.append(f"- Strict pass rate among modeled stations: {len(strict_passes) / len(modeled_rows) * 100:.1f}%")

    lines.extend([
        "",
        "## Status Counts",
        "",
    ])

    for status, count in sorted(status_counts.items()):
        lines.append(f"- {status}: {count}")

    if reason_counts:
        lines.extend(["", "## Failure Reasons", ""])

        for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {reason}: {count}")

    lines.extend(["", "## Metric Summaries", ""])

    for label, summary, unit in [
        ("MAE", mae_summary, "F"),
        ("RMSE", rmse_summary, "F"),
        ("Correlation", correlation_summary, ""),
    ]:
        if summary is None:
            continue

        lines.extend([
            f"### {label}",
            "",
            f"- Median: {summary['median']:.4f} {unit}".rstrip(),
            f"- P75: {summary['p75']:.4f} {unit}".rstrip(),
            f"- P90: {summary['p90']:.4f} {unit}".rstrip(),
            f"- Min: {summary['minimum']:.4f} {unit}".rstrip(),
            f"- Max: {summary['maximum']:.4f} {unit}".rstrip(),
            "",
        ])

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(lines) + "\n")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Analyze a batch validation report and summarize model performance."
    )
    parser.add_argument(
        "batch_report",
        nargs="?",
        type=Path,
        default=None,
        help="Path to a batch_*_targets_*_hubs.csv report.",
    )
    parser.add_argument(
        "--worst",
        type=int,
        default=20,
        help="Number of worst stations to print.",
    )
    parser.add_argument(
        "--write-markdown",
        action="store_true",
        help="Also write a compact Markdown analysis report next to the CSV.",
    )
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    batch_report = arguments.batch_report or find_default_batch_report()
    rows = read_csv_rows(batch_report)
    modeled_rows = model_rows(rows)

    print("Batch Validation Analysis")
    print("=========================")
    print(f"Source report: {batch_report}")
    print(f"Total rows: {len(rows)}")
    print(f"Modeled stations: {len(modeled_rows)}")
    print()

    print_counts("Status Counts", count_by_value(rows, "status"))

    failure_rows = [row for row in rows if row.get("reason", "") != ""]

    if failure_rows:
        print_counts("Failure Reasons", count_by_value(failure_rows, "reason"))

    print_strict_goal_summary(rows)
    print_metric_summary("MAE Summary", summarize_metric(modeled_rows, "test_mae_f"), "F")
    print_metric_summary("RMSE Summary", summarize_metric(modeled_rows, "test_rmse_f"), "F")
    print_metric_summary("Correlation Summary", summarize_metric(modeled_rows, "test_correlation"))
    print_relationships(modeled_rows)
    print_worst_rows(modeled_rows, arguments.worst)

    if arguments.write_markdown:
        markdown_file = REPORT_DIR / f"{batch_report.stem}_analysis.md"
        write_markdown_report(markdown_file, batch_report, rows)
        print(f"Markdown report: {markdown_file}")


if __name__ == "__main__":
    main()
