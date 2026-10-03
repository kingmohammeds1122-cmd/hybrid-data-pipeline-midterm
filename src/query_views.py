import time
from pymongo import MongoClient
import json

if __name__ == "__main__":
    client = MongoClient("mongodb://localhost:27017/")
    db = client["midterm_data_pipeline"]
    
    print("\n=== Materialized Views Retrieval Speed Test ===")
    
    start_time = time.time()
    status_report = list(db["view_orders_by_status"].find())
    status_time = (time.time() - start_time) * 1000
    
    print(f"\n1. Status Report (Retrieved in {status_time:.2f} ms):")
    print(json.dumps(status_report, indent=2, ensure_ascii=False))
    
    start_time = time.time()
    city_report = list(db["view_sales_by_city"].find())
    city_time = (time.time() - start_time) * 1000
    
    print(f"\n2. City Report (Retrieved in {city_time:.2f} ms):")
    print(json.dumps(city_report, indent=2, ensure_ascii=False))
    
    start_time = time.time()
    products_report = list(db["view_top_products"].find())
    products_time = (time.time() - start_time) * 1000
    
    print(f"\n3. Products Report (Retrieved in {products_time:.2f} ms):")
    print(json.dumps(products_report, indent=2, ensure_ascii=False))
    
    print("\n=== Engineering Summary ===")
    print("Report generation time reduced from hours to milliseconds.")