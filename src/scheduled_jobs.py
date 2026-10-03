import time
import datetime
from pymongo import MongoClient
from src.materialized_views import create_status_view, create_city_view, create_products_view

def log_job_execution(job_name: str, status: str, duration: float, error_message: str = None):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[JOB LOG] [{timestamp}] Job: '{job_name}'")
    print(f"  - Status: {status}")
    print(f"  - Duration: {round(duration, 4)} seconds")
    if error_message:
        print(f"  - Error: {error_message}")
    print("-" * 50)


def job_refresh_materialized_views():
    job_name = "Refresh Materialized Views"
    start_time = time.time()
    print(f"\n-> Starting job: {job_name}...")
    
    try:
        client = MongoClient("mongodb://localhost:27017/")
        db = client["midterm_data_pipeline"]
        
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


def job_generate_periodic_report():
    job_name = "Generate Periodic Summary Report"
    start_time = time.time()
    print(f"\n-> Starting job: {job_name}...")
    
    try:
        client = MongoClient("mongodb://localhost:27017/")
        db = client["midterm_data_pipeline"]
        
        total_orders = db["orders_validated"].estimated_document_count()
        timestamp = datetime.datetime.now().isoformat()
        
        print(f"  [Periodic Report] Total orders count: {total_orders} (Time: {timestamp})")
        
        end_time = time.time()
        duration = end_time - start_time
        log_job_execution(job_name, "SUCCESS", duration)
        
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        log_job_execution(job_name, "FAILED", duration, str(e))


if __name__ == "__main__":
    print("\n=== Manual Scheduled Jobs Test ===")
    
    job_refresh_materialized_views()
    job_generate_periodic_report()
    
    print("\n=== Scheduled Jobs Test Completed ===")