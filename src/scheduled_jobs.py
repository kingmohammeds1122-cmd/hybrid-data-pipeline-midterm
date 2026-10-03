"""
الجزء الرابع من المشروع النهائي: المهام المجدولة (Scheduled Jobs).
الهدف: جدولة وتشغيل مهام تلقائية مرتبطة بالمشروع (مثل تحديث العروض المادية والتقارير) 
مع إمكانية التشغيل اليدوي وتسجيل أوقات البدء والانتهاْء والحالة (نجاح/فشل).
"""
import time
import datetime
from pymongo import MongoClient
from src.materialized_views import create_status_view, create_city_view, create_products_view

def log_job_execution(job_name: str, status: str, duration: float, error_message: str = None):
    """تسجيل نتائج تنفيذ المهمة في وحدة التحكم (أو قاعدة البيانات)."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[JOB LOG] [{timestamp}] المهمة: '{job_name}'")
    print(f"  - الحالة: {status}")
    print(f"  - المدة المستغرقة: {round(duration, 4)} ثانية")
    if error_message:
        print(f"  - الخطأ: {error_message}")
    print("-" * 50)

# ==========================================
# المهمة المجدولة الأولى: تحديث العروض المادية
# ==========================================
def job_refresh_materialized_views():
    """المهمة الأولى: تحديث جميع العروض المادية دورياً."""
    job_name = "Refresh Materialized Views"
    start_time = time.time()
    print(f"\n-> بدء تنفيذ المهمة: {job_name}...")
    
    try:
        client = MongoClient("mongodb://localhost:27017/")
        db = client["midterm_data_pipeline"]
        
        # استدعاء دوال تحديث العروض المادية
        create_status_view(db)
        create_city_view(db)
        create_products_view(db)
        
        end_time = time.time()
        duration = end_time - start_time
        log_job_execution(job_name, "SUCCESS", duration)
        
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        log_job_execution(job_name, "FAILED", duration, str(e))

# ==========================================
# المهمة المجدولة الثانية: تقرير الفحص والملخص الدوري
# ==========================================
def job_generate_periodic_report():
    """المهمة الثانية: توليد تقرير دوري عن حالة البيانات وعدد السجلات."""
    job_name = "Generate Periodic Summary Report"
    start_time = time.time()
    print(f"\n-> بدء تنفيذ المهمة: {job_name}...")
    
    try:
        client = MongoClient("mongodb://localhost:27017/")
        db = client["midterm_data_pipeline"]
        
        total_orders = db["orders_validated"].estimated_document_count()
        timestamp = datetime.datetime.now().isoformat()
        
        print(f"  [تقرير دوري] إجمالي السجلات في مجموعة الطلبات: {total_orders} سجل (الوقت: {timestamp})")
        
        end_time = time.time()
        duration = end_time - start_time
        log_job_execution(job_name, "SUCCESS", duration)
        
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        log_job_execution(job_name, "FAILED", duration, str(e))

# ==========================================
# نقطة التشغيل اليدوي والجدولة
# ==========================================
if __name__ == "__main__":
    print("\n=== اختبار التشغيل اليدوي للمهام المجدولة ===")
    
    # التشغيل اليدوي للمهمة الأولى
    job_refresh_materialized_views()
    
    # التشغيل اليدوي للمهمة الثانية
    job_generate_periodic_report()
    
    print("\n=== اكتمل اختبار المهام المجدولة بنجاح ===")