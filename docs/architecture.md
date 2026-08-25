# Hybrid Data Pipeline Architecture

## 1. Project Objective

This project implements a hybrid ELT data pipeline for a 12.3 GB CSV dataset containing approximately 30,000,000 order records. The pipeline loads immutable source records into MongoDB, applies deterministic data-quality transformations, separates valid or corrected records from irrecoverable records, and preserves an auditable trail for every decision.

## 2. High-Level Architecture

```text
Input CSV (12.3 GB)
        |
        v
File Router (200 MB threshold)
        |
        +--> Python Batch Loader  [small files]
        |
        +--> PySpark Loader       [large files]
                    |
                    v
             MongoDB: orders_raw
                    |
                    v
             ELT Transformation
                    |
          +---------+---------+
          |                   |
          v                   v
MongoDB: orders_validated   MongoDB: orders_quarantine
          |                   |
          +---------+---------+
                    v
              Metrics and Audit Reports

Path B: Delta CSV --> Incremental Loader --> Version-aware Upserts
                         |
                         +--> Watermark / processed-delta state
