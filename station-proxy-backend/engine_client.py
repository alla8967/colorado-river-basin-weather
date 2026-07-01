"""Manage the persistent C++ station proxy engine process used by FastAPI.

The backend keeps this process alive so large NOAA station CSVs are loaded once instead of for every request."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_READY_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True)
class EngineClientConfig:
    """Filesystem contract for the persistent C++ station engine."""

    executable: Path
    server_dir: Path
    target_data_file: Path
    hub_data_file: Path


class EngineClient:
    """Owns the persistent C++ engine process and its line-based protocol."""

    def __init__(self, config: EngineClientConfig) -> None:
        self.config = config
        self._process: Optional[subprocess.Popen] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._ready_event = threading.Event()
        self._stderr_tail: list[str] = []
        self._last_start_error: Optional[str] = None
        self._lock = threading.Lock()

    def is_running(self) -> bool:
        return self.process_running() and self._ready_event.is_set()

    def process_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def ready_timeout_seconds(self) -> float:
        configured_timeout = os.getenv("STATION_PROXY_ENGINE_READY_TIMEOUT_SECONDS", "")

        if configured_timeout == "":
            return DEFAULT_READY_TIMEOUT_SECONDS

        try:
            return float(configured_timeout)
        except ValueError:
            return DEFAULT_READY_TIMEOUT_SECONDS

    def wait_until_ready(self, timeout_seconds: Optional[float] = None) -> bool:
        if self.is_running():
            return True

        if not self.process_running():
            return False

        timeout = self.ready_timeout_seconds() if timeout_seconds is None else timeout_seconds
        return self._ready_event.wait(timeout) and self.process_running()

    def missing_runtime_files(self) -> list[Path]:
        """Return required runtime files that are absent from the local workspace."""
        required_paths = [
            self.config.executable,
            self.config.target_data_file,
            self.config.hub_data_file,
        ]
        return [path for path in required_paths if not path.exists()]

    def status(self) -> dict:
        """Return a frontend-friendly summary of engine loader readiness."""
        missing_files = [str(path) for path in self.missing_runtime_files()]
        return_code = self._process.poll() if self._process is not None else None
        stderr_tail = "\n".join(self._stderr_tail[-6:]) or None

        if missing_files:
            return {
                "engineRunning": False,
                "engineProcessRunning": self.process_running(),
                "engineState": "missing-runtime-files",
                "engineMessage": (
                    "Station Proxy is missing required runtime files before "
                    "the C++ engine can load."
                ),
                "engineDetails": self._last_start_error,
                "engineReturnCode": return_code,
                "missingFiles": missing_files,
            }

        if self._process is None:
            return {
                "engineRunning": False,
                "engineProcessRunning": False,
                "engineState": "stopped",
                "engineMessage": "Station Proxy engine has not started yet.",
                "engineDetails": self._last_start_error,
                "engineReturnCode": None,
                "missingFiles": [],
            }

        if return_code is not None:
            exit_context = "after" if self._ready_event.is_set() else "before"
            return {
                "engineRunning": False,
                "engineProcessRunning": False,
                "engineState": "exited",
                "engineMessage": f"Station Proxy engine exited {exit_context} becoming ready.",
                "engineDetails": stderr_tail or self._last_start_error,
                "engineReturnCode": return_code,
                "missingFiles": [],
            }

        if self._ready_event.is_set():
            return {
                "engineRunning": True,
                "engineProcessRunning": True,
                "engineState": "ready",
                "engineMessage": "Persistent C++ station engine is running and loaded.",
                "engineDetails": None,
                "engineReturnCode": None,
                "missingFiles": [],
            }

        return {
            "engineRunning": False,
            "engineProcessRunning": True,
            "engineState": "loading",
            "engineMessage": "Station Proxy engine is loading NOAA station data.",
            "engineDetails": stderr_tail,
            "engineReturnCode": None,
            "missingFiles": [],
        }

    def start(self, wait_until_ready: bool = False) -> None:
        """Start the engine if it is not already alive."""
        if self.process_running():
            if wait_until_ready and not self.wait_until_ready():
                raise TimeoutError("Station Proxy engine did not become ready before the timeout.")
            return

        self._ready_event.clear()
        self._stderr_tail = []
        missing_files = self.missing_runtime_files()
        if missing_files:
            missing_list = ", ".join(str(path) for path in missing_files)
            self._last_start_error = f"Missing required Station Proxy runtime files: {missing_list}"
            raise FileNotFoundError(self._last_start_error)

        self._process = subprocess.Popen(
            [str(self.config.executable)],
            cwd=str(self.config.server_dir),
            env={
                **os.environ,
                "STATION_PROXY_TARGET_FILE": str(self.config.target_data_file),
                "STATION_PROXY_HUB_FILE": str(self.config.hub_data_file),
            },
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._last_start_error = None

        self._stderr_thread = threading.Thread(
            target=self._drain_stderr,
            args=(self._process,),
            daemon=True,
        )
        self._stderr_thread.start()

        if wait_until_ready and not self.wait_until_ready():
            raise TimeoutError("Station Proxy engine did not become ready before the timeout.")

    def stop(self) -> None:
        """Ask the engine to shut down, then kill it if it does not exit."""
        if self._process is None or self._process.poll() is not None:
            return

        self._ready_event.clear()
        try:
            if self._process.stdin is not None:
                self._process.stdin.write("shutdown\n")
                self._process.stdin.flush()
        except Exception:
            pass

        try:
            self._process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._process.kill()

    def query(self, latitude: float, longitude: float) -> dict:
        """Send one coordinate pair to the C++ engine and parse one JSON reply."""
        with self._lock:
            try:
                self.start(wait_until_ready=True)
            except Exception as error:
                return {
                    "status": "error",
                    "message": "Failed to start persistent C++ engine",
                    "details": str(error),
                    "engineExecutable": str(self.config.executable),
                    "targetDataFile": str(self.config.target_data_file),
                    "hubDataFile": str(self.config.hub_data_file),
                }

            if self._process is None or self._process.poll() is not None:
                return {
                    "status": "error",
                    "message": "Persistent C++ engine is not running",
                    "engineExecutable": str(self.config.executable),
                }

            if self._process.stdin is None or self._process.stdout is None:
                return {
                    "status": "error",
                    "message": "Persistent C++ engine pipes are unavailable",
                }

            try:
                self._process.stdin.write(f"{latitude} {longitude}\n")
                self._process.stdin.flush()

                response_line = self._process.stdout.readline()

                if response_line == "":
                    return {
                        "status": "error",
                        "message": "Persistent C++ engine returned no output",
                    }

                response_line = response_line.strip()

                try:
                    return json.loads(response_line)
                except json.JSONDecodeError as error:
                    return {
                        "status": "error",
                        "message": "Persistent C++ engine returned invalid JSON",
                        "details": str(error),
                        "rawOutput": response_line,
                    }

            except Exception as error:
                return {
                    "status": "error",
                    "message": "Communication error with persistent C++ engine",
                    "details": str(error),
                }

    def _drain_stderr(self, process: subprocess.Popen) -> None:
        """Continuously read engine stderr so the pipe cannot fill and block."""
        if process.stderr is None:
            return

        for line in process.stderr:
            stripped = line.rstrip()
            self._stderr_tail.append(stripped)
            self._stderr_tail = self._stderr_tail[-12:]

            if stripped == "READY":
                self._ready_event.set()

            print(f"[station_engine_server] {stripped}")
