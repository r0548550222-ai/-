"""Public text-parsing interface for attendance reports."""

from config import (
    DEFAULT_EMPLOYEE_ID,
    DEFAULT_EMPLOYEE_NAME,
    DEFAULT_REPORT_PERIOD,
)
from models import AttendanceReport, ReportType
from parsing.classifier import classify
from parsing.attendance_parser import ParserRegistry


def parse_report(
    text: str,
    report_type: ReportType = ReportType.UNKNOWN,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    employee_name: str = DEFAULT_EMPLOYEE_NAME,
    report_period: str = DEFAULT_REPORT_PERIOD,
) -> AttendanceReport:
    """Classify and parse extracted text into the project's report model."""
    selected_type = report_type
    if selected_type is ReportType.UNKNOWN:
        selected_type = classify(text)

    parser = ParserRegistry.get_parser(selected_type.value)
    return parser.parse(text, employee_id, employee_name, report_period)