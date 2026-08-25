from datetime import datetime, timezone
from pathlib import Path
from pymongo import MongoClient, UpdateOne
from bson import json_util
from src.quality_rules import clean_record

RUN_ID = "d99b6635-6877-4263-9b17-ff522a49fb48"
URI = "mongodb://localhost:27017"
DB_NAME = "midterm_data_pipeline"
BATCH_SIZE = 1000

root = Path(r"D:\midterm-data-pipeline")
backup_path = root / "reports" / f"quarantine_date_candidates_{RUN_ID}.jsonl"

client = MongoClient(URI, serverSelectionTimeoutMS=30000)
db = client[DB_NAME]
q = db["orders_quarantine"]
v = db["orders_validated"]
audit = db["quarantine_reprocessing_audit"]

candidate_filter = {
    "run_id": RUN_ID,
    "error_codes": ["INVALID_IMPOSSIBLE_DATE"],
}

candidate_count = q.count_documents(candidate_filter)
print("candidate_count:", candidate_count)
print("backup_path:", backup_path)

# Create a BSON-JSON backup before any database deletion.
backup_path.parent.mkdir(parents=True, exist_ok=True)
with backup_path.open("w", encoding="utf-8") as handle:
    for doc in q.find(candidate_filter, {"_id": 1, "run_id": 1, "source_row_number": 1, "error_codes": 1, "error_details": 1, "raw_record": 1}, batch_size=BATCH_SIZE):
        handle.write(json_util.dumps(doc, ensure_ascii=False) + "\n")
print("candidate_backup_created:", backup_path.exists())

moved = 0
skipped = 0
failed = 0
inserted = 0
updated = 0
unchanged = 0
processed = 0

cursor = q.find(candidate_filter, batch_size=BATCH_SIZE)
ops = []
audit_ops = []
quarantine_ids = []


def flush_batch():
    global moved, inserted, updated, unchanged, failed, ops, audit_ops, quarantine_ids
    if not ops:
        return
    try:
        result = v.bulk_write(ops, ordered=False)
        batch_inserted = len(result.upserted_ids)
        batch_updated = result.modified_count
        batch_unchanged = result.matched_count - result.modified_count

        audit.bulk_write(audit_ops, ordered=False)
        delete_result = q.delete_many({"_id": {"$in": quarantine_ids}})
        if delete_result.deleted_count != len(quarantine_ids):
            raise RuntimeError(f"Delete verification failed: expected {len(quarantine_ids)}, got {delete_result.deleted_count}")

        inserted += batch_inserted
        updated += batch_updated
        unchanged += batch_unchanged
        moved += delete_result.deleted_count
    except Exception as exc:
        failed += len(ops)
        print("BATCH_FAILED:", type(exc).__name__, str(exc))
    finally:
        ops = []
        audit_ops = []
        quarantine_ids = []

for doc in cursor:
    processed += 1
    raw = doc.get("raw_record") or {}
    try:
        result = clean_record(raw)
        if result.quality_status not in ("valid", "corrected") or result.error_codes:
            skipped += 1
            continue

        data = result.as_dict()
        order_id = str(data.get("order_id") or "").strip()
        if not order_id:
            skipped += 1
            continue

        now = datetime.now(timezone.utc)
        data.update({
            "run_id": RUN_ID,
            "reprocessed_from_quarantine": True,
            "reprocessed_at": now,
            "reprocess_reason": "DATE_STANDARDIZATION",
            "original_quarantine_id": str(doc["_id"]),
            "original_error_codes": doc.get("error_codes", []),
            "source_row_number": doc.get("source_row_number"),
        })

        ops.append(UpdateOne({"order_id": order_id}, {"$set": data}, upsert=True))
        audit_ops.append(UpdateOne(
            {"quarantine_id": str(doc["_id"])},
            {"$setOnInsert": {
                "quarantine_id": str(doc["_id"]),
                "run_id": RUN_ID,
                "order_id": order_id,
                "source_row_number": doc.get("source_row_number"),
                "action": "moved_to_validated",
                "reason": "DATE_STANDARDIZATION",
                "audited_at": now,
            }},
            upsert=True,
        ))
        quarantine_ids.append(doc["_id"])

        if len(ops) >= BATCH_SIZE:
            flush_batch()
            if moved % 10000 == 0:
                print(f"processed={processed} moved={moved} skipped={skipped} failed={failed}")
    except Exception as exc:
        failed += 1
        print("RECORD_FAILED:", type(exc).__name__, str(exc))

flush_batch()

print("REPROCESSING COMPLETE")
print("candidate_count:", candidate_count)
print("processed:", processed)
print("moved:", moved)
print("skipped:", skipped)
print("failed:", failed)
print("inserted_count:", inserted)
print("updated_count:", updated)
print("unchanged_count:", unchanged)
print("validated_total:", v.count_documents({}))
print("quarantine_total:", q.count_documents({}))
print("audit_total:", audit.count_documents({"run_id": RUN_ID}))
print("conservation_check:", db["orders_raw"].count_documents({}) == v.count_documents({}) + q.count_documents({}))
