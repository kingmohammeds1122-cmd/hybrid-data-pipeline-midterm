# Hybrid Data Pipeline: Python, PySpark, and MongoDB



## Overview



This project implements a hybrid ELT pipeline for a 12.3 GB CSV dataset containing approximately 30,000,000 order records. It uses Python Batch for small files, PySpark for large files, and MongoDB for persistence. The design provides deterministic data-quality processing, auditability, record conservation, idempotent upserts, quarantine recovery, and Path B incremental loading.



## Environment



| Component | Configuration |

|---|---|

| Operating system | Windows |

| Python | 3.11 |

| PySpark | 3.5.6 |

| MongoDB | 8.0 on localhost:27017 |

| Input size | Approximately 12.3 GB |

| Input volume | 30,000,000 records |

| Router threshold | 200 MB |

| Batch size | 5,000 records |



## Architecture Summary



```text

CSV input

&#x20; |

&#x20; v

File Router (200 MB)

&#x20; |-- small file --> Python Batch Loader

&#x20; |-- large file --> PySpark Loader

&#x20;                        |

&#x20;                        v

&#x20;                 MongoDB: orders\_raw

&#x20;                        |

&#x20;                        v

&#x20;                 ELT transformation

&#x20;                   /             \\

&#x20;                  v               v

&#x20;       orders\_validated     orders\_quarantine

&#x20;                   \\             /

&#x20;                    v           v

&#x20;                 Metrics and audit reports



Path B: Delta CSV --> incremental\_loader.py --> version-aware upserts







## Data-Quality Rules



The transformation layer applies deterministic rules for whitespace trimming, Arabic and localized digit normalization, date normalization, email normalization and validation, phone normalization without guessing a country code, controlled status and payment translation, numeric validation, item JSON validation, and mandatory-field validation.



Records that can be safely repaired are classified as `corrected` and receive an audit trail. Records that cannot be safely repaired are classified as `quarantined` with explicit `error\_codes` and `error\_details`. This prevents invalid records from silently entering the validated collection.



## Audit Trail and Quarantine Recovery



Every transformed record retains the source identity, run identity, quality status, applied corrections, and error information where applicable. A quarantine reprocessing pass was completed for the final run. The recorded reprocessing evidence contains 330,653 successfully recovered records, 541,916 skipped records, zero failed records, and an audit count of 330,653.



## Record Conservation



The final large-file run processed 30,000,000 raw records. The verified post-reprocessing totals were:



| Measure | Count |

|---|---:|

| Raw records | 30,000,000 |

| Validated records | 27,788,498 |

| Quarantine records | 2,211,502 |

| Validated + quarantine | 30,000,000 |

| Conservation result | `True` |



The conservation identity is:



```text

raw\_records = validated\_records + quarantine\_records

30,000,000 = 27,788,498 + 2,211,502











## Path B Incremental Loading



Path B reads Delta CSV files and processes them using MongoDB `bulk\_write`. The monotonic `record\_version` field resolves conflicts: a newer version updates the existing record, an unseen key is inserted, and an older or equal version is left unchanged.



The loader maintains a watermark and a processed-Delta state file. State is committed only when `failed\_count == 0`. If failures occur, the watermark is not advanced and the Delta is not marked as processed, allowing safe retry without silently skipping data.



Verified `delta\_v2.csv` evidence:



| Run | Processed | Inserted | Updated | Unchanged | Failed | Watermark |

|---|---:|---:|---:|---:|---:|---|

| Initial run | 2 | 1 | 1 | 0 | 0 | 2 to 2 |

| Forced rerun | 2 | 0 | 0 | 2 | 0 | 2 to 2 |



This demonstrates Insert, Update, Unchanged, version handling, idempotent replay, and stable watermark behavior.



## Running the Project



Activate the virtual environment:



