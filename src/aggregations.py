"""
الجزء الثاني من المشروع النهائي: التجميعات التحليلية (Aggregations).
تم استخدام ($limit) كعينة بحجم مليون سجل لتسريع الاختبار والعرض، 
وإثبات صحة الاستعلامات دون التسبب باختناق القرص الصلب.
"""
from typing import Any, Dict, List
from pymongo.database import Database

def get_sales_by_city(db: Database) -> List[Dict[str, Any]]:
    pipeline = [
        {"$limit": 1000000}, 
        {"$match": {"city": {"$ne": None}}},
        {"$group": {
            "_id": "$city", 
            "total_revenue": {"$sum": "$total_amount"}, 
            "total_orders": {"$sum": 1}
        }},
        {"$sort": {"total_revenue": -1}},
        {"$limit": 5}
    ]
    return list(db["orders_validated"].aggregate(pipeline))

def get_top_products(db: Database) -> List[Dict[str, Any]]:
    pipeline = [
        {"$limit": 1000000},
        {"$match": {"items": {"$type": "array"}}},
        {"$unwind": "$items"},
        {"$group": {
            "_id": "$items.product_id",
            "product_name": {"$first": "$items.product_name"},
            "units_sold": {"$sum": "$items.quantity"}
        }},
        {"$sort": {"units_sold": -1}},
        {"$limit": 5}
    ]
    return list(db["orders_validated"].aggregate(pipeline))

def get_top_customers(db: Database) -> List[Dict[str, Any]]:
    pipeline = [
        {"$limit": 1000000},
        {"$match": {"customer_id": {"$ne": None}}},
        {"$group": {
            "_id": "$customer_id", 
            "total_spent": {"$sum": "$total_amount"}, 
            "orders_count": {"$sum": 1}
        }},
        {"$sort": {"total_spent": -1}},
        {"$limit": 5}
    ]
    return list(db["orders_validated"].aggregate(pipeline))

def get_sales_by_period(db: Database) -> List[Dict[str, Any]]:
    pipeline = [
        {"$limit": 1000000},
        {"$match": {"order_date": {"$ne": None}}},
        {"$group": {
            "_id": "$order_date", 
            "daily_revenue": {"$sum": "$total_amount"}, 
            "orders_count": {"$sum": 1}
        }},
        {"$sort": {"_id": -1}},
        {"$limit": 5}
    ]
    return list(db["orders_validated"].aggregate(pipeline))

def get_orders_by_status(db: Database) -> List[Dict[str, Any]]:
    pipeline = [
        {"$limit": 1000000},
        {"$group": {
            "_id": "$status", 
            "count": {"$sum": 1}, 
            "total_value": {"$sum": "$total_amount"}
        }},
        {"$sort": {"count": -1}}
    ]
    return list(db["orders_validated"].aggregate(pipeline))

if __name__ == "__main__":
    from pymongo import MongoClient
    import json
    
    # الاتصال بقاعدة البيانات
    client = MongoClient("mongodb://localhost:27017/")
    database = client["midterm_data_pipeline"]
    
    print("\n=== بدء اختبار الجزء الثاني: التجميعات (عينة 1 مليون سجل) ===")
    
    print("\n1. توزيع الطلبات حسب الحالة:")
    print(json.dumps(get_orders_by_status(database), indent=2, ensure_ascii=False))
    
    print("\n2. المبيعات حسب المدينة (أعلى 5):")
    print(json.dumps(get_sales_by_city(database), indent=2, ensure_ascii=False))
    
    print("\n3. أفضل المنتجات مبيعاً:")
    print(json.dumps(get_top_products(database), indent=2, ensure_ascii=False))
    
    print("\n4. أفضل العملاء إنفاقاً:")
    print(json.dumps(get_top_customers(database), indent=2, ensure_ascii=False))
    
    print("\n5. المبيعات اليومية:")
    print(json.dumps(get_sales_by_period(database), indent=2, ensure_ascii=False))
    
    print("\n=== اكتمل الجزء الثاني بنجاح ===")