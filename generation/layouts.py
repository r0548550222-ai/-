"""Report-type-specific data layouts used by the output renderers."""

from dataclasses import dataclass
from typing import Literal

from models import ReportType


@dataclass(frozen=True)
class ColumnLayout:
    field_name: str
    label: str
    value_format: Literal["date", "time", "duration", "hours", "text"]


@dataclass(frozen=True)
class SummaryFieldLayout:
    field_name: str
    label: str
    value_format: Literal["count", "currency", "duration", "hours", "text"]


@dataclass(frozen=True)
class ReportLayout:
    title: str
    columns: tuple[ColumnLayout, ...]
    summary_position: Literal["before_table", "after_table"]
    summary_fields: tuple[SummaryFieldLayout, ...]


_REPORT_LAYOUTS = {
    ReportType.TYPE_A.value: ReportLayout(
        title="דוח שכר",
        columns=(
            ColumnLayout("work_date", "תאריך", "date"),
            ColumnLayout("entry_time", "כניסה", "time"),
            ColumnLayout("exit_time", "יציאה", "time"),
            ColumnLayout("total_work_minutes", "שעות", "hours"),
            ColumnLayout("notes", "הערות", "text"),
        ),
        summary_position="before_table",
        summary_fields=(
            SummaryFieldLayout("hourly_rate", "מחיר לשעה", "currency"),
            SummaryFieldLayout("total_work_days", "ימי עבודה", "count"),
            SummaryFieldLayout("total_absent_days", "ימי היעדרות", "count"),
            SummaryFieldLayout("total_payment", "לתשלום", "currency"),
            SummaryFieldLayout("total_travel_days", "ימי נסיעה", "count"),
            SummaryFieldLayout("travel_expenses", "הוצאות נסיעה", "currency"),
            SummaryFieldLayout("bonus_amount", "בונוס", "currency"),
            SummaryFieldLayout("summary_notes", "הערות סיכום", "text"),
        ),
    ),
    ReportType.TYPE_B.value: ReportLayout(
        title="דוח נוכחות מפורט",
        columns=(
            ColumnLayout("work_date", "תאריך", "date"),
            ColumnLayout("day_of_week", "יום", "text"),
            ColumnLayout("workplace", "מקום עבודה", "text"),
            ColumnLayout("entry_time", "כניסה", "time"),
            ColumnLayout("exit_time", "יציאה", "time"),
            ColumnLayout("break_duration_minutes", "הפסקה", "duration"),
            ColumnLayout("total_work_minutes", "סה״כ שעות", "hours"),
            ColumnLayout("overtime_100_minutes", "100%", "hours"),
            ColumnLayout("overtime_125_minutes", "125%", "hours"),
            ColumnLayout("overtime_150_minutes", "150%", "hours"),
            ColumnLayout("notes", "הערות", "text"),
        ),
        summary_position="after_table",
        summary_fields=(
            SummaryFieldLayout("total_work_days", "ימי עבודה", "count"),
            SummaryFieldLayout("total_absent_days", "ימי היעדרות", "count"),
            SummaryFieldLayout("total_work_minutes", "סה״כ שעות", "hours"),
            SummaryFieldLayout("total_100_minutes", "שעות 100%", "hours"),
            SummaryFieldLayout("total_125_minutes", "שעות 125%", "hours"),
            SummaryFieldLayout("total_150_minutes", "שעות 150%", "hours"),
            SummaryFieldLayout("total_saturday_minutes", "שעות שבת", "hours"),
            SummaryFieldLayout("summary_notes", "הערות סיכום", "text"),
        ),
    ),
}


def get_report_layout(report_type: str) -> ReportLayout:
    """Return the layout matching a report type, or reject unsupported types."""
    try:
        return _REPORT_LAYOUTS[report_type]
    except KeyError as exc:
        raise ValueError(f"לא קיימת פריסה עבור סוג דוח: {report_type}") from exc
