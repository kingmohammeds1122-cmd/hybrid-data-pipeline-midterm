"""Final-project queries, indexes, and explain statistics on real values."""
from __future__ import annotations

from typing import Any
import json
import pymongo
from pymongo.database import Database
from config import settings


def _collection(db: Database):
    return db[settings.ORDERS_VALIDATED_COLLECTION]


def query_customer_orders(db: Database, customer_id: str, limit: int = 10):
    return list(_collection(db).find({"customer_id": customer_id}).sort("order_date", -1).limit(limit))


def query_orders_by_status(db: Database, status: str, limit: int = 10):
    return list(_collection(db).find({"status": status}).sort("order_date", -1).limit(limit))


def query_high_value_orders(db: Database, min_amount: float = 5000.0, limit: int = 10):
    return list(_collection(db).find({"total_amount": {"$gte": min_amount}}).sort("total_amount", -1).limit(limit))


def query_orders_by_city(db: Database, city: str, limit: int = 10):
    return list(_collection(db).find({"city": city}).sort("order_date", -1).limit(limit))


def query_orders_by_date_range(db: Database, start_date: str, end_date: str, limit: int = 10):
    return list(_collection(db).find({"order_date": {"$gte": start_date, "$lte": end_date}}).sort("order_date", 1).limit(limit))


def create_required_indexes(db: Database) -> list[str]:
    collection = _collection(db)
    return [
        collection.create_index([("customer_id", 1), ("order_date", -1)], name="idx_final_customer_date"),
        collection.create_index([("status", 1), ("order_date", -1)], name="idx_final_status_date"),
        collection.create_index([("city", 1), ("status", 1)], name="idx_final_city_status"),
        collection.create_index([("total_amount", -1)], name="idx_final_total_amount"),
    ]


def drop_final_project_indexes(db: Database) -> None:
    collection = _collection(db)
    for name in ("idx_final_customer_date", "idx_final_status_date", "idx_final_city_status", "idx_final_total_amount", "idx_final_customer_id", "idx_final_status", "idx_final_order_date"):
        try:
            collection.drop_index(name)
        except pymongo.errors.OperationFailure:
            pass


def _explain(collection: Any, filter_: dict[str, Any], sort: list[tuple[str, int]] | None = None) -> dict[str, Any]:
    cursor = collection.find(filter_)
    if sort:
        cursor = cursor.sort(sort)
    return cursor.explain()["executionStats"]


def _first_real_values(db: Database) -> tuple[str, str, str]:
    doc = _collection(db).find_one(
        {"customer_id": {"$nin": [None, ""]}, "status": {"$nin": [None, ""]}, "city": {"$nin": [None, ""]}},
        {"customer_id": 1, "status": 1, "city": 1, "_id": 0},
    )
    if not doc:
        raise RuntimeError("No validated document contains customer_id, status, and city values.")
    return str(doc["customer_id"]), str(doc["status"]), str(doc["city"])


def explain_three_queries(db: Database) -> dict[str, Any]:
    customer_id, status, city = _first_real_values(db)
    cases = {
        "customer_id": ({"customer_id": customer_id}, [("order_date", -1)]),
        "status": ({"status": status}, [("order_date", -1)]),
        "city_status": ({"city": city, "status": status}, None),
    }
    drop_final_project_indexes(db)
    before = {name: _explain(_collection(db), filter_, sort) for name, (filter_, sort) in cases.items()}
    create_required_indexes(db)
    after = {name: _explain(_collection(db), filter_, sort) for name, (filter_, sort) in cases.items()}
    return {"sample_values": {"customer_id": customer_id, "status": status, "city": city}, "before": before, "after": after}


def compact_explain(stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "execution_time_ms": stats.get("executionTimeMillis"),
        "docs_examined": stats.get("totalDocsExamined"),
        "keys_examined": stats.get("totalKeysExamined"),
        "n_returned": stats.get("nReturned"),
        "stage": stats.get("executionStages", {}).get("stage"),
    }


if __name__ == "__main__":
    from pymongo import MongoClient
    client = MongoClient(settings.MONGODB_URI)
    try:
        db = client[settings.MONGODB_DATABASE]
        result = explain_three_queries(db)
        result["compact_explain"] = {
            "before": {name: compact_explain(stats) for name, stats in result["before"].items()},
            "after": {name: compact_explain(stats) for name, stats in result["after"].items()},
        }
        print(json.dumps(result, default=str, ensure_ascii=False, indent=2))
    finally:
        client.close()
