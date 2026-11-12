"""
tests/test_parser.py
--------------------
בדיקות יחידה עבור מודלי הנתונים, מנגנון ה-Registry והפרסרים.
"""

import pytest
from datetime import date
from dataclasses import FrozenInstanceError

from models import AttendanceRow, AttendanceReport, ReportSummary
from parsing.attendance_parser import (
    BaseParser,
    ParserRegistry,
    TypeAParser,
    TypeBParser,
    clean_text,
)
from models import ReportType
from parsing.parser import parse_report
from tests.fixture_helpers import load_ocr_fixture


def test_attendance_row_immutability():
    """
    מוודא ששורה מסוג AttendanceRow מוגדרת כ-frozen
    וזורקת שגיאה בעת ניסיון שינוי ישיר של שדה.
    """
    row = AttendanceRow(
        work_date=date(2026, 10, 1),
        day_of_week="רביעי",
        entry_time=480,
        exit_time=1020,
        total_work_minutes=540
    )

    with pytest.raises(FrozenInstanceError):
        row.total_work_minutes = 600  # type: ignore


def test_report_models_are_frozen_and_normalize_collections_to_tuples():
    row = AttendanceRow(
        work_date=date(2026, 10, 1),
        day_of_week="רביעי",
    )
    source_rows = [row]
    report = AttendanceReport(
        employee_id="123",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type="TYPE_A",
        rows=source_rows,
    )
    source_rows.clear()

    assert report.rows == (row,)
    assert isinstance(report.rows, tuple)
    with pytest.raises(FrozenInstanceError):
        report.employee_name = "שינוי"  # type: ignore

    summary = ReportSummary(summary_notes=["הערה"])
    assert summary.summary_notes == ("הערה",)
    assert isinstance(summary.summary_notes, tuple)
    with pytest.raises(FrozenInstanceError):
        summary.total_work_minutes = 60  # type: ignore


@pytest.mark.parametrize("field_name", ["entry_time", "exit_time"])
@pytest.mark.parametrize("value", ["08:00", 90.0, True])
def test_attendance_row_rejects_non_integer_clock_minutes(field_name, value):
    with pytest.raises(TypeError, match=field_name):
        AttendanceRow(
            work_date=date(2026, 10, 1),
            day_of_week="רביעי",
            **{field_name: value},
        )


@pytest.mark.parametrize("value", [-1, 24 * 60])
def test_attendance_row_rejects_clock_minutes_outside_day(value):
    with pytest.raises(ValueError, match="between 0 and 1439"):
        AttendanceRow(
            work_date=date(2026, 10, 1),
            day_of_week="רביעי",
            entry_time=value,
        )


def test_parser_registry_and_factory():
    """
    בודק את מנגנון הרישום והמפעל (Registry Pattern) –
    מוודא שניתן לרשום פרסר חדש ושפונקציית המפעל מחזירה את המופע הנכון.
    """
    # יצירת פרסר מדומה חדש לבדיקת הרישום
    class DummyParser(BaseParser):
        def get_report_type_identifier(self) -> str:
            return "TYPE_DUMMY"

        def _is_header_line(self, line: str) -> bool:
            return False

        def _parse_row(self, line: str):
            return None

        def _parse_summary(self, rows, lines):
            return ReportSummary()

    # רישום ה-Parser תחת מזהה ייעודי
    ParserRegistry.register("TYPE_DUMMY")(DummyParser)

    # וידוא שליפה תקינה מהרגיסטרי
    parser = ParserRegistry.get_parser("TYPE_DUMMY")
    assert isinstance(parser, DummyParser)
    assert parser.get_report_type_identifier() == "TYPE_DUMMY"

    # וידוא זריקת שגיאה בעת חיפוש מזהה לא קיים
    with pytest.raises(KeyError):
        ParserRegistry.get_parser("NON_EXISTENT_TYPE")


