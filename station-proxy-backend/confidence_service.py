from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from api_models import AnalyzeConfidenceResponse, ConfidenceSupportResponse, ErrorResponse
# settings configures imports for weather_reconstruction_model/scripts.
from settings import BackendSettings
from common.confidence_data import load_confidence_support_inputs
from common.confidence_support import (
    ConfidenceSupportConfig,
    SupportPoint,
    calculate_confidence_support,
)


class ConfidenceService:
    """Caches confidence inputs and scores clicked support points."""

    def __init__(self, settings: BackendSettings) -> None:
        self.settings = settings
        self._inputs = None
        self._lock = threading.Lock()

    def validation_metrics_file(self) -> Optional[Path]:
        if self.settings.confidence_validation_metrics_file.exists():
            return self.settings.confidence_validation_metrics_file

        print(
            "[confidence_support] Validation metrics file not found; "
            f"continuing without validation evidence: {self.settings.confidence_validation_metrics_file}"
        )
        return None

    def load_inputs_once(self):
        """Load confidence support inputs once so point scoring is mostly in-memory."""
        with self._lock:
            if self._inputs is not None:
                return self._inputs

            self._inputs = load_confidence_support_inputs(
                target_candidate_file=self.settings.confidence_target_candidate_file,
                hub_candidate_file=self.settings.confidence_hub_candidate_file,
                terrain_file=self.settings.confidence_terrain_feature_file,
                validation_metrics_file=self.validation_metrics_file(),
                model_reference=self.settings.confidence_model_reference,
            )
            print(
                "[confidence_support] Loaded "
                f"{len(self._inputs.target_stations)} targets, "
                f"{len(self._inputs.hub_stations)} hubs, "
                f"{len(self._inputs.terrain_by_station_id)} terrain rows, "
                f"{len(self._inputs.validation_by_station_id)} validation rows"
            )

            return self._inputs

    def config(self) -> ConfidenceSupportConfig:
        config_kwargs = {
            "model_reference": self.settings.confidence_model_reference,
        }

        if self.settings.confidence_score_version:
            config_kwargs["score_version"] = self.settings.confidence_score_version

        return ConfidenceSupportConfig(**config_kwargs)

    def analyze_point(
        self,
        latitude: float,
        longitude: float,
        elevation_m: Optional[float] = None,
    ) -> AnalyzeConfidenceResponse:
        try:
            inputs = self.load_inputs_once()
            result = calculate_confidence_support(
                SupportPoint(
                    latitude=latitude,
                    longitude=longitude,
                    elevation_m=elevation_m,
                ),
                target_stations=inputs.target_stations,
                hub_stations=inputs.hub_stations,
                validation_by_station_id=inputs.validation_by_station_id,
                config=self.config(),
            )
            data = result.as_dict()
            data["inputFiles"] = {
                "targetCandidates": str(self.settings.confidence_target_candidate_file),
                "hubCandidates": str(self.settings.confidence_hub_candidate_file),
                "terrainFeatures": str(self.settings.confidence_terrain_feature_file),
                "validationMetrics": (
                    str(self.settings.confidence_validation_metrics_file)
                    if self.settings.confidence_validation_metrics_file.exists()
                    else None
                ),
            }
            return ConfidenceSupportResponse(**data)
        except Exception as error:
            return ErrorResponse(
                status="error",
                message="Failed to analyze confidence support",
                details=str(error),
            )
