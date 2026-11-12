from pathlib import Path


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_ocr_fixture(filename: str) -> str:
    """Load a saved OCR text sample from the test fixtures directory."""
    return (FIXTURES_DIR / filename).read_text(encoding="utf-8")
