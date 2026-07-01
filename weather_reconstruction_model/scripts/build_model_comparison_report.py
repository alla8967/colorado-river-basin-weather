"""Render an HTML report comparing model validation runs.

This gives reviewers a compact view of which configurations performed best across targets and variables."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from common.csv_utils import write_csv_rows
from common.metrics import mean
from common.number_utils import to_float
from common.reporting import escape_html as escape
from common.reporting import render_metric_card
from config import (
    ML_GOAL_MAX_MAE,
    ML_GOAL_MAX_RMSE,
    ML_GOAL_MIN_CORRELATION,
    REPORT_DIR,
)

STRICT_MAX_MAE = ML_GOAL_MAX_MAE
STRICT_MAX_RMSE = ML_GOAL_MAX_RMSE
STRICT_MIN_CORRELATION = ML_GOAL_MIN_CORRELATION
DEFAULT_OUTPUT_DIR = REPORT_DIR / "comparisons"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two station-metrics reports and write CSV/HTML summaries."
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="Baseline station_metrics.csv file.",
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        required=True,
        help="Candidate station_metrics.csv file.",
    )
    parser.add_argument(
        "--baseline-label",
        default="Baseline",
        help="Short label for the baseline model.",
    )
    parser.add_argument(
        "--candidate-label",
        default="Candidate",
        help="Short label for the candidate model.",
    )
    parser.add_argument(
        "--output-stem",
        default="model_comparison",
        help="Output filename stem for CSV and HTML files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for comparison reports.",
    )
    return parser.parse_args()


def load_station_metrics(file_path: Path) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}

    with file_path.open("r", newline="") as file:
        for row in csv.DictReader(file):
            rows[row["target_station_id"]] = {
                "target_station_id": row["target_station_id"],
                "target_name": row["target_name"],
                "test_rows": int(row["test_rows"]),
                "mae": to_float(row["mae"]),
                "rmse": to_float(row["rmse"]),
                "correlation": to_float(row["correlation"]),
            }

    return rows


def strict_pass(row: dict[str, object]) -> bool:
    return (
        to_float(row["mae"]) < STRICT_MAX_MAE
        and to_float(row["rmse"]) < STRICT_MAX_RMSE
        and to_float(row["correlation"]) >= STRICT_MIN_CORRELATION
    )


def build_comparison_rows(
    baseline_rows: dict[str, dict[str, object]],
    candidate_rows: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    comparison_rows: list[dict[str, object]] = []

    for station_id in sorted(set(baseline_rows).intersection(candidate_rows)):
        baseline = baseline_rows[station_id]
        candidate = candidate_rows[station_id]
        baseline_mae = to_float(baseline["mae"])
        candidate_mae = to_float(candidate["mae"])
        baseline_rmse = to_float(baseline["rmse"])
        candidate_rmse = to_float(candidate["rmse"])
        baseline_correlation = to_float(baseline["correlation"])
        candidate_correlation = to_float(candidate["correlation"])

        comparison_rows.append({
            "target_station_id": station_id,
            "target_name": baseline["target_name"],
            "baseline_test_rows": baseline["test_rows"],
            "candidate_test_rows": candidate["test_rows"],
            "baseline_mae": baseline_mae,
            "candidate_mae": candidate_mae,
            "mae_delta": candidate_mae - baseline_mae,
            "baseline_rmse": baseline_rmse,
            "candidate_rmse": candidate_rmse,
            "rmse_delta": candidate_rmse - baseline_rmse,
            "baseline_correlation": baseline_correlation,
            "candidate_correlation": candidate_correlation,
            "correlation_delta": candidate_correlation - baseline_correlation,
            "baseline_strict_pass": strict_pass(baseline),
            "candidate_strict_pass": strict_pass(candidate),
        })

    comparison_rows.sort(key=lambda row: row["mae_delta"])
    return comparison_rows


def summarize(
    baseline_rows: dict[str, dict[str, object]],
    candidate_rows: dict[str, dict[str, object]],
    comparison_rows: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "baseline_station_count": len(baseline_rows),
        "candidate_station_count": len(candidate_rows),
        "common_station_count": len(comparison_rows),
        "baseline_common_mae": mean([row["baseline_mae"] for row in comparison_rows]),
        "candidate_common_mae": mean([row["candidate_mae"] for row in comparison_rows]),
        "baseline_common_rmse": mean([row["baseline_rmse"] for row in comparison_rows]),
        "candidate_common_rmse": mean([row["candidate_rmse"] for row in comparison_rows]),
        "baseline_common_correlation": mean(
            [row["baseline_correlation"] for row in comparison_rows]
        ),
        "candidate_common_correlation": mean(
            [row["candidate_correlation"] for row in comparison_rows]
        ),
        "improved_count": sum(1 for row in comparison_rows if row["mae_delta"] < 0),
        "regressed_count": sum(1 for row in comparison_rows if row["mae_delta"] > 0),
        "unchanged_count": sum(1 for row in comparison_rows if row["mae_delta"] == 0),
        "baseline_common_strict_count": sum(
            1 for row in comparison_rows if row["baseline_strict_pass"]
        ),
        "candidate_common_strict_count": sum(
            1 for row in comparison_rows if row["candidate_strict_pass"]
        ),
    }


def write_comparison_csv(
    output_file: Path,
    comparison_rows: list[dict[str, object]],
) -> None:
    rows = []
    for row in comparison_rows:
        rows.append({
            "target_station_id": row["target_station_id"],
            "target_name": row["target_name"],
            "baseline_test_rows": row["baseline_test_rows"],
            "candidate_test_rows": row["candidate_test_rows"],
            "baseline_mae": f"{row['baseline_mae']:.4f}",
            "candidate_mae": f"{row['candidate_mae']:.4f}",
            "mae_delta": f"{row['mae_delta']:.4f}",
            "baseline_rmse": f"{row['baseline_rmse']:.4f}",
            "candidate_rmse": f"{row['candidate_rmse']:.4f}",
            "rmse_delta": f"{row['rmse_delta']:.4f}",
            "baseline_correlation": f"{row['baseline_correlation']:.6f}",
            "candidate_correlation": f"{row['candidate_correlation']:.6f}",
            "correlation_delta": f"{row['correlation_delta']:.6f}",
            "baseline_strict_pass": row["baseline_strict_pass"],
            "candidate_strict_pass": row["candidate_strict_pass"],
        })

    write_csv_rows(
        output_file,
        rows,
        [
            "target_station_id",
            "target_name",
            "baseline_test_rows",
            "candidate_test_rows",
            "baseline_mae",
            "candidate_mae",
            "mae_delta",
            "baseline_rmse",
            "candidate_rmse",
            "rmse_delta",
            "baseline_correlation",
            "candidate_correlation",
            "correlation_delta",
            "baseline_strict_pass",
            "candidate_strict_pass",
        ],
    )


def write_comparison_html(
    output_file: Path,
    comparison_rows: list[dict[str, object]],
    summary: dict[str, object],
    baseline_label: str,
    candidate_label: str,
    baseline_path: Path,
    candidate_path: Path,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        build_html(
            comparison_rows,
            summary,
            baseline_label,
            candidate_label,
            baseline_path,
            candidate_path,
        )
    )


def build_html(
    rows: list[dict[str, object]],
    summary: dict[str, object],
    baseline_label: str,
    candidate_label: str,
    baseline_path: Path,
    candidate_path: Path,
) -> str:
    best_rows = rows[:8]
    worst_rows = sorted(rows, key=lambda row: row["mae_delta"], reverse=True)[:8]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Model Comparison</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f6f7f9;
      color: #20242a;
      line-height: 1.45;
    }}
    header {{
      background: #18232f;
      color: white;
      padding: 30px 40px;
    }}
    header h1 {{
      margin: 0 0 8px;
      font-size: 30px;
    }}
    header p {{
      margin: 0;
      color: #d5dce6;
    }}
    main {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 28px;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 12px;
    }}
    .card, .panel {{
      background: white;
      border: 1px solid #d9dee7;
      border-radius: 8px;
      padding: 16px;
    }}
    .label {{
      color: #667085;
      font-size: 13px;
    }}
    .value {{
      margin-top: 4px;
      font-weight: 700;
      font-size: 25px;
    }}
    .grid-two {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(460px, 1fr));
      gap: 16px;
      margin-top: 18px;
    }}
    h2 {{
      margin: 34px 0 12px;
      font-size: 22px;
    }}
    h3 {{
      margin: 0 0 12px;
      font-size: 17px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      padding: 9px 8px;
      border-bottom: 1px solid #d9dee7;
      text-align: left;
      white-space: nowrap;
    }}
    th {{
      color: #344054;
      font-size: 12px;
      text-transform: uppercase;
      background: #f8fafc;
    }}
    .station-name {{
      white-space: normal;
      min-width: 170px;
    }}
    .good {{
      color: #177245;
      font-weight: 700;
    }}
    .bad {{
      color: #b42318;
      font-weight: 700;
    }}
    .note {{
      color: #667085;
      font-size: 14px;
    }}
    @media (max-width: 700px) {{
      header {{ padding: 24px 20px; }}
      main {{ padding: 20px 14px 42px; }}
      th, td {{ white-space: normal; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Model Comparison</h1>
    <p>{escape(candidate_label)} compared against {escape(baseline_label)} on common target stations.</p>
  </header>
  <main>
    <section class="cards">
      {card("Common Stations", str(summary["common_station_count"]))}
      {card("Improved By MAE", f"{summary['improved_count']}/{summary['common_station_count']}")}
      {card("Regressed By MAE", f"{summary['regressed_count']}/{summary['common_station_count']}")}
      {card(f"{baseline_label} MAE", f"{summary['baseline_common_mae']:.2f} F")}
      {card(f"{candidate_label} MAE", f"{summary['candidate_common_mae']:.2f} F")}
      {card("MAE Change", f"{summary['candidate_common_mae'] - summary['baseline_common_mae']:+.2f} F")}
      {card(f"{baseline_label} Strict", f"{summary['baseline_common_strict_count']}/{summary['common_station_count']}")}
      {card(f"{candidate_label} Strict", f"{summary['candidate_common_strict_count']}/{summary['common_station_count']}")}
    </section>

    <section class="grid-two">
      <div class="panel">
        <h3>Biggest Improvements</h3>
        {comparison_table(best_rows, baseline_label, candidate_label)}
      </div>
      <div class="panel">
        <h3>Biggest Regressions</h3>
        {comparison_table(worst_rows, baseline_label, candidate_label)}
      </div>
    </section>

    <section>
      <h2>All Common Stations</h2>
      <div class="panel">
        {comparison_table(rows, baseline_label, candidate_label)}
      </div>
    </section>

    <section>
      <h2>Source Files</h2>
      <div class="panel">
        <p class="note">Baseline: {escape(baseline_path)}</p>
        <p class="note">Candidate: {escape(candidate_path)}</p>
      </div>
    </section>
  </main>
</body>
</html>
"""


