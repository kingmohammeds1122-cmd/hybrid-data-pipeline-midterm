from pathlib import Path

path = Path(r"D:\midterm-data-pipeline\src\quality_rules.py")
text = path.read_text(encoding="utf-8-sig")

start = text.index("ARABIC_DIGIT_TRANSLATION")
end = text.index("@dataclass")

constants = r'''ARABIC_DIGIT_TRANSLATION = str.maketrans(
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
    "\u0645\u062f\u0641\u0648\u0639": "\u062a\u062a\u0645 \u0627\u0644\u062f\u0641\u0639",
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


'''
text = text[:start] + constants + text[end:]

start = text.index("def normalize_numeric_text")
end = text.index("def normalize_known_number_word")
numeric_function = r'''def normalize_numeric_text(value: Any) -> Decimal | None:
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


'''
text = text[:start] + numeric_function + text[end:]
path.write_text(text, encoding="utf-8", newline="\n")
print("Quality rules rebuilt safely.")
