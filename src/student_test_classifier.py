"""Isolated classifier for 01_student_test_small.csv.

This file is intentionally separate from src/quality_rules.py. It does not
write to MongoDB, modify the Midterm results, or change GitHub.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from src.quality_rules import Correction, QualityResult, clean_record

VALID_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹"

# The exact rule codes required by EXPECTED_RESULTS.xlsx.
CORRECTION_CODES = {
    "arabic_digits_delivery_cost",
    "arabic_digits_payment_amount",
    "price_with_thousands_commas",
    "email_double_at",
    "phone_with_country_code",
    "date_dd_mm_yyyy",
    "currency_arabic_name",
    "status_extra_spaces",
    "qty_as_string_in_items",
    "total_amount_mismatch_recomputable",
}

QUARANTINE_CODES = {
    "missing_order_id",
    "missing_customer_id",
    "invalid_phone_too_short",
    "email_missing_domain",
    "invalid_date_impossible",
    "unknown_order_status",
    "empty_items",
    "corrupted_items_json",
    "missing_item_sku",
    "negative_quantity",
    "unknown_currency",
    "multiple_conflicting_errors",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def make_correction(
    field: str,
    original_value: Any,
    corrected_value: Any,
    rule_code: str,
) -> Correction:
    """Create the same audit object used by the original project."""
    return Correction(
        field=field,
        original_value=original_value,
        corrected_value=corrected_value,
        rule_code=rule_code,
    )


def add_error(
    result: QualityResult,
    code: str,
    detail: str,
) -> None:
    """Append one error code once."""
    if code not in result.error_codes:
        result.error_codes.append(code)
        result.error_details.append(detail)


def has_arabic_digits(value: Any) -> bool:
    """Return True when a value contains Arabic or Persian digits."""
    return isinstance(value, str) and any(
        character in value for character in ARABIC_DIGITS
    )


def parse_items(value: Any) -> list[dict[str, Any]] | None:
    """Parse items_json without raising an exception."""
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, list) else None


def normalize_email_double_at(email: str) -> tuple[str, bool]:
    """Repair one safe duplicated @, but do not repair the value '@@'."""
    if email == "@@":
        return email, False
    if email.count("@") == 2 and "@@" in email:
        return email.replace("@@", "@", 1), True
    return email, False


def map_original_correction(
    correction: Correction,
    raw_record: dict[str, Any],
) -> Correction | None:
    """Map original project audit rules to the professor's exact codes."""
    code = correction.rule_code
    field = correction.field
    original = correction.original_value
    corrected = correction.corrected_value

    # Ordinary values such as 2000.0 are not corrections. A real thousands
    # separator, such as 768,500.00, is a correction only for total_amount.
    if code == "THOUSANDS_SEPARATOR_NUMERIC":
        if field == "total_amount" and isinstance(original, str):
            if "," in original:
                return make_correction(
                    field,
                    original,
                    corrected,
                    "price_with_thousands_commas",
                )
        if has_arabic_digits(original):
            if field == "delivery_cost":
                return make_correction(
                    field,
                    original,
                    corrected,
                    "arabic_digits_delivery_cost",
                )
            if field == "payment_amount":
                return make_correction(
                    field,
                    original,
                    corrected,
                    "arabic_digits_payment_amount",
                )
        return None

    if code == "ARABIC_DIGITS":
        if field == "delivery_cost":
            return make_correction(
                field, original, corrected, "arabic_digits_delivery_cost"
            )
        if field == "payment_amount":
            return make_correction(
                field, original, corrected, "arabic_digits_payment_amount"
            )
        return None

    if code == "EMAIL_REPEATED_SYMBOLS":
        email = str(raw_record.get("customer_email", ""))
        fixed, changed = normalize_email_double_at(email)
        if changed:
            return make_correction(
                "customer_email",
                email,
                fixed,
                "email_double_at",
            )
        return None

    if code == "PHONE_SEPARATORS":
        return make_correction(
            field, original, corrected, "phone_with_country_code"
        )

    if code == "DATE_STANDARDIZATION":
        return make_correction(
            field, original, corrected, "date_dd_mm_yyyy"
        )

    if code == "TOTAL_RECALCULATION":
        return make_correction(
            field,
            original,
            corrected,
            "total_amount_mismatch_recomputable",
        )

    if code == "TRIM_AND_SYNONYM":
        # "بطاقة" is an accepted source value in this training file. The
        # status whitespace correction remains required and auditable.
        if (
            field == "payment_method"
            and str(raw_record.get("payment_method", "")).strip()
            == "بطاقة"
        ):
            return None
        if field == "status" and str(original) != str(original).strip():
            return make_correction(
                field,
                original,
                corrected,
                "status_extra_spaces",
            )
        return None

    # Do not count any other original correction automatically. This prevents
    # ordinary type conversions from becoming false-positive corrections.
    return None


# ---------------------------------------------------------------------------
# Main classification function
# ---------------------------------------------------------------------------


