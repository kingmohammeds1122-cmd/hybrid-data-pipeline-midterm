"""ELT transformation, classification, quarantine, and idempotent loads."""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING, MongoClient

from config import settings
from src.quality_rules import QualityResult, clean_record


class ELTPipelineError(RuntimeError):
    """Raised when the ELT pipeline cannot complete safely."""



def create_mongodb_client() -> MongoClient:
    """Create a MongoDB client from central project settings."""

    return MongoClient(
        settings.MONGODB_URI,
        connectTimeoutMS=settings.MONGODB_CONNECT_TIMEOUT_MS,
        serverSelectionTimeoutMS=(
            settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS
        ),
    )



def ensure_final_collection_indexes(database: Any) -> None:
    """Ensure indexes required for final idempotent writes exist."""

    validated_collection = database[settings.ORDERS_VALIDATED_COLLECTION]
    validated_collection.create_index(
        [(settings.ORDER_BUSINESS_KEY, ASCENDING)],
        name="uq_orders_validated_order_id",
        unique=True,
    )

    quarantine_collection = database[
        settings.ORDERS_QUARANTINE_COLLECTION
    ]
    quarantine_collection.create_index(
        [
            (settings.RUN_ID_FIELD, ASCENDING),
            ("source_row_number", ASCENDING),
        ],
        name="uq_quarantine_run_source_row",
        unique=True,
    )



def get_latest_run_id(database: Any) -> str:
    """Return the latest raw run ID according to ingestion time."""

    latest_document = database[settings.ORDERS_RAW_COLLECTION].find_one(
        {},
        projection={settings.RUN_ID_FIELD: 1, "_id": 0},
        sort=[("ingested_at", -1)],
    )

    if not latest_document or not latest_document.get(settings.RUN_ID_FIELD):
        raise ELTPipelineError("No raw records are available for processing.")

    return str(latest_document[settings.RUN_ID_FIELD])



def find_duplicate_order_ids(
    database: Any,
    run_id: str,
) -> set[str]:
    """Find known duplicate business keys within one raw run."""

    raw_collection = database[settings.ORDERS_RAW_COLLECTION]
    duplicate_ids: set[str] = set()
    dollar = "$"

    pipeline = [
        {
            dollar + "match": {
                settings.RUN_ID_FIELD: run_id,
            }
        },
        {
            dollar + "group": {
                "_id": dollar + "raw_record.order_id",
                "count": {dollar + "sum": 1},
            }
        },
        {
            dollar + "match": {
                "_id": {dollar + "ne": None},
                "count": {dollar + "gt": 1},
            }
        },
    ]

    for duplicate in raw_collection.aggregate(pipeline, allowDiskUse=True):
        duplicate_id = duplicate.get("_id")
        if isinstance(duplicate_id, str) and duplicate_id.strip():
            duplicate_ids.add(duplicate_id.strip())

    return duplicate_ids



def build_final_document(
    raw_document: dict[str, Any],
    quality_result: QualityResult,
) -> dict[str, Any]:
    """Build a traceable final document for validated or quarantine storage."""

    return {
        **quality_result.record,
        "run_id": raw_document["run_id"],
        "source_file": raw_document["source_file"],
        "source_row_number": raw_document["source_row_number"],
        "ingested_at": raw_document["ingested_at"],
        "engine_used": raw_document["engine_used"],
        "raw_record": raw_document["raw_record"],
        "quality_status": quality_result.quality_status,
        "corrections": [
            correction.as_dict()
            for correction in quality_result.corrections
        ],
        "error_codes": quality_result.error_codes,
        "error_details": quality_result.error_details,
        "processed_at": datetime.now(timezone.utc),
    }



