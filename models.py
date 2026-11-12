"""
models.py
---------
מודלי הנתונים (DTO) המשותפים לכל שכבות מערכת עיבוד דוחות הנוכחות.
מנגנון הרישום הדינמי של הפרסרים נמצא ב-parsing/attendance_parser.py (ParserRegistry).
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class ReportType(Enum):
    """Canonical report types: A is payroll summary; B is detailed attendance."""

    TYPE_A = "TYPE_A"
    TYPE_B = "TYPE_B"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class AttendanceRow:
    """
    מייצגת שורה בודדת בדו"ח הנוכחות (ברמת יום/משמרת).
    מוגדרת כ-frozen=True להבטחת אי-שינויות (Immutability).
    """
    # שדות משותפים לכלל הדו"חות
    work_date: date
    day_of_week: str
    entry_time: Optional[int] = None
    exit_time: Optional[int] = None
    total_work_minutes: int = 0

    # שדות ייעודיים ותומכים (עבור סוג A, סוג B וטרנספורמציות)
    workplace: Optional[str] = None
    break_duration_minutes: int = 0

    overtime_100_minutes: int = 0
    overtime_125_minutes: int = 0
    overtime_150_minutes: int = 0
    saturday_minutes: int = 0

    notes: str = ""

    def __post_init__(self) -> None:
        """אימות נתונים בסיסי בעת יצירת האובייקט."""
        for field_name in ("entry_time", "exit_time"):
            value = getattr(self, field_name)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool)
            ):
                raise TypeError(
                    f"{field_name} must be integer minutes since midnight or None, "
                    f"got {type(value).__name__}"
                )
            if value is not None and not 0 <= value < 24 * 60:
                raise ValueError(f"{field_name} must be between 0 and 1439 minutes")
        for field_name in (
            "total_work_minutes",
            "break_duration_minutes",
            "overtime_100_minutes",
            "overtime_125_minutes",
            "overtime_150_minutes",
            "saturday_minutes",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{field_name} must be an integer number of minutes")
            if value < 0:
                raise ValueError(f"{field_name} cannot be negative: {value}")


@dataclass(frozen=True)
class ReportSummary:
    """
    מרכזת את נתוני הסיכום החודשי או התקופתי של הדו"ח.
    """
    total_work_days: int = 0
    total_absent_days: int = 0
    total_work_minutes: int = 0

    # סיכומי שעות לפי מדרגות ואחוזים
    total_100_minutes: int = 0
    total_125_minutes: int = 0
    total_150_minutes: int = 0
    total_saturday_minutes: int = 0

    # נתונים כספיים ונסיעות
    hourly_rate: float = 0.0
    total_payment: float = 0.0
    total_travel_days: int = 0
    travel_expenses: float = 0.0
    bonus_amount: float = 0.0

    # הערות וסיכומים כלליים
    summary_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "summary_notes", tuple(self.summary_notes))
        for field_name in (
            "total_work_minutes",
            "total_100_minutes",
            "total_125_minutes",
            "total_150_minutes",
            "total_saturday_minutes",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{field_name} must be an integer number of minutes")
            if value < 0:
                raise ValueError(f"{field_name} cannot be negative: {value}")


@dataclass(frozen=True)
class AttendanceReport:
    """
    האובייקט המרכזי העובר בין שכבות המערכת (DTO).
    """
    employee_id: str
    employee_name: str
    report_period: str
    report_type: str

    rows: tuple[AttendanceRow, ...] = ()
    summary: ReportSummary = field(default_factory=ReportSummary)
    is_synthetic: bool = False
    simulation_seed: Optional[int] = None
    simulation_date: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "rows", tuple(self.rows))
