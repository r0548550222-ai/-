"""
tests/test_cli.py
-----------------
בדיקות יחידה ואינטגרציה עבור ממשק ה-CLI וזרימת הצינור המרכזי.
"""

import pytest
from datetime import date

from config import (
    DEFAULT_MAXIMUM_DATE_SHIFT_DAYS,
    DEFAULT_MAX_SHIFT_MINUTES,
    DEFAULT_MIN_SHIFT_MINUTES,
    DEFAULT_OVERTIME_100_LIMIT_MINUTES,
)
from generation.generator import HtmlRenderer
from models import AttendanceReport, AttendanceRow, ReportSummary
from main import process_attendance_pipeline


def _stub_pipeline_parser(monkeypatch, report):
    monkeypatch.setattr("pipeline.extract_text_from_pdf", lambda path: "150%")
    monkeypatch.setattr("pipeline.parse_report", lambda **kwargs: report)


def test_pipeline_missing_file(tmp_path):
    """בודק זריקת שגיאה כאשר קובץ הקלט אינו קיים."""
    with pytest.raises(FileNotFoundError):
        process_attendance_pipeline(
            file_path="non_existent_file.pdf",
            employee_id="123",
            employee_name="בדיקה",
            period="2026-10",
            report_type="TYPE_A",
            output_html_path=str(tmp_path / "test.html")
        )


def test_pipeline_invalid_extension(tmp_path):
    """בודק זריקת שגיאה כאשר הקובץ אינו בפורמט PDF."""
    with pytest.raises(ValueError, match="פורמט PDF"):
        process_attendance_pipeline(
            file_path="requirements.txt",
            employee_id="123",
            employee_name="בדיקה",
            period="2026-10",
            report_type="TYPE_A",
            output_html_path=str(tmp_path / "test.html")
        )


def test_pipeline_refuses_existing_output_without_changing_source(
    tmp_path, monkeypatch
):
    input_pdf = tmp_path / "source.pdf"
    input_pdf.write_bytes(b"%PDF-1.4 source remains unchanged")
    source_bytes = input_pdf.read_bytes()
    output_path = tmp_path / "already-there.html"
    output_path.write_text("existing output", encoding="utf-8")

    def extraction_must_not_run(_):
        pytest.fail("the pipeline should reject an existing output first")

    monkeypatch.setattr("pipeline.extract_text_from_pdf", extraction_must_not_run)

    with pytest.raises(FileExistsError, match="קובץ הפלט כבר קיים"):
        process_attendance_pipeline(
            file_path=str(input_pdf),
            employee_id="123",
            employee_name="בדיקה",
            period="2026-10",
            report_type="TYPE_A",
            output_html_path=str(output_path),
        )

    assert input_pdf.read_bytes() == source_bytes
    assert output_path.read_text(encoding="utf-8") == "existing output"


def test_pipeline_rejects_output_path_that_is_the_source(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4 source")
    source_bytes = source.read_bytes()

    with pytest.raises(ValueError, match="נפרד מקובץ המקור"):
        process_attendance_pipeline(
            file_path=str(source),
            employee_id="123",
            employee_name="בדיקה",
            period="2026-10",
            report_type="TYPE_A",
            output_html_path=str(source),
        )

    assert source.read_bytes() == source_bytes


def test_pipeline_invalid_report_type(tmp_path):
    """בודק זריקת שגיאה עבור סוג דוח לא מוכר."""
    # יצירת קובץ PDF דמה ריק לצורך בדיקה
    dummy_pdf = tmp_path / "dummy.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy content")

    with pytest.raises(ValueError, match="סוג דוח לא מוכר"):
        process_attendance_pipeline(
            file_path=str(dummy_pdf),
            employee_id="123",
            employee_name="בדיקה",
            period="2026-10",
            report_type="UNKNOWN_TYPE",
            output_html_path=str(tmp_path / "test.html")
        )


