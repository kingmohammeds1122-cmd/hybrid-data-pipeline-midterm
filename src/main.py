"""Single entry point for the complete hybrid ELT data pipeline."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from config import settings
from src.batch_loader import load_csv_to_raw
from src.elt_pipeline import process_run
from src.file_router import route_file
from src.metrics import (
    build_run_result,
    validate_result_consistency,
    write_results_file,
)
from src.schema_validation import validate_headers
from src.spark_loader import load_csv_to_raw_with_spark


class MainPipelineError(RuntimeError):
    """Raised when the complete pipeline cannot finish safely."""


def validate_input_file_schema(input_file: Path) -> None:
    """Validate CSV headers before inserting any raw data."""
    with input_file.open(
        "r",
        encoding=settings.CSV_ENCODING,
        newline=settings.CSV_NEWLINE,
    ) as handle:
        reader = csv.DictReader(handle)
        validate_headers(reader.fieldnames)


def routing_result_as_dict(decision: Any) -> dict[str, Any]:
    """Convert a RoutingDecision into a report-friendly dictionary."""
    return {
        "file_path": str(decision.file_path),
        "file_size_bytes": decision.file_size_bytes,
        "file_size_mb": decision.file_size_mb,
        "threshold_mb": decision.threshold_mb,
        "engine": decision.engine,
        "reason": decision.reason,
    }


def run_complete_pipeline(
    input_file: Path,
    progress_interval: int,
) -> dict[str, Any]:
    """Route, validate, load, transform, classify, and persist one run."""
    decision = route_file(input_file)
    validate_input_file_schema(decision.file_path)
    router_result = routing_result_as_dict(decision)

    print(f"Input file: {decision.file_path}")
    print(f"File size: {decision.file_size_mb:.2f} MB")
    print(f"Selected engine: {decision.engine}")
    print(f"Profile: {settings.PIPELINE_PROFILE}")
    print(f"Database: {settings.MONGODB_DATABASE}")
    print("Input schema: PASS")
    print(f"Reason: {decision.reason}")

    if decision.engine == "python_batch":
        raw_load_result = load_csv_to_raw(
            input_file=decision.file_path,
            batch_size=settings.BATCH_SIZE,
        )
    elif decision.engine == "pyspark":
        raw_load_result = load_csv_to_raw_with_spark(
            input_file=decision.file_path,
        )
    else:
        raise MainPipelineError(
            f"Unsupported engine selected: {decision.engine}"
        )

    run_id = str(raw_load_result["run_id"])
    elt_result = process_run(
        run_id=run_id,
        progress_interval=progress_interval,
    )

    result = build_run_result(
        run_id=run_id,
        input_file=decision.file_path,
        engine_used=decision.engine,
        router_result=router_result,
        raw_load_result=raw_load_result,
        elt_result=elt_result,
    )

    validate_result_consistency(result)
    write_results_file(result)
    return result


def print_professor_results(result: dict[str, Any]) -> None:
    """Print the exact labels used in the professor's reference sheet."""
    elt_metrics = result.get("elt", {})
    raw_metrics = result.get("raw_load", {})

    input_orders_raw = int(
        elt_metrics.get(
            "raw_records_read",
            raw_metrics.get("records_loaded", 0),
        )
    )
    clean_valid = int(elt_metrics.get("valid_records", 0))
    corrected = int(elt_metrics.get("corrected_records", 0))
    quarantine = int(elt_metrics.get("quarantined_records", 0))
    orders_validated = clean_valid + corrected
    consistency = orders_validated + quarantine

    print()
    print("==========================================")
    print("بيانات التدريب العامة - مقرر البيانات الضخمة")
    print("==========================================")
    print()
    print(f"Input / orders_raw: {input_orders_raw:,}")
    print(f"Clean Valid: {clean_valid:,}")
    print(f"Corrected: {corrected:,}")
    print(f"orders_validated: {orders_validated:,}")
    print(f"orders_quarantine: {quarantine:,}")
    print(f"Consistency: {consistency:,}")
    print("==========================================")


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the complete-pipeline command-line interface."""
    parser = argparse.ArgumentParser(
        description="Run the complete hybrid orders ELT pipeline."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=settings.SOURCE_DATA_FILE,
        help="Input CSV path.",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=10_000,
        help="Print ELT progress after this many records.",
    )
    return parser


def main() -> int:
    """Run the complete pipeline and print final metrics."""
    parser = build_argument_parser()
    arguments = parser.parse_args()

    try:
        result = run_complete_pipeline(
            input_file=arguments.input,
            progress_interval=arguments.progress_interval,
        )
    except (
        FileNotFoundError,
        ValueError,
        OSError,
        MainPipelineError,
    ) as error:
        parser.error(str(error))
        return 2

    print("Complete hybrid ELT pipeline finished successfully")
    print(f"run_id: {result['run_id']}")
    print(f"engine_used: {result['engine_used']}")
    print(f"results_file: {settings.RESULTS_FILE}")
    print(
        "classification_total: "
        f"{result['consistency']['classification_total']}"
    )
    print_professor_results(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