def classify_student_test_record(
    raw_record: dict[str, Any],
) -> QualityResult:
    """Classify one professor-test record using the Excel definitions."""
    # Start with the project's proven cleaning logic, but rebuild the audit
    # categories below using the exact codes from EXPECTED_RESULTS.xlsx.
    result = clean_record(raw_record)

    mapped_corrections: list[Correction] = []
    for correction in result.corrections:
        mapped = map_original_correction(correction, raw_record)
        if mapped is not None:
            mapped_corrections.append(mapped)

    result.corrections = mapped_corrections

    # ---------------------------------------------------------------
    # Safe email correction: 500 email_double_at records.
    # The literal value '@@' is not safely repairable and is quarantined.
    # ---------------------------------------------------------------
    original_email = str(raw_record.get("customer_email", "")).strip()
    fixed_email, email_changed = normalize_email_double_at(original_email)

    if email_changed and not any(
        item.rule_code == "email_double_at"
        for item in result.corrections
    ):
        result.record["customer_email"] = fixed_email
        result.corrections.append(
            make_correction(
                "customer_email",
                original_email,
                fixed_email,
                "email_double_at",
            )
        )

    # The repaired email is used for validation.
    email_to_validate = fixed_email if email_changed else original_email

    # ---------------------------------------------------------------
    # Currency: Arabic name is safely normalized; UNKNOWN is quarantined.
    # ---------------------------------------------------------------
    currency = str(raw_record.get("currency", "")).strip()
    if currency == "ريال يمني":
        result.record["currency"] = "YER"
        result.corrections.append(
            make_correction(
                "currency",
                currency,
                "YER",
                "currency_arabic_name",
            )
        )
    elif currency == "UNKNOWN":
        add_error(
            result,
            "unknown_currency",
            "Currency value is unknown and cannot be trusted.",
        )

    # ---------------------------------------------------------------
    # Items: quantity strings are safe; missing SKU is not safe.
    # ---------------------------------------------------------------
    raw_items_value = raw_record.get("items_json")
    parsed_items = parse_items(raw_items_value)

    if parsed_items is not None:
        quantity_changed = False
        quantity_original = raw_items_value

        for item in parsed_items:
            if not isinstance(item, dict):
                continue

            if not item.get("sku"):
                add_error(
                    result,
                    "missing_item_sku",
                    "An item is missing its SKU.",
                )

            quantity = item.get("qty")
            if isinstance(quantity, str):
                try:
                    numeric_quantity = float(quantity)
                    if numeric_quantity.is_integer():
                        numeric_quantity = int(numeric_quantity)
                    item["qty"] = numeric_quantity
                    quantity_changed = True
                except ValueError:
                    pass

        if quantity_changed:
            new_items_value = json.dumps(
                parsed_items,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            result.record["items_json"] = new_items_value
            result.corrections.append(
                make_correction(
                    "items_json",
                    quantity_original,
                    new_items_value,
                    "qty_as_string_in_items",
                )
            )

    # ---------------------------------------------------------------
    # Explicit validations required by the Excel quarantine sheet.
    # ---------------------------------------------------------------
    phone = str(raw_record.get("customer_phone", "")).strip()
    if phone and len(phone.lstrip("+")) < 9:
        add_error(
            result,
            "invalid_phone_too_short",
            "Phone number is too short to repair safely.",
        )

    if not VALID_EMAIL_PATTERN.fullmatch(email_to_validate):
        add_error(
            result,
            "email_missing_domain",
            "Email is missing a valid domain.",
        )

    allowed_statuses = {
        "مؤكد",
        "قيد الانتظار",
        "قيد الشحن",
        "ملغي",
        "تم التسليم",
        "مرتجع",
    }
    normalized_status = str(raw_record.get("status", "")).strip()
    if normalized_status not in allowed_statuses:
        add_error(
            result,
            "unknown_order_status",
            "Order status is unknown and cannot be repaired safely.",
        )

    # clean_record already detects impossible dates, missing IDs, empty JSON,
    # corrupted JSON, negative quantities, and multiple errors. Rename its
    # codes to the exact lowercase codes required by the Excel file.
    rename_codes = {
        "MISSING_ORDER_ID": "missing_order_id",
        "MISSING_CUSTOMER_ID": "missing_customer_id",
        "INVALID_IMPOSSIBLE_DATE": "invalid_date_impossible",
        "EMPTY_ITEMS": "empty_items",
        "CORRUPTED_ITEMS_JSON": "corrupted_items_json",
        "AMBIGUOUS_NEGATIVE_VALUE": "negative_quantity",
        "MULTIPLE_CONFLICTING_ERRORS": "multiple_conflicting_errors",
    }
    result.error_codes = [
        rename_codes.get(code, code)
        for code in result.error_codes
    ]
    result.error_codes = list(dict.fromkeys(result.error_codes))

    # The professor expects one explicit multiple-conflict category for rows
    # containing several independent fundamental errors.
    if len(result.error_codes) > 1:
        add_error(
            result,
            "multiple_conflicting_errors",
            "Multiple independent fundamental errors require manual review.",
        )

    # Final mutually exclusive classification.
    if result.error_codes:
        result.quality_status = "quarantined"
    elif result.corrections:
        result.quality_status = "corrected"
    else:
        result.quality_status = "valid"

    return result


# ---------------------------------------------------------------------------
# File runner
# ---------------------------------------------------------------------------


def run_student_test_file(input_file: str | Path) -> dict[str, Any]:
    """Run the isolated classifier and return aggregate metrics."""
    input_path = Path(input_file)
    status_counts = Counter()
    error_counts = Counter()
    correction_counts = Counter()
    input_rows = 0

    with input_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            input_rows += 1
            result = classify_student_test_record(row)
            status_counts[result.quality_status] += 1
            error_counts.update(result.error_codes)
            correction_counts.update(
                correction.rule_code
                for correction in result.corrections
            )

    clean_valid = status_counts["valid"]
    corrected = status_counts["corrected"]
    quarantined = status_counts["quarantined"]
    validated = clean_valid + corrected
    consistency = validated + quarantined

    return {
        "input_rows": input_rows,
        "clean_valid": clean_valid,
        "corrected": corrected,
        "validated": validated,
        "quarantined": quarantined,
        "consistency": consistency,
        "error_case_counts": dict(error_counts),
        "correction_rule_counts": dict(correction_counts),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the isolated professor-test classifier without MongoDB."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to 01_student_test_small.csv",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            run_student_test_file(args.input),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
