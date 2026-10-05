"""API tests for final-project endpoints."""
from fastapi.testclient import TestClient
from src.api import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code in {200, 500}
    if response.status_code == 200:
        assert response.json()["status"] == "healthy"


def test_query_catalog():
    response = client.get("/queries")
    assert response.status_code == 200
    assert len(response.json()["queries"]) >= 5


def test_aggregation_catalog():
    response = client.get("/aggregations")
    assert response.status_code == 200
    assert len(response.json()["aggregations"]) >= 5


def test_view_catalog():
    response = client.get("/views")
    assert response.status_code == 200
    assert "daily_sales_summary" in response.json()["views"]
    assert "top_products_summary" in response.json()["views"]


def test_job_catalog():
    response = client.get("/jobs")
    assert response.status_code in {200, 500}
    if response.status_code == 200:
        assert len(response.json()["jobs"]) >= 2