def test_type_a_parser_execution():
    parser = TypeAParser()
    report = parser.parse(
        "מחיר לשעה לתשלום ימי עבודה הערות\n" + TYPE_A_LINE,
        "12345",
        "ישראל ישראלי",
        "2026-10",
    )

    assert isinstance(report, AttendanceReport)
    assert report.employee_id == "12345"
    assert report.employee_name == "ישראל ישראלי"
    assert report.report_type == "TYPE_A"
    assert isinstance(report.summary, ReportSummary)


def test_type_b_parser_execution():
    parser = TypeBParser()
    report = parser.parse(
        "מקום עבודה הפסקה 125% 150% שבת\n" + TYPE_A_LINE,
        "67890",
        "שרה כהן",
        "2026-10",
    )

    assert isinstance(report, AttendanceReport)
    assert report.employee_id == "67890"
    assert report.employee_name == "שרה כהן"
    assert report.report_type == "TYPE_B"
    assert isinstance(report.rows, tuple)


def test_parser_rejects_reports_without_attendance_rows():
    with pytest.raises(ValueError, match="No attendance rows"):
        TypeAParser().parse(
            "מחיר לשעה לתשלום ימי עבודה הערות",
            "12345",
            "ישראל ישראלי",
            "2026-10",
        )


def test_base_parser_cleans_text_once_before_parsing_lines(monkeypatch):
    raw_text = "מחיר לשעה לתשלום ימי עבודה הערות\n" + TYPE_A_LINE
    clean_calls = []

    def tracked_clean_text(text):
        clean_calls.append(text)
        return clean_text(text)

    monkeypatch.setattr(
        "parsing.attendance_parser.clean_text", tracked_clean_text
    )
    report = TypeAParser().parse(raw_text, "12345", "בדיקה", "2023-02")

    assert clean_calls == [raw_text]
    assert report.rows[0].work_date == date(2023, 2, 1)
    assert report.rows[0].entry_time == 8 * 60
    assert report.rows[0].exit_time == 16 * 60
    assert report.report_type == "TYPE_A"


# ==============================================================================
# בדיקות רגרסיה לשורות OCR (ה-OCR מחזיר עמודות בסדר חזותי, הפוך מהסדר הלוגי)
# ==============================================================================

TYPE_A_LINE = "0.00 0.00 0.00 7.50 7.50 00:30 16:00 08:00 יום רביעי 01/02/2023"
TYPE_B_LINE = "3.50 12:00 8:30 שני 1/9/22"


def test_type_a_row_assigns_entry_exit_and_break_correctly():
    row = TypeAParser()._parse_row(TYPE_A_LINE)

    assert row is not None
    assert row.work_date == date(2023, 2, 1)
    assert row.day_of_week == "רביעי"
    assert isinstance(row.entry_time, int)
    assert isinstance(row.exit_time, int)
    assert row.entry_time == 8 * 60
    assert row.exit_time == 16 * 60
    assert row.break_duration_minutes == 30
    assert isinstance(row.break_duration_minutes, int)
    # סה"כ שעות נלקח מהעמודה העשרונית ולא משארית של התאריך (למשל 2023)
    assert row.total_work_minutes == 450
    assert isinstance(row.total_work_minutes, int)


def test_type_b_row_entry_before_exit_and_total_hours():
    row = TypeBParser()._parse_row(TYPE_B_LINE)

    assert row is not None
    assert row.work_date == date(2022, 9, 1)
    assert row.entry_time == 8 * 60 + 30
    assert row.exit_time == 12 * 60
    assert row.total_work_minutes == 210


def test_type_b_time_roles_follow_column_position_even_for_overnight_hours():
    line = "7.75 יום שני 22:00 06:00 00:15 05/02/2023"

    row = TypeBParser()._parse_row(line)

    assert row is not None
    assert row.entry_time == 22 * 60
    assert row.exit_time == 6 * 60
    assert row.break_duration_minutes == 15
    assert row.total_work_minutes == 465


def test_type_b_reversed_ocr_columns_follow_their_positions():
    line = "7.50 7.50 00:30 16:00 08:00 05/02/2023"

    row = TypeBParser()._parse_row(line)

    assert row is not None
    assert row.entry_time == 8 * 60
    assert row.exit_time == 16 * 60
    assert row.break_duration_minutes == 30


