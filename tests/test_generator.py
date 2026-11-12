"""
tests/test_generator.py
-----------------------
בדיקות יחידה עבור שכבת הרנדור והיצירה (Generation & Rendering Layer).
מאמת תקינות יצירת קובץ הפלט, שמירה על מבנה הטבלה, כיווניות הטקסט (RTL),
ובידוד מלא מכל תלות בשלבי ה-OCR או הפרסור.
"""

import os
from dataclasses import replace
from datetime import date

import pytest

from models import AttendanceReport, AttendanceRow, ReportSummary
from generation.generator import HtmlRenderer, PdfRenderer
from generation.layouts import get_report_layout


def test_html_renderer_creates_file(tmp_path):
    """
    בודק שמתודת ה-render מקבלת אובייקט AttendanceReport מעודכן
    ומייצרת קובץ פלט HTML חדש ותקין בנתיב היעד המבוקש.
    """
    # הכנת אובייקט דו"ח דמה (מעודכן משלב הטרנספורמציה)
    row = AttendanceRow(
        work_date=date(2026, 10, 1),
        day_of_week="רביעי",
        entry_time=8 * 60,
        exit_time=17 * 60,
        total_work_minutes=480,
        break_duration_minutes=60,
        overtime_125_minutes=0,
        overtime_150_minutes=0,
        notes="תקין"
    )

    summary = ReportSummary(
        total_work_days=1,
        total_work_minutes=480,
        total_125_minutes=0,
        total_150_minutes=0
    )

    report = AttendanceReport(
        employee_id="12345",
        employee_name="ישראל ישראלי",
        report_period="2026-10",
        report_type="TYPE_B",
        rows=(row,),
        summary=summary
    )

    # שימוש בפיקסצ'ר tmp_path של pytest ליצירת נתיב זמני ומבוקר לקובץ הפלט
    output_file = tmp_path / "test_report.html"

    renderer = HtmlRenderer()
    renderer.render(report, str(output_file))

    # 1. אימות פיזי שקובץ הפלט נוצר בהצלחה
    assert os.path.exists(output_file)

    # 2. קריאת תוכן הקובץ ואימות שמירת המבנה, כיווניות ה-RTL והנתונים המעודכנים
    content = output_file.read_text(encoding="utf-8")
    assert 'dir="rtl"' in content
    assert "ישראל ישראלי" in content
    assert "12345" in content
    assert "08:00" in content
    assert "17:00" in content
    assert "01:00" in content
    assert "08:00" in content
    assert "<table>" in content


def test_renderer_isolation_from_parser_and_ocr(tmp_path):
    """
    מאמת בידוד מלא: הרנדרר פועל אך ורק מול חוזה אובייקט ה-AttendanceReport,
    ללא כל צורך, היכרות או תלות בשלבי ה-OCR או הפרסור.
    """
    report = AttendanceReport(
        employee_id="99999",
        employee_name="בדיקת בידוד",
        report_period="2026-10",
        report_type="TYPE_B",
        rows=(),
        summary=ReportSummary()
    )

    output_file = tmp_path / "isolation_test.html"
    renderer = HtmlRenderer()

    # הרנדור מושלם בהצלחה מול ה-DTO בלבד
    renderer.render(report, str(output_file))
    assert os.path.exists(output_file)

    content = output_file.read_text(encoding="utf-8")
    assert "בדיקת בידוד" in content


def _sample_report(name="ישראל ישראלי"):
    row = AttendanceRow(
        work_date=date(2026, 10, 1),
        day_of_week="רביעי",
        entry_time=8 * 60,
        exit_time=17 * 60,
        total_work_minutes=480,
        break_duration_minutes=60,
        overtime_100_minutes=480,
        notes="תקין",
    )
    return AttendanceReport(
        employee_id="12345", employee_name=name, report_period="2026-10",
        report_type="TYPE_A", rows=(row,),
        summary=ReportSummary(
            total_work_days=1,
            total_work_minutes=480,
            total_100_minutes=480,
        ))


def _report_with_layout_data(report_type):
    row = AttendanceRow(
        work_date=date(2026, 10, 1),
        day_of_week="חמישי",
        entry_time=8 * 60,
        exit_time=17 * 60,
        total_work_minutes=510,
        workplace="מטה",
        break_duration_minutes=30,
        overtime_100_minutes=60,
        overtime_125_minutes=30,
        overtime_150_minutes=15,
        saturday_minutes=20,
        notes="יום תקין",
    )
    return AttendanceReport(
        employee_id="12345",
        employee_name="ישראל ישראלי",
        report_period="2026-10",
        report_type=report_type,
        rows=(row,),
        summary=ReportSummary(
            total_work_days=2,
            total_absent_days=1,
            total_work_minutes=510,
            total_100_minutes=60,
            total_125_minutes=30,
            total_150_minutes=15,
            total_saturday_minutes=20,
            hourly_rate=47.5,
            total_payment=1500.0,
            total_travel_days=2,
            travel_expenses=18.5,
            bonus_amount=75.0,
            summary_notes=("הערת סיכום",),
        ),
    )