def card(label: str, value: str) -> str:
    return render_metric_card(label, value)


def comparison_table(
    rows: list[dict[str, object]],
    baseline_label: str,
    candidate_label: str,
) -> str:
    body = "\n".join(
        f"""
        <tr>
          <td>{escape(row["target_station_id"])}</td>
          <td class="station-name">{escape(row["target_name"])}</td>
          <td>{row["baseline_mae"]:.2f}</td>
          <td>{row["candidate_mae"]:.2f}</td>
          <td>{delta_cell(row["mae_delta"])}</td>
          <td>{row["baseline_rmse"]:.2f}</td>
          <td>{row["candidate_rmse"]:.2f}</td>
          <td>{row["baseline_correlation"]:.3f}</td>
          <td>{row["candidate_correlation"]:.3f}</td>
          <td>{strict_cell(row["baseline_strict_pass"])}</td>
          <td>{strict_cell(row["candidate_strict_pass"])}</td>
        </tr>"""
        for row in rows
    )
    return f"""
    <table>
      <thead>
        <tr>
          <th>Station</th>
          <th>Name</th>
          <th>{escape(baseline_label)} MAE</th>
          <th>{escape(candidate_label)} MAE</th>
          <th>Delta</th>
          <th>{escape(baseline_label)} RMSE</th>
          <th>{escape(candidate_label)} RMSE</th>
          <th>{escape(baseline_label)} r</th>
          <th>{escape(candidate_label)} r</th>
          <th>{escape(baseline_label)} Strict</th>
          <th>{escape(candidate_label)} Strict</th>
        </tr>
      </thead>
      <tbody>{body}</tbody>
    </table>"""


