"""Five final-project aggregation reports using real MongoDB data."""
from __future__ import annotations
from typing import Any
from pymongo.database import Database
from config import settings


def _collection(db: Database):
    return db[settings.ORDERS_VALIDATED_COLLECTION]


def get_sales_by_city(db: Database) -> list[dict[str, Any]]:
    return list(_collection(db).aggregate([
        {"$match": {"city": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$city", "total_revenue": {"$sum": "$total_amount"}, "total_orders": {"$sum": 1}}},
        {"$sort": {"total_revenue": -1}}, {"$limit": 10},
    ]))


def get_top_products(db: Database) -> list[dict[str, Any]]:
    return list(_collection(db).aggregate([
        {"$match": {"items": {"$type": "array"}}},
        {"$unwind": "$items"},
        {"$group": {"_id": "$items.sku", "product_name": {"$first": "$items.item_name"}, "units_sold": {"$sum": "$items.quantity"}, "revenue": {"$sum": "$items.subtotal"}}},
        {"$sort": {"units_sold": -1}}, {"$limit": 10},
    ]))


def get_top_customers(db: Database) -> list[dict[str, Any]]:
    return list(_collection(db).aggregate([
        {"$match": {"customer_id": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$customer_id", "total_spent": {"$sum": "$total_amount"}, "orders_count": {"$sum": 1}}},
        {"$sort": {"total_spent": -1}}, {"$limit": 10},
    ]))


def get_sales_by_period(db: Database) -> list[dict[str, Any]]:
    return list(_collection(db).aggregate([
        {"$match": {"order_date": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$order_date", "daily_revenue": {"$sum": "$total_amount"}, "orders_count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}, {"$limit": 100},
    ]))


def get_orders_by_status(db: Database) -> list[dict[str, Any]]:
    return list(_collection(db).aggregate([
        {"$group": {"_id": "$status", "count": {"$sum": 1}, "total_value": {"$sum": "$total_amount"}}},
        {"$sort": {"count": -1}},
    ]))


REPORTS = {
    "sales_by_city": get_sales_by_city,
    "top_products": get_top_products,
    "top_customers": get_top_customers,
    "sales_by_period": get_sales_by_period,
    "orders_by_status": get_orders_by_status,
}


def run_report(db: Database, name: str) -> list[dict[str, Any]]:
    if name not in REPORTS:
        raise KeyError(f"Unknown aggregation report: {name}")
    return REPORTS[name](db)


if __name__ == "__main__":
    import json
    from pymongo import MongoClient
    client = MongoClient(settings.MONGODB_URI)
    try:
        db = client[settings.MONGODB_DATABASE]
        for name in REPORTS:
            print(f"\n=== {name} ===")
            print(json.dumps(run_report(db, name), default=str, ensure_ascii=False, indent=2))
    finally:
        client.close()
