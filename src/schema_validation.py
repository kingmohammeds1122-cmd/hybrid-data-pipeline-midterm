"""Schema gates for the student test and the general pipeline."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

RAW_REQUIRED_FIELDS = {
    "order_id", "order_date", "status", "customer_id", "customer_name",
    "customer_phone", "customer_email", "city", "district", "delivery_type",
    "delivery_cost", "payment_method", "payment_status", "payment_amount",
    "currency", "total_amount", "items_json",
}

FINAL_REQUIRED_FIELDS = RAW_REQUIRED_FIELDS | {
    "quality_status", "corrections", "error_codes", "error_details",
    "run_id", "source_row_number",
}


class SchemaValidationError(ValueError):
    """Raised when an input or final document violates the project schema."""


def validate_headers(headers: Iterable[str] | None) -> None:
    actual = set(headers or [])
    missing = sorted(RAW_REQUIRED_FIELDS - actual)
    if missing:
        raise SchemaValidationError(
            "Input schema validation failed; missing columns: "
            + ", ".join(missing)
        )


def validate_raw_record(record: Mapping[str, Any], source_row: int) -> None:
    missing = sorted(field for field in RAW_REQUIRED_FIELDS if field not in record)
    if missing:
        raise SchemaValidationError(
            f"Raw schema failed at source row {source_row}; missing: "
            + ", ".join(missing)
        )


def validate_final_document(document: Mapping[str, Any], source_row: int) -> None:
    missing = sorted(field for field in FINAL_REQUIRED_FIELDS if field not in document)
    if missing:
        raise SchemaValidationError(
            f"Final schema failed at source row {source_row}; missing: "
            + ", ".join(missing)
        )

    if document.get("quality_status") not in {"valid", "corrected", "quarantined"}:
        raise SchemaValidationError(
            f"Final schema failed at source row {source_row}; invalid quality_status."
        )

    if not isinstance(document.get("corrections"), list):
        raise SchemaValidationError(
            f"Final schema failed at source row {source_row}; corrections must be a list."
        )

    if not isinstance(document.get("error_codes"), list):
        raise SchemaValidationError(
            f"Final schema failed at source row {source_row}; error_codes must be a list."
        )

    if not isinstance(document.get("error_details"), list):
        raise SchemaValidationError(
            f"Final schema failed at source row {source_row}; error_details must be a list."
        )
