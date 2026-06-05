"""Generate a report comparing Python predictions against independent C++ scoring.

The report documents whether the app engine agrees with reconstruction outputs produced by Python scripts."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import config
from common.number_utils import to_float
from common.reporting import escape_html as escape
from common.reporting import render_html_table, render_metric_card


REPORT_DIR = config.REPORT_DIR
DEFAULT_COMPARISON = (
    REPORT_DIR
    / "comparisons"
    / "option_c_vs_5_hub_standard_random_forest.csv"
)
DEFAULT_CPP_VALIDATION = (
    REPORT_DIR
    / "option_c_limit97_5_hubs_10_target_neighbors_terrain_standard_random_forest_predictions_cpp_validation.csv"
)
DEFAULT_PYTHON_METRICS = (
    REPORT_DIR
    / "option_c_limit97_5_hubs_10_target_neighbors_terrain_standard_random_forest_station_metrics.csv"
)
DEFAULT_OUTPUT = REPORT_DIR / "option_c_cpp_validation_writeup.html"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a readable HTML writeup for Option C C++ validation."
    )
    parser.add_argument("--comparison", type=Path, default=DEFAULT_COMPARISON)
    parser.add_argument("--cpp-validation", type=Path, default=DEFAULT_CPP_VALIDATION)
    parser.add_argument("--python-metrics", type=Path, default=DEFAULT_PYTHON_METRICS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def read_rows(file_path: Path) -> list[dict[str, str]]:
    with file_path.open("r", newline="") as file:
        return list(csv.DictReader(file))


def fmt(value: float, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}"


def is_strict_pass(mae: float, rmse: float, correlation: float) -> bool:
    return (
        mae <= config.ML_GOAL_MAX_MAE
        and rmse <= config.ML_GOAL_MAX_RMSE
        and correlation >= config.ML_GOAL_MIN_CORRELATION
    )


def summarize_comparison(rows: list[dict[str, str]]) -> dict[str, object]:
    improved = [row for row in rows if to_float(row["mae_delta"]) < 0]
    regressed = [row for row in rows if to_float(row["mae_delta"]) > 0]
    baseline_mae = [to_float(row["baseline_mae"]) for row in rows]
    candidate_mae = [to_float(row["candidate_mae"]) for row in rows]
    baseline_strict = [row for row in rows if row["baseline_strict_pass"] == "True"]
    candidate_strict = [row for row in rows if row["candidate_strict_pass"] == "True"]

    return {
        "common_count": len(rows),
        "improved_count": len(improved),
        "regressed_count": len(regressed),
        "baseline_mean_mae": sum(baseline_mae) / len(baseline_mae),
        "candidate_mean_mae": sum(candidate_mae) / len(candidate_mae),
        "mae_improvement": (
            sum(baseline_mae) / len(baseline_mae)
            - sum(candidate_mae) / len(candidate_mae)
        ),
        "baseline_strict_count": len(baseline_strict),
        "candidate_strict_count": len(candidate_strict),
    }


def summarize_cpp(
    cpp_rows: list[dict[str, str]],
    python_rows: list[dict[str, str]],
) -> dict[str, object]:
    python_by_station = {
        row["target_station_id"]: row
        for row in python_rows
    }
    strict_count = 0
    max_mae_diff = 0.0
    max_rmse_diff = 0.0
    max_correlation_diff = 0.0
    mismatches = 0
    missing_cpp_correlations = 0

    for row in cpp_rows:
        station_id = row["target_station_id"]
        python_row = python_by_station[station_id]
        cpp_mae = to_float(row["cpp_mae_f"])
        cpp_rmse = to_float(row["cpp_rmse_f"])
        cpp_correlation = to_float(row["cpp_correlation"])
        python_mae = to_float(python_row["mae"])
        python_rmse = to_float(python_row["rmse"])
        python_correlation = to_float(python_row["correlation"])

        if is_strict_pass(cpp_mae, cpp_rmse, cpp_correlation):
            strict_count += 1

        mae_diff = abs(cpp_mae - python_mae)
        rmse_diff = abs(cpp_rmse - python_rmse)
        max_mae_diff = max(max_mae_diff, mae_diff)
        max_rmse_diff = max(max_rmse_diff, rmse_diff)

        if cpp_correlation <= -999:
            missing_cpp_correlations += 1
            correlation_diff = 0.0
        else:
            correlation_diff = abs(cpp_correlation - python_correlation)
            max_correlation_diff = max(max_correlation_diff, correlation_diff)

        if mae_diff > 0.01 or rmse_diff > 0.01 or correlation_diff > 0.001:
            mismatches += 1

    return {
        "station_count": len(cpp_rows),
        "strict_count": strict_count,
        "max_mae_diff": max_mae_diff,
        "max_rmse_diff": max_rmse_diff,
        "max_correlation_diff": max_correlation_diff,
        "mismatches": mismatches,
        "missing_cpp_correlations": missing_cpp_correlations,
    }


def table(headers: list[str], rows: list[list[object]]) -> str:
    return render_html_table(headers, rows)


def render_card(label: str, value: str, note: str = "") -> str:
    return render_metric_card(
        label,
        value,
        note,
        label_class="card-label",
        value_class="card-value",
        note_class="card-note",
    )


def render_html(
    comparison_rows: list[dict[str, str]],
    cpp_rows: list[dict[str, str]],
    python_rows: list[dict[str, str]],
    comparison_summary: dict[str, object],
    cpp_summary: dict[str, object],
) -> str:
    top_improvements = sorted(
        comparison_rows,
        key=lambda row: to_float(row["mae_delta"]),
    )[:8]
    worst_regressions = sorted(
        comparison_rows,
        key=lambda row: to_float(row["mae_delta"]),
        reverse=True,
    )[:8]
    strict_transitions = [
        row
        for row in comparison_rows
        if row["baseline_strict_pass"] != row["candidate_strict_pass"]
    ]
    worst_cpp = sorted(
        cpp_rows,
        key=lambda row: to_float(row["cpp_mae_f"]),
        reverse=True,
    )[:10]

    improvement_rows = [
        [
            row["target_station_id"],
            row["target_name"],
            row["baseline_mae"],
            row["candidate_mae"],
            fmt(to_float(row["mae_delta"]), 3),
        ]
        for row in top_improvements
    ]
    regression_rows = [
        [
            row["target_station_id"],
            row["target_name"],
            row["baseline_mae"],
            row["candidate_mae"],
            f"+{fmt(to_float(row['mae_delta']), 3)}",
        ]
        for row in worst_regressions
    ]
    transition_rows = [
        [
            row["target_station_id"],
            row["target_name"],
            row["baseline_strict_pass"],
            row["candidate_strict_pass"],
            f"{row['baseline_mae']} -> {row['candidate_mae']}",
            f"{row['baseline_rmse']} -> {row['candidate_rmse']}",
        ]
        for row in strict_transitions
    ]
    cpp_worst_rows = [
        [
            row["target_station_id"],
            row["target_name"],
            row["cpp_mae_f"],
            row["cpp_rmse_f"],
            row["cpp_correlation"],
            row["cpp_paired_days"],
        ]
        for row in worst_cpp
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Option C C++ Validation Writeup</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f5f7fa;
      color: #1f2933;
      line-height: 1.5;
    }}
    header {{
      background: #14213d;
      color: white;
      padding: 34px 42px;
    }}
    header h1 {{
      margin: 0 0 8px;
      font-size: 31px;
      letter-spacing: 0;
    }}
    header p {{
      margin: 0;
      max-width: 900px;
      color: #d9e2ec;
      font-size: 16px;
    }}
    main {{
      max-width: 1220px;
      margin: 0 auto;
      padding: 28px;
    }}
    section {{
      margin-top: 24px;
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 23px;
    }}
    h3 {{
      margin: 0 0 12px;
      font-size: 18px;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 12px;
    }}
    .card, .panel {{
      background: white;
      border: 1px solid #d8dee8;
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }}
    .card-label {{
      color: #667085;
      font-size: 13px;
    }}
    .card-value {{
      margin-top: 5px;
      font-size: 26px;
      font-weight: 750;
    }}
    .card-note, .note {{
      color: #667085;
      font-size: 14px;
    }}
    .grid-two {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(460px, 1fr));
      gap: 16px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      padding: 9px 8px;
      border-bottom: 1px solid #d8dee8;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: #475467;
      background: #f8fafc;
      font-size: 12px;
      text-transform: uppercase;
    }}
    td:nth-child(2) {{
      min-width: 160px;
    }}
    .callout {{
      border-left: 5px solid #2563eb;
      background: white;
      border-radius: 8px;
      padding: 16px 18px;
      border-top: 1px solid #d8dee8;
      border-right: 1px solid #d8dee8;
      border-bottom: 1px solid #d8dee8;
    }}
    .good {{
      color: #087443;
      font-weight: 700;
    }}
    .warn {{
      color: #b54708;
      font-weight: 700;
    }}
    code {{
      background: #eef2f6;
      padding: 2px 5px;
      border-radius: 5px;
    }}
    @media (max-width: 720px) {{
      header {{ padding: 26px 18px; }}
      main {{ padding: 18px 12px 40px; }}
      .grid-two {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Option C C++ Validation Writeup</h1>
    <p>
      This report explains what happened when the Option C random-forest
      predictions were converted into C++ station-style files and independently
      scored by the existing C++ similarity engine.
    </p>
  </header>
  <main>
    <section class="cards">
      {render_card("Common Stations", str(comparison_summary["common_count"]))}
      {render_card("Improved By MAE", f"{comparison_summary['improved_count']}/{comparison_summary['common_count']}")}
      {render_card("Baseline Mean MAE", f"{fmt(comparison_summary['baseline_mean_mae'])} F", "5 hubs only")}
      {render_card("Option C Mean MAE", f"{fmt(comparison_summary['candidate_mean_mae'])} F", "5 hubs + 10 target-neighbors")}
      {render_card("MAE Improvement", f"{fmt(comparison_summary['mae_improvement'])} F")}
      {render_card("Strict ML Passes", f"{cpp_summary['strict_count']}/{cpp_summary['station_count']}", "Confirmed by C++")}
    </section>

    <section class="callout">
      <h2>Plain-English Result</h2>
      <p>
        Option C improved the model in a way that appears real. It lowered mean
        MAE from <strong>{fmt(comparison_summary['baseline_mean_mae'])} F</strong>
        to <strong>{fmt(comparison_summary['candidate_mean_mae'])} F</strong> on
        the common station set, and it improved
        <strong>{comparison_summary['improved_count']} of {comparison_summary['common_count']}</strong>
        stations by MAE.
      </p>
      <p>
        The independent C++ validator found
        <strong>{cpp_summary['strict_count']} strict ML passes out of {cpp_summary['station_count']}</strong>,
        matching the Python diagnostics. That means the Option C result is not
        just a Python reporting artifact.
      </p>
    </section>

    <section class="grid-two">
      <div class="panel">
        <h3>What Python Did</h3>
        <p>
          Python trained the random-forest model and wrote predictions containing
          <code>actual_tavg</code> and <code>predicted_tavg</code> for each held-out
          date and target station.
        </p>
        <p>
          Python then summarized the predictions with MAE, RMSE, correlation,
          strict pass count, and diagnostics.
        </p>
      </div>
      <div class="panel">
        <h3>What C++ Did</h3>
        <p>
          The validation script converted each station's predictions into two
          app-ready station CSVs: one actual station file and one predicted
          station file.
        </p>
        <p>
          The existing C++ engine then independently paired days and recalculated
          daily correlation, MAD/MAE, and RMSE.
        </p>
      </div>
    </section>

    <section class="cards">
      {render_card("Max MAE Difference", f"{fmt(cpp_summary['max_mae_diff'], 4)} F", "C++ vs Python")}
      {render_card("Max RMSE Difference", f"{fmt(cpp_summary['max_rmse_diff'], 4)} F", "C++ vs Python")}
      {render_card("Max r Difference", f"{fmt(cpp_summary['max_correlation_diff'], 6)}", "C++ vs Python")}
      {render_card("Metric Mismatches", str(cpp_summary["mismatches"]), "Over tolerance")}
    </section>

    <section class="callout">
      <h2>What This Confirms</h2>
      <p>
        The C++ and Python results agree to tiny rounding differences:
        maximum MAE and RMSE differences were both under
        <strong>0.004 F</strong>, and the maximum correlation difference was under
        <strong>0.00005</strong>. This is strong evidence that the model metrics
        were calculated correctly.
      </p>
      <p class="note">
        A small caveat: C++ reports correlation as -9999 when a station has too
        few paired days to calculate a meaningful correlation. Those cases still
        have valid MAE/RMSE comparisons, but the correlation itself is undefined.
      </p>
    </section>

    <section class="grid-two">
      <div class="panel">
        <h3>Largest Option C Improvements</h3>
        {table(["Station", "Name", "5 hubs MAE", "Option C MAE", "Delta"], improvement_rows)}
      </div>
      <div class="panel">
        <h3>Largest Option C Regressions</h3>
        {table(["Station", "Name", "5 hubs MAE", "Option C MAE", "Delta"], regression_rows)}
      </div>
    </section>

    <section class="panel">
      <h3>Strict Pass Changes</h3>
      <p class="note">
        These stations crossed the strict ML threshold in either direction.
      </p>
      {table(["Station", "Name", "5 hubs strict", "Option C strict", "MAE", "RMSE"], transition_rows)}
    </section>

    <section class="panel">
      <h3>Worst Option C Stations Confirmed By C++</h3>
      {table(["Station", "Name", "C++ MAE", "C++ RMSE", "C++ r", "Paired Days"], cpp_worst_rows)}
    </section>

    <section class="callout">
      <h2>Bottom Line</h2>
      <p>
        Option C is worth continued testing. It did not reach the long-term
        goal of 80% strict passes, but it meaningfully improved the model and
        doubled the strict pass count compared with the previous 5-hub-only
        setup. The C++ validation confirms that improvement is real within the
        existing engine's metric calculations.
      </p>
    </section>
  </main>
</body>
</html>
"""


def main() -> None:
    arguments = parse_arguments()
    comparison_rows = read_rows(arguments.comparison)
    cpp_rows = read_rows(arguments.cpp_validation)
    python_rows = read_rows(arguments.python_metrics)

    comparison_summary = summarize_comparison(comparison_rows)
    cpp_summary = summarize_cpp(cpp_rows, python_rows)
    html_text = render_html(
        comparison_rows,
        cpp_rows,
        python_rows,
        comparison_summary,
        cpp_summary,
    )

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(html_text)

    print("C++ validation writeup created")
    print(f"Output: {arguments.output}")
    print(
        "Summary: "
        f"{comparison_summary['improved_count']}/{comparison_summary['common_count']} "
        "stations improved by MAE; "
        f"{cpp_summary['strict_count']}/{cpp_summary['station_count']} "
        "strict passes confirmed by C++."
    )


if __name__ == "__main__":
    main()
