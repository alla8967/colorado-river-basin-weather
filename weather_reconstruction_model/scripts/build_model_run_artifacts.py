from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Iterable

import config
from common.confidence_data import (
    ConfidenceSupportInputs,
    TerrainStationRecord,
    load_confidence_support_inputs,
)
from common.confidence_support import (
    ConfidenceSupportConfig,
    SupportPoint,
    SupportStation,
    calculate_confidence_support,
)
from common.csv_utils import (
    CsvRow,
    count_csv_rows,
    read_csv_fieldnames,
    read_csv_rows,
    write_csv_rows,
)
from common.geo_utils import calculate_distance_km
from common.json_utils import write_json_file
from common.model_artifacts import (
    build_feature_schema_payload,
    build_validation_model_run_manifest,
)
from common.model_runs import resolve_model_run
from common.number_utils import to_optional_float
from pipeline.model_features import resolve_model_feature_selection


MODEL_RUN_ID = (
    "option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain_"
    "offset_terrain_standard_random_forest"
)
TABLE_ID = "option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain"
MODEL_OUTPUT_SLUG = "offset_terrain_standard_random_forest"

DEFAULT_GENERAL_TABLE = config.GENERAL_TABLE_DIR / f"{TABLE_ID}.csv"
DEFAULT_STATION_METRICS = config.REPORT_DIR / f"{TABLE_ID}_{MODEL_OUTPUT_SLUG}_station_metrics.csv"
DEFAULT_VALIDATION_PREDICTIONS = config.PREDICTION_DIR / f"{TABLE_ID}_{MODEL_OUTPUT_SLUG}_predictions.csv"

CALIBRATION_FIELDNAMES = [
    "target_station_id",
    "target_name",
    "latitude",
    "longitude",
    "elevation_m",
    "observed_mae_f",
    "observed_rmse_f",
    "observed_correlation",
    "test_rows",
    "support_score",
    "support_label",
    "component_station_coverage",
    "component_hub_support",
    "component_data_quality",
    "component_elevation_match",
    "component_terrain_similarity",
    "component_terrain_complexity",
    "component_extrapolation_risk",
    "nearest_other_target_distance_km",
    "targets_within_50km",
    "targets_within_100km",
    "nearest_hub_distance_km",
    "hubs_within_100km",
    "hubs_within_200km",
    "nearest_validation_station_id",
    "nearest_validation_distance_km",
    "validation_stations_within_150km",
    "terrain_status",
    "dem_elevation_m",
    "slope_degrees",
    "local_relief_m",
    "local_relief_m_r990m",
    "local_relief_m_r3000m",
    "terrain_position_index_m",
]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export the current scattered model outputs into the standard "
            "model_runs/<model_run_id>/ artifact contract."
        )
    )
    parser.add_argument("--model-run-id", default=MODEL_RUN_ID)
    parser.add_argument("--output-root", type=Path, default=config.MODEL_RUN_DIR)
    parser.add_argument("--general-table", type=Path, default=DEFAULT_GENERAL_TABLE)
    parser.add_argument("--station-metrics", type=Path, default=DEFAULT_STATION_METRICS)
    parser.add_argument(
        "--validation-predictions",
        type=Path,
        default=DEFAULT_VALIDATION_PREDICTIONS,
    )
    parser.add_argument("--target-candidates", type=Path, default=config.TARGET_CANDIDATE_FILE)
    parser.add_argument("--hub-candidates", type=Path, default=config.HUB_CANDIDATE_FILE)
    parser.add_argument("--terrain-features", type=Path, default=config.TERRAIN_FEATURE_FILE)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite files in an existing model run folder.",
    )
    return parser.parse_args()


def require_input_files(paths: Iterable[Path]) -> None:
    missing = [path for path in paths if not path.exists()]
    if missing:
        missing_text = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"Missing required source file(s): {missing_text}")


