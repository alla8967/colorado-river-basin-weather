from __future__ import annotations

import argparse
from pathlib import Path
from typing import Mapping

import config
from common.csv_utils import read_csv_rows, write_csv_rows
from common.json_utils import write_json_file
from common.model_runs import resolve_model_run
from common.reliability_surface import (
    CORRELATION_FIELDS,
    MAE_FIELDS,
    RMSE_FIELDS,
    STATION_ID_FIELDS,
    STATION_NAME_FIELDS,
    TEST_ROWS_FIELDS,
    VARIABLE_LAYERS,
    build_station_extent_boundary_geojson,
    first_present,
    first_present_float,
    first_present_int,
)


DEFAULT_BOUNDARY_FILE = (
    config.PROJECT_DIR
    / "weather_reconstruction_model"
    / "inputs"
    / "colorado_river_basin_boundary.geojson"
)
DEFAULT_ARTIFACT_ROOTS = [
    config.MODEL_RUN_DIR,
    config.OUTPUT_DIR,
    config.PROJECT_DIR / "ml_reconstruction" / "weather_reconstruction_artifacts",
]
STATION_METRICS_FIELDNAMES = [
    "target_station_id",
    "target_name",
    "test_rows",
    "mae",
    "rmse",
    "correlation",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare the restored repo to build Paloma v1 reliability surfaces. "
            "This can generate the station-extent boundary and normalize explicit "
            "Alpine station-holdout metric CSVs into model_runs/paloma_v1_<variable>."
        )
    )
    parser.add_argument("--model-run-root", type=Path, default=config.MODEL_RUN_DIR)
    parser.add_argument("--boundary-file", type=Path, default=DEFAULT_BOUNDARY_FILE)
    parser.add_argument("--boundary-padding-km", type=float, default=30.0)
    parser.add_argument("--target-candidates", type=Path, default=config.TARGET_CANDIDATE_FILE)
    parser.add_argument("--hub-candidates", type=Path, default=config.HUB_CANDIDATE_FILE)
    parser.add_argument("--terrain-features", type=Path, default=config.TERRAIN_FEATURE_FILE)
    parser.add_argument("--tavg-metrics", type=Path, default=None)
    parser.add_argument("--tmin-metrics", type=Path, default=None)
    parser.add_argument("--tmax-metrics", type=Path, default=None)
    parser.add_argument(
        "--artifact-root",
        action="append",
        type=Path,
        default=[],
        help="Additional folder to scan for candidate Alpine metrics CSVs.",
    )
    parser.add_argument(
        "--copy-discovered",
        action="store_true",
        help="Copy an unambiguous discovered metrics CSV when no explicit path is provided.",
    )
    parser.add_argument(
        "--skip-scan",
        action="store_true",
        help="Do not scan artifact roots for candidate metrics files.",
    )
    parser.add_argument(
        "--report-file",
        type=Path,
        default=config.OUTPUT_DIR / "reports" / "paloma_reliability_input_readiness.json",
    )
    return parser.parse_args()


def explicit_metric_paths(args: argparse.Namespace) -> dict[str, Path | None]:
    return {
        "tavg": args.tavg_metrics,
        "tmin": args.tmin_metrics,
        "tmax": args.tmax_metrics,
    }


def candidate_files(roots: list[Path]) -> list[Path]:
    patterns = [
        "*station_metrics.csv",
        "*holdout*.csv",
    ]
    files = []
    for root in roots:
        if not root.exists():
            continue
        for pattern in patterns:
            files.extend(root.rglob(pattern))
    return sorted(set(files))


def infer_variable_from_path(path: Path) -> str | None:
    name = path.name.lower()
    for variable in VARIABLE_LAYERS:
        if variable in name:
            return variable
    return None


def infer_variable_from_rows(path: Path, max_rows: int = 25) -> str | None:
    try:
        rows = read_csv_rows(path)
    except UnicodeDecodeError:
        return None

    variables = {
        str(row.get("variable") or row.get("temperature_variable") or "").strip().lower()
        for row in rows[:max_rows]
    }
    variables.discard("")
    matched = variables & set(VARIABLE_LAYERS)
    if len(matched) == 1:
        return next(iter(matched))
    return None


def canonical_metric_rows(path: Path, variable: str | None = None) -> list[dict[str, object]]:
    rows = []
    for row in read_csv_rows(path):
        row_variable = str(row.get("variable") or row.get("temperature_variable") or "").strip().lower()
        if variable is not None and row_variable in VARIABLE_LAYERS and row_variable != variable:
            continue

        station_id = first_present(row, STATION_ID_FIELDS)
        mae = first_present_float(row, MAE_FIELDS)
        if station_id is None or mae is None:
            continue

        rows.append({
            "target_station_id": station_id,
            "target_name": first_present(row, STATION_NAME_FIELDS) or station_id,
            "test_rows": first_present_int(row, TEST_ROWS_FIELDS) or "",
            "mae": round(mae, 6),
            "rmse": optional_round(first_present_float(row, RMSE_FIELDS), 6),
            "correlation": optional_round(first_present_float(row, CORRELATION_FIELDS), 8),
        })

    return rows


