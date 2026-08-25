"""Deterministic data-quality and correction rules for order records."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


ARABIC_DIGIT_TRANSLATION = str.maketrans(
    {
        **{chr(0x660 + i): str(i) for i in range(10)},
        **{chr(0x6F0 + i): str(i) for i in range(10)},
    }
)


STATUS_SYNONYMS: dict[str, str] = {
    "\u0645\u0624\u0643\u062f": "\u0645\u0624\u0643\u062f",
    "\u0645\u0624\u0643\u062f\u0629": "\u0645\u0624\u0643\u062f",
    "\u0642\u064a\u062f \u0627\u0644\u0627\u0646\u062a\u0638\u0627\u0631": "\u0642\u064a\u062f \u0627\u0644\u0627\u0646\u062a\u0638\u0627\u0631",
    "\u0645\u0644\u063a\u0649": "\u0645\u0644\u063a\u0649",
    "\u0645\u0644\u063a\u0627\u0629": "\u0645\u0644\u063a\u0649",
    "\u0645\u0643\u062a\u0645\u0644": "\u0645\u0643\u062a\u0645\u0644",
    "\u0645\u0643\u062a\u0645\u0644\u0629": "\u0645\u0643\u062a\u0645\u0644",
}


PAYMENT_STATUS_SYNONYMS: dict[str, str] = {
    "\u062a\u0645 \u0627\u0644\u062f\u0641\u0639": "\u062a\u0645 \u0627\u0644\u062f\u0641\u0639",
    "\u0645\u062f\u0641\u0648\u0639": "\u062a\u0645 \u0627\u0644\u062f\u0641\u0639",
    "\u0645\u062f\u0641\u0648\u0639\u0629": "\u062a\u0645 \u0627\u0644\u062f\u0641\u0639",
    "\u0628\u0627\u0646\u062a\u0638\u0627\u0631 \u0627\u0644\u062f\u0641\u0639": "\u0628\u0627\u0646\u062a\u0638\u0627\u0631 \u0627\u0644\u062f\u0641\u0639",
    "\u0642\u064a\u062f \u0627\u0644\u062f\u0641\u0639": "\u0628\u0627\u0646\u062a\u0638\u0627\u0631 \u0627\u0644\u062f\u0641\u0639",
    "\u0641\u0634\u0644 \u0627\u0644\u062f\u0641\u0639": "\u0641\u0634\u0644 \u0627\u0644\u062f\u0641\u0639",
}


PAYMENT_METHOD_SYNONYMS: dict[str, str] = {
    "\u0645\u062d\u0641\u0638\u0629 \u0625\u0644\u0643\u062a\u0631\u0648\u0646\u064a\u0629": "\u0645\u062d\u0641\u0638\u0629 \u0625\u0644\u0643\u062a\u0631\u0648\u0646\u064a\u0629",
    "\u0643\u0627\u0634": "\u0646\u0642\u062f\u064a",
    "\u0646\u0642\u062f\u0627": "\u0646\u0642\u062f\u064a",
    "\u0646\u0642\u062f\u0627\u064b": "\u0646\u0642\u062f\u064a",
    "\u0628\u0637\u0627\u0642\u0629": "\u0628\u0637\u0627\u0642\u0629 \u0628\u0646\u0643\u064a\u0629",
    "\u0628\u0637\u0627\u0642\u0629 \u0628\u0646\u0643\u064a\u0629": "\u0628\u0637\u0627\u0642\u0629 \u0628\u0646\u0643\u064a\u0629",
}


ARABIC_NUMBER_WORDS: dict[str, Decimal] = {
    "\u0635\u0641\u0631": Decimal("0"),
    "\u0648\u0627\u062d\u062f": Decimal("1"),
    "\u0648\u0627\u062d\u062f\u0629": Decimal("1"),
    "\u0627\u062b\u0646\u0627\u0646": Decimal("2"),
    "\u0627\u062b\u0646\u064a\u0646": Decimal("2"),
    "\u0627\u062b\u0646\u062a\u0627\u0646": Decimal("2"),
    "\u062b\u0644\u0627\u062b\u0629": Decimal("3"),
    "\u062b\u0644\u0627\u062b": Decimal("3"),
    "\u0623\u0631\u0628\u0639\u0629": Decimal("4"),
    "\u062e\u0645\u0633\u0629": Decimal("5"),
    "\u0633\u062a\u0629": Decimal("6"),
    "\u0633\u0628\u0639\u0629": Decimal("7"),
    "\u062b\u0645\u0627\u0646\u064a\u0629": Decimal("8"),
    "\u062a\u0633\u0639\u0629": Decimal("9"),
    "\u0639\u0634\u0631\u0629": Decimal("10"),
    "\u0623\u0644\u0641": Decimal("1000"),
    "\u0623\u0644\u0641\u0627\u0646": Decimal("2000"),
    "\u062e\u0645\u0633\u0629 \u0622\u0644\u0627\u0641": Decimal("5000"),
}


@dataclass
class Correction:
    """One auditable field-level correction."""

    field: str
    original_value: Any
    corrected_value: Any
    rule_code: str

    def as_dict(self) -> dict[str, Any]:
        """Return the correction in the required audit format."""

        return {
            "field": self.field,
            "original_value": self.original_value,
            "corrected_value": self.corrected_value,
            "rule_code": self.rule_code,
        }


@dataclass
class QualityResult:
    """Result of applying deterministic quality rules to one order."""

    record: dict[str, Any]
    quality_status: str = "valid"
    corrections: list[Correction] = field(default_factory=list)
    error_codes: list[str] = field(default_factory=list)
    error_details: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Return the result as a MongoDB-ready dictionary."""

        result = dict(self.record)
        result["quality_status"] = self.quality_status
        result["corrections"] = [
            correction.as_dict()
            for correction in self.corrections
        ]
        result["error_codes"] = self.error_codes
        result["error_details"] = self.error_details
        return result


