"""Build frontend-ready reliability surfaces and station overlays for a model run.

These artifacts power the reliability map modes served by the FastAPI backend."""

from __future__ import annotations

import argparse
from pathlib import Path

import config
from common.json_utils import write_json_file
from common.model_runs import resolve_model_run
from common.reliability_surface import (
    VARIABLE_LAYERS,
    build_grid_cells,
    build_helpfulness_surface_payload,
    build_overall_surface_payload,
    build_summary_payload,
    build_variable_surface_payload,
    build_station_extent_boundary_geojson,
    extract_polygon_rings,
    load_boundary_geojson,
    normalize_holdout_anchors,
    write_reliability_png,
)


DEFAULT_RELIABILITY_RUN_ID = "paloma_v1_reliability"
DEFAULT_VARIABLE_RUN_IDS = {
    "tavg": "paloma_v1_tavg",
    "tmin": "paloma_v1_tmin",
    "tmax": "paloma_v1_tmax",
}
DEFAULT_BOUNDARY_FILE = (
    config.PROJECT_DIR
    / "weather_reconstruction_model"
    / "inputs"
    / "colorado_river_basin_boundary.geojson"
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build Colorado River Basin model reliability surfaces from Paloma "
            "station holdout metrics and a basin GeoJSON mask."
        )
    )
    parser.add_argument("--model-run-root", type=Path, default=config.MODEL_RUN_DIR)
    parser.add_argument("--reliability-run-id", default=DEFAULT_RELIABILITY_RUN_ID)
    parser.add_argument("--tavg-run-id", default=DEFAULT_VARIABLE_RUN_IDS["tavg"])
    parser.add_argument("--tmin-run-id", default=DEFAULT_VARIABLE_RUN_IDS["tmin"])
    parser.add_argument("--tmax-run-id", default=DEFAULT_VARIABLE_RUN_IDS["tmax"])
    parser.add_argument("--boundary-file", type=Path, default=DEFAULT_BOUNDARY_FILE)
    parser.add_argument("--target-candidates", type=Path, default=config.TARGET_CANDIDATE_FILE)
    parser.add_argument("--hub-candidates", type=Path, default=config.HUB_CANDIDATE_FILE)
    parser.add_argument("--terrain-features", type=Path, default=config.TERRAIN_FEATURE_FILE)
    parser.add_argument("--boundary-padding-km", type=float, default=30.0)
    parser.add_argument(
        "--regenerate-boundary",
        action="store_true",
        help="Rebuild the station-extent rectangle GeoJSON even if --boundary-file exists.",
    )
    parser.add_argument("--spacing-km", type=float, default=25.0)
    parser.add_argument("--max-points", type=int, default=10000)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help=(
            "Build surfaces for variables with available station_metrics.csv files. "
            "The overall layer is written only when TAVG, TMIN, and TMAX are all present."
        ),
    )
    return parser.parse_args()


def require_file(file_path: Path, description: str) -> None:
    if not file_path.exists():
        raise FileNotFoundError(f"Missing {description}: {file_path}")


def load_or_build_boundary(arguments: argparse.Namespace) -> dict[str, object]:
    coordinate_files = [
        arguments.target_candidates,
        arguments.hub_candidates,
        arguments.terrain_features,
    ]

    if arguments.boundary_file.exists() and not arguments.regenerate_boundary:
        return load_boundary_geojson(arguments.boundary_file)

    boundary = build_station_extent_boundary_geojson(
        coordinate_files=coordinate_files,
        padding_km=arguments.boundary_padding_km,
    )
    write_json_file(arguments.boundary_file, boundary)
    return boundary


