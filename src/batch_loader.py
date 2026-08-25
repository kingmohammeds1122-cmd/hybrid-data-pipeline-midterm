"""Streaming Python Batch loader for the orders_raw MongoDB collection."""

from __future__ import annotations

import argparse
import csv
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pymongo import MongoClient

from config import settings


def create_mongodb_client() -> MongoClient:
    """Create a MongoDB client from the central configuration."""

    return MongoClient(
        settings.MONGODB_URI,
        connectTimeoutMS=settings.MONGODB_CONNECT_TIMEOUT_MS,
        serverSelectionTimeoutMS=(
            settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS
        ),
    )


def load_csv_to_raw(
    input_file: Path,
    batch_size: int,
) -> dict[str, Any]:
    """Load every CSV row into orders_raw without cleaning or conversion."""

    if not input_file.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_file}")

    if not input_file.is_file():
        raise ValueError(f"Input path is not a regular file: {input_file}")

    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero.")

    run_id = str(uuid4())
    source_file = str(input_file.resolve())
    started_at = datetime.now(timezone.utc)
    started_performance = time.perf_counter()
    total_records = 0
    total_batches = 0
    batch: list[dict[str, Any]] = []

    client = create_mongodb_client()

    try:
        client.admin.command("ping")
        database = client[settings.MONGODB_DATABASE]
        raw_collection = database[settings.ORDERS_RAW_COLLECTION]

        with input_file.open(
            mode="r",
            encoding=settings.CSV_ENCODING,
            newline=settings.CSV_NEWLINE,
        ) as file_handle:
            reader = csv.DictReader(file_handle)

            if not reader.fieldnames:
                raise ValueError("The input CSV has no header row.")

            for source_row_number, csv_record in enumerate(reader, start=2):
                raw_record = {
                    key: value for key, value in csv_record.items()
                }

                raw_document: dict[str, Any] = {
                    "run_id": run_id,
                    "source_file": source_file,
                    "source_row_number": source_row_number,
                    "ingested_at": started_at,
                    "engine_used": "python_batch",
                    "raw_record": raw_record,
                }

                batch.append(raw_document)

                if len(batch) >= batch_size:
                    raw_collection.insert_many(batch, ordered=False)
                    total_records += len(batch)
                    total_batches += 1
                    print(
                        f"batch={total_batches} "
                        f"records={len(batch)} "
                        f"total_records={total_records}"
                    )
                    batch.clear()

            if batch:
                raw_collection.insert_many(batch, ordered=False)
                total_records += len(batch)
                total_batches += 1
                print(
                    f"batch={total_batches} "
                    f"records={len(batch)} "
                    f"total_records={total_records}"
                )

        elapsed_seconds = time.perf_counter() - started_performance

        return {
            "run_id": run_id,
            "source_file": source_file,
            "engine_used": "python_batch",
            "records_loaded": total_records,
            "batches_inserted": total_batches,
            "batch_size": batch_size,
            "elapsed_seconds": round(elapsed_seconds, 6),
            "records_per_second": (
                round(total_records / elapsed_seconds, 2)
                if elapsed_seconds > 0
                else 0.0
            ),
        }
    finally:
        client.close()


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""

    parser = argparse.ArgumentParser(
        description="Stream a CSV file into the orders_raw collection."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=settings.SAMPLE_DATA_FILE,
        help="Path to the input CSV file.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=settings.BATCH_SIZE,
        help="Number of records per insert_many operation.",
    )
    return parser


def main() -> int:
    """Run the Python Batch raw loader."""

    parser = build_argument_parser()
    arguments = parser.parse_args()

    try:
        result = load_csv_to_raw(
            input_file=arguments.input,
            batch_size=arguments.batch_size,
        )
    except (FileNotFoundError, ValueError, OSError) as error:
        parser.error(str(error))
        return 2

    print("Python Batch raw loading completed successfully")
    for key, value in result.items():
        print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
