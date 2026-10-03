"""
الجزء الأول من المشروع النهائي: الاستعلامات والفهارس.
"""
import pymongo
from pymongo.database import Database
from typing import Dict, List, Any

# ==========================================
# النقطة الأولى: 5 استعلامات عملية 
# ==========================================
def query_customer_orders(db: Database, customer_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """1. جلب طلبات عميل معين مرتبة من الأحدث للأقدم."""
    return list(db["orders_validated"].find({"customer_id": customer_id}).sort("order_date", -1).limit(limit))

def query_orders_by_status(db: Database, status: str, limit: int = 10) -> List[Dict[str, Any]]:
    """2. تصفية الطلبات بناءً على حالتها (مثال: مكتملة، ملغاة)."""
    return list(db["orders_validated"].find({"status": status}).limit(limit))

def query_high_value_orders(db: Database, min_amount: float = 5000.0, limit: int = 10) -> List[Dict[str, Any]]:
    """3. جلب الطلبات ذات القيمة العالية (أكبر من مبلغ محدد)."""
    return list(db["orders_validated"].find({"total_amount": {"$gte": min_amount}}).sort("total_amount", -1).limit(limit))

def query_orders_by_city(db: Database, city: str, limit: int = 10) -> List[Dict[str, Any]]:
    """4. جلب الطلبات الخاصة بمدينة معينة."""
    return list(db["orders_validated"].find({"city": city}).limit(limit))

def query_orders_by_date_range(db: Database, start_date: str, end_date: str, limit: int = 10) -> List[Dict[str, Any]]:
    """5. جلب الطلبات التي تمت خلال نطاق زمني معين."""
    return list(db["orders_validated"].find(
        {"order_date": {"$gte": start_date, "$lte": end_date}}
    ).sort("order_date", 1).limit(limit))


# ==========================================
# النقطة الثانية: إنشاء 3 فهارس (بينها فهرس مركب)
# ==========================================
def create_required_indexes(db: Database):
    """إنشاء الفهارس لخدمة الاستعلامات السابقة."""
    collection = db["orders_validated"]
    
    # 1. فهرس أحادي لخدمة استعلام العملاء
    collection.create_index([("customer_id", pymongo.ASCENDING)], name="idx_customer_id")
    
    # 2. فهرس أحادي لخدمة استعلام حالة الطلب
    collection.create_index([("status", pymongo.ASCENDING)], name="idx_status")
    
    # 3. فهرس مركب (Compound Index) لخدمة الاستعلامات التي تدمج المدينة والحالة
    collection.create_index(
        [("city", pymongo.ASCENDING), ("status", pymongo.ASCENDING)], 
        name="idx_compound_city_status"
    )
    print("-> تم إنشاء الفهارس الثلاثة بنجاح (بما في ذلك الفهرس المركب).")


# ==========================================
# النقطة الثالثة: تنفيذ explain وتحليل الأداء
# ==========================================
def test_explain_plans(db: Database):
    """مقارنة أداء الاستعلام قبل وبعد الفهرس."""
    collection = db["orders_validated"]
    
    # استعلام تجريبي لقياس الأداء
    test_query = {"customer_id": "CUST_001"}
    
    print("\n--- تحليل الأداء (Explain Stats) ---")
    
    # 1. محاكاة غياب الفهرس (حذفه إن وجد)
    try:
        collection.drop_index("idx_customer_id")
    except Exception:
        pass
        
    explain_before = collection.find(test_query).explain()["executionStats"]
    stage_before = explain_before.get("executionStages", {}).get("stage")
    docs_examined_before = explain_before.get("totalDocsExamined")
    print(f"قبل الفهرس: تم فحص {docs_examined_before} سجل (المرحلة: {stage_before})")
    
    # 2. إعادة إنشاء الفهرس لقياس التحسن
    create_required_indexes(db)
    
    explain_after = collection.find(test_query).explain()["executionStats"]
    stage_after = explain_after.get("executionStages", {}).get("stage")
    docs_examined_after = explain_after.get("totalDocsExamined")
    print(f"بعد الفهرس: تم فحص {docs_examined_after} سجل (المرحلة: {stage_after})")
    print("------------------------------------\n")

# ==========================================
# نقطة التشغيل والاختبار الصارم
# ==========================================
if __name__ == "__main__":
    from pymongo import MongoClient
    
    # الاتصال بقاعدة البيانات الخاصة بالمشروع
    client = MongoClient("mongodb://localhost:27017/")
    database = client["midterm_data_pipeline"]
    
    print("\n=== بدء اختبار الجزء الأول ===")
    test_explain_plans(database)
    print("=== اكتمل الجزء الأول بنجاح ===")