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
        self._lock = threading.Lock()

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self) -> None:
        """Start the engine if it is not already alive."""
        if self.is_running():
            return

        if not self.config.executable.exists():
            raise FileNotFoundError(
                f"Could not find persistent C++ engine executable: {self.config.executable}"
            )

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

        self._stderr_thread = threading.Thread(
            target=self._drain_stderr,
            args=(self._process,),
            daemon=True,
        )
        self._stderr_thread.start()

    def stop(self) -> None:
        """Ask the engine to shut down, then kill it if it does not exit."""
        if self._process is None or self._process.poll() is not None:
            return

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
                self.start()
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
            print(f"[station_engine_server] {line.rstrip()}")
