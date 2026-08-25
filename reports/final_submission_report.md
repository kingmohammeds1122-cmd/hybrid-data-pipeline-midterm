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

---

# Academic Submission Evidence Summary

This report consolidates the verified implementation and evidence for the hybrid data pipeline assignment.

Final verified totals: orders_raw = 30,000,000; orders_validated = 27,788,498; orders_quarantine = 2,211,502; conservation = True.

Path B evidence: initial run Insert = 1 and Update = 1; idempotent rerun Unchanged = 2; Failed = 0; watermark remained stable.

Automated verification completed with 17 passed tests. Supporting screenshots are stored in the evidence directory.

Evidence files: final_pipeline_verification.png, mongodb_collections_and_indexes.png, path_b_metrics.png, quality_and_quarantine_metrics.png, and project_structure.png.

## Strict Compliance Updates

The README now includes installation commands, the reproducible sample command, the main pipeline command, a justification for the 200 MB routing threshold, a Python Batch versus PySpark comparison, and an explicit three-experiment Path B narrative.

The quality layer now emits EMPTY_ITEMS for valid empty item arrays and MULTIPLE_CONFLICTING_ERRORS when independent quality errors coexist. These behaviors are covered by permanent automated tests.

The metrics builder now generates required aliases including file_name, file_size_bytes, file_size_mb, rows_read, raw_loaded, valid_count, corrected_count, quarantine_count, elapsed_seconds, throughput, batch_size, partitions_processed, and error_case_counts.

Path B MongoDB cleanup now uses try/finally so the client is closed safely even when an exception occurs.

The final Path B report contains only successful hardened runs. A pre-hardening failed attempt is preserved separately as diagnostic backup evidence and is excluded from the submission report.

## Latest Verification Status

The current implementation includes explicit EMPTY_ITEMS and MULTIPLE_CONFLICTING_ERRORS quarantine codes, permanent edge-case tests, automatic required metrics aliases, safe Path B try/finally cleanup, and a cleaned successful Path B history.

Latest automated verification: 19 passed.

## Spark UI Evidence

Spark UI evidence was captured from the large-file Spark run. The evidence shows Spark 3.5.6, 6 completed Jobs, 6 completed Stages, 99 successful Tasks, 12.4 GiB of input, and 30,000,000 input records. Stage details also show local task execution and task-level input and shuffle metrics.

The selected advanced path is Path B. Path A standalone-cluster requirements are not claimed.
