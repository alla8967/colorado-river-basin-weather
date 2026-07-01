"""Optional in-process StationProxyEngine client backed by pybind11.

The module is dependency-safe: importing it does not require the native extension
to exist, and callers can fall back to the process client when unavailable."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional

from engine_client import EngineClientConfig

try:
    import _station_proxy_engine as native_engine
except Exception as import_error:  # pragma: no cover - depends on local extension
    native_engine = None
    NATIVE_IMPORT_ERROR: Optional[Exception] = import_error
else:
    NATIVE_IMPORT_ERROR = None


class NativeEngineClient:
    """Load and query StationProxyEngine directly inside the Python process."""

    def __init__(self, config: EngineClientConfig) -> None:
        self.config = config
        self._engine = None
        self._loaded = False
        self._last_start_error: Optional[str] = None
        self._lock = threading.Lock()

    @classmethod
    def is_available(cls) -> bool:
        return native_engine is not None

    def missing_runtime_files(self) -> list[Path]:
        required_paths = [
            self.config.target_data_file,
            self.config.hub_data_file,
        ]
        return [path for path in required_paths if not path.exists()]

    def is_running(self) -> bool:
        return self._loaded

    def process_running(self) -> bool:
        return False

    def status(self) -> dict:
        if native_engine is None:
            return {
                "engineRunning": False,
                "engineProcessRunning": False,
                "engineState": "native-unavailable",
                "engineMessage": "Native Station Proxy extension is not built or importable.",
                "engineDetails": str(NATIVE_IMPORT_ERROR) if NATIVE_IMPORT_ERROR else None,
                "engineReturnCode": None,
                "missingFiles": [],
            }

        missing_files = [str(path) for path in self.missing_runtime_files()]
        if missing_files:
            return {
                "engineRunning": False,
                "engineProcessRunning": False,
                "engineState": "missing-runtime-files",
                "engineMessage": "Station Proxy is missing required native runtime files.",
                "engineDetails": self._last_start_error,
                "engineReturnCode": None,
                "missingFiles": missing_files,
            }

        if self._loaded:
            return {
                "engineRunning": True,
                "engineProcessRunning": False,
                "engineState": "ready",
                "engineMessage": "Native C++ station engine is loaded in-process.",
                "engineDetails": None,
                "engineReturnCode": None,
                "missingFiles": [],
            }

        return {
            "engineRunning": False,
            "engineProcessRunning": False,
            "engineState": "stopped",
            "engineMessage": "Native C++ station engine has not loaded yet.",
            "engineDetails": self._last_start_error,
            "engineReturnCode": None,
            "missingFiles": [],
        }

    def start(self, wait_until_ready: bool = False) -> None:
        del wait_until_ready
        with self._lock:
            if self._loaded:
                return

            if native_engine is None:
                self._last_start_error = (
                    "Native Station Proxy extension is unavailable. Run "
                    "`make native-engine PYTHON=.venv/bin/python` after installing "
                    "the native optional dependencies."
                )
                raise RuntimeError(self._last_start_error)

            missing_files = self.missing_runtime_files()
            if missing_files:
                missing_list = ", ".join(str(path) for path in missing_files)
                self._last_start_error = (
                    f"Missing required Station Proxy runtime files: {missing_list}"
                )
                raise FileNotFoundError(self._last_start_error)

            engine = native_engine.StationProxyEngine()
            loaded = engine.load(
                str(self.config.target_data_file),
                str(self.config.hub_data_file),
            )
            if not loaded:
                self._last_start_error = "Native Station Proxy engine failed to load data."
                raise RuntimeError(self._last_start_error)

            self._engine = engine
            self._loaded = True
            self._last_start_error = None

    def stop(self) -> None:
        with self._lock:
            self._engine = None
            self._loaded = False

    def query(self, latitude: float, longitude: float) -> dict:
        try:
            self.start(wait_until_ready=True)
        except Exception as error:
            return {
                "status": "error",
                "message": "Failed to start native C++ engine",
                "details": str(error),
                "targetDataFile": str(self.config.target_data_file),
                "hubDataFile": str(self.config.hub_data_file),
            }

        with self._lock:
            try:
                response = self._engine.analyze_location_json(latitude, longitude)
                return json.loads(response)
            except json.JSONDecodeError as error:
                return {
                    "status": "error",
                    "message": "Native C++ engine returned invalid JSON",
                    "details": str(error),
                    "rawOutput": response,
                }
            except Exception as error:
                return {
                    "status": "error",
                    "message": "Communication error with native C++ engine",
                    "details": str(error),
                }
