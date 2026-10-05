"""Central configuration for the hybrid orders data pipeline."""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", r"D:\midterm-data-pipeline"))
SOURCE_DATA_FILE = Path(os.getenv(
    "PIPELINE_INPUT_FILE",
    r"C:\Big Data\orders_huge_mixed_quality.csv",
))
SAMPLE_DATA_FILE = PROJECT_ROOT / "data" / "sample" / "orders_sample.csv"
REPORTS_DIRECTORY = PROJECT_ROOT / "reports"
RESULTS_FILE = REPORTS_DIRECTORY / "results.json"
LOGS_DIRECTORY = PROJECT_ROOT / "logs"

PIPELINE_PROFILE = os.getenv("PIPELINE_PROFILE", "midterm").strip().lower()

SMALL_FILE_THRESHOLD_MB = int(os.getenv("SMALL_FILE_THRESHOLD_MB", "200"))
DEFAULT_SAMPLE_ROWS = int(os.getenv("DEFAULT_SAMPLE_ROWS", "100000"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5000"))
CSV_ENCODING = os.getenv("CSV_ENCODING", "utf-8-sig")
CSV_NEWLINE = os.getenv("CSV_NEWLINE", "")

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "midterm_data_pipeline")
MONGODB_CONNECT_TIMEOUT_MS = int(os.getenv("MONGODB_CONNECT_TIMEOUT_MS", "5000"))
MONGODB_SERVER_SELECTION_TIMEOUT_MS = int(os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "5000"))

ORDERS_RAW_COLLECTION = os.getenv("ORDERS_RAW_COLLECTION", "orders_raw")
ORDERS_VALIDATED_COLLECTION = os.getenv("ORDERS_VALIDATED_COLLECTION", "orders_validated")
ORDERS_QUARANTINE_COLLECTION = os.getenv("ORDERS_QUARANTINE_COLLECTION", "orders_quarantine")

ORDER_BUSINESS_KEY = "order_id"
RUN_ID_FIELD = "run_id"
SOURCE_FILE_FIELD = "source_file"
ENGINE_USED_FIELD = "engine_used"
QUALITY_STATUS_FIELD = "quality_status"
CORRECTIONS_FIELD = "corrections"
ERROR_CODES_FIELD = "error_codes"
ERROR_DETAILS_FIELD = "error_details"
RAW_RECORD_FIELD = "raw_record"

SUPPORTED_ENGINES = ("python_batch", "pyspark")
QUALITY_STATUSES = ("valid", "corrected", "quarantined")

DELTA_DIRECTORY = PROJECT_ROOT / "data" / "delta"
INCREMENTAL_STATE_FILE = REPORTS_DIRECTORY / "incremental_state.json"
INCREMENTAL_BATCH_SIZE = int(os.getenv("INCREMENTAL_BATCH_SIZE", "5000"))
INCREMENTAL_VERSION_FIELD = "record_version"
INCREMENTAL_UPDATED_AT_FIELD = "updated_at"
INCREMENTAL_OPERATION_FIELD = "operation"


def ensure_runtime_directories() -> None:
    REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    LOGS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    SAMPLE_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)


def validate_configuration() -> None:
    if SMALL_FILE_THRESHOLD_MB <= 0:
        raise ValueError("SMALL_FILE_THRESHOLD_MB must be greater than zero.")
    if DEFAULT_SAMPLE_ROWS <= 0:
        raise ValueError("DEFAULT_SAMPLE_ROWS must be greater than zero.")
    if BATCH_SIZE <= 0:
        raise ValueError("BATCH_SIZE must be greater than zero.")
    if not MONGODB_URI.strip():
        raise ValueError("MONGODB_URI must not be empty.")
    if not MONGODB_DATABASE.strip():
        raise ValueError("MONGODB_DATABASE must not be empty.")
    if PIPELINE_PROFILE not in {"midterm", "student-test"}:
        raise ValueError("PIPELINE_PROFILE must be 'midterm' or 'student-test'.")


ensure_runtime_directories()
validate_configuration()