@pytest.mark.parametrize(
    ("report_type", "expected_headers", "summary_position"),
    [
        (
            "TYPE_A",
            ("תאריך", "כניסה", "יציאה", "שעות", "הערות"),
            "before_table",
        ),
        (
            "TYPE_B",
            (
                "תאריך", "יום", "מקום עבודה", "כניסה", "יציאה", "הפסקה",
                "סה״כ שעות", "100%", "125%", "150%", "הערות",
            ),
            "after_table",
        ),
    ],
)
def test_html_renderer_uses_report_type_layout_and_summary_position(
    tmp_path, report_type, expected_headers, summary_position
):
    report = _report_with_layout_data(report_type)
    layout = get_report_layout(report_type)
    output = tmp_path / f"{report_type}.html"

    HtmlRenderer().render(report, str(output))

    content = output.read_text(encoding="utf-8")
    table_start = content.index("<table>")
    summary_start = content.index("<h2>סיכום</h2>")
    expected_before = summary_position == "before_table"
    assert (summary_start < table_start) is expected_before
    for header in expected_headers:
        assert f"<th>{header}</th>" in content
    assert content.count("<th>") == len(layout.columns)
    assert content.count("<td>") == len(layout.columns)
    assert layout.summary_position == summary_position
    if report_type == "TYPE_A":
        assert "מקום עבודה" not in content
        assert "מחיר לשעה" in content
    else:
        assert "מטה" in content
        assert "הפסקה" in content


@pytest.mark.parametrize(
    ("report_type", "renderer", "suffix"),
    [
        ("TYPE_A", HtmlRenderer(), ".html"),
        ("TYPE_B", HtmlRenderer(), ".html"),
        ("TYPE_A", PdfRenderer(), ".pdf"),
        ("TYPE_B", PdfRenderer(), ".pdf"),
    ],
)
def test_renderers_preserve_report_and_write_to_a_new_file(
    tmp_path, report_type, renderer, suffix
):
    if suffix == ".pdf":
        pytest.importorskip("reportlab")
        pytest.importorskip("pypdf")

    source = tmp_path / "source.pdf"
    original_bytes = b"source pdf stays untouched"
    source.write_bytes(original_bytes)
    report = _report_with_layout_data(report_type)
    if report_type == "TYPE_B":
        report = replace(
            report,
            summary=replace(report.summary, total_work_minutes=123),
        )
    original_report = report
    output = tmp_path / f"new-report{suffix}"

    try:
        renderer.render(report, str(output))
    except RuntimeError as exc:
        if "גופן" in str(exc):
            pytest.skip("אין גופן עברי זמין בסביבה זו")
        raise

    assert output.resolve() != source.resolve()
    assert output.exists()
    assert source.read_bytes() == original_bytes
    assert report == original_report
    if report_type == "TYPE_B" and suffix == ".html":
        content = output.read_text(encoding="utf-8")
        assert "02:03" in content
        assert "08:30" in content


@pytest.mark.parametrize(
    ("report_type", "expected_headers", "position_header", "summary_position"),
    [
        (
            "TYPE_A",
            ("תאריך", "כניסה", "יציאה", "שעות", "הערות"),
            "תאריך",
            "before_table",
        ),
        (
            "TYPE_B",
            (
                "תאריך", "יום", "מקום עבודה", "כניסה", "יציאה", "הפסקה",
                "סה ״ כ שעות", "100%", "125%", "150%", "הערות",
            ),
            "מקום עבודה",
            "after_table",
        ),
    ],
)
def test_pdf_renderer_uses_report_type_layout_and_summary_position(
    tmp_path, report_type, expected_headers, position_header, summary_position
):
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")
    report = _report_with_layout_data(report_type)
    output = tmp_path / f"{report_type}.pdf"

    try:
        PdfRenderer().render(report, str(output))
    except RuntimeError as exc:
        if "גופן" in str(exc):
            pytest.skip("אין גופן עברי זמין בסביבה זו")
        raise

    text = "\n".join(page.extract_text() for page in pypdf.PdfReader(str(output)).pages)
    summary_label = "2 : ימי עבודה"
    for header in expected_headers:
        assert header in text
    assert summary_label in text
    assert (text.index(summary_label) < text.index(position_header)) is (
        summary_position == "before_table"
    )


