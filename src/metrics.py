"""Metrics persistence for the hybrid orders data pipeline."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings



def make_json_safe(value: Any) -> Any:
    """Convert common runtime values into JSON-compatible values."""

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            str(key): make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [make_json_safe(item) for item in value]

    if hasattr(value, "item") and callable(value.item):
        return make_json_safe(value.item())

    return value



def build_run_result(
    *,
    run_id: str,
    input_file: Path,
    engine_used: str,
    router_result: dict[str, Any],
    raw_load_result: dict[str, Any],
    elt_result: dict[str, Any],
) -> dict[str, Any]:
    """Build one complete report entry for reports/results.json."""

    return {
        "report_created_at": datetime.now(timezone.utc),
        "run_id": run_id,
        "input_file": input_file,
        "engine_used": engine_used,
        "configuration": {
            "small_file_threshold_mb": settings.SMALL_FILE_THRESHOLD_MB,
            "batch_size": settings.BATCH_SIZE,
            "mongodb_database": settings.MONGODB_DATABASE,
            "orders_raw_collection": settings.ORDERS_RAW_COLLECTION,
            "orders_validated_collection": (
                settings.ORDERS_VALIDATED_COLLECTION
            ),
            "orders_quarantine_collection": (
                settings.ORDERS_QUARANTINE_COLLECTION
            ),
        },
        "router": router_result,
        "raw_load": raw_load_result,
        "elt": elt_result,
        "file_name": input_file.name,
        "file_size_bytes": router_result.get("file_size_bytes"),
        "file_size_mb": router_result.get("file_size_mb"),
        "rows_read": elt_result.get("raw_records_read", 0),
        "raw_loaded": raw_load_result.get("records_loaded", 0),
        "valid_count": elt_result.get("valid_records", 0),
        "corrected_count": elt_result.get("corrected_records", 0),
        "quarantine_count": elt_result.get("quarantined_records", 0),
        "elapsed_seconds": elt_result.get("elapsed_seconds", 0),
        "throughput": elt_result.get("records_per_second", 0),
        "throughput_records_per_second": elt_result.get("records_per_second", 0),
        "batch_size": raw_load_result.get("batch_size", settings.BATCH_SIZE),
        "partitions_processed": raw_load_result.get("partitions_processed"),
        "error_case_counts": elt_result.get("error_case_counts", {}),
        "consistency": {
            "raw_records_read": elt_result.get("raw_records_read", 0),
            "validated_classification_records": (
                elt_result.get("valid_records", 0)
                + elt_result.get("corrected_records", 0)
            ),
            "quarantined_classification_records": elt_result.get(
                "quarantined_records",
                0,
            ),
            "classification_total": (
                elt_result.get("valid_records", 0)
                + elt_result.get("corrected_records", 0)
                + elt_result.get("quarantined_records", 0)
            ),
        },
    }



def read_results_file(results_file: Path) -> dict[str, Any]:
    """Read the report file or return an empty report structure."""

    if not results_file.exists() or results_file.stat().st_size == 0:
        return {"runs": []}

    with results_file.open("r", encoding="utf-8") as file_handle:
        content = json.load(file_handle)

    if not isinstance(content, dict):
        raise ValueError("The metrics report must contain a JSON object.")

    runs = content.get("runs")
    if runs is None:
        content["runs"] = []
    elif not isinstance(runs, list):
        raise ValueError("The metrics report field 'runs' must be a list.")

    return content



def write_results_file(
    result: dict[str, Any],
    results_file: Path = settings.RESULTS_FILE,
) -> None:
    """Append a result atomically so a partial write cannot corrupt JSON."""

    results_file.parent.mkdir(parents=True, exist_ok=True)
    report = read_results_file(results_file)
    report["runs"].append(make_json_safe(result))

    serialized_report = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
    )

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix="results_",
        suffix=".tmp",
        dir=results_file.parent,
        text=True,
    )

    try:
        with os.fdopen(
            file_descriptor,
            mode="w",
            encoding="utf-8",
            newline="\n",
        ) as temporary_handle:
            temporary_handle.write(serialized_report)
            temporary_handle.write("\n")
            temporary_handle.flush()
            os.fsync(temporary_handle.fileno())

        os.replace(temporary_name, results_file)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise



def validate_result_consistency(result: dict[str, Any]) -> None:
    """Validate the required raw-to-classification conservation equation."""

    consistency = result.get("consistency", {})
    raw_records = consistency.get("raw_records_read", 0)
    classification_total = consistency.get("classification_total", 0)

    if raw_records != classification_total:
        raise ValueError(
            "Metrics inconsistency: raw_records_read must equal "
            "valid_records + corrected_records + quarantined_records."
        )
