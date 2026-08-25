"""Unit tests for the eight deterministic cleaning rules."""

from __future__ import annotations

import json

from src.quality_rules import (
    clean_record,
    normalize_arabic_digits,
    normalize_email,
    normalize_known_number_word,
    normalize_numeric_text,
    normalize_order_date,
    normalize_phone,
    normalize_synonym,
)


def test_arabic_digits_are_converted_to_western_digits() -> None:
    """Arabic and Persian digits must become Western digits."""

    assert normalize_arabic_digits("٥٠٠٠") == "5000"
    assert normalize_arabic_digits("۱۲۳") == "123"


def test_thousands_separators_are_removed_from_numeric_values() -> None:
    """Unambiguous separators must be removed before numeric conversion."""

    assert normalize_numeric_text("125,000.00") == 125000
    assert normalize_numeric_text("١٢٥٬٠٠٠٫٥٠") == 125000.50


def test_only_known_number_words_are_converted() -> None:
    """Known words are converted, while unknown text is not guessed."""

    assert normalize_known_number_word("ألفان") == 2000
    assert normalize_known_number_word("خمسة آلاف") == 5000
    assert normalize_known_number_word("قيمة غير معروفة") == "قيمة غير معروفة"


def test_phone_separators_are_removed_without_country_guessing() -> None:
    """Phone formatting is normalized without inventing a country code."""

    assert normalize_phone("4567 123 77 967+") == "+456712377967"
    assert normalize_phone("00967712345678") == "+967712345678"


def test_repeated_email_symbols_are_repaired() -> None:
    """Only obvious repeated email symbols are repaired."""

    assert normalize_email(" user@@mail..com ") == "user@mail.com"


def test_supported_date_formats_are_standardized() -> None:
    """Supported valid date formats must be parsed."""

    assert normalize_order_date("2025-01-31") is not None
    assert normalize_order_date("31/01/2025") is not None
    assert normalize_order_date("2025-02-30") is None


def test_known_synonyms_are_normalized() -> None:
    """Known status synonyms are normalized after trimming."""

    assert normalize_synonym("  مدفوع  ", {"مدفوع": "تم الدفع"}) == "تم الدفع"
    assert normalize_synonym("قيمة مجهولة", {"مدفوع": "تم الدفع"}) == "قيمة مجهولة"


def build_valid_record() -> dict[str, str]:
    """Build a valid raw record for rule-combination tests."""

    return {
        "order_id": "طلب-TEST-001",
        "order_date": "2025-01-31",
        "status": "مؤكد",
        "customer_id": "عميل-TEST-001",
        "customer_name": "اسم الاختبار",
        "customer_phone": "702 390 941",
        "customer_email": "user@@example..com",
        "city": "تعز",
        "district": "شعوب",
        "delivery_type": "سريع",
        "delivery_cost": "5,000.00",
        "payment_method": "كاش",
        "payment_status": "مدفوع",
        "payment_amount": "15,000.00",
        "currency": "YER",
        "total_amount": "15,000.00",
        "items_json": json.dumps(
            [
                {
                    "sku": "SKU-001",
                    "name": "منتج اختبار",
                    "qty": 1,
                    "unit_price": 10000,
                    "total": 10000,
                }
            ],
            ensure_ascii=False,
        ),
    }


def test_valid_record_is_corrected_and_audited() -> None:
    """Correctable values must receive corrections and an audit trail."""

    result = clean_record(build_valid_record())
    result_document = result.as_dict()

    assert result.quality_status == "corrected"
    assert result.record["customer_email"] == "user@example.com"
    assert result.record["payment_method"] == "نقدي"
    assert result.record["payment_status"] == "تم الدفع"
    assert result.record["total_amount"] == 15000
    assert result_document["corrections"]
    assert all(
        correction["field"]
        and correction["original_value"] is not None
        and correction["rule_code"]
        for correction in result_document["corrections"]
    )


def test_negative_quantity_is_quarantined() -> None:
    """An ambiguous negative quantity must not be silently corrected."""

    record = build_valid_record()
    record["items_json"] = json.dumps(
        [
            {
                "sku": "SKU-NEGATIVE",
                "name": "منتج",
                "qty": -2,
                "unit_price": 100,
                "total": -200,
            }
        ],
        ensure_ascii=False,
    )

    result = clean_record(record)

    assert result.quality_status == "quarantined"
    assert "AMBIGUOUS_NEGATIVE_VALUE" in result.error_codes
    assert result.error_details


def test_corrupted_items_json_is_quarantined() -> None:
    """Malformed JSON must be quarantined with the official error code."""

    record = build_valid_record()
    record["items_json"] = "[invalid-json"

    result = clean_record(record)

    assert result.quality_status == "quarantined"
    assert "CORRUPTED_ITEMS_JSON" in result.error_codes


def test_missing_business_identifiers_are_quarantined() -> None:
    """Missing order or customer IDs must be quarantined."""

    record = build_valid_record()
    record["order_id"] = ""
    record["customer_id"] = ""

    result = clean_record(record)

    assert result.quality_status == "quarantined"
    assert "MISSING_ORDER_ID" in result.error_codes
    assert "MISSING_CUSTOMER_ID" in result.error_codes


def test_empty_items_are_quarantined_with_explicit_code() -> None:
    record = build_valid_record()
    record["items_json"] = "[]"
    result = clean_record(record)
    assert result.quality_status == "quarantined"
    assert "EMPTY_ITEMS" in result.error_codes


def test_multiple_independent_errors_receive_aggregate_code() -> None:
    record = build_valid_record()
    record["order_id"] = ""
    record["customer_id"] = ""
    record["items_json"] = "[invalid-json"
    result = clean_record(record)
    assert result.quality_status == "quarantined"
    assert "MULTIPLE_CONFLICTING_ERRORS" in result.error_codes
    assert len(result.error_codes) > 1