def test_type_b_four_clock_columns_calculate_break_duration_and_overnight_total():
    line = "7.75 22:00 23:00 23:15 06:00 05/02/2023"

    row = TypeBParser()._parse_row(line)

    assert row is not None
    assert row.entry_time == 22 * 60
    assert row.exit_time == 6 * 60
    assert row.break_duration_minutes == 15
    assert row.total_work_minutes == 465


@pytest.mark.parametrize(
    ("line", "reason"),
    [
        ("08:00 16:00 7.50", "missing date"),
        ("7.50 01/02/2023 08:00", "fewer than two time values"),
        (
            "01/02/2023 08:00 16:00",
            "missing numeric total-hours value",
        ),
    ],
)
def test_malformed_attendance_rows_are_skipped_and_reported(
    line, reason, caplog
):
    assert TypeBParser()._parse_row(line) is None
    assert reason in caplog.text


def test_parser_preserves_time_column_order_instead_of_sorting_clock_values():
    row = TypeBParser()._parse_row("7.50 08:00 00:00 01/02/2023")

    assert row is not None
    assert row.entry_time == 8 * 60
    assert row.exit_time == 0


def test_overnight_shift_is_not_swapped():
    line = "7.50 00:30 06:00 22:00 יום שני 05/02/2023"
    row = TypeAParser()._parse_row(line)

    assert row.entry_time == 22 * 60
    assert row.exit_time == 6 * 60


def test_parser_selects_total_hours_closest_to_clock_duration():
    line = "8.00 7.50 0.50 00:30 16:00 08:00 01/02/2023"

    row = TypeAParser()._parse_row(line)

    assert row is not None
    assert row.total_work_minutes == 450


def test_saturday_row_is_not_dropped_as_header():
    text = (
        "תאריך יום מקום עבודה כניסה יציאה הפסקה סה\"כ 100% 125% 150% שבת\n"
        "0.00 0.00 0.00 7.50 7.50 00:30 16:00 08:00 יום שבת 04/02/2023\n"
        "0.00 0.00 0.00 7.50 7.50 00:30 16:00 08:00 יום ראשון 05/02/2023\n"
    )
    report = TypeAParser().parse(text, "1", "בדיקה", "2023-02")

    assert [r.work_date.day for r in report.rows] == [4, 5]
    assert report.summary.total_work_days == 2
    assert report.summary.total_work_minutes == 900


@pytest.mark.parametrize("value", ["01:30", 90.0, True])
def test_duration_models_reject_non_integer_minutes(value):
    with pytest.raises(TypeError, match="total_work_minutes"):
        AttendanceRow(
            work_date=date(2026, 10, 1),
            day_of_week="רביעי",
            total_work_minutes=value,
        )


def test_parse_report_returns_attendance_report_for_explicit_type():
    report = parse_report(
        "מקום עבודה הפסקה 150%\n" + TYPE_A_LINE,
        report_type=ReportType.TYPE_B,
        employee_id="123",
        employee_name="ישראל ישראלי",
        report_period="2023-02",
    )

    assert isinstance(report, AttendanceReport)
    assert report.report_type == "TYPE_B"
    assert len(report.rows) == 1


def test_parse_report_can_classify_text_when_type_is_not_provided():
    report = parse_report(
        "מחיר לשעה לתשלום ימי עבודה הערות\n" + TYPE_B_LINE,
        report_type=ReportType.UNKNOWN,
        employee_id="123",
        employee_name="שרה כהן",
        report_period="2022-09",
    )

    assert isinstance(report, AttendanceReport)
    assert report.report_type == "TYPE_A"
    assert len(report.rows) == 1


def test_parse_report_from_saved_ocr_fixture():
    report = parse_report(
        load_ocr_fixture("a_r_25.txt"),
        report_type=ReportType.TYPE_B,
        employee_id="test",
        employee_name="בדיקת OCR",
        report_period="2023-02",
    )

    assert report.report_type == "TYPE_B"
    assert report.rows
