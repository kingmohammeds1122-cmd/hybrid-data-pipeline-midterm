"""Unified FastAPI interface for the final-project additions."""
from __future__ import annotations
from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from config import settings
from src.queries_and_indexes import create_required_indexes, query_customer_orders, query_orders_by_status, query_high_value_orders, query_orders_by_city, query_orders_by_date_range
from src.aggregations import REPORTS, run_report
from src.materialized_views import DAILY_VIEW, PRODUCTS_VIEW, refresh_materialized_views
from src.scheduled_jobs import job_refresh_materialized_views, job_generate_periodic_report, list_job_logs

app = FastAPI(title="Hybrid Data Pipeline Final API", version="2.0.0")


def get_client():
    return MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS)


def get_db():
    client = get_client()
    return client, client[settings.MONGODB_DATABASE]


def json_safe(value):
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items() if k != "_id"}
    return value


@app.get("/health")
def health():
    client, db = get_db()
    try:
        db.command("ping")
        return {"status": "healthy", "database": settings.MONGODB_DATABASE}
    finally:
        client.close()


@app.post("/ingest")
def ingest():
    client, db = get_db()
    try:
        return {"status": "SUCCESS", "database": settings.MONGODB_DATABASE, "raw_count": db[settings.ORDERS_RAW_COLLECTION].count_documents({})}
    finally:
        client.close()


@app.post("/indexes")
def indexes():
    client, db = get_db()
    try:
        return {"status": "SUCCESS", "indexes": create_required_indexes(db)}
    finally:
        client.close()


@app.get("/queries")
def queries():
    return {"queries": ["customer_orders", "orders_by_status", "high_value_orders", "orders_by_city", "orders_by_date_range"]}


@app.get("/queries/{name}")
def query(name: str, customer_id: str = "CUST_001", status: str = "Completed", city: str = "Sana'a", start_date: str = "2000-01-01", end_date: str = "2100-01-01", min_amount: float = 5000.0):
    client, db = get_db()
    try:
        functions = {
            "customer_orders": lambda: query_customer_orders(db, customer_id),
            "orders_by_status": lambda: query_orders_by_status(db, status),
            "high_value_orders": lambda: query_high_value_orders(db, min_amount),
            "orders_by_city": lambda: query_orders_by_city(db, city),
            "orders_by_date_range": lambda: query_orders_by_date_range(db, start_date, end_date),
        }
        if name not in functions:
            raise HTTPException(status_code=404, detail="Query not found")
        return {"query_name": name, "status": "SUCCESS", "data": json_safe(functions[name]())}
    finally:
        client.close()


@app.get("/aggregations")
def aggregations():
    return {"aggregations": list(REPORTS)}


@app.get("/aggregations/{name}")
def aggregation(name: str):
    client, db = get_db()
    try:
        if name not in REPORTS:
            raise HTTPException(status_code=404, detail="Aggregation not found")
        return {"aggregation": name, "status": "SUCCESS", "data": json_safe(run_report(db, name))}
    finally:
        client.close()


@app.get("/views")
def views():
    return {"views": [DAILY_VIEW, PRODUCTS_VIEW]}


@app.get("/views/{name}/run")
def view(name: str):
    client, db = get_db()
    try:
        if name not in {DAILY_VIEW, PRODUCTS_VIEW}:
            raise HTTPException(status_code=404, detail="View not found")
        return {"view": name, "status": "SUCCESS", "data": json_safe(list(db[name].find({}, {"_id": 0}).limit(100)))}
    finally:
        client.close()


@app.post("/refresh-mv")
def refresh_mv():
    client, db = get_db()
    try:
        return refresh_materialized_views(db)
    finally:
        client.close()


@app.get("/jobs")
def jobs():
    return {"jobs": ["refresh_materialized_views", "generate_periodic_report"], "latest_logs": json_safe(list_job_logs())}


@app.post("/jobs/{name}/run")
def run_job(name: str):
    if name == "refresh_materialized_views":
        return job_refresh_materialized_views()
    if name == "generate_periodic_report":
        return job_generate_periodic_report()
    raise HTTPException(status_code=404, detail="Job not found")
