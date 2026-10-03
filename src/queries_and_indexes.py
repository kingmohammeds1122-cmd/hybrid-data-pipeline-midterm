import pymongo
from pymongo.database import Database
from typing import Dict, List, Any


def query_customer_orders(db: Database, customer_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    return list(db["orders_validated"].find({"customer_id": customer_id}).sort("order_date", -1).limit(limit))

def query_orders_by_status(db: Database, status: str, limit: int = 10) -> List[Dict[str, Any]]:
    return list(db["orders_validated"].find({"status": status}).limit(limit))

def query_high_value_orders(db: Database, min_amount: float = 5000.0, limit: int = 10) -> List[Dict[str, Any]]:
    return list(db["orders_validated"].find({"total_amount": {"$gte": min_amount}}).sort("total_amount", -1).limit(limit))

def query_orders_by_city(db: Database, city: str, limit: int = 10) -> List[Dict[str, Any]]:
    return list(db["orders_validated"].find({"city": city}).limit(limit))

def query_orders_by_date_range(db: Database, start_date: str, end_date: str, limit: int = 10) -> List[Dict[str, Any]]:
    return list(db["orders_validated"].find(
        {"order_date": {"$gte": start_date, "$lte": end_date}}
    ).sort("order_date", 1).limit(limit))


def create_required_indexes(db: Database):
    collection = db["orders_validated"]
    
    collection.create_index([("customer_id", pymongo.ASCENDING)], name="idx_customer_id")
    collection.create_index([("status", pymongo.ASCENDING)], name="idx_status")
    collection.create_index(
        [("city", pymongo.ASCENDING), ("status", pymongo.ASCENDING)], 
        name="idx_compound_city_status"
    )
    print("Indexes created successfully.")


def test_explain_plans(db: Database):
    collection = db["orders_validated"]
    test_query = {"customer_id": "CUST_001"}
    
    print("\n--- Explain Stats Analysis ---")
    
    try:
        collection.drop_index("idx_customer_id")
    except Exception:
        pass
        
    explain_before = collection.find(test_query).explain()["executionStats"]
    stage_before = explain_before.get("executionStages", {}).get("stage")
    docs_examined_before = explain_before.get("totalDocsExamined")
    print(f"Before index: Examined {docs_examined_before} docs (Stage: {stage_before})")
    
    create_required_indexes(db)
    
    explain_after = collection.find(test_query).explain()["executionStats"]
    stage_after = explain_after.get("executionStages", {}).get("stage")
    docs_examined_after = explain_after.get("totalDocsExamined")
    print(f"After index: Examined {docs_examined_after} docs (Stage: {stage_after})")
    print("------------------------------------\n")


if __name__ == "__main__":
    from pymongo import MongoClient
    
    client = MongoClient("mongodb://localhost:27017/")
    database = client["midterm_data_pipeline"]
    
    print("\n=== Part 1 Test Started ===")
    test_explain_plans(database)
    print("=== Part 1 Completed Successfully ===")