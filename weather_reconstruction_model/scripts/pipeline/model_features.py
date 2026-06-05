"""Resolve feature-selection modes for general temperature models.

This keeps model trainers and artifact exporters aligned on which columns belong to each configuration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Collection, Iterable

import train_general_temperature_model as general_model
from common.pairwise_skill import PAIRWISE_SKILL_COLUMNS
from common.weather_cache import validate_temperature_variable


@dataclass(frozen=True)
class ModelFeatureSelection:
    """Resolved feature-column contract for a general training table."""

    variable: str
    target_column: str
    baseline_column: str
    label_column: str
    hub_count: int
    target_neighbor_count: int
    feature_columns: list[str]

    @property
    def prediction_output(self) -> str:
        return f"daily_{self.variable}_f"

    @property
    def prediction_transform(self) -> str:
        return f"{self.baseline_column} + predicted_offset"

    @property
    def required_training_columns(self) -> set[str]:
        return {self.target_column, self.baseline_column, self.label_column}

    def with_feature_columns(
        self,
        feature_columns: Iterable[str],
    ) -> "ModelFeatureSelection":
        return replace(self, feature_columns=list(feature_columns))


def is_pairwise_feature_column(column: str) -> bool:
    return any(
        column.endswith(f"_{suffix}")
        for suffix in PAIRWISE_SKILL_COLUMNS
    )


def add_offset_feature_columns(
    feature_columns: list[str],
    fieldnames: Iterable[str],
    hub_count: int,
    target_neighbor_count: int,
    variable: str = "tavg",
) -> None:
    """Append available regional-baseline offset features in stable order."""
    variable = validate_temperature_variable(variable)
    available_fieldnames = set(fieldnames)
    regional_baseline_column = f"regional_baseline_{variable}"

    if regional_baseline_column in available_fieldnames:
        feature_columns.append(regional_baseline_column)

    for prefix, count in (
        ("hub", hub_count),
        ("target_neighbor", target_neighbor_count),
    ):
        for index in range(1, count + 1):
            column = f"{prefix}_{index}_{variable}_offset_from_baseline"

            if column in available_fieldnames:
                feature_columns.append(column)


def resolve_model_feature_selection(
    fieldnames: Iterable[str],
    *,
    variable: str = "tavg",
    include_terrain: bool = True,
    include_offset_features: bool = True,
    exclude_pairwise_features: bool = False,
    nonempty_feature_columns: Collection[str] | None = None,
) -> ModelFeatureSelection:
    """Resolve model feature columns from a training-table header."""
    variable = validate_temperature_variable(variable)
    fieldname_list = list(fieldnames)
    hub_count = general_model.get_hub_count(fieldname_list, variable=variable)
    target_neighbor_count = general_model.get_target_neighbor_count(
        fieldname_list,
        variable=variable,
    )
    feature_columns = general_model.build_feature_columns(
        hub_count,
        fieldname_list,
        include_terrain=include_terrain,
        variable=variable,
    )

    if include_offset_features:
        add_offset_feature_columns(
            feature_columns,
            fieldname_list,
            hub_count,
            target_neighbor_count,
            variable=variable,
        )

    if exclude_pairwise_features:
        feature_columns = [
            column
            for column in feature_columns
            if not is_pairwise_feature_column(column)
        ]

    if nonempty_feature_columns is not None:
        feature_columns = [
            column
            for column in feature_columns
            if column in nonempty_feature_columns
        ]

    return ModelFeatureSelection(
        variable=variable,
        target_column=f"target_{variable}",
        baseline_column=f"regional_baseline_{variable}",
        label_column=f"target_{variable}_offset_from_baseline",
        hub_count=hub_count,
        target_neighbor_count=target_neighbor_count,
        feature_columns=feature_columns,
    )


def missing_training_columns(
    fieldnames: Iterable[str],
    feature_selection: ModelFeatureSelection,
) -> list[str]:
    return sorted(feature_selection.required_training_columns - set(fieldnames))


def require_training_columns(
    fieldnames: Iterable[str],
    feature_selection: ModelFeatureSelection,
    error_prefix: str,
) -> None:
    missing_columns = missing_training_columns(fieldnames, feature_selection)
    if missing_columns:
        raise ValueError(f"{error_prefix}: " + ", ".join(missing_columns))


def require_feature_columns(feature_selection: ModelFeatureSelection) -> None:
    if not feature_selection.feature_columns:
        raise ValueError("No usable feature columns were found.")
