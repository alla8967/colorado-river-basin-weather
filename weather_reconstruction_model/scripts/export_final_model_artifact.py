"""Train/export a final model artifact and write its manifest metadata.

This packages the production-style model state used by downstream reports and frontend summaries."""

from __future__ import annotations

import argparse
import csv
import math
from datetime import date
from pathlib import Path
from time import perf_counter

import config
from common.csv_utils import read_csv_fieldnames, read_csv_rows
from common.json_utils import write_json_file
from common.model_artifacts import (
    ChunkedRandomForestRegressor,
    build_feature_schema_payload,
    build_serialized_model_artifact_manifest,
    merge_serialized_model_run_manifest,
    project_relative_path,
)
from common.model_runs import load_json_file, resolve_model_run
from common.number_utils import to_float
from common.weather_cache import TEMPERATURE_VARIABLES, validate_temperature_variable
from pipeline.model_features import (
    require_feature_columns,
    require_training_columns,
    resolve_model_feature_selection,
)
from pipeline.training_data import (
    build_unscaled_features_and_labels,
)


DEFAULT_MODEL_RUN_ID = (
    "option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain_"
    "offset_terrain_standard_random_forest"
)
DEFAULT_GENERAL_TABLE = (
    config.GENERAL_TABLE_DIR
    / "option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain.csv"
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train the current best tree model on all rows in a completed general "
            "training table and export a serialized production model artifact."
        )
    )
    parser.add_argument("--model-run-id", default=DEFAULT_MODEL_RUN_ID)
    parser.add_argument("--model-run-root", type=Path, default=config.MODEL_RUN_DIR)
    parser.add_argument("--general-table", type=Path, default=DEFAULT_GENERAL_TABLE)
    parser.add_argument("--output-model", type=Path, default=None)
    parser.add_argument("--output-manifest", type=Path, default=None)
    parser.add_argument(
        "--variable",
        choices=sorted(TEMPERATURE_VARIABLES),
        default="tavg",
        help="Daily temperature variable to train and serialize.",
    )
    parser.add_argument("--forest-trees", type=int, default=200)
    parser.add_argument("--max-depth", type=int, default=18)
    parser.add_argument("--min-samples-leaf", type=int, default=5)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--jobs", type=int, default=-1)
    parser.add_argument("--exclude-terrain", action="store_true")
    parser.add_argument(
        "--training-strategy",
        choices=["chunked-forest", "full-forest"],
        default="chunked-forest",
        help=(
            "chunked-forest streams large Paloma tables and trains a weighted "
            "forest ensemble over row chunks; full-forest loads all rows at once."
        ),
    )
    parser.add_argument(
        "--chunk-rows",
        type=int,
        default=100000,
        help="Rows per chunk when --training-strategy=chunked-forest.",
    )
    parser.add_argument(
        "--keep-empty-feature-columns",
        action="store_true",
        help="Deprecated compatibility flag. Empty columns are kept unless --drop-empty-feature-columns is passed.",
    )
    parser.add_argument(
        "--drop-empty-feature-columns",
        action="store_true",
        help="Scan all feature values and drop columns that are blank across the table.",
    )
    parser.add_argument(
        "--exclude-pairwise-features",
        action="store_true",
        help="Drop pairwise skill feature columns from no-pairwise Paloma exports.",
    )
    return parser.parse_args()


def import_training_dependencies():
    try:
        import joblib
        import numpy as np
        from sklearn.ensemble import RandomForestRegressor
    except ModuleNotFoundError as error:
        raise SystemExit(
            "numpy, scikit-learn, and joblib are required to export the final model. "
            "Use the project .venv or install those packages."
        ) from error

    return joblib, np, RandomForestRegressor