def main() -> None:
    arguments = parse_arguments()
    require_file(arguments.target_candidates, "target station candidate CSV")
    require_file(arguments.hub_candidates, "hub station candidate CSV")

    boundary_geojson = load_or_build_boundary(arguments)
    polygons = extract_polygon_rings(boundary_geojson)
    if not polygons:
        raise ValueError(f"Boundary file does not contain Polygon or MultiPolygon geometry: {arguments.boundary_file}")

    bounds, grid, cells = build_grid_cells(
        polygons=polygons,
        spacing_km=arguments.spacing_km,
        max_points=arguments.max_points,
    )
    output_dir = arguments.output_dir or (
        arguments.model_run_root / arguments.reliability_run_id
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    run_ids = {
        "tavg": arguments.tavg_run_id,
        "tmin": arguments.tmin_run_id,
        "tmax": arguments.tmax_run_id,
    }
    coordinate_files = [
        arguments.target_candidates,
        arguments.hub_candidates,
        arguments.terrain_features,
    ]
    surfaces = {}
    skipped_variables = []

    for variable in VARIABLE_LAYERS:
        source_paths = resolve_model_run(arguments.model_run_root, run_ids[variable])
        if not source_paths.station_metrics.exists():
            if arguments.allow_missing:
                skipped_variables.append(variable)
                continue
            require_file(source_paths.station_metrics, f"{variable.upper()} station holdout metrics")
        calibration_points_file = (
            source_paths.calibration_points
            if source_paths.calibration_points.exists()
            else None
        )
        anchors = normalize_holdout_anchors(
            station_metrics_file=source_paths.station_metrics,
            coordinate_files=coordinate_files,
            calibration_points_file=calibration_points_file,
            terrain_file=arguments.terrain_features,
        )
        image_file_name = f"reliability_surface_{variable}.png"
        payload, raster = build_variable_surface_payload(
            reliability_run_id=arguments.reliability_run_id,
            source_model_run_id=run_ids[variable],
            variable=variable,
            anchors=anchors,
            boundary_geojson=boundary_geojson,
            bounds=bounds,
            grid=grid,
            cells=cells,
            image_file_name=image_file_name,
        )
        write_json_file(output_dir / f"reliability_surface_{variable}.json", payload)
        write_reliability_png(output_dir / image_file_name, raster)
        surfaces[variable] = payload

    if not surfaces:
        missing_text = ", ".join(variable.upper() for variable in VARIABLE_LAYERS)
        raise FileNotFoundError(
            "No station holdout metrics were available to build reliability surfaces. "
            f"Missing: {missing_text}"
        )

    summary_surfaces = {}
    helpfulness_image_file_name = "reliability_surface_helpfulness.png"
    helpfulness_payload, helpfulness_raster = build_helpfulness_surface_payload(
        reliability_run_id=arguments.reliability_run_id,
        source_model_run_ids=run_ids,
        variable_payloads=surfaces,
        boundary_geojson=boundary_geojson,
        bounds=bounds,
        grid=grid,
        cells=cells,
        image_file_name=helpfulness_image_file_name,
    )
    write_json_file(output_dir / "reliability_surface_helpfulness.json", helpfulness_payload)
    write_reliability_png(output_dir / helpfulness_image_file_name, helpfulness_raster)
    summary_surfaces["helpfulness"] = helpfulness_payload

    if set(VARIABLE_LAYERS).issubset(surfaces):
        overall_image_file_name = "reliability_surface_overall.png"
        overall_payload, overall_raster = build_overall_surface_payload(
            reliability_run_id=arguments.reliability_run_id,
            source_model_run_ids=run_ids,
            variable_payloads=surfaces,
            boundary_geojson=boundary_geojson,
            bounds=bounds,
            grid=grid,
            cells=cells,
            image_file_name=overall_image_file_name,
        )
        write_json_file(output_dir / "reliability_surface_overall.json", overall_payload)
        write_reliability_png(output_dir / overall_image_file_name, overall_raster)
        summary_surfaces["overall"] = overall_payload
    summary_surfaces.update(surfaces)
    write_json_file(
        output_dir / "reliability_summary.json",
        build_summary_payload(arguments.reliability_run_id, summary_surfaces),
    )

    print(f"Reliability run: {output_dir}")
    print(f"Boundary: {arguments.boundary_file}")
    print(f"Grid: {grid['width']} x {grid['height']} with {grid['maskedPointCount']} masked points")
    print(f"Layers: {', '.join(summary_surfaces)}")
    if skipped_variables:
        print(f"Skipped missing variables: {', '.join(skipped_variables)}")


if __name__ == "__main__":
    main()
