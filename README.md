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
