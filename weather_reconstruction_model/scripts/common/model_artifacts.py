from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Mapping, Sequence


NO_SERIALIZED_ESTIMATOR_NOTE = "No serialized estimator is present for this run yet."
SERIALIZED_ESTIMATOR_NOTE = (
    "Serialized estimator is trained on all rows from the current best completed training table."
)
PRODUCTION_ESTIMATOR_NOTE = (
    "Production estimator is trained on all eligible rows and is not holdout evidence."
)
STATION_HOLDOUT_CONFIDENCE_NOTE = (
    "Use separate station-holdout validation outputs for confidence calibration."
)
PENDING_CONFIDENCE_GRID_NOTE = "Confidence grid is pending calibrated-confidence generation."
PRODUCTION_ESTIMATOR_CAVEAT = (
    "This production estimator is not holdout evidence; calibrate confidence from "
    "station-holdout validation."
)


@dataclass
class ChunkedRandomForestRegressor:
    """A production regressor made from forests trained over table chunks."""

    models: Sequence[object]
    estimator_counts: Sequence[int]
    training_row_counts: Sequence[int]

    def predict(self, features):
        if not self.models:
            raise ValueError("ChunkedRandomForestRegressor has no trained models.")

        total_weight = sum(self.estimator_counts)
        if total_weight <= 0:
            raise ValueError("ChunkedRandomForestRegressor estimator weights are invalid.")

        weighted_predictions = None
        for model, estimator_count in zip(self.models, self.estimator_counts):
            predictions = model.predict(features)
            if weighted_predictions is None:
                weighted_predictions = predictions * estimator_count
            else:
                weighted_predictions += predictions * estimator_count

        return weighted_predictions / total_weight


def project_relative_path(path: Path, project_dir: Path) -> str:
    """Return a project-relative path when possible, otherwise an absolute path."""
    try:
        return str(path.resolve().relative_to(project_dir.resolve()))
    except ValueError:
        return str(path.resolve())


def project_relative_sources(
    source_files: Mapping[str, Path],
    project_dir: Path,
) -> dict[str, str]:
    """Return a source-file manifest with paths normalized for review."""
    return {
        label: project_relative_path(source_path, project_dir)
        for label, source_path in source_files.items()
    }


def infer_feature_unit(column_name: str, variable: str = "tavg") -> str | None:
    """Infer the display unit for a model feature column."""
    if column_name.endswith("_km"):
        return "km"
    if column_name.endswith("_m") or "_elevation" in column_name or "_relief" in column_name:
        return "m"
    if "slope" in column_name and "sin" not in column_name and "cos" not in column_name:
        return "degrees"
    if variable in column_name:
        return "F"
    if column_name.endswith("_percent"):
        return "percent"
    return None


def build_feature_schema_payload(
    *,
    model_run_id: str,
    source_training_table: Path,
    project_dir: Path,
    target_column: str,
    prediction_output: str,
    prediction_transform: str,
    hub_count: int,
    target_neighbor_count: int,
    feature_columns: Sequence[str],
    variable: str = "tavg",
) -> dict[str, object]:
    """Build the standard model-run feature schema artifact."""
    features = list(feature_columns)

    return {
        "featureSchemaVersion": "feature-schema-v1",
        "modelRunId": model_run_id,
        "sourceTrainingTable": project_relative_path(source_training_table, project_dir),
        "targetColumn": target_column,
        "predictionOutput": prediction_output,
        "predictionTransform": prediction_transform,
        "hubCount": hub_count,
        "targetNeighborCount": target_neighbor_count,
        "featureCount": len(features),
        "features": [
            {
                "name": column,
                "type": "float",
                "unit": infer_feature_unit(column, variable),
                "required": True,
            }
            for column in features
        ],
    }


def build_model_run_manifest(
    *,
    model_run_id: str,
    model_family: str,
    prediction_target: str,
    training_mode: str,
    validation_mode: str,
    project_dir: Path,
    source_files: Mapping[str, Path],
    summary_metrics: Mapping[str, object],
    notes: Sequence[str],
    model_variant: str | None = None,
) -> dict[str, object]:
    """Build the shared model-run manifest shape served by the app."""
    manifest: dict[str, object] = {
        "modelRunId": model_run_id,
        "modelFamily": model_family,
    }
    if model_variant is not None:
        manifest["modelVariant"] = model_variant

    manifest.update(
        {
            "predictionTarget": prediction_target,
            "trainingMode": training_mode,
            "validationMode": validation_mode,
            "createdAt": date.today().isoformat(),
            "sourceFiles": project_relative_sources(source_files, project_dir),
            "summaryMetrics": dict(summary_metrics),
            "notes": list(notes),
        }
    )
    return manifest


