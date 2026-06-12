"""Test station engine backend selection without requiring the native extension."""

from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / "station-proxy-backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from engine_adapter import build_engine_client, normalize_engine_mode
from engine_client import EngineClientConfig


class FakeNativeAvailable:
    def __init__(self, config):
        self.config = config

    @classmethod
    def is_available(cls) -> bool:
        return True


class FakeNativeUnavailable(FakeNativeAvailable):
    @classmethod
    def is_available(cls) -> bool:
        return False


class FakeProcessClient:
    def __init__(self, config):
        self.config = config


def config() -> EngineClientConfig:
    return EngineClientConfig(
        executable=Path("station_engine_server"),
        server_dir=Path("Station_Engine_Server"),
        target_data_file=Path("target.csv"),
        hub_data_file=Path("hub.csv"),
    )


def test_engine_mode_normalization() -> None:
    assert normalize_engine_mode("process") == "process"
    assert normalize_engine_mode("native") == "native"
    assert normalize_engine_mode("auto") == "auto"
    assert normalize_engine_mode("bad") == "process"
    assert normalize_engine_mode("") == "process"


def test_auto_mode_uses_native_only_when_available() -> None:
    unavailable = build_engine_client(
        config(),
        "auto",
        native_client_class=FakeNativeUnavailable,
        process_client_class=FakeProcessClient,
    )
    available = build_engine_client(
        config(),
        "auto",
        native_client_class=FakeNativeAvailable,
        process_client_class=FakeProcessClient,
    )

    assert isinstance(unavailable, FakeProcessClient)
    assert isinstance(available, FakeNativeAvailable)


def test_explicit_native_mode_returns_native_client_even_when_unavailable() -> None:
    client = build_engine_client(
        config(),
        "native",
        native_client_class=FakeNativeUnavailable,
        process_client_class=FakeProcessClient,
    )

    assert isinstance(client, FakeNativeUnavailable)


if __name__ == "__main__":
    test_engine_mode_normalization()
    test_auto_mode_uses_native_only_when_available()
    test_explicit_native_mode_returns_native_client_even_when_unavailable()
    print("Engine adapter tests passed.")