def normalize_arabic_digits(value: Any) -> Any:
    """Convert Arabic and Persian digits to Western digits."""

    if not isinstance(value, str):
        return value

    return value.translate(ARABIC_DIGIT_TRANSLATION)


def normalize_numeric_text(value: Any) -> Decimal | None:
    """Remove unambiguous separators and convert a value to Decimal."""

    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None

    normalized = normalize_arabic_digits(str(value)).strip()
    normalized = normalized.replace("\u066c", "")
    normalized = normalized.replace(",", "")
    normalized = normalized.replace("\u066b", ".")
    normalized = normalized.replace(" ", "")

    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def normalize_known_number_word(value: Any) -> Any:
    """Convert only explicitly known and unambiguous number words."""

    if not isinstance(value, str):
        return value

    normalized = " ".join(value.strip().split())
    return ARABIC_NUMBER_WORDS.get(normalized, value)


def normalize_phone(value: Any) -> Any:
    """Normalize phone separators and place an existing plus sign first."""

    if value is None:
        return None

    normalized = normalize_arabic_digits(str(value)).strip()
    has_plus_sign = "+" in normalized
    digits = re.sub(r"[^0-9]", "", normalized)

    if not digits:
        return normalized

    if digits.startswith("00"):
        digits = digits[2:]
        has_plus_sign = True

    if has_plus_sign:
        return f"+{digits}"

    return digits


def normalize_email(value: Any) -> Any:
    """Repair only clearly repeated @ and dot symbols in email addresses."""

    if not isinstance(value, str):
        return value

    normalized = value.strip()
    normalized = re.sub(r"@+", "@", normalized)
    normalized = re.sub(r"\.{2,}", ".", normalized)
    normalized = normalized.strip(".")
    return normalized


def normalize_order_date(value: Any) -> datetime | None:
    """Parse supported date formats and reject impossible dates."""

    if value is None:
        return None

    normalized = normalize_arabic_digits(str(value)).strip()
    supported_formats = (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
    )

    for date_format in supported_formats:
        try:
            return datetime.strptime(normalized, date_format)
        except ValueError:
            continue

    return None


def normalize_synonym(
    value: Any,
    synonyms: dict[str, str],
) -> Any:
    """Trim text and apply only a known dictionary mapping."""

    if not isinstance(value, str):
        return value

    normalized = " ".join(value.strip().split())
    return synonyms.get(normalized, normalized)


def parse_items_json(value: Any) -> list[dict[str, Any]] | None:
    """Parse a non-empty JSON array containing item dictionaries."""

    if not isinstance(value, str) or not value.strip():
        return None

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, list):
        return None

    if not all(isinstance(item, dict) for item in parsed):
        return None

    return parsed


def to_plain_number(value: Decimal) -> int | float:
    """Convert Decimal to int when exact, otherwise to float."""

    if value == value.to_integral_value():
        return int(value)

    return float(value)


