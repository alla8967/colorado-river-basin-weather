"""Regression tests for public response hardening."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from fastapi import HTTPException

PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / "station-proxy-backend"


def load_backend_module():
    backend_path = str(BACKEND_DIR)
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    module_name = "station_proxy_backend_security_test"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, BACKEND_DIR / "main.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_response_path_sanitizer_redacts_project_and_home_paths() -> None:
    backend = load_backend_module()

    payload = {
        "sourceFile": str(PROJECT_DIR / "Station_Engine_Server" / "station_engine_server"),
        "details": f"Missing file: {PROJECT_DIR / 'NOAA_Inventory_Sort' / 'target.csv'}",
        "outsideFile": "/Users/example/private/secret.csv",
    }

    sanitized = backend.sanitize_response_paths(payload, PROJECT_DIR)
    serialized = json.dumps(sanitized)

    assert str(PROJECT_DIR) not in serialized
    assert "/Users/example" not in serialized
    assert sanitized["sourceFile"] == "Station_Engine_Server/station_engine_server"
    assert "NOAA_Inventory_Sort/target.csv" in sanitized["details"]
    assert sanitized["outsideFile"] == "~/private/secret.csv"


def test_engine_health_payload_does_not_expose_absolute_project_paths() -> None:
    backend = load_backend_module()

    health = backend.test()
    payload = health.model_dump() if hasattr(health, "model_dump") else health.dict()

    assert str(PROJECT_DIR) not in json.dumps(payload)


def test_reliability_bad_inputs_return_422_not_500() -> None:
    backend = load_backend_module()

    class DummyRequest:
        headers = {}

    cases = [
        lambda: backend.reliability_surface(DummyRequest(), layer="../secret"),
        lambda: backend.reliability_service.station_overlay_image_response("overall", "../secret"),
        lambda: backend.reliability_service.station("overall", ""),
    ]

    for case in cases:
        try:
            case()
        except HTTPException as error:
            assert error.status_code == 422
            assert str(PROJECT_DIR) not in json.dumps(error.detail)
        else:
            raise AssertionError("Expected bad public input to raise HTTPException.")


def test_security_headers_are_configured() -> None:
    backend = load_backend_module()

    headers = backend.SECURITY_HEADERS
    assert "Content-Security-Policy" in headers
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_proxy_frontend_escapes_data_derived_markup() -> None:
    results_js = (BACKEND_DIR / "static" / "js" / "results.js").read_text()
    maps_js = (BACKEND_DIR / "static" / "js" / "maps.js").read_text()
    charts_js = (BACKEND_DIR / "static" / "js" / "charts.js").read_text()

    assert "escapeHtml(best.proxyStation.stationName)" in results_js
    assert "escapeHtml(nearest.stationName)" in results_js
    assert "escapeHtml(proxy.stationName)" in maps_js
    assert "escapeHtml(comparisonOptionLabel(option, index, fallbackPrefix))" in charts_js


if __name__ == "__main__":
    test_response_path_sanitizer_redacts_project_and_home_paths()
    test_engine_health_payload_does_not_expose_absolute_project_paths()
    test_reliability_bad_inputs_return_422_not_500()
    test_security_headers_are_configured()
    test_proxy_frontend_escapes_data_derived_markup()
    print("security hardening tests passed")
