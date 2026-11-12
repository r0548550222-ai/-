"""
tests/test_ocr.py
-----------------
בדיקות יחידה עבור רכיב ה-OCR וניקוי הטקסט הגולמי.
"""

import sys
from types import SimpleNamespace
from unittest.mock import Mock

from ocr.ocr import clean_text, extract_text_with_ocr


def test_clean_text_basic_spacing():
    """בודק הסרת רווחים מיותרים ומעברי שורה מיותרים."""
    raw = "   שלום   עולם   \n\n   בדיקת   מערכת   "
    expected = "שלום עולם\nבדיקת מערכת"
    assert clean_text(raw) == expected


def test_clean_text_broken_times():
    """בודק תיקון שגיאות OCR נפוצות בשעות (למשל רווחים סביב נקודתיים)."""
    raw = "כניסה: 08 : 30 | יציאה: 17 : 00"
    # בהנחה שמנגנון הניקוי מטפל ברווחים סביב הנקודתיים
    cleaned = clean_text(raw)
    assert "08:30" in cleaned
    assert "17:00" in cleaned


def test_clean_text_empty_input():
    """בודק טיפול במחרוזת ריקה או None."""
    assert clean_text("") == ""
    assert clean_text(None) == ""  # type: ignore


def test_clean_text_pads_single_digit_hour():
    assert clean_text("כניסה 9 : 15") == "כניסה 09:15"


def test_extract_text_with_ocr_uses_high_resolution_table_segmentation(monkeypatch):
    image = object()
    convert_from_path = Mock(return_value=[image])
    image_to_string = Mock(return_value="extracted report text")
    pytesseract_module = SimpleNamespace(
        pytesseract=SimpleNamespace(tesseract_cmd=None),
        image_to_string=image_to_string,
    )
    monkeypatch.setitem(
        sys.modules,
        "pdf2image",
        SimpleNamespace(convert_from_path=convert_from_path),
    )
    monkeypatch.setitem(sys.modules, "pytesseract", pytesseract_module)
    monkeypatch.setenv("TESSERACT_CMD", "tesseract")
    monkeypatch.setenv("POPPLER_PATH", "poppler")

    assert extract_text_with_ocr("report.pdf") == "extracted report text"
    convert_from_path.assert_called_once_with(
        "report.pdf", dpi=300, poppler_path="poppler"
    )
    image_to_string.assert_called_once_with(
        image, lang="heb+eng", config="--psm 6"
    )
