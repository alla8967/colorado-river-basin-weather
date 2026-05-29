from __future__ import annotations

from typing import Any, Optional, Union

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard shape for recoverable backend errors returned as JSON."""

    status: str
    message: str
    details: Optional[str] = None


class HealthResponse(BaseModel):
    """Backend health and active data-source summary."""

    status: str
    engine: str
    engineRunning: bool
    engineExecutable: str
    targetDataFile: str
    hubDataFile: str
    activeModelRunId: str
    modelRunRoot: str


class ConfidenceGridSummary(BaseModel):
    """Small summary of the active model-run confidence grid."""

    scoreVersion: Optional[str] = None
    calibrationStatus: Optional[str] = None
    pointType: Optional[str] = None
    pointCount: int


class CurrentModelRunResponse(BaseModel):
    """Response contract for the active model-run metadata endpoint."""

    status: str
    activeModelRunId: str
    manifest: dict[str, Any]
    confidenceGrid: ConfidenceGridSummary


class NearbyStationResponse(BaseModel):
    """Station summary used by confidence/support estimates."""

    stationId: str
    stationName: str
    stationRole: str
    distanceKm: float
    elevationDifferenceM: Optional[float] = None


class ConfidenceSupportResponse(BaseModel):
    """Point-level support estimate for the confidence map workflow."""

    scoreVersion: str
    modelReference: Optional[str] = None
    status: str
    latitude: float
    longitude: float
    score: float
    label: str
    components: dict[str, float]
    reasons: list[str]
    warnings: list[str]
    nearestStations: list[NearbyStationResponse]
    inputFiles: dict[str, Optional[str]]


AnalyzeConfidenceResponse = Union[ConfidenceSupportResponse, ErrorResponse]
