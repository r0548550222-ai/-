"""
ocr.py
------
שכבת קריאת הקבצים (OCR / PDF Extraction) וניקוי טקסט גולמי
עבור מערכת עיבוד דוחות הנוכחות.
"""

import os
import shutil

from errors import OCRProcessingError
from parsing.attendance_parser import clean_text

try:
    import pypdf
except ImportError:
    pypdf = None


def extract_text_from_pdf(file_path: str) -> str:
    """
    מחלצת טקסט גולמי מקובץ PDF (תומך בקבצים מבוססי טקסט).

    פרמטרים:
        file_path (str): נתיב לקובץ ה-PDF.

    מחזיר:
        str: טקסט גולמי המופק מהעמודים.
    """
    if pypdf is None:
        # בלי pypdf אי אפשר לקרוא שכבת טקסט, אבל עדיין אפשר לנסות OCR על הסריקה
        return extract_text_with_ocr(file_path)

    extracted_text: list[str] = []
    try:
        with open(file_path, "rb") as file:
            reader = pypdf.PdfReader(file)
            for page_index, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    extracted_text.append(text)
    except (OSError, pypdf.errors.PdfReadError) as exc:
        raise OCRProcessingError(
            f"שגיאה בחילוץ טקסט מהקובץ {file_path}: {exc}"
        ) from exc

    text = "\n".join(extracted_text).strip()
    if text:
        return text

    return extract_text_with_ocr(file_path)


def extract_text_with_ocr(file_path: str) -> str:
    """מחלצת טקסט מסריקת PDF באמצעות Poppler ו-Tesseract."""
    try:
        import pytesseract
    except ImportError as exc:
        raise OCRProcessingError(
            "הקובץ אינו מכיל טקסט, ונדרשות החבילות pdf2image ו-pytesseract "
            "להפעלת OCR."
        ) from exc

    try:
        import pdf2image
    except ImportError as exc:
        raise OCRProcessingError(
            "הקובץ אינו מכיל טקסט, ונדרשות החבילות pdf2image ו-pytesseract "
            "להפעלת OCR."
        ) from exc

    convert_from_path = getattr(pdf2image, "convert_from_path", None)
    if convert_from_path is None:
        raise OCRProcessingError(
            "הקובץ אינו מכיל טקסט, ונדרשות החבילות pdf2image ו-pytesseract "
            "להפעלת OCR."
        )

    try:
        from pdf2image.exceptions import (
            PDFInfoNotInstalledError,
            PDFPageCountError,
            PDFPopplerTimeoutError,
            PDFSyntaxError,
        )
    except ImportError:
        PDFInfoNotInstalledError = PDFPageCountError = PDFPopplerTimeoutError = PDFSyntaxError = Exception

    tesseract_cmd = os.environ.get("TESSERACT_CMD") or shutil.which("tesseract")
    if not tesseract_cmd:
        raise OCRProcessingError(
            "לא נמצא Tesseract OCR. התקן Tesseract עם חבילת השפה העברית "
            "או הגדר את TESSERACT_CMD."
        )
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    poppler_path = os.environ.get("POPPLER_PATH")
    if not poppler_path and not shutil.which("pdftoppm"):
        raise OCRProcessingError(
            "לא נמצא Poppler (pdftoppm). התקן Poppler או הגדר את POPPLER_PATH."
        )

    try:
        images = convert_from_path(file_path, dpi=300, poppler_path=poppler_path)
        return "\n".join(
            pytesseract.image_to_string(
                image, lang="heb+eng", config="--psm 6"
            )
            for image in images
        ).strip()
    except (
        OSError,
        RuntimeError,
        ValueError,
        PDFInfoNotInstalledError,
        PDFPageCountError,
        PDFPopplerTimeoutError,
        PDFSyntaxError,
        pytesseract.TesseractError,
        pytesseract.TesseractNotFoundError,
    ) as exc:
        raise OCRProcessingError(
            f"שגיאה בהפעלת OCR עבור {file_path}: {exc}"
        ) from exc