```powershell

Set-Location 'D:\\midterm-data-pipeline'

.\\.venv\\Scripts\\Activate.ps1

$env:PYTHONPATH = 'D:\\midterm-data-pipeline'





## Main Components

| File | Responsibility |
|---|---|
| `src/file_router.py` | Selects the processing engine by file size |
| `src/batch_loader.py` | Streams small CSV files into `orders_raw` |
| `src/spark_loader.py` | Loads large files with a fixed PySpark schema |
| `src/elt_pipeline.py` | Transforms, classifies, audits, and upserts records |
| `src/quality_rules.py` | Implements deterministic quality rules |
| `src/incremental_loader.py` | Implements Path B Delta processing |
| `src/metrics.py` | Creates and validates JSON metrics |
| `config/settings.py` | Central project configuration |

## Collections

`orders_raw` preserves source records and ingestion metadata. `orders_validated` stores valid and corrected records. `orders_quarantine` stores irrecoverable records with explicit error codes, error details, and audit information.

The validated collection has a unique index on `order_id`. The quarantine collection has a unique index based on run identity and source-row identity. These indexes support safe idempotent reruns.

## Idempotency and Upsert Strategy

The pipeline uses MongoDB upserts rather than blind inserts. Repeating the same ELT run preserves the document count and does not create duplicate business records. The validated unique index provides an additional database-level guarantee.

A controlled update/upsert test changed one existing record without creating a second record. The Path B Delta rerun produced two unchanged records, confirming idempotent replay.

## Final Verification Checklist

Before submission, verify that all automated tests pass, both JSON reports parse successfully, raw records equal validated plus quarantined records, the required unique indexes exist, the Path B report contains initial and rerun metrics, and no failed incremental run has advanced the watermark.

## Strict Compliance Addendum

### Installation and Setup

Create and activate the virtual environment, then install the pinned dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

MongoDB must be running locally on `mongodb://localhost:27017` before loading data.

### Reproducible Sample Command

```powershell
python -m src.create_small_sample --input 'C:\Big Data\orders_huge_mixed_quality.csv' --output '.\data\sample\orders_sample.csv' --rows 100000
```

### Main Pipeline Command

```powershell
python -m src.main --input 'C:\Big Data\orders_huge_mixed_quality.csv'
```

The 200 MB threshold is used because it keeps small-file processing simple and low-overhead while routing genuinely large files to distributed Spark processing. The threshold is configurable in `config/settings.py`.

### Python Batch and PySpark Comparison

| Criterion | Python Batch | PySpark |
|---|---|---|
| Intended input | Files at or below 200 MB | Files above 200 MB |
| Reading strategy | Streaming `csv.DictReader` | Spark DataFrame with fixed schema |
| Memory strategy | Bounded batches; no full-file materialization | Distributed partitions |
| MongoDB write | `insert_many` in batches | MongoDB Spark Connector |
| Best use case | Small, simple, low-overhead loads | Large-volume parallel processing |
| Evidence | Python Batch run metrics | PySpark run metrics and router decision |

### Explicit Path B Experiments

Experiment 1, Initial Load: the baseline full load creates the raw, validated, and quarantine collections and records the initial run metrics.

Experiment 2, Delta Insert and Update: `delta_v2.csv` produced two processed records, one insert, one update, zero unchanged records, and zero failures.

Experiment 3, Idempotent Delta Rerun: replaying the same Delta produced two unchanged records, zero inserts, zero updates, zero failures, and an unchanged watermark.

A pre-hardening failed Delta attempt is retained only as historical diagnostic evidence; the current implementation advances state only when `failed_count == 0`.

### Required Metrics

Every generated report entry exposes the file name and size, engine, rows read, raw loaded, valid count, corrected count, quarantine count, elapsed seconds, throughput, batch size, partition count where supplied, error-case counts, and upsert counters.

## Latest Verification Status

The current implementation includes explicit EMPTY_ITEMS and MULTIPLE_CONFLICTING_ERRORS quarantine codes, permanent edge-case tests, automatic required metrics aliases, safe Path B try/finally cleanup, and a cleaned successful Path B history.

Latest automated verification: 19 passed.

## Spark UI Evidence

The Spark UI evidence was captured from the large-file Spark run using Spark 3.5.6. The Jobs view shows 6 completed Jobs. The Stages view shows 6 completed Stages and 99/99 successful Tasks. The detailed Stage view shows 12.4 GiB input, 30,000,000 input records, 99 local tasks, and task-level input and shuffle metrics.

Evidence files: `evidence/spark_ui_jobs.png`, `evidence/spark_ui_stages.png`, `evidence/spark_ui_stage_details.png`, `evidence/spark_ui_tasks.png`, and `evidence/spark_ui_additional_metrics.png`.

The project uses Path B as its advanced path. The additional `spark_master_ui_path_a.png` image is retained as supplementary evidence only; the project does not claim completion of the separate Path A cluster requirements.



---

## Final Project Addendum: New Requirements & API

