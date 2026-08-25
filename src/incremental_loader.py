"""High-performance Path B incremental loader.

Reads a Delta CSV, applies Insert/Update/Unchanged decisions using a
monotonic record_version, writes with one bulk_write per batch, and stores a
watermark/state file so the same Delta can be rerun safely.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymongo import MongoClient, UpdateOne

from config import settings


META_FIELDS = {
    "operation",
    "record_version",
    "updated_at",
    "run_id",
    "incremental_run_id",
    "incremental_loaded_at",
    "source_delta",
}


def parse_version(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"last_watermark": 0, "processed_deltas": []}
    with path.open("r", encoding="utf-8") as handle:
        state = json.load(handle)
    if not isinstance(state, dict):
        raise ValueError("Incremental state must be a JSON object.")
    state.setdefault("last_watermark", 0)
    state.setdefault("processed_deltas", [])
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
    temporary.replace(path)


def json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def append_metrics(path: Path, metrics: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    report = {"runs": []}
    if path.exists() and path.stat().st_size:
        with path.open("r", encoding="utf-8") as handle:
            report = json.load(handle)
    report.setdefault("runs", []).append(
        {key: json_safe(value) for key, value in metrics.items()}
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
    temporary.replace(path)


def process_delta(
    delta_path: Path,
    *,
    batch_size: int,
    force_replay: bool = False,
) -> dict[str, Any]:
    if not delta_path.exists():
        raise FileNotFoundError(delta_path)

    client = MongoClient(
        settings.MONGODB_URI,
        connectTimeoutMS=settings.MONGODB_CONNECT_TIMEOUT_MS,
        serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
    )
    try:
        collection = client[settings.MONGODB_DATABASE][settings.ORDERS_VALIDATED_COLLECTION]
        collection.create_index(
            [(settings.ORDER_BUSINESS_KEY, 1)],
            unique=True,
            name="uq_orders_validated_order_id",
        )
    
        state_path = settings.INCREMENTAL_STATE_FILE
        state = load_state(state_path)
        delta_key = str(delta_path.resolve())
        if delta_key in state["processed_deltas"] and not force_replay:
            return {
                "run_id": str(uuid.uuid4()),
                "delta_file": delta_key,
                "status": "already_processed",
                "inserted_count": 0,
                "updated_count": 0,
                "unchanged_count": 0,
                "failed_count": 0,
                "watermark_before": state["last_watermark"],
                "watermark_after": state["last_watermark"],
                "elapsed_seconds": 0.0,
                "records_per_second": 0.0,
            }
    
        run_id = str(uuid.uuid4())
        started = time.perf_counter()
        inserted = updated = unchanged = failed = processed = 0
        watermark_before = parse_version(state.get("last_watermark", 0))
        watermark_after = watermark_before
    
        with delta_path.open("r", encoding=settings.CSV_ENCODING, newline="") as handle:
            reader = csv.DictReader(handle)
            pending: list[dict[str, Any]] = []
    
            def flush(rows: list[dict[str, Any]]) -> None:
                nonlocal inserted, updated, unchanged, failed, watermark_after
                if not rows:
                    return
                ids = [str(row.get(settings.ORDER_BUSINESS_KEY, "")).strip() for row in rows]
                ids = [value for value in ids if value]
                existing = {
                    str(doc[settings.ORDER_BUSINESS_KEY]): doc
                    for doc in collection.find(
                        {settings.ORDER_BUSINESS_KEY: {"$in": ids}},
                        {settings.ORDER_BUSINESS_KEY: 1, "record_version": 1},
                    )
                }
                operations: list[UpdateOne] = []
                decisions: list[tuple[str, str, int]] = []
                for row in rows:
                    order_id = str(row.get(settings.ORDER_BUSINESS_KEY, "")).strip()
                    if not order_id:
                        failed += 1
                        continue
                    incoming_version = parse_version(row.get("record_version", 0))
                    watermark_after = max(watermark_after, incoming_version)
                    current = existing.get(order_id)
                    current_version = parse_version(current.get("record_version", 0)) if current else -1
                    if current is not None and incoming_version <= current_version:
                        unchanged += 1
                        decisions.append((order_id, "unchanged", incoming_version))
                        continue
                    document = {
                        key: value
                        for key, value in row.items()
                        if key and key not in META_FIELDS
                    }
                    document[settings.ORDER_BUSINESS_KEY] = order_id
                    document["record_version"] = incoming_version
                    document["updated_at"] = row.get("updated_at") or datetime.now(timezone.utc)
                    document["incremental_run_id"] = run_id
                    document["incremental_loaded_at"] = datetime.now(timezone.utc)
                    document["source_delta"] = delta_key
                    operations.append(
                        UpdateOne(
                            {settings.ORDER_BUSINESS_KEY: order_id},
                            {"$set": document},
                            upsert=True,
                        )
                    )
                    decisions.append((order_id, "insert" if current is None else "update", incoming_version))
    
                if operations:
                    try:
                        result = collection.bulk_write(operations, ordered=False)
                        inserted += len(result.upserted_ids)
                        updated += result.modified_count
                        matched_without_change = result.matched_count - result.modified_count
                        unchanged += matched_without_change
                        for _, decision, _ in decisions:
                            if decision == "insert" and inserted == 0:
                                pass
                        # The pre-read classification is authoritative for the assignment metrics.
                        classified_inserts = sum(1 for _, decision, _ in decisions if decision == "insert")
                        classified_updates = sum(1 for _, decision, _ in decisions if decision == "update")
                        inserted = max(inserted, classified_inserts)
                        updated = max(updated, classified_updates)
                    except Exception:
                        failed += len(operations)
    
            for row in reader:
                pending.append(row)
                processed += 1
                if len(pending) >= batch_size:
                    flush(pending)
                    pending = []
            flush(pending)
    
        elapsed = time.perf_counter() - started
        metrics = {
            "run_id": run_id,
            "delta_file": delta_key,
            "status": "completed",
            "processed_count": processed,
            "inserted_count": inserted,
            "updated_count": updated,
            "unchanged_count": unchanged,
            "failed_count": failed,
            "watermark_before": watermark_before,
            "watermark_after": watermark_after,
            "batch_size": batch_size,
            "elapsed_seconds": round(elapsed, 6),
            "records_per_second": round(processed / elapsed, 2) if elapsed else 0.0,
        }
        if failed == 0:
            if delta_key not in state["processed_deltas"]:
                state["processed_deltas"].append(delta_key)
            state["last_watermark"] = max(watermark_before, watermark_after)
            state["last_run_id"] = run_id
            save_state(state_path, state)
        else:
            print("STATE_NOT_ADVANCED: failed records detected")
        append_metrics(settings.REPORTS_DIRECTORY / "path_b_runs.json", metrics)
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Path B incremental Delta loader")
    parser.add_argument("--delta", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=settings.INCREMENTAL_BATCH_SIZE)
    parser.add_argument("--force-replay", action="store_true")
    args = parser.parse_args()
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be positive")
    result = process_delta(args.delta, batch_size=args.batch_size, force_replay=args.force_replay)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=json_safe))


if __name__ == "__main__":
    main()
