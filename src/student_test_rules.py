"""Official classifier for the instructor's 20,000-row student test file."""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any


KNOWN_STATUSES = {
    "مؤكد",
    "قيد الانتظار",
    "قيد الشحن",
    "ملغي",
    "تم التسليم",
    "مرتجع",
}

ARABIC_DIGITS = str.maketrans(
    {
        **{chr(0x660 + i): str(i) for i in range(10)},
        **{chr(0x6F0 + i): str(i) for i in range(10)},
    }
)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _number(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).translate(ARABIC_DIGITS).strip()
    text = text.replace("٬", "").replace(",", "").replace("٫", ".")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _plain(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


def _has_arabic_digits(value: Any) -> bool:
    return any(ch in _text(value) for ch in "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹")


def _append_error(errors: list[tuple[str, str]], code: str, detail: str) -> None:
    errors.append((code, detail))


def clean_student_record(raw_record: dict[str, Any]):
    """Classify one instructor-test record using the official rule names."""
    from src.quality_rules import Correction, QualityResult, parse_items_json

    record = dict(raw_record)
    corrections: list[Correction] = []
    errors: list[tuple[str, str]] = []

    def correct(field: str, value: Any, code: str) -> None:
        old = record.get(field)
        if old != value:
            record[field] = value
            corrections.append(Correction(field, old, value, code))

    order_id = _text(record.get("order_id"))
    customer_id = _text(record.get("customer_id"))
    if not order_id:
        _append_error(errors, "missing_order_id", "order_id is missing.")
    else:
        record["order_id"] = order_id
    if not customer_id:
        _append_error(errors, "missing_customer_id", "customer_id is missing.")
    else:
        record["customer_id"] = customer_id

    phone = _text(record.get("customer_phone"))
    phone_digits = re.sub(r"\D", "", phone.translate(ARABIC_DIGITS))
    if len(phone_digits) < 9:
        _append_error(errors, "invalid_phone_too_short", "Phone number is too short.")
    elif phone.startswith("+967") or phone.startswith("00967"):
        local = phone_digits[3:] if phone_digits.startswith("967") else phone_digits
        correct("customer_phone", local, "phone_with_country_code")

    email = _text(record.get("customer_email"))
    if "@@" in email:
        fixed = re.sub(r"@+", "@", email)
        correct("customer_email", fixed, "email_double_at")
        email = fixed
    if email.count("@") != 1 or "." not in email.rsplit("@", 1)[-1]:
        _append_error(errors, "email_missing_domain", "Email domain is missing.")

    date_value = _text(record.get("order_date"))
    parsed_date = None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            from datetime import datetime
            parsed_date = datetime.strptime(date_value, fmt)
            if fmt.startswith("%d-"):
                correct("order_date", parsed_date.isoformat(sep=" ", timespec="seconds"), "date_dd_mm_yyyy")
            break
        except ValueError:
            pass
    if parsed_date is None:
        _append_error(errors, "invalid_date_impossible", "Date is invalid or impossible.")

    status_original = record.get("status")
    status = _text(status_original)
    if status != status_original:
        correct("status", status, "status_extra_spaces")
    if status not in KNOWN_STATUSES:
        _append_error(errors, "unknown_order_status", "Order status is unknown.")

    currency = _text(record.get("currency"))
    if currency == "ريال يمني":
        correct("currency", "YER", "currency_arabic_name")
    elif currency != "YER":
        _append_error(errors, "unknown_currency", "Currency is unknown.")

    for field, code in (("delivery_cost", "arabic_digits_delivery_cost"), ("payment_amount", "arabic_digits_payment_amount")):
        value = record.get(field)
        if _has_arabic_digits(value):
            number = _number(value)
            if number is not None:
                correct(field, _plain(number), code)

    total = record.get("total_amount")
    if isinstance(total, str) and "," in total:
        number = _number(total)
        if number is not None:
            correct("total_amount", _plain(number), "price_with_thousands_commas")

    items_raw = record.get("items_json")
    items = parse_items_json(items_raw)
    if items is None:
        _append_error(errors, "corrupted_items_json", "Items JSON is corrupted.")
    elif not items:
        _append_error(errors, "empty_items", "Items list is empty.")
    else:
        missing_sku = False
        negative_quantity = False
        item_total = Decimal("0")
        for item in items:
            if not isinstance(item, dict) or not _text(item.get("sku")):
                missing_sku = True
            quantity_raw = item.get("qty") if isinstance(item, dict) else None
            quantity = _number(quantity_raw)
            if quantity is not None and quantity < 0:
                negative_quantity = True
            if isinstance(quantity_raw, str) and quantity is not None and quantity >= 0:
                parsed_items = json.loads(items_raw)
                for parsed_item in parsed_items:
                    if isinstance(parsed_item.get("qty"), str):
                        parsed_item["qty"] = _plain(_number(parsed_item["qty"]))
                correct("items_json", json.dumps(parsed_items, ensure_ascii=False, separators=(",", ":")), "qty_as_string_in_items")
                items = parsed_items
                break
        if missing_sku:
            _append_error(errors, "missing_item_sku", "An item has no SKU.")
        if negative_quantity:
            _append_error(errors, "negative_quantity", "Item quantity is negative.")
        if not missing_sku and not negative_quantity:
            for item in items:
                item_total += _number(item.get("total")) or Decimal("0")
            delivery = _number(record.get("delivery_cost"))
            current = _number(record.get("total_amount"))
            if delivery is not None and current is not None:
                expected = item_total + delivery
                if current != expected:
                    correct("total_amount", _plain(expected), "total_amount_mismatch_recomputable")

    if len(errors) > 1:
        errors = [("multiple_conflicting_errors", "Multiple conflicting quality errors require quarantine.")]

    error_codes = [code for code, _ in errors]
    error_details = [detail for _, detail in errors]
    status = "quarantined" if errors else ("corrected" if corrections else "valid")
    return QualityResult(record, status, corrections, error_codes, error_details)