def numeric_values(rows: list[CsvRow], column: str) -> list[float]:
    values = []
    for row in rows:
        value = to_optional_float(row.get(column))
        if value is not None:
            values.append(value)
    return values


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def sum_int_column(rows: list[CsvRow], column: str) -> int:
    total = 0
    for row in rows:
        value = row.get(column)
        if value is not None and str(value).strip():
            total += int(float(value))
    return total


def build_model_run_feature_schema(
    model_run_id: str,
    general_table: Path,
) -> dict[str, object]:
    fieldnames = read_csv_fieldnames(general_table)
    feature_selection = resolve_model_feature_selection(
        fieldnames,
        variable="tavg",
        include_terrain=True,
    )

    return build_feature_schema_payload(
        model_run_id=model_run_id,
        source_training_table=general_table,
        project_dir=config.PROJECT_DIR,
        target_column=feature_selection.label_column,
        prediction_output=feature_selection.prediction_output,
        prediction_transform=feature_selection.prediction_transform,
        hub_count=feature_selection.hub_count,
        target_neighbor_count=feature_selection.target_neighbor_count,
        feature_columns=feature_selection.feature_columns,
        variable="tavg",
    )


def station_lookup(inputs: ConfidenceSupportInputs) -> dict[str, SupportStation]:
    return {
        station.station_id: station
        for station in [*inputs.target_stations, *inputs.hub_stations]
    }


def distance_between_stations(station_a: SupportStation, station_b: SupportStation) -> float:
    return calculate_distance_km(
        station_a.latitude,
        station_a.longitude,
        station_b.latitude,
        station_b.longitude,
    )


def nearest_distance(
    station: SupportStation,
    stations: list[SupportStation],
    exclude_station_ids: set[str],
) -> float | None:
    distances = [
        distance_between_stations(station, candidate)
        for candidate in stations
        if candidate.station_id not in exclude_station_ids
    ]
    if not distances:
        return None
    return min(distances)


def count_within_radius(
    station: SupportStation,
    stations: list[SupportStation],
    radius_km: float,
    exclude_station_ids: set[str],
) -> int:
    return sum(
        1
        for candidate in stations
        if (
            candidate.station_id not in exclude_station_ids
            and distance_between_stations(station, candidate) <= radius_km
        )
    )


def nearest_validation_neighbor(
    station: SupportStation,
    validation_stations: list[SupportStation],
) -> tuple[str, float] | tuple[None, None]:
    neighbors = [
        (
            candidate.station_id,
            distance_between_stations(station, candidate),
        )
        for candidate in validation_stations
        if candidate.station_id != station.station_id
    ]
    if not neighbors:
        return None, None
    return min(neighbors, key=lambda item: item[1])


def fmt(value: object, decimals: int = 4) -> str:
    numeric_value = to_optional_float(value)
    if numeric_value is None:
        return ""
    return f"{numeric_value:.{decimals}f}"


def terrain_row_value(
    terrain_by_station_id: dict[str, TerrainStationRecord],
    station_id: str,
    field_name: str,
) -> str:
    terrain_record = terrain_by_station_id.get(station_id)
    if terrain_record is None:
        return ""
    return terrain_record.raw_row.get(field_name, "")


