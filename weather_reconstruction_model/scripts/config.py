"""Define shared project paths and default artifact locations for reconstruction scripts.

Scripts import this module so generated inputs, outputs, caches, and model runs resolve consistently."""

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / "NOAA_Inventory_Sort"
OUTPUT_DIR = PROJECT_DIR / "weather_reconstruction_model" / "outputs"
CACHE_DIR = PROJECT_DIR / "weather_reconstruction_model" / "cache"
MODEL_RUN_DIR = PROJECT_DIR / "weather_reconstruction_model" / "model_runs"

TRAINING_TABLE_DIR = OUTPUT_DIR / "training_tables"
PREDICTION_DIR = OUTPUT_DIR / "predictions"
VALIDATION_DIR = OUTPUT_DIR / "validation"
REPORT_DIR = OUTPUT_DIR / "reports"
GENERAL_TABLE_DIR = OUTPUT_DIR / "general_training_tables"
TERRAIN_FEATURE_FILE = PROJECT_DIR / "terrain_data" / "processed" / "station_terrain_features.csv"
WEATHER_CACHE_FILE = CACHE_DIR / "weather_data.sqlite"

TARGET_CANDIDATE_FILE = DATA_DIR / "target_station_candidates.csv"
HUB_CANDIDATE_FILE = DATA_DIR / "hub_station_candidates.csv"
TARGET_DAILY_FILE = DATA_DIR / "target_daily_app_ready.csv"
HUB_DAILY_FILE = DATA_DIR / "hub_daily_app_ready.csv"

DEFAULT_TARGET_STATION_ID = "USC00052223"
DEFAULT_TARGET_LIMIT = 25
DEFAULT_HUB_COUNT = 5
DEFAULT_TRAIN_END_YEAR = 2023
DEFAULT_TEST_START_YEAR = 2024
DEFAULT_ALPHA = 0.0

MIN_OVERLAP_PERCENT = 90.0
MIN_OVERLAP_DAYS = 1000
MAX_ELEVATION_DIFFERENCE_M = 500.0

MIN_SHARED_DAYS = 1000
MIN_TEST_DAYS = 365

PASS_MAX_MAE = 2.5
PASS_MAX_RMSE = 3.5
PASS_MIN_CORRELATION = 0.95

BORDERLINE_MAX_MAE = 3.5
BORDERLINE_MAX_RMSE = 4.5
BORDERLINE_MIN_CORRELATION = 0.90

ML_GOAL_MAX_MAE = 1.5
ML_GOAL_MAX_RMSE = 2.0
ML_GOAL_MIN_CORRELATION = 0.985
ML_GOAL_PASS_RATE = 0.80
