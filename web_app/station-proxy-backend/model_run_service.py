from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException

from api_models import ConfidenceGridSummary, CurrentModelRunResponse
# settings configures imports for ml_reconstruction/weather_reconstruction_model/scripts.
from settings import BackendSettings
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
                    "details": str(error),
                    "modelRunId": self.settings.active_model_run_id,
                },
            ) from error

        return CurrentModelRunResponse(
            status="ok",
            activeModelRunId=self.settings.active_model_run_id,
            manifest=manifest,
            confidenceGrid=self.confidence_grid_summary(confidence_grid),
        )

    def current_confidence_grid(self) -> dict[str, Any]:
        paths = self.active_paths()

        try:
            require_model_run_files(paths)
            return load_confidence_grid(paths)
        except FileNotFoundError as error:
            raise self.not_found_error(self.settings.active_model_run_id, error) from error
        except ValueError as error:
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "message": "Active model confidence grid failed contract validation.",
                    "details": str(error),
                    "modelRunId": self.settings.active_model_run_id,
                },
            ) from error

    def not_found_error(self, model_run_id: str, error: Exception) -> HTTPException:
        return HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "message": f"Model run is unavailable: {model_run_id}",
                "details": str(error),
                "modelRunRoot": str(self.settings.model_run_root),
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