def optional_round(value: float | None, digits: int) -> float | str:
    if value is None:
        return ""
    return round(value, digits)


def summarize_candidate(path: Path) -> dict[str, object]:
    inferred_variable = infer_variable_from_path(path) or infer_variable_from_rows(path)
    try:
        canonical_rows = canonical_metric_rows(path, inferred_variable)
    except UnicodeDecodeError:
        canonical_rows = []

    return {
        "path": str(path),
        "inferredVariable": inferred_variable,
        "usableMetricRows": len(canonical_rows),
    }


def write_station_metrics(model_run_root: Path, variable: str, source_file: Path) -> dict[str, object]:
    rows = canonical_metric_rows(source_file, variable)
    if not rows:
        raise ValueError(f"No usable {variable.upper()} station metric rows in {source_file}.")

    paths = resolve_model_run(model_run_root, f"paloma_v1_{variable}")
    write_csv_rows(paths.station_metrics, rows, STATION_METRICS_FIELDNAMES)
    return {
        "status": "prepared",
        "modelRunId": paths.model_run_id,
        "stationMetrics": str(paths.station_metrics),
        "sourceFile": str(source_file),
        "rowCount": len(rows),
    }


def resolve_metric_sources(
    args: argparse.Namespace,
    candidates: list[Mapping[str, object]],
) -> dict[str, Path | None]:
    explicit_paths = explicit_metric_paths(args)
    resolved = dict(explicit_paths)
    if not args.copy_discovered:
        return resolved

    for variable in VARIABLE_LAYERS:
        if resolved[variable] is not None:
            continue

        matches = [
            Path(str(candidate["path"]))
            for candidate in candidates
            if candidate.get("inferredVariable") == variable
            and int(candidate.get("usableMetricRows") or 0) > 0
        ]
        if len(matches) == 1:
            resolved[variable] = matches[0]

    return resolved


def build_boundary(args: argparse.Namespace) -> dict[str, object]:
    boundary = build_station_extent_boundary_geojson(
        coordinate_files=[
            args.target_candidates,
            args.hub_candidates,
            args.terrain_features,
        ],
        padding_km=args.boundary_padding_km,
    )
    write_json_file(args.boundary_file, boundary)
    return {
        "status": "prepared",
        "boundaryFile": str(args.boundary_file),
        "stationCount": boundary["properties"]["stationCount"],
        "paddingKm": boundary["properties"]["paddingKm"],
        "paddedBounds": boundary["properties"]["paddedBounds"],
    }


def build_report(args: argparse.Namespace) -> dict[str, object]:
    roots = [
        *DEFAULT_ARTIFACT_ROOTS,
        *args.artifact_root,
    ]
    candidates = [] if args.skip_scan else [
        summarize_candidate(path)
        for path in candidate_files(roots)
    ]
    sources = resolve_metric_sources(args, candidates)
    variables: dict[str, object] = {}

    for variable in VARIABLE_LAYERS:
        source = sources[variable]
        if source is None:
            matching_candidates = [
                candidate
                for candidate in candidates
                if candidate.get("inferredVariable") == variable
            ]
            variables[variable] = {
                "status": "missing",
                "expectedModelRunId": f"paloma_v1_{variable}",
                "candidateFiles": matching_candidates,
            }
            continue

        variables[variable] = write_station_metrics(args.model_run_root, variable, source)

    missing = [
        variable
        for variable, result in variables.items()
        if isinstance(result, Mapping) and result.get("status") == "missing"
    ]
    return {
        "status": "ready" if not missing else "missing_inputs",
        "boundary": build_boundary(args),
        "variables": variables,
        "missingVariables": missing,
        "candidateMetricFiles": candidates,
        "nextBuildCommand": (
            "python3 weather_reconstruction_model/scripts/build_reliability_surfaces.py"
        ),
    }


def main() -> None:
    args = parse_args()
    report = build_report(args)
    write_json_file(args.report_file, report)
    print(f"Readiness report: {args.report_file}")
    print(f"Boundary: {report['boundary']['boundaryFile']}")

    for variable in VARIABLE_LAYERS:
        variable_report = report["variables"][variable]
        print(f"{variable.upper()}: {variable_report['status']}")

    if report["missingVariables"]:
        missing_text = ", ".join(variable.upper() for variable in report["missingVariables"])
        print(f"Missing metric inputs: {missing_text}")
    else:
        print(report["nextBuildCommand"])


if __name__ == "__main__":
    main()
