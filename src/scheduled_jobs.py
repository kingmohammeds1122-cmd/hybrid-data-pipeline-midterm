"""Final-project scheduled jobs with persistent execution logs."""
from __future__ import annotations
import time
from datetime import datetime, timezone
from pymongo import MongoClient
from config import settings
from src.materialized_views import refresh_materialized_views

JOBS_LOG = "jobs_log"


def _now():
    return datetime.now(timezone.utc)


def _run_job(job_name: str, function, *args, **kwargs) -> dict:
    started = _now()
    timer = time.perf_counter()
    status = "SUCCESS"
    error_message = None
    result = None
    client = MongoClient(settings.MONGODB_URI)
    try:
        db = client[settings.MONGODB_DATABASE]
        result = function(db, *args, **kwargs)
    except Exception as exc:
        status = "FAILED"
        error_message = str(exc)
    finally:
        ended = _now()
        duration = round(time.perf_counter() - timer, 6)
        client[settings.MONGODB_DATABASE][JOBS_LOG].insert_one({
            "job_name": job_name,
            "started_at": started,
            "ended_at": ended,
            "duration_seconds": duration,
            "status": status,
            "error_message": error_message,
            "result": result,
        })
        client.close()
    if status == "FAILED":
        raise RuntimeError(error_message)
    return {"job_name": job_name, "status": status, "duration_seconds": duration, "result": result}


def job_refresh_materialized_views(run_id: str | None = None) -> dict:
    return _run_job("refresh_materialized_views", refresh_materialized_views, run_id=run_id)


def job_generate_periodic_report() -> dict:
    def report(db):
        return {"validated_count": db[settings.ORDERS_VALIDATED_COLLECTION].count_documents({}), "quarantine_count": db[settings.ORDERS_QUARANTINE_COLLECTION].count_documents({})}
    return _run_job("generate_periodic_report", report)


def list_job_logs(limit: int = 50) -> list[dict]:
    client = MongoClient(settings.MONGODB_URI)
    try:
        db = client[settings.MONGODB_DATABASE]
        return list(db[JOBS_LOG].find({}, {"_id": 0}).sort("started_at", -1).limit(limit))
    finally:
        client.close()


if __name__ == "__main__":
    print(job_refresh_materialized_views())
    print(job_generate_periodic_report())
