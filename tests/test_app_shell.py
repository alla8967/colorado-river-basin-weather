"""Smoke-test the HTML shell and static frontend references served by FastAPI.

The test catches broken script/style links and missing reliability controls before browser testing."""

import importlib.util
import re
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / "station-proxy-backend"
STATIC_REF_RE = re.compile(r"""["'](?P<path>/(?:static|assets)/[^"']+)["']""")
JS_IMPORT_RE = re.compile(r"""import\s+(?:[^"']+\s+from\s+)?["'](?P<path>\./[^"']+)["']""")


def load_backend_module():
    backend_path = str(BACKEND_DIR)
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    module_name = "station_proxy_backend_main"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, BACKEND_DIR / "main.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_app_shell_serves_html_and_static_assets():
    backend = load_backend_module()

    response = backend.home()
    html_path = Path(response.path)
    html = html_path.read_text()

    assert html_path == BACKEND_DIR / "index.html"
    assert "/static/styles.css" in html
    assert 'type="module" src="/static/js/main.js' in html
    assert 'id="reliability-map-mode-select"' in html
    assert "<option value=\"mae\">Holdout MAE</option>" in html
    assert "<option value=\"rmse\">Holdout RMSE</option>" in html
    assert "<option value=\"bias\">Holdout Bias</option>" in html
    assert "Show Stations" in html
    assert "Model Support" not in html
    assert "model-support-tab" not in html
    assert "confidence-map" not in html

    styles = (BACKEND_DIR / "static" / "styles.css").read_text()
    main_js = (BACKEND_DIR / "static" / "js" / "main.js").read_text()
    api_js = (BACKEND_DIR / "static" / "js" / "api.js").read_text()

    assert "engine-status" in styles
    assert "mode-description" in styles
    assert "fetchEngineStatus" in main_js
    assert "missing-runtime-files" in main_js
    assert "Missing required runtime files" in main_js
    assert "stationDataNotice" in main_js
    assert "initializeReliabilityMap" in main_js
    assert "initializeConfidenceMap" not in main_js
    assert 'fetchFirstJson("/test")' in api_js
    assert "fetchFirstJson(`/analyze-location?${query}`)" in api_js
    assert "http://127.0.0.1:8000" in api_js


def test_engine_health_reports_loader_state_without_starting_engine():
    backend = load_backend_module()

    health = backend.test()
    payload = health.model_dump() if hasattr(health, "model_dump") else health.dict()

    assert payload["engineState"] in {
        "missing-runtime-files",
        "stopped",
        "loading",
        "ready",
        "exited",
    }
    assert isinstance(payload["engineRunning"], bool)
    assert isinstance(payload["engineProcessRunning"], bool)
    assert isinstance(payload["missingFiles"], list)
    assert payload["engineMessage"]
    assert payload["stationDataMode"] in {"full-noaa", "configured", "demo-fixture"}
    assert isinstance(payload["stationDataNotice"], str)


def test_frontend_asset_graph_points_to_existing_files():
    html = (BACKEND_DIR / "index.html").read_text()

    referenced_paths = {
        match.group("path").split("?", 1)[0].split("#", 1)[0]
        for match in STATIC_REF_RE.finditer(html)
    }

    assert "/static/styles.css" in referenced_paths
    assert "/static/js/main.js" in referenced_paths

    missing_assets = [
        path for path in sorted(referenced_paths)
        if not (BACKEND_DIR / path.lstrip("/")).exists()
    ]
    assert missing_assets == []

    missing_modules = []
    for js_file in sorted((BACKEND_DIR / "static" / "js").glob("*.js")):
        source = js_file.read_text()
        for match in JS_IMPORT_RE.finditer(source):
            import_path = match.group("path").split("?", 1)[0].split("#", 1)[0]
            imported_path = (js_file.parent / import_path).resolve()
            if not imported_path.exists():
                missing_modules.append(f"{js_file.name} -> {match.group('path')}")

    assert missing_modules == []


def test_openapi_exposes_expected_app_routes():
    backend = load_backend_module()
    route_paths = {route.path for route in backend.app.routes}

    expected_paths = {
        "/",
        "/index.html",
        "/test",
        "/model-runs/current",
        "/model-runs/current/confidence-grid",
        "/model-runs/reliability/summary",
        "/model-runs/reliability/surface",
        "/model-runs/reliability/surface.png",
        "/model-runs/reliability/station-overlay.png",
        "/model-runs/reliability/sample",
        "/model-runs/reliability/station",
        "/run-engine",
        "/analyze-location",
        "/analyze-confidence",
        "/assets",
        "/static",
    }

    assert expected_paths <= route_paths


if __name__ == "__main__":
    test_app_shell_serves_html_and_static_assets()
    test_frontend_asset_graph_points_to_existing_files()
    test_openapi_exposes_expected_app_routes()
    print("App shell smoke test passed.")