def test_pipeline_parses_transforms_and_renders_html(tmp_path, monkeypatch):
    """בודק חיבור מלא של פענוח, טרנספורמציה ורינדור."""
    input_pdf = tmp_path / "attendance.pdf"
    input_pdf.write_bytes(b"%PDF-1.4 placeholder")

    report = AttendanceReport(
        employee_id="123",
        employee_name="עובד לבדיקה",
        report_period="2026-10",
        report_type="TYPE_A",
        rows=(
            AttendanceRow(
                work_date=date(2026, 10, 1),
                day_of_week="חמישי",
                entry_time=8 * 60,
                exit_time=17 * 60,
                break_duration_minutes=60,
            ),
        ),
        summary=ReportSummary(),
    )
    _stub_pipeline_parser(monkeypatch, report)
    output_path = tmp_path / "processed.html"

    result = process_attendance_pipeline(
        file_path=str(input_pdf),
        employee_id="123",
        employee_name="עובד לבדיקה",
        period="2026-10",
        report_type="TYPE_A",
        output_html_path=str(output_path),
    )

    assert result == str(output_path)
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert 'dir="rtl"' in content
    assert "עובד לבדיקה" in content
    assert "08:00" in content
    assert "08:00" in content


def test_pipeline_synthetic_simulation_uses_demo_identity_and_preserves_input(
    tmp_path, monkeypatch
):
    input_pdf = tmp_path / "source.pdf"
    input_pdf.write_bytes(b"%PDF-1.4 source remains unchanged")
    source_bytes = input_pdf.read_bytes()
    report = AttendanceReport(
        employee_id="real-id",
        employee_name="Real person",
        report_period="2026-10",
        report_type="TYPE_A",
        rows=(
            AttendanceRow(
                work_date=date(2026, 10, 1),
                day_of_week="חמישי",
                entry_time=8 * 60,
                exit_time=17 * 60,
                break_duration_minutes=30,
            ),
        ),
    )
    _stub_pipeline_parser(monkeypatch, report)
    output_path = tmp_path / "synthetic.html"

    process_attendance_pipeline(
        file_path=str(input_pdf),
        employee_id="real-id",
        employee_name="Real person",
        period="2026-10",
        report_type="TYPE_A",
        output_html_path=str(output_path),
        synthetic_simulation=True,
        seed=73,
        min_shift_minutes=15,
        max_shift_minutes=60,
        simulation_date="2026-11-09",
        holiday_dates=("2026-10-01",),
    )

    content = output_path.read_text(encoding="utf-8")
    assert "נתונים סינתטיים — לצורכי לימוד בלבד" in content
    assert "seed: 73" in content
    assert "תאריך הפקה: 2026-11-09" in content
    assert "עובד/ת לדוגמה" in content
    assert "DEMO" in content
    assert "Real person" not in content
    assert "real-id" not in content
    assert input_pdf.read_bytes() == source_bytes
    assert report.employee_name == "Real person"


def test_pipeline_passes_configured_shift_defaults_to_transformation_rules(
    tmp_path, monkeypatch
):
    input_pdf = tmp_path / "source.pdf"
    input_pdf.write_bytes(b"%PDF-1.4 source")
    report = AttendanceReport(
        employee_id="1",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type="TYPE_A",
        rows=(
            AttendanceRow(
                work_date=date(2026, 10, 1),
                day_of_week="חמישי",
                entry_time=8 * 60,
                exit_time=16 * 60,
            ),
        ),
    )
    _stub_pipeline_parser(monkeypatch, report)
    captured_rules = []

    def capture_transform(strategy, source_report, rules, seed):
        captured_rules.append((rules, seed))
        return source_report

    def capture_output(renderer, transformed_report, output_path):
        assert transformed_report.rows == report.rows

    monkeypatch.setattr(
        "transformation.transformer.TypeATransformationStrategy.transform_report",
        capture_transform,
    )
    monkeypatch.setattr(HtmlRenderer, "render", capture_output)

    process_attendance_pipeline(
        file_path=str(input_pdf),
        employee_id="1",
        employee_name="בדיקה",
        period="2026-10",
        report_type="TYPE_A",
        output_html_path=str(tmp_path / "output.html"),
        synthetic_simulation=True,
    )

    assert len(captured_rules) == 1
    rules, seed = captured_rules[0]
    assert seed == 42
    assert rules.min_shift_minutes == DEFAULT_MIN_SHIFT_MINUTES == 20
    assert rules.max_shift_minutes == DEFAULT_MAX_SHIFT_MINUTES == 30
    assert rules.overtime_100_limit_minutes == DEFAULT_OVERTIME_100_LIMIT_MINUTES
    assert rules.maximum_date_shift_days == DEFAULT_MAXIMUM_DATE_SHIFT_DAYS