def scan_table(
    table_path: Path,
    feature_columns: list[str],
    collect_nonempty_features: bool = False,
) -> dict[str, object]:
    row_count = 0
    target_station_ids: set[str] = set()
    nonempty_feature_columns: set[str] = set()

    with table_path.open("r", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            row_count += 1
            target_station_ids.add(row["target_station_id"])

            if collect_nonempty_features:
                for column in feature_columns:
                    value = row.get(column, "")
                    if value not in ("", None):
                        nonempty_feature_columns.add(column)

    return {
        "rowCount": row_count,
        "targetStationCount": len(target_station_ids),
        "nonemptyFeatureColumns": nonempty_feature_columns,
    }


def chunk_estimator_counts(total_estimators: int, chunk_count: int) -> list[int]:
    if chunk_count <= 0:
        raise ValueError("Cannot train chunked forest with no chunks.")

    base_count = total_estimators // chunk_count
    remainder = total_estimators % chunk_count

    if base_count == 0:
        return [
            1 if index < total_estimators else 0
            for index in range(chunk_count)
        ]

    return [
        base_count + (1 if index < remainder else 0)
        for index in range(chunk_count)
    ]


def fill_feature_row(feature_matrix, row_index: int, row: dict[str, str], feature_columns: list[str]) -> None:
    for column_index, column in enumerate(feature_columns):
        feature_matrix[row_index, column_index] = to_float(row.get(column, ""))


def train_chunked_forest(
    table_path: Path,
    np,
    RandomForestRegressor,
    feature_columns: list[str],
    label_column: str,
    forest_trees: int,
    chunk_rows: int,
    max_depth: int,
    min_samples_leaf: int,
    random_state: int,
    jobs: int,
    row_count: int,
):
    if chunk_rows <= 0:
        raise ValueError("--chunk-rows must be positive.")
    if forest_trees <= 0:
        raise ValueError("--forest-trees must be positive.")

    chunk_count = math.ceil(row_count / chunk_rows)
    if chunk_count > forest_trees:
        raise ValueError(
            "Chunked forest needs at least one tree per chunk. Increase "
            "--forest-trees or --chunk-rows."
        )
    estimator_counts = chunk_estimator_counts(forest_trees, chunk_count)
    models = []
    training_row_counts = []
    current_chunk = 0

    with table_path.open("r", newline="") as file:
        reader = csv.DictReader(file)
        features = np.empty((chunk_rows, len(feature_columns)), dtype=np.float32)
        labels = np.empty(chunk_rows, dtype=np.float32)
        chunk_row_count = 0

        def train_current_chunk() -> None:
            nonlocal current_chunk, features, labels, chunk_row_count

            if chunk_row_count == 0:
                return

            estimator_count = estimator_counts[current_chunk]
            if estimator_count <= 0:
                current_chunk += 1
                chunk_row_count = 0
                return

            chunk_features = features[:chunk_row_count]
            chunk_labels = labels[:chunk_row_count]
            model = RandomForestRegressor(
                n_estimators=estimator_count,
                max_depth=max_depth,
                min_samples_leaf=min_samples_leaf,
                random_state=random_state + current_chunk,
                n_jobs=jobs,
            )
            print(
                f"Training chunk {current_chunk + 1}/{chunk_count}: "
                f"{chunk_row_count} rows, {estimator_count} trees",
                flush=True,
            )
            model.fit(chunk_features, chunk_labels)
            models.append(model)
            training_row_counts.append(chunk_row_count)
            current_chunk += 1
            chunk_row_count = 0

        for row in reader:
            fill_feature_row(features, chunk_row_count, row, feature_columns)
            labels[chunk_row_count] = to_float(row[label_column])
            chunk_row_count += 1

            if chunk_row_count == chunk_rows:
                train_current_chunk()

        train_current_chunk()

    return ChunkedRandomForestRegressor(
        models=models,
        estimator_counts=[
            count
            for count in estimator_counts
            if count > 0
        ],
        training_row_counts=training_row_counts,
    )


def main() -> None:
    started_at = perf_counter()
    arguments = parse_arguments()
    variable = validate_temperature_variable(arguments.variable)
    joblib, np, RandomForestRegressor = import_training_dependencies()
    paths = resolve_model_run(arguments.model_run_root, arguments.model_run_id)
    output_model = arguments.output_model or paths.root / "model.joblib"
    output_manifest = arguments.output_manifest or paths.root / "model_artifact_manifest.json"

    fieldnames = read_csv_fieldnames(arguments.general_table)
    feature_selection = resolve_model_feature_selection(
        fieldnames,
        variable=variable,
        include_terrain=not arguments.exclude_terrain,
        exclude_pairwise_features=arguments.exclude_pairwise_features,
    )
    require_training_columns(
        fieldnames,
        feature_selection,
        "Final offset model export requires missing columns",
    )
    feature_columns = list(feature_selection.feature_columns)

    print("Scanning table metadata...")
    table_scan = scan_table(
        arguments.general_table,
        feature_columns,
        collect_nonempty_features=arguments.drop_empty_feature_columns,
    )
    row_count = int(table_scan["rowCount"])
    if row_count <= 0:
        raise ValueError(f"Training table is empty: {arguments.general_table}")
    target_station_count = int(table_scan["targetStationCount"])

    if arguments.drop_empty_feature_columns:
        feature_selection = feature_selection.with_feature_columns(
            column
            for column in feature_columns
            if column in table_scan["nonemptyFeatureColumns"]
        )
        feature_columns = list(feature_selection.feature_columns)

    require_feature_columns(feature_selection)

    print("Final Model Artifact Export")
    print("===========================")
    print(f"Model run: {arguments.model_run_id}")
    print(f"Training table: {arguments.general_table}")
    print(f"Temperature variable: {variable}")
    print(f"Rows: {row_count}")
    print(f"Target stations: {target_station_count}")
    print(f"Feature inputs: {len(feature_columns)}")
    print(f"Training strategy: {arguments.training_strategy}")
    print(f"Output model: {output_model}")

    if arguments.training_strategy == "full-forest":
        print("Loading full table into memory...")
        rows = read_csv_rows(arguments.general_table)
        features, labels = build_unscaled_features_and_labels(
            rows,
            feature_columns,
            label_column=feature_selection.label_column,
        )
        model = RandomForestRegressor(
            n_estimators=arguments.forest_trees,
            max_depth=arguments.max_depth,
            min_samples_leaf=arguments.min_samples_leaf,
            random_state=arguments.random_state,
            n_jobs=arguments.jobs,
        )
        print("Training RandomForestRegressor on all rows...")
        model.fit(features, labels)
        chunk_count = 1
        chunk_rows = row_count
    else:
        print("Training chunked RandomForestRegressor ensemble on all rows...")
        model = train_chunked_forest(
            arguments.general_table,
            np,
            RandomForestRegressor,
            feature_columns,
            feature_selection.label_column,
            arguments.forest_trees,
            arguments.chunk_rows,
            arguments.max_depth,
            arguments.min_samples_leaf,
            arguments.random_state,
            arguments.jobs,
            row_count,
        )
        chunk_count = len(model.models)
        chunk_rows = arguments.chunk_rows

    artifact = {
        "model": model,
        "modelRunId": arguments.model_run_id,
        "modelFamily": "random_forest",
        "variable": variable,
        "predictionTarget": feature_selection.prediction_output,
        "predictionMode": "offset_from_regional_baseline",
        "predictionTransform": feature_selection.prediction_transform,
        "trainingMode": "all_eligible_rows_no_holdout_production",
        "featureColumns": feature_columns,
        "labelColumn": feature_selection.label_column,
        "baselineColumn": feature_selection.baseline_column,
        "includeTerrain": not arguments.exclude_terrain,
        "hubCount": feature_selection.hub_count,
        "targetNeighborCount": feature_selection.target_neighbor_count,
        "rowCount": row_count,
        "targetStationCount": target_station_count,
        "sourceTrainingTable": project_relative_path(
            arguments.general_table,
            config.PROJECT_DIR,
        ),
        "createdAt": date.today().isoformat(),
        "trainingStrategy": arguments.training_strategy,
        "chunkRows": chunk_rows,
        "chunkCount": chunk_count,
        "hyperparameters": {
            "n_estimators": arguments.forest_trees,
            "max_depth": arguments.max_depth,
            "min_samples_leaf": arguments.min_samples_leaf,
            "random_state": arguments.random_state,
            "n_jobs": arguments.jobs,
        },
    }
    output_model.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, output_model)

    artifact_manifest = build_serialized_model_artifact_manifest(
        artifact=artifact,
        model_path=output_model,
        source_training_table=arguments.general_table,
        project_dir=config.PROJECT_DIR,
    )
    write_json_file(output_manifest, artifact_manifest)
    write_json_file(
        paths.feature_schema,
        build_feature_schema_payload(
            model_run_id=arguments.model_run_id,
            source_training_table=arguments.general_table,
            project_dir=config.PROJECT_DIR,
            target_column=feature_selection.label_column,
            prediction_output=feature_selection.prediction_output,
            prediction_transform=artifact["predictionTransform"],
            hub_count=feature_selection.hub_count,
            target_neighbor_count=feature_selection.target_neighbor_count,
            feature_columns=feature_columns,
            variable=variable,
        ),
    )
    existing_manifest = load_json_file(paths.manifest) if paths.manifest.exists() else None
    write_json_file(
        paths.manifest,
        merge_serialized_model_run_manifest(
            existing_manifest=existing_manifest,
            artifact_manifest=artifact_manifest,
            model_run_id=paths.model_run_id,
            variable=variable,
            source_table=arguments.general_table,
            row_count=row_count,
            station_count=target_station_count,
            project_dir=config.PROJECT_DIR,
        ),
    )

    print(f"Model artifact: {output_model}")
    print(f"Artifact manifest: {output_manifest}")
    print(f"Elapsed time: {perf_counter() - started_at:.1f} seconds")


if __name__ == "__main__":
    main()