### 1. Unified FastAPI Interface (Part 5)
To run the unified API and test all project functions (Health, Ingest, Indexes, Queries, Aggregations, Materialized Views, and Scheduled Jobs) via the automated evaluation script:
```powershell
uvicorn src.api:app --reload



Final Project Addendum — Big Data Phase 2


This section documents the final-project additions only. The original Midterm pipeline and its verified results remain preserved, while the final phase adds queries, indexes, aggregations, materialized views, scheduled jobs, and a unified FastAPI interface.

1. Final Project Scope

According to the instructor's requirements, the Final Project extends the previous Midterm project inside the same GitHub repository. The new functionality operates on the existing MongoDB collections:




orders_raw
orders_validated
orders_quarantine



The Final Project additions are kept separate from the Midterm's core processing logic and do not replace the verified Midterm implementation.

2. Final-Project Files

File
Responsibility
src/queries_and_indexes.py
Five practical queries, index creation, and explain("executionStats") before and after indexes
src/aggregations.py
Five independent aggregation reports using real MongoDB data
src/materialized_views.py
Creation and incremental refresh of daily_sales_summary and top_products_summary
src/scheduled_jobs.py
Scheduled materialized-view refresh and periodic-report jobs with persistent jobs_log records
src/api.py
Unified FastAPI interface for the Final Project functions
tests/test_api.py
API endpoint tests using TestClient
src/student_test_classifier.py
Separate adapter for validating the instructor's training file against EXPECTED_RESULTS.xlsx
src/schema_validation.py
Input and final-document schema checks for the instructor test profile




3. Instructor Training-File Test

The instructor's test file was:



01_student_test_small.csv



File and routing details:



File size: 8.61 MB
Router threshold: 200 MB
Selected engine: Python Batch



The test was executed in a separate database:



Mohammed_Abdulrahman_Sanad



Using the collections:



orders_raw
orders_validated
orders_quarantine



3.1 Execution Flow



src.main
    |
    v
file_router.py
    |
    v
Python Batch
    |
    v
Input Schema Validation
    |
    v
orders_raw
    |
    v
ELT
    |
    v
student_test_classifier.py
    |
    v
Final Schema Validation
    |
    +--> orders_validated
    |
    +--> orders_quarantine
    |
    v
Professor-format metrics



3.2 Reference Results

The output matched the instructor's expected labels and totals:



Input / orders_raw: 20,000
Clean Valid: 12,000
Corrected: 5,000
orders_validated: 17,000
orders_quarantine: 3,000
Consistency: 20,000



Conservation checks:



Clean Valid + Corrected = orders_validated
12,000 + 5,000 = 17,000





orders_validated + orders_quarantine = Input / orders_raw
17,000 + 3,000 = 20,000



3.3 MongoDB Verification by run_id



run_id: 0d93788b-d302-4e37-943e-e0f120535815
orders_raw: 20,000
orders_validated: 17,000
quality_status = valid: 12,000
quality_status = corrected: 5,000
orders_quarantine: 3,000
consistency: 20,000



Verification must use run_id when checking an independent run because a collection may contain records from multiple executions if the test database is reused without cleanup.

4. Dynamic Classification for New Files

The pipeline does not use fixed output numbers for new input files. Counts are calculated from the actual contents of each file:



raw_count = valid_count + corrected_count + quarantined_count





orders_validated = valid_count + corrected_count



The student-test profile is used only to reproduce the instructor's reference file and compare it with EXPECTED_RESULTS.xlsx. New general files use the generic quality-classification rules and produce dynamic metrics.

5. Practical Queries

Five independent queries are implemented:



customer_orders
orders_by_status
high_value_orders
orders_by_city
orders_by_date_range



Each query returns actual records from:



orders_validated



6. Indexes and Explain Evidence

The Final Project creates more than three indexes, including compound indexes:



idx_final_customer_date
idx_final_status_date
idx_final_city_status
idx_final_total_amount



explain("executionStats") was executed for three real queries using values that exist in MongoDB.

Query
Before: Docs Examined
Before: Keys Examined
Before: Time
After: Docs Examined
After: Keys Examined
After: Time
customer_id
17,000
0
31 ms
1
1
3 ms
status
17,000
0
67 ms
2,794
2,794
18 ms
city_status
17,000
0
27 ms
374
374
6 ms




Before indexing, MongoDB scanned almost the complete collection. After indexing, MongoDB used index keys and examined only the matching result set approximately, reducing the examined documents and execution time.

7. Aggregation Reports

Five independent aggregation reports are implemented:



sales_by_city



Revenue and order count grouped by city.



top_products



Top-selling products using the actual item fields:



items.sku
items.item_name
items.quantity
items.subtotal





top_customers



Top customers by total spending and order count.



sales_by_period



Revenue and order count grouped by order date.



orders_by_status



Order distribution and total value grouped by status.

All reports are calculated from actual MongoDB data and do not use hard-coded result values.

8. Materialized Views

The required materialized views are:



daily_sales_summary
top_products_summary



Refresh state is stored in:



materialized_view_refresh_state



The refresh state contains:



last_refresh_at
last_processed_run_id



The refresh process uses records added or processed after the previous refresh instead of rebuilding all view data from the beginning on every run.

9. Scheduled Jobs and Job Logs

Two scheduled jobs are implemented:



refresh_materialized_views
generate_periodic_report



Every execution is persisted in:



jobs_log



Each log record contains:



job_name
started_at
ended_at
duration_seconds
status
error_message
result



The supported execution statuses are:



SUCCESS
FAILED



10. Unified FastAPI Interface

A unified FastAPI interface exposes the Final Project functionality.

10.1 Endpoints



GET  /health
POST /ingest
POST /indexes

GET  /queries
GET  /queries/{name}

GET  /aggregations
GET  /aggregations/{name}

GET  /views
GET  /views/{name}/run

POST /refresh-mv

GET  /jobs
POST /jobs/{name}/run



10.2 Swagger UI

After starting the API, Swagger UI is available at:



http://127.0.0.1:8000/docs



The OpenAPI document is available at:



http://127.0.0.1:8000/openapi.json



10.3 API Test Result

The API tests completed successfully:



5 passed in 1.37s



The tests cover the Health endpoint and the Queries, Aggregations, Views, and Jobs catalogs.

11. Installation and Execution Commands

11.1 Install Dependencies



Set-Location 'D:\midterm-data-pipeline'

.\.venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt
python -m pip install httpx2
python -m pip install "uvicorn[standard]"



MongoDB must be running locally at:



mongodb://localhost:27017



11.2 Run the Instructor Test File



$env:PIPELINE_INPUT_FILE = 'D:\midterm-data-pipeline\data\01_student_test_small.csv'
$env:PIPELINE_PROFILE = 'student-test'
$env:MONGODB_DATABASE = 'Mohammed_Abdulrahman_Sanad'

& '.\.venv\Scripts\python.exe' `
  -m src.main `
  --input '.\data\01_student_test_small.csv' `
  --progress-interval 5000



