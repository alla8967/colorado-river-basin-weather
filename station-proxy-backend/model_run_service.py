"""Load current model-run manifests, summaries, and confidence grids for the app.

The service keeps generated model artifacts behind a small backend API surface."""

from __future__ import annotations

from typing import Any, Optional

from api_models import ConfidenceGridSummary, CurrentModelRunResponse
from fastapi import HTTPException
from response_safety import sanitize_response_paths

# settings must be imported before `common`: importing it adds
# weather_reconstruction_model/scripts to sys.path.
from settings import BackendSettings

# isort: split
from common.model_runs import (
    load_confidence_grid,
    load_model_manifest,
    require_model_run_files,
    resolve_model_run,
)


class ModelRunService:
    """Loads and validates active model-run artifacts for API endpoints."""

    def __init__(self, settings: BackendSettings) -> None:
        self.settings = settings

    def active_paths(self, model_run_id: Optional[str] = None):
        return resolve_model_run(
            self.settings.model_run_root,
            model_run_id or self.settings.active_model_run_id,
        )

    def current_summary(self) -> CurrentModelRunResponse:
        paths = self.active_paths()

        try:
            require_model_run_files(paths)
            manifest = load_model_manifest(paths)
            confidence_grid = load_confidence_grid(paths)
        except FileNotFoundError as error:
            raise self.not_found_error(self.settings.active_model_run_id, error) from error
        except ValueError as error:
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "message": "Active model run failed contract validation.",
                    "details": sanitize_response_paths(
                        str(error),
                        self.settings.project_dir,
                        "details",
                    ),
                    "modelRunId": self.settings.active_model_run_id,
                },
            ) from error

        return CurrentModelRunResponse(
            status="ok",
            activeModelRunId=self.settings.active_model_run_id,
            manifest=sanitize_response_paths(manifest, self.settings.project_dir),
            confidenceGrid=self.confidence_grid_summary(
                sanitize_response_paths(confidence_grid, self.settings.project_dir)
            ),
        )

    def current_confidence_grid(self) -> dict[str, Any]:
        paths = self.active_paths()

        try:
            require_model_run_files(paths)
            return sanitize_response_paths(
                load_confidence_grid(paths),
                self.settings.project_dir,
            )
        except FileNotFoundError as error:
            raise self.not_found_error(self.settings.active_model_run_id, error) from error
        except ValueError as error:
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "message": "Active model confidence grid failed contract validation.",
                    "details": sanitize_response_paths(
                        str(error),
                        self.settings.project_dir,
                        "details",
                    ),
                    "modelRunId": self.settings.active_model_run_id,
                },
            ) from error

    def not_found_error(self, model_run_id: str, error: Exception) -> HTTPException:
        return HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "message": f"Model run is unavailable: {model_run_id}",
                "details": sanitize_response_paths(
                    str(error),
                    self.settings.project_dir,
                    "details",
                ),
                "modelRunRoot": sanitize_response_paths(
                    str(self.settings.model_run_root),
                    self.settings.project_dir,
                    "modelRunRoot",
                ),
            },
        )

    def confidence_grid_summary(self, confidence_grid: dict[str, Any]) -> ConfidenceGridSummary:
        return ConfidenceGridSummary(
            scoreVersion=confidence_grid.get("scoreVersion"),
            calibrationStatus=confidence_grid.get("calibrationStatus"),
            pointType=confidence_grid.get("pointType"),
            pointCount=confidence_grid.get(
                "pointCount",
                len(confidence_grid.get("points", [])),
            ),
        )
