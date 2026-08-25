"""Central configuration for the hybrid orders data pipeline."""

from __future__ import annotations

import os
from pathlib import Path


# Project paths
PROJECT_ROOT: Path = Path(r"D:\midterm-data-pipeline")

SOURCE_DATA_FILE: Path = Path(
    r"C:\Big Data\orders_huge_mixed_quality.csv"
)

SAMPLE_DATA_FILE: Path = (
    PROJECT_ROOT / "data" / "sample" / "orders_sample.csv"
)

REPORTS_DIRECTORY: Path = PROJECT_ROOT / "reports"
RESULTS_FILE: Path = REPORTS_DIRECTORY / "results.json"
LOGS_DIRECTORY: Path = PROJECT_ROOT / "logs"


# File-router and processing settings
SMALL_FILE_THRESHOLD_MB: int = 200
DEFAULT_SAMPLE_ROWS: int = 100_000
BATCH_SIZE: int = 5_000

CSV_ENCODING: str = "utf-8-sig"
CSV_NEWLINE: str = ""


# MongoDB settings
MONGODB_URI: str = os.getenv(
    "MONGODB_URI",
    "mongodb://localhost:27017",
)

MONGODB_DATABASE: str = os.getenv(
    "MONGODB_DATABASE",
    "midterm_data_pipeline",
)

MONGODB_CONNECT_TIMEOUT_MS: int = int(
    os.getenv("MONGODB_CONNECT_TIMEOUT_MS", "5000")
)

MONGODB_SERVER_SELECTION_TIMEOUT_MS: int = int(
    os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "5000")
)


# Required MongoDB collection names
ORDERS_RAW_COLLECTION: str = "orders_raw"
ORDERS_VALIDATED_COLLECTION: str = "orders_validated"
ORDERS_QUARANTINE_COLLECTION: str = "orders_quarantine"


# Stable business key and metadata fields
ORDER_BUSINESS_KEY: str = "order_id"
RUN_ID_FIELD: str = "run_id"
SOURCE_FILE_FIELD: str = "source_file"
ENGINE_USED_FIELD: str = "engine_used"
QUALITY_STATUS_FIELD: str = "quality_status"
CORRECTIONS_FIELD: str = "corrections"
ERROR_CODES_FIELD: str = "error_codes"
ERROR_DETAILS_FIELD: str = "error_details"
RAW_RECORD_FIELD: str = "raw_record"

SUPPORTED_ENGINES: tuple[str, str] = (
    "python_batch",
    "pyspark",
)

QUALITY_STATUSES: tuple[str, str, str] = (
    "valid",
    "corrected",
    "quarantined",
)


def ensure_runtime_directories() -> None:
    """Create directories required for runtime outputs."""

    REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    LOGS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    SAMPLE_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)


def validate_configuration() -> None:
    """Validate mandatory configuration values."""

    if SMALL_FILE_THRESHOLD_MB <= 0:
        raise ValueError(
            "SMALL_FILE_THRESHOLD_MB must be greater than zero."
        )

    if DEFAULT_SAMPLE_ROWS <= 0:
        raise ValueError(
            "DEFAULT_SAMPLE_ROWS must be greater than zero."
        )

    if BATCH_SIZE <= 0:
        raise ValueError("BATCH_SIZE must be greater than zero.")

    if not MONGODB_URI.strip():
        raise ValueError("MONGODB_URI must not be empty.")

    if not MONGODB_DATABASE.strip():
        raise ValueError("MONGODB_DATABASE must not be empty.")

    expected_collections = {
        ORDERS_RAW_COLLECTION,
        ORDERS_VALIDATED_COLLECTION,
        ORDERS_QUARANTINE_COLLECTION,
    }

    required_collections = {
        "orders_raw",
        "orders_validated",
        "orders_quarantine",
    }

    if expected_collections != required_collections:
        raise ValueError(
            "MongoDB collection names do not match the assignment."
        )


ensure_runtime_directories()
validate_configuration()

# Path B incremental-loading settings
DELTA_DIRECTORY: Path = PROJECT_ROOT / "data" / "delta"
INCREMENTAL_STATE_FILE: Path = REPORTS_DIRECTORY / "incremental_state.json"
INCREMENTAL_BATCH_SIZE: int = 5000
INCREMENTAL_VERSION_FIELD: str = "record_version"
INCREMENTAL_UPDATED_AT_FIELD: str = "updated_at"
INCREMENTAL_OPERATION_FIELD: str = "operation"
