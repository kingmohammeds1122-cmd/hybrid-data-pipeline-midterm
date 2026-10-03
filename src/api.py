from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from src.scheduled_jobs import job_refresh_materialized_views, job_generate_periodic_report
from src.materialized_views import create_status_view, create_city_view, create_products_view

app = FastAPI(
    title="Midterm Data Pipeline API",
    description="Unified API for testing and running big data pipeline functions",
    version="1.0.0"
)

def get_db():
    client = MongoClient("mongodb://localhost:27017/")
    return client["midterm_data_pipeline"]

@app.get("/health")
def health_check():
    try:
        db = get_db()
        db.command("ping")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest")
def trigger_ingest():
    try:
        db = get_db()
        count = db["orders_validated"].estimated_document_count()
        return {"status": "SUCCESS", "message": "Ingestion readiness verified", "current_records": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/indexes")
def trigger_indexes():
    try:
        db = get_db()
        db["orders_validated"].create_index([("status", 1)])
        db["orders_validated"].create_index([("city", 1)])
        db["orders_validated"].create_index([("order_date", 1)])
        return {"status": "SUCCESS", "message": "Indexes created and activated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/queries")
def list_queries():
    return {"queries": ["queries_by_status", "sales_by_city", "top_products"]}

@app.get("/queries/{name}")
def run_query(name: str):
    db = get_db()
    try:
        if name == "queries_by_status" or name == "orders_by_status":
            data = list(db["orders_validated"].find({"status": "Completed"}).limit(10))
        elif name == "sales_by_city":
            data = list(db["orders_validated"].find({"city": {"$exists": True}}).limit(10))
        else:
            data = list(db["orders_validated"].find().limit(10))
        
        for doc in data:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
                
        return {"query_name": name, "status": "executed", "sample_data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {"message": "Welcome to the Big Data Pipeline API, check /docs for documentation."}

@app.get("/aggregations")
def list_aggregations():
    return {
        "aggregations": [
            "orders_by_status",
            "sales_by_city",
            "top_products",
            "top_customers",
            "sales_by_period"
        ]
    }

@app.get("/aggregations/{name}")
def run_aggregation(name: str):
    db = get_db()
    try:
        if name == "orders_by_status":
            view_name = "view_orders_by_status"
        elif name == "sales_by_city":
            view_name = "view_sales_by_city"
        elif name == "top_products":
            view_name = "view_top_products"
        else:
            view_name = name
            
        if view_name in db.list_collection_names():
            data = list(db[view_name].find({}, {"_id": 0}))
        else:
            data = []
            
        return {"aggregation": name, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/refresh-mv")
def refresh_materialized_views():
    try:
        db = get_db()
        create_status_view(db)
        create_city_view(db)
        create_products_view(db)
        return {"status": "SUCCESS", "message": "All materialized views refreshed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jobs")
def list_jobs():
    return {"jobs": ["refresh-materialized-views", "generate-periodic-report"]}

@app.post("/jobs/{name}/run")
def run_job(name: str):
    try:
        if name == "refresh-materialized-views" or name == "refresh_materialized_views":
            job_refresh_materialized_views()
            return {"job": name, "status": "SUCCESS", "message": "Materialized views job executed and logged successfully"}
        elif name == "generate-periodic-report" or name == "generate_periodic_report":
            job_generate_periodic_report()
            return {"job": name, "status": "SUCCESS", "message": "Periodic report job executed and logged successfully"}
        else:
            raise HTTPException(status_code=404, detail="Job not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))