def delta_cell(delta: float) -> str:
    css_class = "good" if delta < 0 else "bad" if delta > 0 else ""
    return f'<span class="{css_class}">{delta:+.2f}</span>'


def strict_cell(value: bool) -> str:
    if value:
        return '<span class="good">Pass</span>'
    return '<span class="bad">Fail</span>'


def main() -> None:
    arguments = parse_arguments()
    baseline_rows = load_station_metrics(arguments.baseline)
    candidate_rows = load_station_metrics(arguments.candidate)
    comparison_rows = build_comparison_rows(baseline_rows, candidate_rows)

    if not comparison_rows:
        raise ValueError("No common stations were found between the two reports.")

    summary = summarize(baseline_rows, candidate_rows, comparison_rows)
    csv_file = arguments.output_dir / f"{arguments.output_stem}.csv"
    html_file = arguments.output_dir / f"{arguments.output_stem}.html"

    write_comparison_csv(csv_file, comparison_rows)
    write_comparison_html(
        html_file,
        comparison_rows,
        summary,
        arguments.baseline_label,
        arguments.candidate_label,
        arguments.baseline,
        arguments.candidate,
    )

    print("Model comparison complete")
    print(f"Common stations: {summary['common_station_count']}")
    print(f"Improved by MAE: {summary['improved_count']}")
    print(f"Regressed by MAE: {summary['regressed_count']}")
    print(f"{arguments.baseline_label} common MAE: {summary['baseline_common_mae']:.2f} F")
    print(f"{arguments.candidate_label} common MAE: {summary['candidate_common_mae']:.2f} F")
    print(f"CSV: {csv_file}")
    print(f"HTML: {html_file}")


if __name__ == "__main__":
    main()
