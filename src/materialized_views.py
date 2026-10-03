"""
الجزء الثالث من المشروع النهائي: العروض المادية (Materialized Views).
الهدف: حفظ نتائج التجميعات المعقدة في جداول مادية (Collections) مستقلة 
باستخدام معامل ($out) لتسريع استجابة النظام وتخفيف الحمل عن القرص الصلب.
"""
from pymongo.database import Database
from pymongo import MongoClient
import time

def create_status_view(db: Database):
    print("جاري إنشاء العرض المادي: view_orders_by_status...")
    pipeline = [
        {"$limit": 1000000}, # عينة للتنفيذ السريع
        {"$group": {
            "_id": "$status", 
            "count": {"$sum": 1}, 
            "total_value": {"$sum": "$total_amount"}
        }},
        {"$sort": {"count": -1}},
        {"$out": "view_orders_by_status"} # حفظ النتيجة في كوليكشن جديد
    ]
    db["orders_validated"].aggregate(pipeline)

def create_city_view(db: Database):
    print("جاري إنشاء العرض المادي: view_sales_by_city...")
    pipeline = [
        {"$limit": 1000000},
        {"$match": {"city": {"$ne": None}}},
        {"$group": {
            "_id": "$city", 
            "total_revenue": {"$sum": "$total_amount"}, 
            "total_orders": {"$sum": 1}
        }},
        {"$sort": {"total_revenue": -1}},
        {"$out": "view_sales_by_city"}
    ]
    db["orders_validated"].aggregate(pipeline)

def create_products_view(db: Database):
    print("جاري إنشاء العرض المادي: view_top_products...")
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
        {"$out": "view_top_products"}
    ]
    db["orders_validated"].aggregate(pipeline)

if __name__ == "__main__":
    client = MongoClient("mongodb://localhost:27017/")
    database = client["midterm_data_pipeline"]
    
    print("\n=== بدء الجزء الثالث: بناء العروض المادية (Materialized Views) ===\n")
    
    start_time = time.time()
    
    create_status_view(database)
    create_city_view(database)
    create_products_view(database)
    
    end_time = time.time()
    
    print(f"\n=== اكتمل إنشاء العروض المادية بنجاح في {round(end_time - start_time, 2)} ثانية ===")
    print("الآن يمكن للواجهة البرمجية (API) الاستعلام من هذه الجداول في أجزاء من الثانية بدلاً من انتظار ساعات.")