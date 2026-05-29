from __future__ import annotations

from pathlib import Path
import argparse
import csv
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from common.csv_utils import write_csv_rows
from pipeline.station_holdouts import row_uses_any_station, row_uses_station
import train_station_holdout_model as holdout


def test_prediction_rows_are_variable_specific() -> None:
    rows = holdout.prediction_rows_for_station(
        [
            {
                "date": "2024-01-01",
                "target_station_id": "T1",
                "target_name": "Target One",
            }
        ],
        [20.0],
        [18.5],
        variable="tmin",
        holdout_group_id="group_001",
        holdout_group_size=4,
    )

    assert rows == [
        {
            "date": "2024-01-01",
            "target_station_id": "T1",
            "target_name": "Target One",
            "holdout_group_id": "group_001",
            "holdout_group_size": 4,
            "actual_tmin": "20.00",
            "predicted_tmin": "18.50",
            "error": "1.50",
        }
    ]


def test_row_uses_station_checks_target_hubs_and_neighbors() -> None:
    row = {
        "target_station_id": "T1",
        "hub_1_station_id": "H1",
        "target_neighbor_1_station_id": "N1",
    }

    assert row_uses_station(row, "T1", hub_count=1, target_neighbor_count=1)
    assert row_uses_station(row, "H1", hub_count=1, target_neighbor_count=1)
    assert row_uses_station(row, "N1", hub_count=1, target_neighbor_count=1)
    assert not row_uses_station(row, "OTHER", hub_count=1, target_neighbor_count=1)
    assert row_uses_any_station(
        row,
        {"H1", "OTHER"},
        hub_count=1,
        target_neighbor_count=1,
    )


def test_station_list_overrides_default_ids() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        station_list = Path(temp_dir) / "chunk_001.csv"
        write_csv_rows(
            station_list,
            [
                {
                    "station_id": "T1",
                    "station_name": "Target One",
                },
                {
                    "station_id": "T2",
                    "station_name": "Target Two",
                },
            ],
            ["station_id", "station_name"],
        )
        arguments = argparse.Namespace(
            station_list=station_list,
            station_ids=["DEFAULT"],
        )

        assert holdout.load_station_ids(arguments) == ["T1", "T2"]


def test_station_group_list_loads_groups() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        station_group_list = Path(temp_dir) / "group_001.csv"
        write_csv_rows(
            station_group_list,
            [
                {
                    "group_id": "group_001",
                    "station_id": "T1",
                },
                {
                    "group_id": "group_001",
                    "station_id": "T2",
                },
            ],
            ["group_id", "station_id"],
        )
        arguments = argparse.Namespace(
            station_group_list=station_group_list,
            station_list=None,
            station_ids=[],
        )

        assert holdout.load_station_groups(arguments) == [
            {
                "group_id": "group_001",
                "station_ids": ["T1", "T2"],
            }
        ]


def test_resume_header_mismatch_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        report_file = Path(temp_dir) / "existing.csv"
        with report_file.open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["old_column"])
            writer.writeheader()

        try:
            holdout.open_csv_writer(report_file, ["new_column"], append=True)
        except ValueError:
            return

    raise AssertionError("Expected a ValueError for mismatched resume headers.")


def main() -> None:
    test_prediction_rows_are_variable_specific()
    test_row_uses_station_checks_target_hubs_and_neighbors()
    test_station_list_overrides_default_ids()
    test_station_group_list_loads_groups()
    test_resume_header_mismatch_is_rejected()
    print("station holdout variable tests passed")


if __name__ == "__main__":
    main()
