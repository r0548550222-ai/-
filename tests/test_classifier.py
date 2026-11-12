import pytest

from models import ReportType
from parsing.classifier import UnknownReportTypeError, classify
from parsing.parser import parse_report
from tests.fixture_helpers import load_ocr_fixture


@pytest.mark.parametrize(
    ("filename", "expected_type"),
    [
        ("a_r_25.txt", ReportType.TYPE_B),
        ("a_r_9.txt", ReportType.TYPE_B),
        ("n_r_5_n.txt", ReportType.TYPE_A),
        ("n_r_10_n.txt", ReportType.TYPE_A),
    ],
)
def test_real_pdf_fixtures_classify_and_parse_attendance_rows(
    filename, expected_type
):
    sample_text = load_ocr_fixture(filename)

    assert classify(sample_text) == expected_type

    report = parse_report(sample_text, report_type=expected_type)
    assert report.report_type == expected_type.value
    assert report.rows


def test_classify_payroll_summary_fixture_as_type_a():
    assert classify(load_ocr_fixture("type_a_payroll_sample.txt")) == ReportType.TYPE_A


def test_classify_detailed_report_fixture_as_type_b():
    assert classify(load_ocr_fixture("type_b_detailed_sample.txt")) == ReportType.TYPE_B


@pytest.mark.parametrize(
    "text",
    [
        "Random unrelated text.",
        "מחיר לשעה",
        "לתשלום",
        "ימי עבודה",
        "הערות",
        "הפסקה",
        "125%",
        "150%",
        "מקום",
    ],
)
def test_classify_rejects_insufficient_evidence(text):
    with pytest.raises(UnknownReportTypeError, match="Not enough evidence"):
        classify(text)


def test_classify_rejects_tied_evidence():
    text = "מחיר לשעה יום שעת סה\"כ הערות הפסקה 125%"
    with pytest.raises(UnknownReportTypeError, match="tie"):
        classify(text)


@pytest.mark.parametrize("text", ["", "   ", None, 123])
def test_classify_rejects_empty_or_non_string_input(text):
    with pytest.raises(UnknownReportTypeError, match="empty or non-text"):
        classify(text)