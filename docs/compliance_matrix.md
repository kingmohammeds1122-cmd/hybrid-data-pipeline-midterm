# Assignment Compliance Matrix

This matrix maps the official 11-page assignment requirements to the implementation and submitted evidence. The selected advanced path is **Path B**. Path A cluster requirements are not claimed.

| PDF section | Requirement | Implementation / evidence | Status |
|---|---|---|---|
| 1–4 | Hybrid ELT architecture with automatic Python Batch/PySpark routing | `src/main.py`, `src/file_router.py`, `docs/architecture.md` | PASS |
| 6.1 | Reproducible configurable small sample; no Excel | `src/create_small_sample.py`, README command | PASS |
| 6.2 | One router, configurable 200 MB threshold, printed size/engine/reason | `config/settings.py`, `src/file_router.py`, `src/main.py`, results metrics | PASS |
| 6.3 | Streaming CSV, configurable batches, `insert_many`, no full-file list, progress/error reporting | `src/batch_loader.py`, batch metrics and tests | PASS |
| 6.4 | SparkSession/DataFrame API, fixed String schema, MongoDB Spark Connector, partition metrics, safe Spark cleanup | `src/spark_loader.py`, `scripts/spark_ui_evidence.py`, Spark UI screenshots | PASS |
| 6.5 | Raw-first ELT with run/source/row/time/engine/raw record metadata | `orders_raw`, `src/batch_loader.py`, `src/spark_loader.py` | PASS |
| 6.6 | At least eight deterministic corrections | `src/quality_rules.py`, `tests/`, `reports/results.json` | PASS |
| 6.7 | Correction audit trail with original/corrected values and rule code | `corrections` fields, README and report | PASS |
| 6.8 | Quarantine with explicit error codes and details | `orders_quarantine`, `error_codes`, `error_details`; includes required codes | PASS |
| 6.9 | `orders_raw`, `orders_validated`, `orders_quarantine`; indexes and schema expectations | MongoDB evidence screenshots and report | PASS |
| 6.10 | Stable `order_id`, unique index, upsert, practical idempotency and update proof | `src/elt_pipeline.py`, `scripts/idempotency_update_test.py`, report | PASS |
| 6.11 | Per-run conservation equation | `raw = validated classification + quarantine`; final 30,000,000 conservation evidence | PASS |
| 6.12 | Required metrics and upsert counters | `src/metrics.py`, `reports/results.json`, `reports/path_b_runs.json` | PASS |
| 7 / Path B | Initial Load, Delta-only Insert + Update, version/watermark handling, Insert/Update/Unchanged, replay proof | `src/incremental_loader.py`, Delta CSVs, Path B report and screenshots | PASS |
| 8–9 | Proposed structure, clear main command, config, try/finally, progress, separation, tests | Repository structure, README, source modules, 19 tests | PASS |
| 10 | Practical demo: sample, raw, quality examples, large-file PySpark, Spark UI, collections, metrics, idempotency, Path B | `evidence/` screenshots, reports, README | PASS |
| 11 | GitHub link, README, report, requirements, MongoDB/Spark screenshots, results JSON, idempotency and Path B evidence | Public repository and submitted package | PASS |
| 12–14 | Evaluation, no prohibited behavior, final checklist | Code audit, conservation, tests, evidence, this matrix | PASS |

## Spark UI evidence

The Spark UI evidence was captured from the large-file Spark run. The screenshots show Spark 3.5.6, six completed Jobs, six completed Stages, 99 successful Tasks, 12.4 GiB input, and 30,000,000 input records. The detailed Stage view shows `Process local: 99`, `99 Completed Tasks`, and the task-level input and shuffle metrics.

## Path selection note

The project uses **Path B**. The Path A requirements for a separate Spark Master/Worker cluster, `spark://MASTER_IP:7077`, and cluster-versus-local comparison are therefore not claimed. The local Spark UI screenshot is included because Spark UI is required in the general practical demonstration and delivery evidence.

## Final verification

The working project reported 19 passing tests. The final large-file evidence reports 30,000,000 raw records, 27,788,498 validated records, and 2,211,502 quarantined records, with conservation equal to true. The GitHub repository is `https://github.com/kingmohammeds1122-cmd/hybrid-data-pipeline-midterm`.
