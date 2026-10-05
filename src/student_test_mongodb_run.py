"""Run the professor's small CSV test through MongoDB safely.

This script uses a separate database and separate collection names. It never
removes or writes to the Midterm database/collections.
"""
from __future__ import annotations

import argparse
import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymongo import ASCENDING, MongoClient

from src.student_test_classifier import classify_student_test_record

TEST_DATABASE = "midterm_student_test"
RAW_COLLECTION = "student_test_orders_raw"
VALIDATED_COLLECTION = "student_test_orders_validated"
QUARANTINE_COLLECTION = "student_test_orders_quarantine"
BATCH_SIZE = 1_000


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def result_to_document(
    result: Any,
    run_id: str,
    source_row: int,
) -> dict[str, Any]:
    """Convert QualityResult into a MongoDB-safe document."""
    document = dict(result.record)
    document.update(
        {
            "run_id": run_id,
            "source_row": source_row,
            "quality_status": result.quality_status,
            "corrections": [
                correction.as_dict()
                for correction in result.corrections
            ],
            "error_codes": result.error_codes,
            "error_details": result.error_details,
            "processed_at": utc_now(),
        }
    )
    return document


def create_indexes(database: Any) -> None:
    """Create indexes only in the separate student-test database."""
    database[RAW_COLLECTION].create_index(
        [("run_id", ASCENDING), ("source_row", ASCENDING)],
        unique=True,
        name="uq_student_test_raw_run_row",
    )
    database[VALIDATED_COLLECTION].create_index(
        [("run_id", ASCENDING), ("order_id", ASCENDING)],
        unique=True,
        name="uq_student_test_validated_run_order",
    )
    database[QUARANTINE_COLLECTION].create_index(
        [("run_id", ASCENDING), ("source_row", ASCENDING)],
        unique=True,
        name="uq_student_test_quarantine_run_row",
    )


def run_test(
    input_file: str | Path,
    reset_test_database: bool = False,
) -> dict[str, Any]:
    """Load, classify, and persist one isolated student-test run."""
    input_path = Path(input_file)
    run_id = str(uuid.uuid4())

    client = MongoClient(
        "mongodb://localhost:27017",
        serverSelectionTimeoutMS=10_000,
    )

    try:
        client.admin.command("ping")
        database = client[TEST_DATABASE]

        if reset_test_database:
            # This only affects the separate test database.
            database.drop_collection(RAW_COLLECTION)
            database.drop_collection(VALIDATED_COLLECTION)
            database.drop_collection(QUARANTINE_COLLECTION)

        create_indexes(database)

        raw_collection = database[RAW_COLLECTION]
        validated_collection = database[VALIDATED_COLLECTION]
        quarantine_collection = database[QUARANTINE_COLLECTION]

        raw_batch: list[dict[str, Any]] = []
        validated_batch: list[dict[str, Any]] = []
        quarantine_batch: list[dict[str, Any]] = []

        input_rows = 0
        clean_valid = 0
        corrected = 0
        quarantined = 0

        def flush() -> None:
            if raw_batch:
                raw_collection.insert_many(raw_batch, ordered=False)
                raw_batch.clear()
            if validated_batch:
                validated_collection.insert_many(
                    validated_batch,
                    ordered=False,
                )
                validated_batch.clear()
            if quarantine_batch:
                quarantine_collection.insert_many(
                    quarantine_batch,
                    ordered=False,
                )
                quarantine_batch.clear()

        with input_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as csv_file:
            reader = csv.DictReader(csv_file)

            for source_row, raw_record in enumerate(reader, start=1):
                input_rows += 1

                raw_document = dict(raw_record)
                raw_document.update(
                    {
                        "run_id": run_id,
                        "source_row": source_row,
                        "ingested_at": utc_now(),
                    }
                )
                raw_batch.append(raw_document)

                quality_result = classify_student_test_record(raw_record)
                final_document = result_to_document(
                    quality_result,
                    run_id,
                    source_row,
                )

                if quality_result.quality_status == "valid":
                    clean_valid += 1
                    validated_batch.append(final_document)
                elif quality_result.quality_status == "corrected":
                    corrected += 1
                    validated_batch.append(final_document)
                else:
                    quarantined += 1
                    quarantine_batch.append(final_document)

                if len(raw_batch) >= BATCH_SIZE:
                    flush()

        flush()

        validated = clean_valid + corrected
        consistency = validated + quarantined

        report = {
            "run_id": run_id,
            "database": TEST_DATABASE,
            "collections": {
                "raw": RAW_COLLECTION,
                "validated": VALIDATED_COLLECTION,
                "quarantine": QUARANTINE_COLLECTION,
            },
            "input_file": input_path.name,
            "input_rows": input_rows,
            "clean_valid": clean_valid,
            "corrected": corrected,
            "validated": validated,
            "quarantined": quarantined,
            "consistency": consistency,
            "conservation_pass": consistency == input_rows,
            "expected_reference": {
                "input_rows": 20_000,
                "clean_valid": 12_000,
                "corrected": 5_000,
                "validated": 17_000,
                "quarantined": 3_000,
                "consistency": 20_000,
            },
        }

        return report

    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the professor's CSV in an isolated MongoDB database."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to 01_student_test_small.csv",
    )
    parser.add_argument(
        "--reset-test-database",
        action="store_true",
        help=(
            "Drop only the three student-test collections before running. "
            "Never touches the Midterm database."
        ),
    )
    parser.add_argument(
        "--report",
        default="reports/student_test_mongodb_report.json",
        help="Output JSON report path.",
    )
    args = parser.parse_args()

    report = run_test(
        args.input,
        reset_test_database=args.reset_test_database,
    )

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report_path: {report_path}")


if __name__ == "__main__":
    main()
