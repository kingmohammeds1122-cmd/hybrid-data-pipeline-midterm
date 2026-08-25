"""Unit tests for valid, corrected, and quarantined classification."""

from __future__ import annotations

import json
from typing import Any

from src.quality_rules import clean_record



def build_base_record() -> dict[str, Any]:
    """Create a deterministic valid order record for classification tests."""

    return {
        "order_id": "طلب-CLASS-001",
        "order_date": "2025-01-31T10:30:00",
        "status": "مؤكد",
        "customer_id": "عميل-CLASS-001",
        "customer_name": "عميل الاختبار",
        "customer_phone": "702390941",
        "customer_email": "class@example.com",
        "city": "تعز",
        "district": "شعوب",
        "delivery_type": "سريع",
        "delivery_cost": 10,
        "payment_method": "محفظة إلكترونية",
        "payment_status": "تم الدفع",
        "payment_amount": 110,
        "currency": "YER",
        "total_amount": 110,
        "items_json": json.dumps(
            [
                {
                    "sku": "SKU-CLASS-001",
                    "name": "منتج الاختبار",
                    "qty": 1,
                    "unit_price": 100,
                    "total": 100,
                }
            ],
            ensure_ascii=False,
        ),
    }



def test_valid_record_is_classified_as_valid() -> None:
    """A clean record must remain valid with no corrections or errors."""

    result = clean_record(build_base_record())

    assert result.quality_status == "valid"
    assert result.corrections == []
    assert result.error_codes == []
    assert result.error_details == []



def test_correctable_record_is_classified_as_corrected() -> None:
    """Deterministic corrections must produce corrected status and an audit trail."""

    record = build_base_record()
    record["customer_email"] = "class@@example..com"
    record["customer_phone"] = "702 390 941"
    record["total_amount"] = "999"

    result = clean_record(record)

    assert result.quality_status == "corrected"
    assert result.error_codes == []
    assert result.record["customer_email"] == "class@example.com"
    assert result.record["customer_phone"] == "702390941"
    assert result.record["total_amount"] == 110

    correction_rules = {
        correction.rule_code
        for correction in result.corrections
    }

    assert "EMAIL_REPEATED_SYMBOLS" in correction_rules
    assert "PHONE_SEPARATORS" in correction_rules
    assert "TOTAL_RECALCULATION" in correction_rules

    for correction in result.corrections:
        assert correction.field
        assert correction.rule_code
        assert correction.original_value is not None
        assert correction.corrected_value is not None



def test_missing_order_id_is_classified_as_quarantined() -> None:
    """A missing business key must always be quarantined."""

    record = build_base_record()
    record["order_id"] = ""

    result = clean_record(record)

    assert result.quality_status == "quarantined"
    assert "MISSING_ORDER_ID" in result.error_codes
    assert result.error_details



def test_impossible_date_is_classified_as_quarantined() -> None:
    """An impossible date must be quarantined rather than guessed."""

    record = build_base_record()
    record["order_date"] = "2025-02-30"

    result = clean_record(record)

    assert result.quality_status == "quarantined"
    assert "INVALID_IMPOSSIBLE_DATE" in result.error_codes



def test_corrupted_items_json_is_classified_as_quarantined() -> None:
    """Corrupted item JSON must be preserved as a quarantine reason."""

    record = build_base_record()
    record["items_json"] = "not-valid-json"

    result = clean_record(record)

    assert result.quality_status == "quarantined"
    assert "CORRUPTED_ITEMS_JSON" in result.error_codes
    assert result.error_details



def test_multiple_errors_are_preserved_together() -> None:
    """Multiple structural errors must not be silently discarded."""

    record = build_base_record()
    record["order_id"] = ""
    record["customer_id"] = ""
    record["order_date"] = "2025-02-30"
    record["items_json"] = "not-valid-json"

    result = clean_record(record)

    assert result.quality_status == "quarantined"
    assert "MISSING_ORDER_ID" in result.error_codes
    assert "MISSING_CUSTOMER_ID" in result.error_codes
    assert "INVALID_IMPOSSIBLE_DATE" in result.error_codes
    assert "CORRUPTED_ITEMS_JSON" in result.error_codes
    assert len(result.error_codes) >= 4
    assert len(result.error_details) >= 4