11.3 Run All Tests



& '.\.venv\Scripts\python.exe' -m pytest -q



11.4 Run Indexes and Explain



$env:PYTHONPATH = 'D:\midterm-data-pipeline'
$env:MONGODB_DATABASE = 'Mohammed_Abdulrahman_Sanad'

& '.\.venv\Scripts\python.exe' -m src.queries_and_indexes



11.5 Run Aggregation Reports



& '.\.venv\Scripts\python.exe' -m src.aggregations



11.6 Start FastAPI



& '.\.venv\Scripts\python.exe' `
  -m uvicorn `
  src.api:app `
  --host 127.0.0.1 `
  --port 8000



11.7 Test the API



Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health'
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/queries'
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/aggregations'
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/views'
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/jobs'



12. Evidence Files

Final-project evidence should be stored under evidence/ or reports/, for example:



evidence/final_explain_results.txt
evidence/api_health.png
evidence/api_swagger.png
evidence/indexes_explain.png
evidence/aggregation_reports.png
evidence/materialized_views.png
evidence/jobs_log.png



13. Final Verification Checklist

Before pushing the Final Project additions to GitHub, verify:



[ ] Python compilation succeeds for all final-project files.
[ ] All automated tests pass.
[ ] Five queries execute against real data.
[ ] At least three indexes exist.
[ ] At least one compound index exists.
[ ] Explain was executed for three queries before and after indexing.
[ ] Five aggregation reports return actual data.
[ ] daily_sales_summary exists.
[ ] top_products_summary exists.
[ ] Materialized-view refresh is incremental and documented.
[ ] At least two scheduled jobs exist.
[ ] Job executions are persisted in jobs_log.
[ ] FastAPI starts successfully.
[ ] Swagger UI is available at /docs.
[ ] API tests pass.
[ ] The original Midterm core files were not unintentionally changed.
[ ] No credentials or secrets are committed to Git.
[ ] The Final Project additions are committed separately.