@pytest.mark.parametrize(
    ("renderer", "filename"),
    [
        (HtmlRenderer(), "existing.html"),
        (PdfRenderer(), "existing.pdf"),
    ],
)
def test_renderers_refuse_to_overwrite_existing_output(
    tmp_path, renderer, filename
):
    output = tmp_path / filename
    original_contents = b"existing output must remain intact"
    output.write_bytes(original_contents)

    with pytest.raises(FileExistsError, match="קובץ הפלט כבר קיים"):
        renderer.render(_report_with_layout_data("TYPE_A"), str(output))

    assert output.read_bytes() == original_contents


def test_html_renderer_escapes_user_input(tmp_path):
    out = tmp_path / "xss.html"
    HtmlRenderer().render(_sample_report(name="<script>alert(1)</script>"), str(out))

    content = out.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in content
    assert "&lt;script&gt;" in content


def test_html_renderer_marks_synthetic_practice_output(tmp_path):
    report = replace(
        _sample_report(),
        is_synthetic=True,
        simulation_seed=73,
        simulation_date="2026-11-09",
    )
    out = tmp_path / "synthetic.html"

    HtmlRenderer().render(report, str(out))
    content = out.read_text(encoding="utf-8")

    assert "נתונים סינתטיים — לצורכי לימוד בלבד" in content
    assert "2026-11-09" in content
    assert "seed: 73" in content
    assert "body.synthetic::before" in content
    assert "תרגול — נתונים סינתטיים" in content


def test_synthetic_output_without_explicit_date_is_deterministic_and_unstated(
    tmp_path,
):
    report = replace(
        _sample_report(),
        is_synthetic=True,
        simulation_seed=73,
        simulation_date=None,
    )
    out = tmp_path / "synthetic-no-date.html"

    HtmlRenderer().render(report, str(out))
    content = out.read_text(encoding="utf-8")

    assert "תאריך הפקה: לא צוין" in content
    assert "2026-11-09" not in content


def test_to_visual_rtl_reverses_hebrew_but_keeps_numbers_ltr():
    from generation.generator import to_visual_rtl

    assert to_visual_rtl("שלום") == "םולש"
    assert to_visual_rtl("שעות 125%") == "125% תועש"
    assert to_visual_rtl("12345") == "12345"
    assert to_visual_rtl("") == ""
    # שעה ותאריך נשארים שלמים וקריאים
    assert "08:30" in to_visual_rtl("כניסה 08:30")
    assert "2026-10-01" in to_visual_rtl("תאריך 2026-10-01")


def test_pdf_renderer_creates_file(tmp_path):
    import pytest
    pytest.importorskip("reportlab")
    from generation.generator import PdfRenderer

    out = tmp_path / "report.pdf"
    try:
        PdfRenderer().render(_sample_report(), str(out))
    except RuntimeError as exc:
        if "גופן" in str(exc):
            pytest.skip("אין גופן עברי זמין בסביבה זו")
        raise

    assert out.exists() and out.stat().st_size > 1000
    assert out.read_bytes().startswith(b"%PDF")


def test_synthetic_pdf_marks_each_page(tmp_path):
    import pytest

    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")
    from datetime import timedelta
    from generation.generator import PdfRenderer

    report = replace(
        _sample_report(),
        is_synthetic=True,
        simulation_seed=739,
        simulation_date="2026-11-09",
        rows=tuple(
            AttendanceRow(
                work_date=date(2026, 10, 1) + timedelta(days=index),
                day_of_week="יום",
                entry_time=8 * 60,
                exit_time=17 * 60,
                total_work_minutes=480,
                break_duration_minutes=60,
            )
            for index in range(70)
        ),
    )
    output = tmp_path / "synthetic.pdf"

    try:
        PdfRenderer().render(report, str(output))
    except RuntimeError as exc:
        if "גופן" in str(exc):
            pytest.skip("אין גופן עברי זמין בסביבה זו")
        raise

    pages = pypdf.PdfReader(str(output)).pages
    assert len(pages) > 1
    assert all("739" in page.extract_text() for page in pages)


def test_html_renderer_formats_minutes_since_midnight_including_midnight(tmp_path):
    row = AttendanceRow(
        work_date=date(2026, 10, 1),
        day_of_week="חמישי",
        entry_time=0,
        exit_time=8 * 60,
    )
    report = AttendanceReport(
        employee_id="123",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type="TYPE_A",
        rows=(row,),
    )
    output = tmp_path / "midnight.html"

    HtmlRenderer().render(report, str(output))

    content = output.read_text(encoding="utf-8")
    assert "<td>00:00</td>" in content
    assert "<td>08:00</td>" in content