def clean_record(raw_record: dict[str, Any]) -> QualityResult:
    """Apply the eight deterministic quality rules to one raw record."""

    record = dict(raw_record)
    corrections: list[Correction] = []
    error_codes: list[str] = []
    error_details: list[str] = []

    def replace_field(
        field_name: str,
        new_value: Any,
        rule_code: str,
    ) -> None:
        """Replace a field and append a field-level audit entry."""

        old_value = record.get(field_name)

        if old_value != new_value:
            record[field_name] = new_value
            corrections.append(
                Correction(
                    field=field_name,
                    original_value=old_value,
                    corrected_value=new_value,
                    rule_code=rule_code,
                )
            )

    # Rule 1: Arabic and Persian digits.
    for field_name in (
        "delivery_cost",
        "payment_amount",
        "total_amount",
        "customer_phone",
    ):
        old_value = record.get(field_name)
        new_value = normalize_arabic_digits(old_value)

        if old_value != new_value:
            replace_field(field_name, new_value, "ARABIC_DIGITS")

    # Rule 2: thousands separators and numeric conversion.
    for field_name in (
        "delivery_cost",
        "payment_amount",
        "total_amount",
    ):
        old_value = record.get(field_name)
        number_value = normalize_numeric_text(old_value)

        if number_value is not None:
            replace_field(
                field_name,
                to_plain_number(number_value),
                "THOUSANDS_SEPARATOR_NUMERIC",
            )

    # Rule 3: known number words only.
    for field_name in (
        "delivery_cost",
        "payment_amount",
        "total_amount",
    ):
        old_value = record.get(field_name)
        word_value = normalize_known_number_word(old_value)

        if word_value != old_value:
            numeric_value = normalize_numeric_text(word_value)

            if numeric_value is not None:
                replace_field(
                    field_name,
                    to_plain_number(numeric_value),
                    "KNOWN_NUMBER_WORD",
                )

    # Rule 4: phone normalization.
    old_phone = record.get("customer_phone")
    new_phone = normalize_phone(old_phone)

    if old_phone != new_phone:
        replace_field(
            "customer_phone",
            new_phone,
            "PHONE_SEPARATORS",
        )

    # Rule 5: obvious repeated email symbols.
    old_email = record.get("customer_email")
    new_email = normalize_email(old_email)

    if old_email != new_email:
        replace_field(
            "customer_email",
            new_email,
            "EMAIL_REPEATED_SYMBOLS",
        )

    # Rule 6: date parsing and standardization.
    old_date = record.get("order_date")
    parsed_date = normalize_order_date(old_date)

    if parsed_date is None:
        error_codes.append("INVALID_IMPOSSIBLE_DATE")
        error_details.append(
            "Order date is missing, invalid, or impossible."
        )
    else:
        new_date = parsed_date.isoformat(timespec="seconds")
        replace_field(
            "order_date",
            new_date,
            "DATE_STANDARDIZATION",
        )

    # Rule 7: trim and known synonyms.
    for field_name, dictionary in (
        ("status", STATUS_SYNONYMS),
        ("payment_status", PAYMENT_STATUS_SYNONYMS),
        ("payment_method", PAYMENT_METHOD_SYNONYMS),
    ):
        old_value = record.get(field_name)
        new_value = normalize_synonym(old_value, dictionary)

        if old_value != new_value:
            replace_field(
                field_name,
                new_value,
                "TRIM_AND_SYNONYM",
            )

    # Normalize the stable business identifiers before final classification.
    original_order_id = record.get("order_id")
    original_customer_id = record.get("customer_id")
    order_id = str(original_order_id or "").strip()
    customer_id = str(original_customer_id or "").strip()

    if original_order_id != order_id:
        replace_field(
            "order_id",
            order_id,
            "TRIM_AND_SYNONYM",
        )

    if original_customer_id != customer_id:
        replace_field(
            "customer_id",
            customer_id,
            "TRIM_AND_SYNONYM",
        )

    if not order_id:
        error_codes.append("MISSING_ORDER_ID")
        error_details.append(
            "Order ID is missing and cannot be inferred safely."
        )

    if not customer_id:
        error_codes.append("MISSING_CUSTOMER_ID")
        error_details.append("Customer ID is missing.")

    # Rule 8: validate items and recalculate total when safe.
    items = parse_items_json(record.get("items_json"))

    if items is None:
        error_codes.append("CORRUPTED_ITEMS_JSON")
        error_details.append(
            "Items JSON is missing or cannot be parsed."
        )
    elif not items:
        error_codes.append("EMPTY_ITEMS")
        error_details.append(
            "Items JSON is a valid array but contains no items."
        )
    else:
        item_total = Decimal("0")
        items_are_valid = True

        for item in items:
            quantity = normalize_numeric_text(item.get("qty"))
            unit_price = normalize_numeric_text(item.get("unit_price"))
            item_total_value = normalize_numeric_text(item.get("total"))

            if quantity is None or unit_price is None:
                items_are_valid = False
                break

            if quantity < 0 or unit_price < 0:
                error_codes.append("AMBIGUOUS_NEGATIVE_VALUE")
                error_details.append(
                    "Negative quantity or price is ambiguous."
                )
                items_are_valid = False
                break

            if item_total_value is None or item_total_value < 0:
                items_are_valid = False
                break

            item_total += item_total_value

        if items_are_valid:
            delivery_cost = normalize_numeric_text(
                record.get("delivery_cost")
            )
            current_total = normalize_numeric_text(
                record.get("total_amount")
            )

            if delivery_cost is None or current_total is None:
                error_codes.append("UNKNOWN_PRICE")
                error_details.append(
                    "The original price or delivery cost is unknown."
                )
            else:
                expected_total = item_total + delivery_cost

                if current_total != expected_total:
                    replace_field(
                        "total_amount",
                        to_plain_number(expected_total),
                        "TOTAL_RECALCULATION",
                    )

    if len(error_codes) > 1 and "MULTIPLE_CONFLICTING_ERRORS" not in error_codes:
        error_codes.append("MULTIPLE_CONFLICTING_ERRORS")
        error_details.append(
            "Multiple independent quality errors require manual review."
        )

    if error_codes:
        quality_status = "quarantined"
    elif corrections:
        quality_status = "corrected"
    else:
        quality_status = "valid"

    return QualityResult(
        record=record,
        quality_status=quality_status,
        corrections=corrections,
        error_codes=error_codes,
        error_details=error_details,
    )

