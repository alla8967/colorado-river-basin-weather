#!/usr/bin/env python3
"""Build a compact run-history table from an Alpine results snapshot."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path


FIELDS = [
    "RUN_ID",
    "JOB_ID",
    "RUN_DATE",
    "VARIABLE",
    "PRESET",
    "PAIRWISE_ENABLED",
    "TARGET_LIMIT",
    "INCLUDED_TARGETS",
    "TEST_TARGET_STATIONS",
    "ROWS_TOTAL",
    "TRAIN_ROWS",
    "TEST_ROWS",
    "HUB_COUNT",
    "TARGET_NEIGHBOR_COUNT",
    "FEATURE_COUNT",
    "MODEL_FAMILY",
    "MODEL_PRESET",
    "TRAIN_MAE",
    "TRAIN_RMSE",
    "TRAIN_R",
    "TEST_MAE",
    "TEST_RMSE",
    "TEST_R",
    "STRICT_PASSES",
    "STRICT_TOTAL",
    "STRICT_PASS_RATE",
    "ELAPSED_SECONDS",
    "GENERAL_TABLE_FILE",
    "PREDICTIONS_FILE",
    "STATION_METRICS_FILE",
    "LOG_FILE",
    "INTERPRETATION",
]


KNOWN_INTERPRETATIONS = {
    "smoke": "Systems check only; not meaningful model evidence.",
    "medium": "Medium TAVG time holdout is the main pairwise/no-pairwise comparison point.",
    "wide-medium": "Wider predictor set did not improve TAVG headline accuracy.",
}


def first_match(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return ""


def parse_random_forest_row(text: str) -> dict[str, str]:
    row = {}
    match = re.search(
        r"^Random Forest\s+"
        r"([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+"
        r"([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if match:
        row["TRAIN_MAE"], row["TRAIN_RMSE"], row["TRAIN_R"] = match.group(1), match.group(2), match.group(3)
        row["TEST_MAE"], row["TEST_RMSE"], row["TEST_R"] = match.group(4), match.group(5), match.group(6)
    return row


def parse_log(path: Path, snapshot: Path) -> dict[str, str]:
    text = path.read_text(errors="replace")
    row = {field: "" for field in FIELDS}
    row["LOG_FILE"] = str(path.relative_to(snapshot))
    row["JOB_ID"] = first_match(path.name, [r"\.(\d+)\.(?:out|err)$", r"(\d{6,})"])
    row["RUN_ID"] = path.stem
    if row["JOB_ID"]:
        row["RUN_ID"] = re.sub(rf"\.?{re.escape(row['JOB_ID'])}$", "", row["RUN_ID"])

    row["RUN_DATE"] = first_match(text, [r"Run date:\s*(.+)", r"Started(?: at)?:\s*(.+)"])
    row["VARIABLE"] = first_match(text, [r"Temperature variable:\s*([A-Za-z0-9_]+)", r"Variable:\s*([A-Za-z0-9_]+)"])
    row["PRESET"] = first_match(text, [r"Preset:\s*([A-Za-z0-9_-]+)"])
    row["ROWS_TOTAL"] = first_match(text, [r"Rows:\s*([0-9,]+)"])
    row["TRAIN_ROWS"] = first_match(text, [r"Training rows:\s*([0-9,]+)"])
    row["TEST_ROWS"] = first_match(text, [r"Testing rows:\s*([0-9,]+)"])
    row["INCLUDED_TARGETS"] = first_match(text, [r"Included targets:\s*([0-9,]+)", r"([0-9,]+)\s+included targets"])
    row["TEST_TARGET_STATIONS"] = first_match(text, [r"Testing target stations:\s*([0-9,]+)", r"([0-9,]+)\s+testing target stations"])
    row["HUB_COUNT"] = first_match(text, [r"Hubs per target:\s*([0-9,]+)"])
    row["TARGET_NEIGHBOR_COUNT"] = first_match(text, [r"Target-neighbor stations per target:\s*([0-9,]+)"])
    row["FEATURE_COUNT"] = first_match(text, [r"Feature inputs:\s*([0-9,]+)"])
    row["MODEL_FAMILY"] = "random_forest"
    row["MODEL_PRESET"] = first_match(text, [r"Model preset:\s*([A-Za-z0-9_-]+)"])
    row["PAIRWISE_ENABLED"] = "false" if re.search(r"pairwise (?:disabled|selection no|no-pairwise)", text, re.I) else ""
    if re.search(r"pairwise", text, re.I) and row["PAIRWISE_ENABLED"] != "false":
        row["PAIRWISE_ENABLED"] = "true"

    row.update(parse_random_forest_row(text))

    strict = re.search(r"Strict passes:\s*([0-9,]+)\s*/\s*([0-9,]+)", text, re.I)
    if strict:
        row["STRICT_PASSES"] = strict.group(1).replace(",", "")
        row["STRICT_TOTAL"] = strict.group(2).replace(",", "")
        try:
            row["STRICT_PASS_RATE"] = f"{100 * int(row['STRICT_PASSES']) / int(row['STRICT_TOTAL']):.1f}%"
        except ZeroDivisionError:
            row["STRICT_PASS_RATE"] = ""
    row["ELAPSED_SECONDS"] = first_match(text, [r"Elapsed time:\s*([0-9.]+)\s*seconds"])

    row["GENERAL_TABLE_FILE"] = first_match(text, [r"General training table:\s*(.+\.csv)"])
    row["PREDICTIONS_FILE"] = first_match(text, [r"Random Forest predictions:\s*(.+\.csv)"])
    row["STATION_METRICS_FILE"] = first_match(text, [r"Random Forest station report:\s*(.+\.csv)"])

    lower_name = path.name.lower()
    if "tmin" in lower_name:
        row["VARIABLE"] = row["VARIABLE"] or "tmin"
        row["INTERPRETATION"] = "TMIN is materially harder, likely reflecting nighttime terrain and siting effects."
    elif "tmax" in lower_name:
        row["VARIABLE"] = row["VARIABLE"] or "tmax"
        row["INTERPRETATION"] = "TMAX is easier than TMIN but worse than direct TAVG."
    elif "nopair" in lower_name or "no_pairwise" in lower_name:
        row["INTERPRETATION"] = "No-pairwise ablation is a key comparison against pairwise selection."
    else:
        row["INTERPRETATION"] = KNOWN_INTERPRETATIONS.get(row["PRESET"], "")

    return row


def write_markdown(rows: list[dict[str, str]], path: Path) -> None:
    columns = ["RUN_ID", "JOB_ID", "VARIABLE", "PRESET", "PAIRWISE_ENABLED", "TEST_MAE", "TEST_RMSE", "TEST_R", "STRICT_PASS_RATE", "INTERPRETATION"]
    lines = [
        "# Alpine Run Summary",
        "",
        "These rows are parsed from recovered Alpine logs. Treat time-holdout runs as model-development evidence, not station-holdout proof.",
        "",
        "|" + "|".join(columns) + "|",
        "|" + "|".join(["---"] * len(columns)) + "|",
    ]
    for row in rows:
        lines.append("|" + "|".join(row.get(column, "").replace("|", "\\|") for column in columns) + "|")
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: build_alpine_run_summary.py SNAPSHOT_DIR", file=sys.stderr)
        return 2
    snapshot = Path(argv[1]).resolve()
    if not snapshot.exists():
        print(f"Snapshot directory does not exist: {snapshot}", file=sys.stderr)
        return 1

    log_paths = sorted(snapshot.glob("logs/*.out")) + sorted(snapshot.glob("**/*.out"))
    seen = set()
    rows = []
    for path in log_paths:
        if path in seen:
            continue
        seen.add(path)
        rows.append(parse_log(path, snapshot))

    csv_path = snapshot / "RUN_SUMMARY.csv"
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    write_markdown(rows, snapshot / "RUN_SUMMARY.md")
    print(f"Wrote {len(rows)} rows to {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
