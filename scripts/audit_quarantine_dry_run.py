from pymongo import MongoClient
from src.quality_rules import clean_record

RUN_ID = "d99b6635-6877-4263-9b17-ff522a49fb48"
client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=30000)
q = client["midterm_data_pipeline"]["orders_quarantine"]

seen = 0
recoverable = 0
still_quarantined = 0
by_original = {}
by_result = {}

cursor = q.find({"run_id": RUN_ID}, {"_id": 0, "raw_record": 1, "error_codes": 1}, batch_size=1000)
for doc in cursor:
    seen += 1
    original = tuple(sorted(doc.get("error_codes", [])))
    by_original[original] = by_original.get(original, 0) + 1
    raw = doc.get("raw_record") or {}
    try:
        result = clean_record(raw)
        status = getattr(result, "quality_status", None)
        errors = getattr(result, "error_codes", None) or []
        if "DUPLICATE_ORDER_ID" in original:
            still_quarantined += 1
            outcome = "excluded_duplicate"
        elif status in ("valid", "corrected") and not errors:
            recoverable += 1
            outcome = status
        else:
            still_quarantined += 1
            outcome = "quarantined"
    except Exception as exc:
        still_quarantined += 1
        outcome = "audit_error:" + type(exc).__name__
    result_key = outcome + "|original=" + ",".join(original)
    by_result[result_key] = by_result.get(result_key, 0) + 1
    if seen % 100000 == 0:
        print(f"audited={seen} recoverable={recoverable} still_quarantined={still_quarantined}")

print("AUDIT COMPLETE")
print("total_quarantine:", seen)
print("recoverable_dry_run:", recoverable)
print("still_quarantined:", still_quarantined)
print("original_error_groups:", by_original)
print("reclassification_results:", by_result)


