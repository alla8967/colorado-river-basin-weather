from __future__ import annotations

from pathlib import Path
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from common.csv_utils import write_csv_rows
import create_station_holdout_chunks as chunker
import merge_station_holdout_results as merger


def test_unique_target_stations_are_sorted_and_deduped() -> None:
    stations = chunker.unique_target_stations([
        {
            "target_station_id": "T2",
            "target_name": "Beta",
        },
        {
            "target_station_id": "T1",
            "target_name": "Alpha",
        },
        {
            "target_station_id": "T1",
            "target_name": "Alpha",
        },
    ])

    assert stations == [
        {
            "station_id": "T1",
            "station_name": "Alpha",
        },
        {
            "station_id": "T2",
            "station_name": "Beta",
        },
    ]
    assert chunker.chunks(stations, 1) == [[stations[0]], [stations[1]]]


def test_merge_collects_rows_and_adds_missing_metadata() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        input_dir = Path(temp_dir)
        metrics_file = input_dir / "chunk_001_station_metrics.csv"
        write_csv_rows(
            metrics_file,
            [
                {
                    "target_station_id": "T1",
                    "target_name": "Alpha",
                    "train_rows": "10",
                    "test_rows": "2",
                    "mae": "1.2",
                    "rmse": "1.8",
                    "correlation": "0.99",
                    "bias": "0.1",
                    "strict_pass": "True",
                    "elapsed_seconds": "0.5",
                }
            ],
            [
                "target_station_id",
                "target_name",
                "train_rows",
                "test_rows",
                "mae",
                "rmse",
                "correlation",
                "bias",
                "strict_pass",
                "elapsed_seconds",
            ],
        )

        rows, files = merger.collect_rows(
            input_dir,
            "*_station_metrics.csv",
            model_id="paloma_v1_tavg",
            variable="tavg",
        )

    assert files == [metrics_file]
    assert rows[0]["model_id"] == "paloma_v1_tavg"
    assert rows[0]["variable"] == "tavg"
    assert merger.duplicate_station_ids(rows) == []
    assert merger.mae_value(rows[0]) == 1.2


def main() -> None:
    test_unique_target_stations_are_sorted_and_deduped()
    test_merge_collects_rows_and_adds_missing_metadata()
    print("paloma holdout helper tests passed")


if __name__ == "__main__":
    main()
