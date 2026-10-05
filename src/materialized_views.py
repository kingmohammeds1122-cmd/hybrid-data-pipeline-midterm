"""Final-project materialized views with incremental refresh metadata."""
from __future__ import annotations
from datetime import datetime, timezone
from pymongo.database import Database
from config import settings

DAILY_VIEW = "daily_sales_summary"
PRODUCTS_VIEW = "top_products_summary"
META_COLLECTION = "materialized_view_refresh_state"


def _now():
    return datetime.now(timezone.utc)


def _source_filter(last_refresh):
    return {"processed_at": {"$gt": last_refresh}} if last_refresh else {}


def refresh_daily_sales_summary(db: Database, last_refresh=None) -> dict:
    pipeline = [
        {"$match": _source_filter(last_refresh)},
        {"$match": {"order_date": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$order_date", "revenue_delta": {"$sum": "$total_amount"}, "orders_delta": {"$sum": 1}}},
    ]
    deltas = list(db[settings.ORDERS_VALIDATED_COLLECTION].aggregate(pipeline))
    view = db[DAILY_VIEW]
    for item in deltas:
        view.update_one(
            {"_id": item["_id"]},
            {"$inc": {"total_revenue": item["revenue_delta"], "total_orders": item["orders_delta"]}, "$set": {"updated_at": _now()}},
            upsert=True,
        )
    return {"view": DAILY_VIEW, "delta_groups": len(deltas)}


def refresh_top_products_summary(db: Database, last_refresh=None) -> dict:
    pipeline = [
        {"$match": _source_filter(last_refresh)},
        {"$match": {"items": {"$type": "array"}}},
        {"$unwind": "$items"},
        {"$group": {"_id": "$items.sku", "product_name": {"$first": "$items.item_name"}, "units_delta": {"$sum": "$items.quantity"}, "revenue_delta": {"$sum": "$items.subtotal"}}},
    ]
    deltas = list(db[settings.ORDERS_VALIDATED_COLLECTION].aggregate(pipeline))
    view = db[PRODUCTS_VIEW]
    for item in deltas:
        view.update_one(
            {"_id": item["_id"]},
            {"$inc": {"units_sold": item["units_delta"], "revenue": item["revenue_delta"]}, "$set": {"product_name": item.get("product_name"), "updated_at": _now()}},
            upsert=True,
        )
    return {"view": PRODUCTS_VIEW, "delta_groups": len(deltas)}


def refresh_materialized_views(db: Database, run_id: str | None = None) -> dict:
    state = db[META_COLLECTION].find_one({"_id": "default"}) or {}
    last_refresh = state.get("last_refresh_at")
    result = {
        "daily": refresh_daily_sales_summary(db, last_refresh),
        "products": refresh_top_products_summary(db, last_refresh),
    }
    now = _now()
    db[META_COLLECTION].update_one(
        {"_id": "default"},
        {"$set": {"last_refresh_at": now, "last_processed_run_id": run_id, "updated_at": now}},
        upsert=True,
    )
    return {"status": "SUCCESS", "incremental": bool(last_refresh), "refreshed_at": now, "details": result}