def process_run(
    run_id: str | None = None,
    progress_interval: int = 5_000,
) -> dict[str, Any]:
    """Process one raw run and perform idempotent final writes."""

    if progress_interval <= 0:
        raise ValueError("progress_interval must be greater than zero.")

    started_performance = time.perf_counter()
    client = create_mongodb_client()

    counts: dict[str, Any] = {
        "raw_records_read": 0,
        "valid_records": 0,
        "corrected_records": 0,
        "quarantined_records": 0,
        "duplicate_records_quarantined": 0,
        "validated_upsert_attempts": 0,
        "quarantine_upsert_attempts": 0,
    }

    try:
        client.admin.command("ping")
        database = client[settings.MONGODB_DATABASE]
        raw_collection = database[settings.ORDERS_RAW_COLLECTION]
        validated_collection = database[
            settings.ORDERS_VALIDATED_COLLECTION
        ]
        quarantine_collection = database[
            settings.ORDERS_QUARANTINE_COLLECTION
        ]

        ensure_final_collection_indexes(database)
        selected_run_id = run_id or get_latest_run_id(database)
        duplicate_order_ids = find_duplicate_order_ids(
            database,
            selected_run_id,
        )

        print(
            "duplicate_order_id_groups="
            f"{len(duplicate_order_ids)}"
        )

        raw_cursor = raw_collection.find(
            {settings.RUN_ID_FIELD: selected_run_id},
            sort=[("source_row_number", 1)],
            batch_size=1000,
        )

        for raw_document in raw_cursor:
            counts["raw_records_read"] += 1
            raw_record = raw_document.get("raw_record")

            if not isinstance(raw_record, dict):
                raise ELTPipelineError(
                    "Raw document does not contain a valid raw_record."
                )

            quality_result = clean_record(raw_record)
            order_id = quality_result.record.get("order_id")

            if (
                isinstance(order_id, str)
                and order_id.strip() in duplicate_order_ids
            ):
                quality_result.error_codes.append("DUPLICATE_ORDER_ID")
                quality_result.error_details.append(
                    "Duplicate order_id requires review and is not merged."
                )
                quality_result.quality_status = "quarantined"
                counts["duplicate_records_quarantined"] += 1

            if quality_result.quality_status == "valid":
                counts["valid_records"] += 1
            elif quality_result.quality_status == "corrected":
                counts["corrected_records"] += 1
            elif quality_result.quality_status == "quarantined":
                counts["quarantined_records"] += 1
            else:
                raise ELTPipelineError(
                    "Unknown quality status returned by quality_rules."
                )

            final_document = build_final_document(
                raw_document=raw_document,
                quality_result=quality_result,
            )

            if quality_result.quality_status == "quarantined":
                quarantine_filter = {
                    "run_id": selected_run_id,
                    "source_row_number": raw_document[
                        "source_row_number"
                    ],
                }
                quarantine_collection.update_one(
                    quarantine_filter,
                    {"$set": final_document},
                    upsert=True,
                )
                counts["quarantine_upsert_attempts"] += 1
            else:
                if not isinstance(order_id, str) or not order_id.strip():
                    raise ELTPipelineError(
                        "A non-quarantined document has no valid order_id."
                    )

                validated_collection.update_one(
                    {"order_id": order_id.strip()},
                    {"$set": final_document},
                    upsert=True,
                )
                counts["validated_upsert_attempts"] += 1

            if counts["raw_records_read"] % progress_interval == 0:
                print(
                    "processed_records="
                    f"{counts['raw_records_read']} "
                    f"run_id={selected_run_id}"
                )

        elapsed_seconds = time.perf_counter() - started_performance
        counts.update(
            {
                "run_id": selected_run_id,
                "duplicate_order_id_groups": len(duplicate_order_ids),
                "elapsed_seconds": round(elapsed_seconds, 6),
                "records_per_second": (
                    round(
                        counts["raw_records_read"] / elapsed_seconds,
                        2,
                    )
                    if elapsed_seconds > 0
                    else 0.0
                ),
            }
        )
        return counts
    finally:
        client.close()



def build_argument_parser() -> argparse.ArgumentParser:
    """Build the ELT command-line interface."""

    parser = argparse.ArgumentParser(
        description="Transform and classify one orders_raw run."
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Raw run ID; latest run is selected when omitted.",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=5_000,
        help="Print progress after this many records.",
    )
    return parser



def main() -> int:
    """Run the ELT pipeline from the command line."""

    parser = build_argument_parser()
    arguments = parser.parse_args()

    try:
        result = process_run(
            run_id=arguments.run_id,
            progress_interval=arguments.progress_interval,
        )
    except (ELTPipelineError, ValueError, OSError) as error:
        parser.error(str(error))
        return 2

    print("ELT transformation and final loading completed successfully")
    for key, value in result.items():
        print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

