"""ELT transformation, classification, quarantine, and idempotent writes."""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING, MongoClient

from config import settings
from src.quality_rules import QualityResult, clean_record
from src.schema_validation import validate_final_document, validate_raw_record


class ELTPipelineError(RuntimeError):
    """Raised when the ELT pipeline cannot finish safely."""


def create_mongodb_client() -> MongoClient:
    return MongoClient(
        settings.MONGODB_URI,
        connectTimeoutMS=settings.MONGODB_CONNECT_TIMEOUT_MS,
        serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
    )


def classify_record(raw_record: dict[str, Any]) -> QualityResult:
    """Use the professor classifier only for the isolated student-test profile."""
    if settings.PIPELINE_PROFILE == "student-test":
        from src.student_test_classifier import classify_student_test_record
        return classify_student_test_record(raw_record)
    return clean_record(raw_record)


def ensure_final_collection_indexes(database: Any) -> None:
    database[settings.ORDERS_VALIDATED_COLLECTION].create_index(
        [(settings.ORDER_BUSINESS_KEY, ASCENDING)],
        name="uq_orders_validated_order_id",
        unique=True,
    )
    database[settings.ORDERS_QUARANTINE_COLLECTION].create_index(
        [(settings.RUN_ID_FIELD, ASCENDING), ("source_row_number", ASCENDING)],
        name="uq_quarantine_run_source_row",
        unique=True,
    )


def get_latest_run_id(database: Any) -> str:
    latest = database[settings.ORDERS_RAW_COLLECTION].find_one(
        {}, projection={settings.RUN_ID_FIELD: 1, "_id": 0}, sort=[("ingested_at", -1)]
    )
    if not latest or not latest.get(settings.RUN_ID_FIELD):
        raise ELTPipelineError("No raw records are available for processing.")
    return str(latest[settings.RUN_ID_FIELD])


def build_final_document(raw_document: dict[str, Any], quality_result: QualityResult) -> dict[str, Any]:
    document = {
        **quality_result.record,
        "run_id": raw_document["run_id"],
        "source_file": raw_document["source_file"],
        "source_row_number": raw_document["source_row_number"],
        "ingested_at": raw_document["ingested_at"],
        "engine_used": raw_document["engine_used"],
        "raw_record": raw_document["raw_record"],
        "quality_status": quality_result.quality_status,
        "corrections": [c.as_dict() for c in quality_result.corrections],
        "error_codes": list(quality_result.error_codes),
        "error_details": list(quality_result.error_details),
        "processed_at": datetime.now(timezone.utc),
    }
    return document


def process_run(run_id: str | None = None, progress_interval: int = 5_000) -> dict[str, Any]:
    if progress_interval <= 0:
        raise ValueError("progress_interval must be greater than zero.")

    started = time.perf_counter()
    client = create_mongodb_client()
    counts: dict[str, Any] = {
        "raw_records_read": 0,
        "valid_records": 0,
        "corrected_records": 0,
        "quarantined_records": 0,
        "validated_upsert_attempts": 0,
        "quarantine_upsert_attempts": 0,
    }

    try:
        client.admin.command("ping")
        database = client[settings.MONGODB_DATABASE]
        raw_collection = database[settings.ORDERS_RAW_COLLECTION]
        validated_collection = database[settings.ORDERS_VALIDATED_COLLECTION]
        quarantine_collection = database[settings.ORDERS_QUARANTINE_COLLECTION]
        ensure_final_collection_indexes(database)
        selected_run_id = run_id or get_latest_run_id(database)

        cursor = raw_collection.find(
            {settings.RUN_ID_FIELD: selected_run_id},
            sort=[("source_row_number", 1)],
            batch_size=1000,
        )

        for raw_document in cursor:
            counts["raw_records_read"] += 1
            source_row = int(raw_document.get("source_row_number", 0))
            raw_record = raw_document.get("raw_record")
            if not isinstance(raw_record, dict):
                raise ELTPipelineError(f"Raw record is not an object at row {source_row}.")
            validate_raw_record(raw_record, source_row)

            quality_result = classify_record(raw_record)
            final_document = build_final_document(raw_document, quality_result)
            validate_final_document(final_document, source_row)

            if quality_result.quality_status == "valid":
                counts["valid_records"] += 1
            elif quality_result.quality_status == "corrected":
                counts["corrected_records"] += 1
            elif quality_result.quality_status == "quarantined":
                counts["quarantined_records"] += 1
            else:
                raise ELTPipelineError(f"Unknown quality status at row {source_row}.")

            if quality_result.quality_status == "quarantined":
                quarantine_collection.update_one(
                    {"run_id": selected_run_id, "source_row_number": source_row},
                    {"$set": final_document},
                    upsert=True,
                )
                counts["quarantine_upsert_attempts"] += 1
            else:
                order_id = final_document.get("order_id")
                if not isinstance(order_id, str) or not order_id.strip():
                    raise ELTPipelineError(f"Non-quarantined record has no order_id at row {source_row}.")
                validated_collection.update_one(
                    {"order_id": order_id.strip()},
                    {"$set": final_document},
                    upsert=True,
                )
                counts["validated_upsert_attempts"] += 1

            if counts["raw_records_read"] % progress_interval == 0:
                print(f"processed_records={counts['raw_records_read']} run_id={selected_run_id}")

        elapsed = time.perf_counter() - started
        counts.update({
            "run_id": selected_run_id,
            "profile": settings.PIPELINE_PROFILE,
            "database": settings.MONGODB_DATABASE,
            "elapsed_seconds": round(elapsed, 6),
            "records_per_second": round(counts["raw_records_read"] / elapsed, 2) if elapsed else 0.0,
        })
        return counts
    finally:
        client.close()


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Transform and classify one orders_raw run.")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--progress-interval", type=int, default=5_000)
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()
    try:
        result = process_run(args.run_id, args.progress_interval)
    except (ELTPipelineError, ValueError, OSError) as error:
        parser.error(str(error))
        return 2
    for key, value in result.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
