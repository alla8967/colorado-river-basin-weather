"""Select the station engine backend implementation."""

from __future__ import annotations

from engine_client import EngineClient, EngineClientConfig
from native_engine_client import NativeEngineClient


VALID_ENGINE_MODES = {"process", "native", "auto"}


def normalize_engine_mode(mode: str) -> str:
    normalized = (mode or "process").strip().lower()
    if normalized not in VALID_ENGINE_MODES:
        return "process"
    return normalized


def build_engine_client(
    config: EngineClientConfig,
    mode: str,
    native_client_class=NativeEngineClient,
    process_client_class=EngineClient,
):
    normalized_mode = normalize_engine_mode(mode)

    if normalized_mode == "native":
        return native_client_class(config)

    if normalized_mode == "auto" and native_client_class.is_available():
        return native_client_class(config)

    return process_client_class(config)
