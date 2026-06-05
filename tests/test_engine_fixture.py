"""Compile and run the C++ engine against tiny fixture station CSVs.

This protects the station-matching contract without requiring the full NOAA app-ready data files."""

import json
import subprocess
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
TARGET_FIXTURE = PROJECT_DIR / "tests" / "fixtures" / "target_daily_app_ready.csv"
HUB_FIXTURE = PROJECT_DIR / "tests" / "fixtures" / "hub_daily_app_ready.csv"
ENGINE_BINARY_NAME = "station_engine_api_test"
ENGINE_BINARY = PROJECT_DIR / ENGINE_BINARY_NAME


def test_fixture_engine_returns_stable_station_ranking():
    subprocess.run(["make", "api", f"API_TARGET={ENGINE_BINARY_NAME}"], cwd=PROJECT_DIR, check=True)

    result = subprocess.run(
        [
            str(ENGINE_BINARY),
            "39.7501",
            "-105.0001",
            str(TARGET_FIXTURE),
            str(HUB_FIXTURE),
        ],
        cwd=PROJECT_DIR,
        check=True,
        text=True,
        capture_output=True,
    )

    data = json.loads(result.stdout)

    assert data["status"] == "ok"
    assert data["targetStationCount"] == 2
    assert data["hubStationCount"] == 3
    assert data["nearestStation"]["stationID"] == "TGT_NEAR"
    assert data["bestProxyStation"]["proxyStation"]["stationID"] == "HUB_GOOD"
    assert data["topProxyMatches"][0]["rank"] == 1
    assert data["topProxyMatches"][0]["pairedDays"] == 3


if __name__ == "__main__":
    test_fixture_engine_returns_stable_station_ranking()
    print("Fixture engine test passed.")