def build_calibration_points(
    model_run_id: str,
    station_metric_rows: list[CsvRow],
    inputs: ConfidenceSupportInputs,
) -> list[dict[str, object]]:
    station_by_id = station_lookup(inputs)
    validation_station_ids = {
        row["target_station_id"]
        for row in station_metric_rows
        if row.get("target_station_id")
    }
    validation_stations = [
        station
        for station_id in validation_station_ids
        if (station := station_by_id.get(station_id)) is not None
    ]
    config_for_support_features = ConfidenceSupportConfig(
        model_reference=model_run_id,
    )
    rows = []
    missing_station_ids = []

    for metric_row in station_metric_rows:
        station_id = metric_row["target_station_id"]
        station = station_by_id.get(station_id)
        if station is None:
            missing_station_ids.append(station_id)
            continue

        support_result = calculate_confidence_support(
            SupportPoint(
                latitude=station.latitude,
                longitude=station.longitude,
                elevation_m=station.elevation_m,
                terrain=station.terrain,
            ),
            target_stations=inputs.target_stations,
            hub_stations=inputs.hub_stations,
            validation_by_station_id={},
            config=config_for_support_features,
        )
        support = support_result.as_dict()
        components = support["components"]
        nearest_validation_id, nearest_validation_distance = nearest_validation_neighbor(
            station,
            validation_stations,
        )

        rows.append({
            "target_station_id": station_id,
            "target_name": metric_row.get("target_name", station.station_name),
            "latitude": fmt(station.latitude, 6),
            "longitude": fmt(station.longitude, 6),
            "elevation_m": fmt(station.elevation_m, 2),
            "observed_mae_f": fmt(metric_row.get("mae"), 4),
            "observed_rmse_f": fmt(metric_row.get("rmse"), 4),
            "observed_correlation": fmt(metric_row.get("correlation"), 6),
            "test_rows": metric_row.get("test_rows", ""),
            "support_score": fmt(support["score"], 2),
            "support_label": support["label"],
            "component_station_coverage": fmt(components.get("stationCoverage"), 2),
            "component_hub_support": fmt(components.get("hubSupport"), 2),
            "component_data_quality": fmt(components.get("dataQuality"), 2),
            "component_elevation_match": fmt(components.get("elevationMatch"), 2),
            "component_terrain_similarity": fmt(components.get("terrainSimilarity"), 2),
            "component_terrain_complexity": fmt(components.get("terrainComplexity"), 2),
            "component_extrapolation_risk": fmt(components.get("extrapolationRisk"), 2),
            "nearest_other_target_distance_km": fmt(
                nearest_distance(station, inputs.target_stations, {station_id}),
                3,
            ),
            "targets_within_50km": count_within_radius(
                station,
                inputs.target_stations,
                50.0,
                {station_id},
            ),
            "targets_within_100km": count_within_radius(
                station,
                inputs.target_stations,
                100.0,
                {station_id},
            ),
            "nearest_hub_distance_km": fmt(
                nearest_distance(station, inputs.hub_stations, set()),
                3,
            ),
            "hubs_within_100km": count_within_radius(
                station,
                inputs.hub_stations,
                100.0,
                set(),
            ),
            "hubs_within_200km": count_within_radius(
                station,
                inputs.hub_stations,
                200.0,
                set(),
            ),
            "nearest_validation_station_id": nearest_validation_id or "",
            "nearest_validation_distance_km": fmt(nearest_validation_distance, 3),
            "validation_stations_within_150km": count_within_radius(
                station,
                validation_stations,
                150.0,
                {station_id},
            ),
            "terrain_status": terrain_row_value(
                inputs.terrain_by_station_id,
                station_id,
                "terrain_status",
            ),
            "dem_elevation_m": terrain_row_value(
                inputs.terrain_by_station_id,
                station_id,
                "dem_elevation_m",
            ),
            "slope_degrees": terrain_row_value(
                inputs.terrain_by_station_id,
                station_id,
                "slope_degrees",
            ),
            "local_relief_m": terrain_row_value(
                inputs.terrain_by_station_id,
                station_id,
                "local_relief_m",
            ),
            "local_relief_m_r990m": terrain_row_value(
                inputs.terrain_by_station_id,
                station_id,
                "local_relief_m_r990m",
            ),
            "local_relief_m_r3000m": terrain_row_value(
                inputs.terrain_by_station_id,
                station_id,
                "local_relief_m_r3000m",
            ),
            "terrain_position_index_m": terrain_row_value(
                inputs.terrain_by_station_id,
                station_id,
                "terrain_position_index_m",
            ),
        })

    if missing_station_ids:
        missing_text = ", ".join(sorted(missing_station_ids))
        raise ValueError(
            "Could not find station metadata for calibration station(s): "
            f"{missing_text}"
        )

    rows.sort(key=lambda row: row["target_station_id"])
    return rows


