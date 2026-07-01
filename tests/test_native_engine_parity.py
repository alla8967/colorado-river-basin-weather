"""Compare native and subprocess engine responses when the pybind extension exists."""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / "station-proxy-backend"
TARGET_FIXTURE = PROJECT_DIR / "tests" / "fixtures" / "target_daily_app_ready.csv"
HUB_FIXTURE = PROJECT_DIR / "tests" / "fixtures" / "hub_daily_app_ready.csv"
SERVER_BINARY = PROJECT_DIR / "Station_Engine_Server" / "station_engine_server"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from engine_client import EngineClient, EngineClientConfig
from native_engine_client import NativeEngineClient


def comparable_subset(payload: dict) -> dict:
    return {
        "status": payload["status"],
        "nearestStationId": payload["nearestStation"]["stationID"],
        "bestProxyStationId": payload["bestProxyStation"]["proxyStation"]["stationID"],
        "topProxyStationIds": [
            row["proxyStation"]["stationID"]
            for row in payload["topProxyMatches"]
        ],
        "topProxyPairedDays": [
            row["pairedDays"]
            for row in payload["topProxyMatches"]
        ],
    }


def test_native_engine_matches_process_engine_on_fixture() -> None:
    if not NativeEngineClient.is_available():
        print("Native engine extension is not built; parity test skipped.")
        return

    if not SERVER_BINARY.exists():
        raise AssertionError("Process engine binary is missing; run `make server` first.")

    config = EngineClientConfig(
        executable=SERVER_BINARY,
        server_dir=PROJECT_DIR / "Station_Engine_Server",
        target_data_file=TARGET_FIXTURE,
        hub_data_file=HUB_FIXTURE,
    )
    process_client = EngineClient(config)
    native_client = NativeEngineClient(config)

    try:
        process_payload = process_client.query(39.7501, -105.0001)
        native_payload = native_client.query(39.7501, -105.0001)
    finally:
        process_client.stop()
        native_client.stop()

    assert comparable_subset(native_payload) == comparable_subset(process_payload)


if __name__ == "__main__":
    test_native_engine_matches_process_engine_on_fixture()
    print("Native engine parity test passed or skipped.")
