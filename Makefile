# Purpose: Project build, test, run, and cleanup targets for local review workflows.

CXX = g++
CXXFLAGS = -std=c++17 -O2 -DNDEBUG -I"C++_Weather_Station_Proxy_Engine"
PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
UVICORN ?= $(PYTHON) -m uvicorn
PYCACHE_PREFIX ?= /tmp/crb_pycache

ENGINE_DIR = C++_Weather_Station_Proxy_Engine
SERVER_DIR = Station_Engine_Server
BACKEND_DIR = station-proxy-backend
PROJECT_ABS = $(abspath .)
FIXTURE_TARGET_FILE = $(PROJECT_ABS)/tests/fixtures/target_daily_app_ready.csv
FIXTURE_HUB_FILE = $(PROJECT_ABS)/tests/fixtures/hub_daily_app_ready.csv

SERVER_TARGET = $(SERVER_DIR)/station_engine_server
API_TARGET = station_engine_api
TEST_API_TARGET = station_engine_api_test
VALIDATE_PREDICTION_TARGET = validate_prediction_similarity
FRONTEND_JS_FILES = $(wildcard $(BACKEND_DIR)/static/js/*.js)

COMPILED_OUTPUTS = \
	$(SERVER_TARGET) \
	$(API_TARGET) \
	$(TEST_API_TARGET) \
	$(VALIDATE_PREDICTION_TARGET) \
	$(ENGINE_DIR)/basin_test \
	$(ENGINE_DIR)/station_engine_api \
	NOAA_Inventory_Sort/noaa_inventory_sort \
	$(BACKEND_DIR)/test_engine

LOCAL_CACHE_DIRS = \
	.pytest_cache \
	build/pycache

PYTHON_COMPILE_FILES = \
	$(BACKEND_DIR)/main.py \
	$(BACKEND_DIR)/settings.py \
	$(BACKEND_DIR)/engine_client.py \
	$(BACKEND_DIR)/api_models.py \
	$(BACKEND_DIR)/confidence_service.py \
	$(BACKEND_DIR)/model_run_service.py \
	$(BACKEND_DIR)/reliability_service.py \
	weather_reconstruction_model/scripts/evaluate_final_model_station_metrics.py \
	weather_reconstruction_model/scripts/build_holdout_baseline_comparison.py \
	tests/test_app_shell.py \
	tests/test_reliability_backend.py

COMMON_ENGINE_SOURCES = \
	$(ENGINE_DIR)/STATION_PROXY_ENGINE.cpp \
	$(ENGINE_DIR)/csv_filereader.cpp \
	$(ENGINE_DIR)/seasonal_analysis.cpp \
	$(ENGINE_DIR)/similarity_scores.cpp \
	$(ENGINE_DIR)/station_dataset.cpp \
	$(ENGINE_DIR)/station_distance.cpp \
	$(ENGINE_DIR)/station_matcher.cpp \
	$(ENGINE_DIR)/station_pair_score.cpp \
	$(ENGINE_DIR)/station_locator.cpp

SERVER_SOURCES = \
	$(SERVER_DIR)/station_engine_server.cpp \
	$(COMMON_ENGINE_SOURCES)

API_SOURCES = \
	$(ENGINE_DIR)/api_main.cpp \
	$(COMMON_ENGINE_SOURCES)

VALIDATE_PREDICTION_SOURCES = \
	$(ENGINE_DIR)/validate_prediction_similarity.cpp \
	$(ENGINE_DIR)/csv_filereader.cpp \
	$(ENGINE_DIR)/seasonal_analysis.cpp \
	$(ENGINE_DIR)/similarity_scores.cpp \
	$(ENGINE_DIR)/station_dataset.cpp

.PHONY: all setup setup-backend setup-model server api validate-prediction check check-js check-python-compile test test-engine test-app-shell test-reliability-backend test-python bootstrap-fixture run run-api run-backend run-backend-fixture doctor clean clean-local-artifacts

all: server api

setup:
	$(PIP) install -e ".[model,terrain,dev]"

setup-backend:
	$(PIP) install -e ".[dev]"

setup-model:
	$(PIP) install -e ".[model,terrain,dev]"

server:
	$(CXX) $(CXXFLAGS) $(SERVER_SOURCES) -o "$(SERVER_TARGET)"

api:
	$(CXX) $(CXXFLAGS) $(API_SOURCES) -o "$(API_TARGET)"

validate-prediction:
	$(CXX) $(CXXFLAGS) $(VALIDATE_PREDICTION_SOURCES) -o "$(VALIDATE_PREDICTION_TARGET)"

check: check-js check-python-compile test-app-shell test-reliability-backend test-engine validate-prediction

check-js:
	@for file in $(FRONTEND_JS_FILES); do \
		node --check "$$file" || exit 1; \
	done

check-python-compile:
	PYTHONPYCACHEPREFIX="$(PYCACHE_PREFIX)" $(PYTHON) -m py_compile $(PYTHON_COMPILE_FILES)

test: test-engine test-app-shell test-reliability-backend test-python

test-engine:
	$(PYTHON) tests/test_engine_fixture.py

test-app-shell:
	$(PYTHON) tests/test_app_shell.py

test-reliability-backend:
	$(PYTHON) tests/test_reliability_backend.py

test-python:
	$(PYTHON) -m pytest weather_reconstruction_model/scripts/tests

bootstrap-fixture: server test-engine check-python-compile test-app-shell test-reliability-backend
	@echo "Fixture bootstrap passed."
	@echo "Run the fixture app with: make run-backend-fixture"

run: server
	cd $(SERVER_DIR) && ./station_engine_server

run-api: api
	./$(API_TARGET) 39.75 -105.0

run-backend: server
	cd $(BACKEND_DIR) && $(UVICORN) main:app --reload

run-backend-fixture: server
	cd $(BACKEND_DIR) && \
	STATION_PROXY_TARGET_FILE="$(FIXTURE_TARGET_FILE)" \
	STATION_PROXY_HUB_FILE="$(FIXTURE_HUB_FILE)" \
	$(UVICORN) main:app --reload

doctor:
	$(PYTHON) weather_reconstruction_model/scripts/audit_project_readiness.py
	$(PYTHON) weather_reconstruction_model/scripts/check_remote_environment.py

clean:
	rm -f $(COMPILED_OUTPUTS)

clean-local-artifacts: clean
	rm -rf $(LOCAL_CACHE_DIRS)
