from __future__ import annotations

from collections.abc import Mapping, Sequence


def row_uses_station(
    row: Mapping[str, str],
    station_id: str,
    hub_count: int,
    target_neighbor_count: int,
) -> bool:
    return row_uses_any_station(
        row,
        {station_id},
        hub_count,
        target_neighbor_count,
    )


def row_uses_any_station(
    row: Mapping[str, str],
    station_ids: set[str],
    hub_count: int,
    target_neighbor_count: int,
) -> bool:
    if row["target_station_id"] in station_ids:
        return True

    for index in range(1, hub_count + 1):
        if row.get(f"hub_{index}_station_id") in station_ids:
            return True

    for index in range(1, target_neighbor_count + 1):
        if row.get(f"target_neighbor_{index}_station_id") in station_ids:
            return True

    return False


def training_rows_for_station_holdout(
    rows: Sequence[Mapping[str, str]],
    heldout_station_ids: set[str],
    train_end_year: int,
    hub_count: int,
    target_neighbor_count: int,
) -> list[Mapping[str, str]]:
    return [
        row
        for row in rows
        if int(row["year"]) <= train_end_year
        and not row_uses_any_station(
            row,
            heldout_station_ids,
            hub_count,
            target_neighbor_count,
        )
    ]