def test_cli_uses_configured_shift_defaults(monkeypatch):
    import cli

    calls = []
    monkeypatch.setattr(cli, "check_system_dependencies", lambda: [])
    monkeypatch.setattr(
        cli,
        "process_attendance_pipeline",
        lambda **kwargs: calls.append(kwargs),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["main.py", "--input", "attendance.pdf", "--synthetic-simulation"],
    )

    cli.main()

    assert calls[0]["min_shift_minutes"] == DEFAULT_MIN_SHIFT_MINUTES == 20
    assert calls[0]["max_shift_minutes"] == DEFAULT_MAX_SHIFT_MINUTES == 30
    assert (
        calls[0]["overtime_100_limit_minutes"]
        == DEFAULT_OVERTIME_100_LIMIT_MINUTES
    )
    assert (
        calls[0]["maximum_date_shift_days"]
        == DEFAULT_MAXIMUM_DATE_SHIFT_DAYS
    )


def test_cli_help_documents_output_selection(monkeypatch, capsys):
    import cli

    monkeypatch.setattr("sys.argv", ["main.py", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "--output" in help_text
    assert "--output-dir" in help_text
    assert "--format" in help_text


def test_cli_output_path_selection_preserves_existing_output_option(tmp_path):
    from cli import _resolve_output_path

    assert _resolve_output_path(None, None, None, None) == "output\\report.pdf"
    assert _resolve_output_path(
        "output\\existing.html", None, None, "source.pdf"
    ) == "output\\existing.html"
    assert _resolve_output_path(
        None, str(tmp_path), "html", "input_pdfs\\source.pdf"
    ) == str(tmp_path / "source.html")
    assert _resolve_output_path(
        "output\\existing.pdf", None, "html", "source.pdf"
    ) == "output\\existing.html"


def test_cli_rejects_conflicting_output_options():
    from cli import _resolve_output_path

    with pytest.raises(ValueError, match="--output או --output-dir"):
        _resolve_output_path("report.pdf", "output", None, "source.pdf")
    with pytest.raises(ValueError, match="אינו תואם"):
        _resolve_output_path("report.pdf", None, "html", "source.pdf")


def test_pipeline_synthetic_simulation_updates_dates_and_report_period(
    tmp_path, monkeypatch
):
    input_pdf = tmp_path / "source.pdf"
    input_pdf.write_bytes(b"%PDF-1.4 source")
    report = AttendanceReport(
        employee_id="real-id",
        employee_name="Real person",
        report_period="2026-10",
        report_type="TYPE_A",
        rows=(
            AttendanceRow(
                work_date=date(2026, 10, 1),
                day_of_week="חמישי",
                entry_time=8 * 60,
                exit_time=16 * 60,
            ),
            AttendanceRow(
                work_date=date(2026, 10, 31),
                day_of_week="שבת",
                entry_time=8 * 60,
                exit_time=16 * 60,
            ),
        ),
    )
    _stub_pipeline_parser(monkeypatch, report)
    captured_reports = []

    def capture_report(transformed_report, output_path):
        captured_reports.append(transformed_report)
        return str(output_path)

    monkeypatch.setattr(
        HtmlRenderer,
        "render",
        lambda self, transformed_report, output_path: capture_report(
            transformed_report, output_path
        ),
    )

    for _ in range(2):
        process_attendance_pipeline(
            file_path=str(input_pdf),
            employee_id="real-id",
            employee_name="Real person",
            period="2026-10",
            report_type="TYPE_A",
            output_html_path=str(tmp_path / "synthetic.html"),
            synthetic_simulation=True,
            seed=73,
            min_shift_minutes=0,
            max_shift_minutes=0,
        )

    first, repeat = captured_reports
    dates = [row.work_date for row in first.rows]
    assert len(first.rows) == 2
    assert dates == [row.work_date for row in repeat.rows]
    assert [row.report_type for row in (first, repeat)] == ["TYPE_A", "TYPE_A"]
    assert (dates[0] - date(2026, 10, 1)).days != 0
    assert (dates[1] - date(2026, 10, 31)).days == (
        dates[0] - date(2026, 10, 1)
    ).days
    assert first.rows[1].entry_time is None
    assert first.rows[1].total_work_minutes == 0
    assert first.summary.total_work_minutes == sum(
        row.total_work_minutes for row in first.rows
    )
    assert first.summary.total_100_minutes == sum(
        row.overtime_100_minutes for row in first.rows
    )
    assert first.report_period == (
        f"{dates[0].strftime('%Y-%m')} עד {dates[-1].strftime('%Y-%m')}"
    )
    assert repeat.report_period == first.report_period
    assert first.simulation_date is None
    assert repeat.simulation_date is None
    assert all(
        row.day_of_week
        == ("שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון")[
            row.work_date.weekday()
        ]
        for row in first.rows
    )


def test_pipeline_rejects_report_without_attendance_rows(tmp_path, monkeypatch):
    input_pdf = tmp_path / "empty.pdf"
    input_pdf.write_bytes(b"%PDF-1.4 placeholder")
    empty_report = AttendanceReport(
        employee_id="123",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type="TYPE_A",
        summary=ReportSummary(),
    )
    _stub_pipeline_parser(monkeypatch, empty_report)

    with pytest.raises(ValueError, match="לא זוהו שורות נוכחות"):
        process_attendance_pipeline(
            file_path=str(input_pdf),
            employee_id="123",
            employee_name="בדיקה",
            period="2026-10",
            report_type="TYPE_A",
            output_html_path=str(tmp_path / "empty.html"),
        )


def test_pipeline_extracts_once_and_passes_text_and_detected_type_to_parser(
    tmp_path, monkeypatch
):
    input_pdf = tmp_path / "source.pdf"
    input_pdf.write_bytes(b"%PDF-1.4 source")
    report = AttendanceReport(
        employee_id="123",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type="TYPE_A",
        rows=(
            AttendanceRow(
                work_date=date(2026, 10, 1),
                day_of_week="חמישי",
                entry_time=8 * 60,
                exit_time=17 * 60,
            ),
        ),
    )
    extracted_text = "הפסקה מקום 150% OCR text"
    extraction_calls = []
    parser_calls = []

    def extract(path):
        extraction_calls.append(path)
        return extracted_text

    def parse(**kwargs):
        parser_calls.append(kwargs)
        return report

    monkeypatch.setattr("pipeline.extract_text_from_pdf", extract)
    monkeypatch.setattr("pipeline.parse_report", parse)
    monkeypatch.setattr(HtmlRenderer, "render", lambda self, report, path: None)

    process_attendance_pipeline(
        file_path=str(input_pdf),
        employee_id="123",
        employee_name="בדיקה",
        period="2026-10",
        report_type="AUTO",
        output_html_path=str(tmp_path / "result.html"),
    )

    assert extraction_calls == [str(input_pdf)]
    assert parser_calls[0]["text"] == extracted_text
    assert parser_calls[0]["report_type"].value == "TYPE_B"
    assert parser_calls[0]["employee_id"] == "123"
    assert parser_calls[0]["report_period"] == "2026-10"


def test_pipeline_processes_text_based_pdf_end_to_end(tmp_path):
    pytest.importorskip("reportlab")
    pytest.importorskip("pypdf")
    from reportlab.pdfgen import canvas

    input_pdf = tmp_path / "attendance.pdf"
    pdf = canvas.Canvas(str(input_pdf))
    pdf.drawString(40, 760, "150% 8.00 7.50 0.50 00:30 16:00 08:00 01/02/2023")
    pdf.save()

    output_html = tmp_path / "attendance.html"
    process_attendance_pipeline(
        file_path=str(input_pdf),
        employee_id="123",
        employee_name="PDF test",
        period="2023-02",
        report_type="TYPE_B",
        output_html_path=str(output_html),
    )

    content = output_html.read_text(encoding="utf-8")
    assert "2023-02-01" in content
    assert "08:00" in content
    assert "16:00" in content
    assert ">07:30<" in content
