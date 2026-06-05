"""Load and normalize the station metadata used by confidence-support scoring.

The helpers turn validation, terrain, and candidate-station files into typed records for scoring scripts and the backend."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from common.confidence_support import (
    SupportStation,
    TerrainFeatures,
    ValidationEvidence,
)
from common.csv_utils import CsvRow, read_csv_rows
from common.number_utils import to_optional_float


STATION_ID_FIELDS = [
    "station_id",
    "target_station_id",
    "validation_station_id",
]

MAE_FIELDS = ["mae", "test_mae", "mean_absolute_error"]
RMSE_FIELDS = ["rmse", "test_rmse"]
CORRELATION_FIELDS = ["correlation", "r", "test_correlation"]
TEST_ROWS_FIELDS = ["test_rows", "paired_days", "paired_count"]
STRICT_PASS_FIELDS = ["strict_pass", "is_strict_pass"]


@dataclass(frozen=True)
class TerrainStationRecord:
    station_id: str
    station_role: str | None = None
    station_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    noaa_elevation_m: float | None = None
    dem_elevation_m: float | None = None
    terrain: TerrainFeatures | None = None
    raw_row: CsvRow = field(default_factory=dict)


@dataclass(frozen=True)
class ConfidenceSupportInputs:
    target_stations: list[SupportStation]
    hub_stations: list[SupportStation]
    validation_by_station_id: dict[str, ValidationEvidence]
    terrain_by_station_id: dict[str, TerrainStationRecord]


def load_confidence_support_inputs(
    target_candidate_file: Path,
    hub_candidate_file: Path,
    terrain_file: Path | None = None,
    validation_metrics_file: Path | None = None,
    model_reference: str | None = None,
) -> ConfidenceSupportInputs:
    terrain_by_station_id = (
        load_terrain_station_records(terrain_file)
        if terrain_file is not None and terrain_file.exists()
        else {}
    )
    validation_by_station_id = (
        load_validation_evidence(validation_metrics_file, model_reference=model_reference)
        if validation_metrics_file is not None and validation_metrics_file.exists()
        else {}
    )

    return ConfidenceSupportInputs(
        target_stations=load_support_stations(
            target_candidate_file,
            station_role="target",
            terrain_by_station_id=terrain_by_station_id,
        ),
        hub_stations=load_support_stations(
            hub_candidate_file,
            station_role="hub",
            terrain_by_station_id=terrain_by_station_id,
        ),
        validation_by_station_id=validation_by_station_id,
        terrain_by_station_id=terrain_by_station_id,
    )


def load_support_stations(
    candidate_file: Path,
    station_role: str,
    terrain_by_station_id: Mapping[str, TerrainStationRecord] | None = None,
) -> list[SupportStation]:
    terrain_by_station_id = terrain_by_station_id or {}
    stations = []

    for row in read_csv_rows(candidate_file):
        station_id = row.get("station_id", "").strip()
        if not station_id:
            continue

        terrain_record = terrain_by_station_id.get(station_id)
        station_name = station_id
        elevation_m = None
        terrain = None

        if terrain_record is not None:
            station_name = terrain_record.station_name or station_id
            elevation_m = first_available_float(
                terrain_record.noaa_elevation_m,
                terrain_record.dem_elevation_m,
            )
            terrain = terrain_record.terrain

        latitude = first_available_float(
            to_optional_float(row.get("latitude")),
            terrain_record.latitude if terrain_record is not None else None,
        )
        longitude = first_available_float(
            to_optional_float(row.get("longitude")),
            terrain_record.longitude if terrain_record is not None else None,
        )

        if latitude is None or longitude is None:
            continue

        stations.append(
            SupportStation(
                station_id=station_id,
                station_name=station_name,
                station_role=station_role,
                latitude=latitude,
                longitude=longitude,
                elevation_m=elevation_m,
                usable_years=to_optional_float(row.get("usable_temp_years")),
                usable_start_year=to_optional_int(row.get("usable_temp_start")),
                usable_end_year=to_optional_int(row.get("usable_temp_end")),
                completeness=None,
                terrain=terrain,
            )
        )

    return stations


def load_terrain_station_records(
    terrain_file: Path,
) -> dict[str, TerrainStationRecord]:
    records = {}

    for row in read_csv_rows(terrain_file):
        station_id = row.get("station_id", "").strip()
        if not station_id:
            continue

        terrain = terrain_features_from_row(row)
        records[station_id] = TerrainStationRecord(
            station_id=station_id,
            station_role=blank_to_none(row.get("station_role")),
            station_name=blank_to_none(row.get("station_name")),
            latitude=to_optional_float(row.get("latitude")),
            longitude=to_optional_float(row.get("longitude")),
            noaa_elevation_m=to_optional_float(row.get("noaa_elevation_m")),
            dem_elevation_m=to_optional_float(row.get("dem_elevation_m")),
            terrain=terrain,
            raw_row=row,
        )

    return records


def terrain_features_from_row(row: Mapping[str, object]) -> TerrainFeatures:
    return TerrainFeatures(
        dem_elevation_m=to_optional_float(row.get("dem_elevation_m")),
        slope_degrees=to_optional_float(row.get("slope_degrees")),
        aspect_sin=to_optional_float(row.get("aspect_sin")),
        aspect_cos=to_optional_float(row.get("aspect_cos")),
        local_relief_m=to_optional_float(row.get("local_relief_m")),
        terrain_position_index_m=to_optional_float(row.get("terrain_position_index_m")),
        slope_degrees_r300m=to_optional_float(row.get("slope_degrees_r300m")),
        aspect_sin_r300m=to_optional_float(row.get("aspect_sin_r300m")),
        aspect_cos_r300m=to_optional_float(row.get("aspect_cos_r300m")),
        local_relief_m_r300m=to_optional_float(row.get("local_relief_m_r300m")),
        terrain_position_index_m_r300m=to_optional_float(row.get("terrain_position_index_m_r300m")),
        slope_degrees_r990m=to_optional_float(row.get("slope_degrees_r990m")),
        aspect_sin_r990m=to_optional_float(row.get("aspect_sin_r990m")),
        aspect_cos_r990m=to_optional_float(row.get("aspect_cos_r990m")),
        local_relief_m_r990m=to_optional_float(row.get("local_relief_m_r990m")),
        terrain_position_index_m_r990m=to_optional_float(row.get("terrain_position_index_m_r990m")),
        slope_degrees_r3000m=to_optional_float(row.get("slope_degrees_r3000m")),
        aspect_sin_r3000m=to_optional_float(row.get("aspect_sin_r3000m")),
        aspect_cos_r3000m=to_optional_float(row.get("aspect_cos_r3000m")),
        local_relief_m_r3000m=to_optional_float(row.get("local_relief_m_r3000m")),
        terrain_position_index_m_r3000m=to_optional_float(row.get("terrain_position_index_m_r3000m")),
    )


def load_validation_evidence(
    metrics_file: Path,
    model_reference: str | None = None,
) -> dict[str, ValidationEvidence]:
    evidence_by_station_id = {}

    for row in read_csv_rows(metrics_file):
        station_id = first_present(row, STATION_ID_FIELDS)
        if station_id is None:
            continue

        strict_pass_value = first_present(row, STRICT_PASS_FIELDS)
        evidence_by_station_id[station_id] = ValidationEvidence(
            station_id=station_id,
            mae=first_present_float(row, MAE_FIELDS),
            rmse=first_present_float(row, RMSE_FIELDS),
            correlation=first_present_float(row, CORRELATION_FIELDS),
            test_rows=first_present_int(row, TEST_ROWS_FIELDS),
            strict_pass=parse_optional_bool(strict_pass_value),
            model_reference=model_reference,
            extra_metrics=numeric_extra_metrics(row),
        )

    return evidence_by_station_id


def numeric_extra_metrics(row: Mapping[str, object]) -> dict[str, float]:
    standard_fields = set(
        STATION_ID_FIELDS
        + MAE_FIELDS
        + RMSE_FIELDS
        + CORRELATION_FIELDS
        + TEST_ROWS_FIELDS
        + STRICT_PASS_FIELDS
        + ["target_name", "station_name"]
    )
    output = {}

    for key, value in row.items():
        if key in standard_fields:
            continue

        numeric_value = to_optional_float(value)
        if numeric_value is not None:
            output[key] = numeric_value

    return output


def first_present(
    row: Mapping[str, object],
    field_names: Sequence[str],
) -> str | None:
    for field_name in field_names:
        value = row.get(field_name)
        if value is None:
            continue

        stripped = str(value).strip()
        if stripped:
            return stripped

    return None


def first_present_float(
    row: Mapping[str, object],
    field_names: Sequence[str],
) -> float | None:
    value = first_present(row, field_names)
    if value is None:
        return None

    return to_optional_float(value)


def first_present_int(
    row: Mapping[str, object],
    field_names: Sequence[str],
) -> int | None:
    value = first_present(row, field_names)
    if value is None:
        return None

    return to_optional_int(value)


def to_optional_int(value: object) -> int | None:
    numeric_value = to_optional_float(value)
    if numeric_value is None:
        return None

    return int(numeric_value)


def parse_optional_bool(value: object) -> bool | None:
    if value is None:
        return None

    normalized = str(value).strip().lower()
    if not normalized:
        return None

    if normalized in {"1", "true", "t", "yes", "y"}:
        return True

    if normalized in {"0", "false", "f", "no", "n"}:
        return False

    return None


def first_available_float(*values: float | None) -> float | None:
    for value in values:
        if value is not None:
            return value

    return None


def blank_to_none(value: object) -> str | None:
    if value is None:
        return None

    stripped = str(value).strip()
    return stripped or None