def build_validation_model_run_manifest(
    *,
    model_run_id: str,
    model_variant: str,
    training_table: Path,
    station_metrics: Path,
    validation_predictions: Path,
    project_dir: Path,
    summary_metrics: Mapping[str, object],
) -> dict[str, object]:
    """Build the standard station-holdout model-run manifest."""
    return build_model_run_manifest(
        model_run_id=model_run_id,
        model_family="random_forest",
        model_variant=model_variant,
        prediction_target="daily_tavg_f",
        training_mode="general_multi_station_offset_model",
        validation_mode="out_of_sample_station_holdout",
        project_dir=project_dir,
        source_files={
            "trainingTable": training_table,
            "stationMetrics": station_metrics,
            "validationPredictions": validation_predictions,
        },
        summary_metrics=summary_metrics,
        notes=[
            NO_SERIALIZED_ESTIMATOR_NOTE,
            PENDING_CONFIDENCE_GRID_NOTE,
        ],
    )


def build_production_model_run_manifest(
    *,
    model_run_id: str,
    source_table: Path,
    variable: str,
    row_count: int,
    station_count: int,
    project_dir: Path,
) -> dict[str, object]:
    """Build the base manifest for an all-rows production estimator."""
    return build_model_run_manifest(
        model_run_id=model_run_id,
        model_family="random_forest",
        prediction_target=f"daily_{variable}_f",
        training_mode="all_eligible_rows_no_holdout_production",
        validation_mode="separate_station_holdout_required_for_confidence",
        project_dir=project_dir,
        source_files={"trainingTable": source_table},
        summary_metrics={
            "trainingRows": row_count,
            "trainingTargetStationCount": station_count,
        },
        notes=[
            PRODUCTION_ESTIMATOR_NOTE,
            STATION_HOLDOUT_CONFIDENCE_NOTE,
        ],
    )


def build_serialized_model_artifact_manifest(
    *,
    artifact: Mapping[str, object],
    model_path: Path,
    source_training_table: Path,
    project_dir: Path,
) -> dict[str, object]:
    """Build the sidecar manifest for a serialized production model file."""
    return {
        "artifactVersion": "model-artifact-v1",
        "createdAt": date.today().isoformat(),
        "modelPath": project_relative_path(model_path, project_dir),
        "sourceTrainingTable": project_relative_path(source_training_table, project_dir),
        "variable": artifact["variable"],
        "trainingMode": artifact["trainingMode"],
        "modelFamily": artifact["modelFamily"],
        "predictionTarget": artifact["predictionTarget"],
        "predictionMode": artifact["predictionMode"],
        "predictionTransform": artifact["predictionTransform"],
        "rowCount": artifact["rowCount"],
        "targetStationCount": artifact["targetStationCount"],
        "featureCount": len(artifact["featureColumns"]),
        "featureColumns": artifact["featureColumns"],
        "labelColumn": artifact["labelColumn"],
        "baselineColumn": artifact["baselineColumn"],
        "includeTerrain": artifact["includeTerrain"],
        "hubCount": artifact["hubCount"],
        "targetNeighborCount": artifact["targetNeighborCount"],
        "trainingStrategy": artifact["trainingStrategy"],
        "chunkRows": artifact["chunkRows"],
        "chunkCount": artifact["chunkCount"],
        "hyperparameters": artifact["hyperparameters"],
        "importantCaveat": PRODUCTION_ESTIMATOR_CAVEAT,
    }


def merge_serialized_model_run_manifest(
    *,
    existing_manifest: Mapping[str, object] | None,
    artifact_manifest: Mapping[str, object],
    model_run_id: str,
    variable: str,
    source_table: Path,
    row_count: int,
    station_count: int,
    project_dir: Path,
) -> dict[str, object]:
    """Attach serialized-model metadata to a model-run manifest."""
    if existing_manifest is None:
        manifest = build_production_model_run_manifest(
            model_run_id=model_run_id,
            source_table=source_table,
            variable=variable,
            row_count=row_count,
            station_count=station_count,
            project_dir=project_dir,
        )
    else:
        manifest = dict(existing_manifest)

    manifest["serializedModel"] = dict(artifact_manifest)
    manifest["predictionTarget"] = f"daily_{variable}_f"
    manifest["trainingMode"] = "all_eligible_rows_no_holdout_production"

    source_files = dict(manifest.get("sourceFiles", {}))
    source_files["trainingTable"] = project_relative_path(source_table, project_dir)
    manifest["sourceFiles"] = source_files

    summary_metrics = dict(manifest.get("summaryMetrics", {}))
    summary_metrics["trainingRows"] = row_count
    summary_metrics["trainingTargetStationCount"] = station_count
    manifest["summaryMetrics"] = summary_metrics

    notes = [
        note
        for note in manifest.get("notes", [])
        if note != NO_SERIALIZED_ESTIMATOR_NOTE
    ]
    if not any("serialized estimator" in note for note in notes):
        notes.append(SERIALIZED_ESTIMATOR_NOTE)
    manifest["notes"] = notes

    return manifest