def write_pending_confidence_grid(model_run_id: str, file_path: Path) -> None:
    write_json_file(
        file_path,
        {
            "modelRunId": model_run_id,
            "scoreVersion": "calibrated-confidence-pending",
            "status": "pending",
            "calibrationStatus": "not_calibrated",
            "points": [],
            "notes": [
                "This placeholder keeps the model-run artifact shape complete.",
                "Build calibrated grid points after choosing the v1 calibration method.",
            ],
        },
    )


def prepare_output_folder(model_run_root: Path, overwrite: bool) -> None:
    if model_run_root.exists() and any(model_run_root.iterdir()) and not overwrite:
        raise FileExistsError(
            f"Model run folder already exists: {model_run_root}. "
            "Use --overwrite to replace generated artifact files."
        )
    model_run_root.mkdir(parents=True, exist_ok=True)


def copy_source_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def build_manifest(
    model_run_id: str,
    general_table: Path,
    station_metrics: Path,
    validation_predictions: Path,
    station_metric_rows: list[CsvRow],
    validation_prediction_rows: int,
) -> dict[str, object]:
    maes = numeric_values(station_metric_rows, "mae")
    rmses = numeric_values(station_metric_rows, "rmse")
    correlations = numeric_values(station_metric_rows, "correlation")

    return build_validation_model_run_manifest(
        model_run_id=model_run_id,
        model_variant=MODEL_OUTPUT_SLUG,
        training_table=general_table,
        station_metrics=station_metrics,
        validation_predictions=validation_predictions,
        project_dir=config.PROJECT_DIR,
        summary_metrics={
            "validationStationCount": len(station_metric_rows),
            "testRows": sum_int_column(station_metric_rows, "test_rows"),
            "validationPredictionRows": validation_prediction_rows,
            "meanMaeF": round(mean(maes) or 0.0, 4),
            "meanRmseF": round(mean(rmses) or 0.0, 4),
            "meanCorrelation": round(mean(correlations) or 0.0, 6),
        },
    )


def main() -> None:
    arguments = parse_arguments()
    require_input_files([
        arguments.general_table,
        arguments.station_metrics,
        arguments.validation_predictions,
        arguments.target_candidates,
        arguments.hub_candidates,
    ])

    paths = resolve_model_run(arguments.output_root, arguments.model_run_id)
    prepare_output_folder(paths.root, arguments.overwrite)

    station_metric_rows = read_csv_rows(arguments.station_metrics)
    validation_prediction_rows = count_csv_rows(arguments.validation_predictions)
    inputs = load_confidence_support_inputs(
        target_candidate_file=arguments.target_candidates,
        hub_candidate_file=arguments.hub_candidates,
        terrain_file=arguments.terrain_features,
        validation_metrics_file=arguments.station_metrics,
        model_reference=arguments.model_run_id,
    )
    calibration_rows = build_calibration_points(
        arguments.model_run_id,
        station_metric_rows,
        inputs,
    )

    copy_source_file(arguments.station_metrics, paths.station_metrics)
    copy_source_file(arguments.validation_predictions, paths.validation_predictions)
    write_csv_rows(paths.calibration_points, calibration_rows, CALIBRATION_FIELDNAMES)
    write_json_file(
        paths.feature_schema,
        build_model_run_feature_schema(arguments.model_run_id, arguments.general_table),
    )
    write_json_file(
        paths.manifest,
        build_manifest(
            arguments.model_run_id,
            arguments.general_table,
            arguments.station_metrics,
            arguments.validation_predictions,
            station_metric_rows,
            validation_prediction_rows,
        ),
    )
    write_pending_confidence_grid(arguments.model_run_id, paths.confidence_grid)

    print(f"Model run exported: {paths.root}")
    print(f"Validation stations: {len(station_metric_rows)}")
    print(f"Validation prediction rows: {validation_prediction_rows}")
    print(f"Calibration points: {len(calibration_rows)}")
    print(
        "Feature schema inputs: "
        f"{build_model_run_feature_schema(arguments.model_run_id, arguments.general_table)['featureCount']}"
    )


if __name__ == "__main__":
    main()
