"""
transformer.py
--------------
שכבת הטרנספורמציה והלוגיקה העסקית (Transformation Layer)
המיישמת את תבנית Strategy Pattern לשינוי, עיבוד וחישוב מחדש של נתוני הנוכחות.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from datetime import date, timedelta
import logging
import math
import random
from typing import Dict

from config import (
    DEFAULT_MAXIMUM_ALLOWED_SHIFT_CHANGE_MINUTES,
    DEFAULT_MAXIMUM_BREAK_MINUTES,
    DEFAULT_MAXIMUM_CLOCK_MINUTE,
    DEFAULT_MAXIMUM_DATE_SHIFT_DAYS,
    DEFAULT_MAXIMUM_SHIFT_DURATION_MINUTES,
    DEFAULT_MAXIMUM_SIMULATED_WORK_MINUTES,
    DEFAULT_MAXIMUM_WORK_MINUTES,
    DEFAULT_MINIMUM_CLOCK_MINUTE,
    DEFAULT_MINIMUM_SIMULATED_WORK_MINUTES,
    DEFAULT_MAX_SHIFT_MINUTES,
    DEFAULT_MIN_SHIFT_MINUTES,
    DEFAULT_OVERTIME_100_LIMIT_MINUTES,
    DEFAULT_OVERTIME_125_LIMIT_MINUTES,
    MINUTES_PER_DAY,
)
from errors import TransformationError
from models import AttendanceRow, AttendanceReport, ReportSummary

_HEBREW_DAYS = ("שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון")
_LOGGER = logging.getLogger(__name__)


class InvalidTransformedRowError(TransformationError):
    """Raised when a transformed attendance row violates business rules."""


@dataclass(frozen=True)
class TransformationRules:
    """Validated options consumed by report transformation strategies."""

    simulation: bool = False
    min_shift_minutes: int = DEFAULT_MIN_SHIFT_MINUTES
    max_shift_minutes: int = DEFAULT_MAX_SHIFT_MINUTES
    time_shift_minutes: int | None = None
    maximum_allowed_shift_change_minutes: int = (
        DEFAULT_MAXIMUM_ALLOWED_SHIFT_CHANGE_MINUTES
    )
    minimum_simulated_work_minutes: int = DEFAULT_MINIMUM_SIMULATED_WORK_MINUTES
    maximum_simulated_work_minutes: int = DEFAULT_MAXIMUM_SIMULATED_WORK_MINUTES
    maximum_work_minutes: int = DEFAULT_MAXIMUM_WORK_MINUTES
    maximum_shift_duration_minutes: int = DEFAULT_MAXIMUM_SHIFT_DURATION_MINUTES
    overtime_100_limit_minutes: int = DEFAULT_OVERTIME_100_LIMIT_MINUTES
    overtime_125_limit_minutes: int = DEFAULT_OVERTIME_125_LIMIT_MINUTES
    minimum_clock_minute: int = DEFAULT_MINIMUM_CLOCK_MINUTE
    maximum_clock_minute: int = DEFAULT_MAXIMUM_CLOCK_MINUTE
    minutes_per_day: int = MINUTES_PER_DAY
    maximum_break_minutes: int = DEFAULT_MAXIMUM_BREAK_MINUTES
    maximum_date_shift_days: int = DEFAULT_MAXIMUM_DATE_SHIFT_DAYS
    holiday_dates: frozenset[date] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.simulation, bool):
            raise TransformationError("simulation חייב להיות ערך בוליאני.")
        integer_fields = (
            "min_shift_minutes",
            "max_shift_minutes",
            "maximum_allowed_shift_change_minutes",
            "minimum_simulated_work_minutes",
            "maximum_simulated_work_minutes",
            "maximum_work_minutes",
            "maximum_shift_duration_minutes",
            "overtime_100_limit_minutes",
            "overtime_125_limit_minutes",
            "minimum_clock_minute",
            "maximum_clock_minute",
            "minutes_per_day",
            "maximum_break_minutes",
            "maximum_date_shift_days",
        )
        if any(
            not isinstance(getattr(self, field_name), int)
            or isinstance(getattr(self, field_name), bool)
            for field_name in integer_fields
        ):
            raise TransformationError(
                "ערכי כללי הטרנספורמציה חייבים להיות מספרים שלמים."
            )
        if (
            self.min_shift_minutes < 0
            or self.maximum_allowed_shift_change_minutes < 0
            or self.max_shift_minutes < self.min_shift_minutes
            or self.max_shift_minutes > self.maximum_allowed_shift_change_minutes
        ):
            raise TransformationError(
                "טווח שינוי השעות אינו תקין לפי גבול השינוי המותר."
            )
        if (
            self.minimum_simulated_work_minutes < 0
            or self.maximum_simulated_work_minutes
            < self.minimum_simulated_work_minutes
            or self.maximum_simulated_work_minutes > self.maximum_work_minutes
            or self.maximum_work_minutes <= 0
            or self.maximum_work_minutes >= self.minutes_per_day
            or self.maximum_shift_duration_minutes <= 0
            or self.maximum_shift_duration_minutes >= self.minutes_per_day
        ):
            raise TransformationError("טווח שעות העבודה המוגדר אינו תקין.")
        if (
            self.overtime_100_limit_minutes < 0
            or self.overtime_125_limit_minutes < 0
        ):
            raise TransformationError("גבולות מדרגות השעות חייבים להיות לא שליליים.")
        if (
            self.minimum_clock_minute < 0
            or self.minutes_per_day <= 0
            or self.maximum_clock_minute >= self.minutes_per_day
            or self.minimum_clock_minute > self.maximum_clock_minute
        ):
            raise TransformationError("טווח דקות השעון אינו תואם לאורך היום שהוגדר.")
        if (
            self.maximum_break_minutes < 0
            or self.maximum_break_minutes > self.maximum_shift_duration_minutes
        ):
            raise TransformationError("תקרת ההפסקה חייבת להיות בטווח משך המשמרת.")
        if self.maximum_date_shift_days < 0:
            raise TransformationError("היסט התאריכים המרבי חייב להיות לא שלילי.")
        if self.time_shift_minutes is not None and (
            not isinstance(self.time_shift_minutes, int)
            or isinstance(self.time_shift_minutes, bool)
        ):
            raise TransformationError("time_shift_minutes חייב להיות מספר שלם.")
        if not isinstance(self.holiday_dates, frozenset) or any(
            type(holiday) is not date for holiday in self.holiday_dates
        ):
            raise TransformationError(
                "holiday_dates חייב להכיל תאריכי date בתוך frozenset."
            )


def validate_row(
    row: AttendanceRow,
    rules: TransformationRules,
) -> None:
    """Validate clock, duration, break, and overtime invariants for one row."""
    identifier = row.work_date.isoformat()
    time_values = (row.entry_time, row.exit_time)
    if (row.entry_time is None) != (row.exit_time is None):
        raise InvalidTransformedRowError(
            f"Row {identifier}: entry and exit times must both be present or absent."
        )
    for field_name, value in zip(("entry_time", "exit_time"), time_values):
        if value is not None and not (
            rules.minimum_clock_minute <= value <= rules.maximum_clock_minute
        ):
            raise InvalidTransformedRowError(
                f"Row {identifier}: {field_name} is outside the configured clock range."
            )

    minute_fields = (
        "total_work_minutes",
        "break_duration_minutes",
        "overtime_100_minutes",
        "overtime_125_minutes",
        "overtime_150_minutes",
        "saturday_minutes",
    )
    for field_name in minute_fields:
        value = getattr(row, field_name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise InvalidTransformedRowError(
                f"Row {identifier}: {field_name} must be a non-negative integer."
            )
    if row.total_work_minutes > rules.maximum_work_minutes:
        raise InvalidTransformedRowError(
            f"Row {identifier}: total work exceeds the configured maximum."
        )
    if row.break_duration_minutes > rules.maximum_break_minutes:
        raise InvalidTransformedRowError(
            f"Row {identifier}: break duration exceeds the configured maximum."
        )

    if row.entry_time is not None and row.exit_time is not None:
        elapsed = (
            row.exit_time - row.entry_time
        ) % rules.minutes_per_day
        if elapsed == 0 or elapsed > rules.maximum_shift_duration_minutes:
            raise InvalidTransformedRowError(
                f"Row {identifier}: exit time is invalid relative to entry time."
            )
        if row.break_duration_minutes > elapsed:
            raise InvalidTransformedRowError(
                f"Row {identifier}: break duration exceeds the elapsed shift."
            )
    if row.entry_time is None and (
        row.total_work_minutes
        or row.break_duration_minutes
        or row.overtime_100_minutes
        or row.overtime_125_minutes
        or row.overtime_150_minutes
        or row.saturday_minutes
    ):
        raise InvalidTransformedRowError(
            f"Row {identifier}: work values cannot be present without clock times."
        )
    if (
        row.overtime_100_minutes
        + row.overtime_125_minutes
        + row.overtime_150_minutes
        != row.total_work_minutes
    ):
        raise InvalidTransformedRowError(
            f"Row {identifier}: overtime tiers do not sum to total work minutes."
        )


class BaseTransformationStrategy(ABC):
    """
    מחלקת בסיס אבסטרקטית המגדירה את החוזה לאסטרטגיות טרנספורמציה שונות.
    מיישמת את תבנית Strategy Pattern.
    """

    @abstractmethod
    def transform_row(
            self,
            row: AttendanceRow,
            rules: TransformationRules,
            seed: int) -> AttendanceRow:
        """
        מבצעת טרנספורמציה על שורה בודדת תוך שמירה קפדנית על עקרון ה-Immutability.
        """
        pass

    def transform_report(
            self,
            report: AttendanceReport,
            rules: TransformationRules,
            seed: int) -> AttendanceReport:
        """
        מבצעת טרנספורמציה על הדו"ח השלם:
        1. מפעילה את האסטרטגיה על כל שורה בנפרד (תוך שימוש ב-seed לדטרמיניזם).
        2. מחשבת מחדש את אובייקט הסיכום (ReportSummary).
        3. מחזירה אובייקט AttendanceReport חדש ונקי.
        """
        # הערה: ה-seed מועבר לכל שורה בנפרד. אין קריאה ל-random.seed גלובלי, כדי לא
        # לשנות את מצב מחולל המספרים האקראיים של שאר התוכנית כתופעת לוואי.
        new_rows: list[AttendanceRow] = []
        source_protected_rows: list[bool] = []
        date_offset = 0
        if rules.simulation and rules.maximum_date_shift_days:
            date_rng = random.Random(seed)
            date_offset = date_rng.randint(
                1, rules.maximum_date_shift_days
            ) * date_rng.choice((-1, 1))

        for row in report.rows:
            source_date = row.work_date
            source_protected_day = (
                source_date.weekday() == 5 or source_date in rules.holiday_dates
            )
            source_protected_rows.append(
                rules.simulation and source_protected_day
            )
            if rules.simulation and date_offset:
                work_date = source_date + timedelta(days=date_offset)
                row = replace(
                    row,
                    work_date=work_date,
                    day_of_week=_HEBREW_DAYS[work_date.weekday()],
                )
            destination_protected_day = (
                row.work_date.weekday() == 5
                or row.work_date in rules.holiday_dates
            )
            if rules.simulation and (
                source_protected_day
                or destination_protected_day
                or row.entry_time is None
                or row.exit_time is None
            ):
                transformed_row = self._clear_work_values(row)
            else:
                transformed_row = self.transform_row(
                    row, rules, self._stable_row_seed(seed, source_date)
                )

            validate_row(transformed_row, rules)
            new_rows.append(transformed_row)

        immutable_rows = tuple(new_rows)
        new_summary = self._calculate_summary(
            immutable_rows,
            report.summary,
            rules,
            tuple(source_protected_rows),
        )

        # יצירת מופע חדש של הדו"ח לשמירה על אי-שינויות של המקור
        return replace(report, rows=immutable_rows, summary=new_summary)

    @staticmethod
    def _stable_row_seed(seed: int, work_date: date) -> int:
        """Derive a deterministic random seed from the run seed and stable row date."""
        return seed * 1_000_003 + work_date.toordinal()

    @staticmethod
    def _clear_work_values(row: AttendanceRow) -> AttendanceRow:
        return replace(
            row,
            entry_time=None,
            exit_time=None,
            total_work_minutes=0,
            break_duration_minutes=0,
            overtime_100_minutes=0,
            overtime_125_minutes=0,
            overtime_150_minutes=0,
            saturday_minutes=0,
        )

    def _calculate_summary(
        self,
        rows: tuple[AttendanceRow, ...],
        original: ReportSummary,
        rules: TransformationRules,
        source_protected_rows: tuple[bool, ...],
    ) -> ReportSummary:
        total_work_minutes = sum(row.total_work_minutes for row in rows)
        hourly_rate = original.hourly_rate
        total_payment = original.total_payment
        if isinstance(hourly_rate, (int, float)) and math.isfinite(hourly_rate):
            if hourly_rate > 0:
                total_payment = round(total_work_minutes * hourly_rate / 60, 2)
            elif total_work_minutes != original.total_work_minutes:
                if original.total_payment:
                    raise TransformationError(
                        "Cannot recalculate total_payment: a valid hourly_rate "
                        "is required."
                    )
                _LOGGER.warning(
                    "total_payment was not recalculated because hourly_rate is missing."
                )
        elif total_work_minutes != original.total_work_minutes:
            raise TransformationError(
                "Cannot recalculate total_payment: hourly_rate is not a valid number."
            )

        return replace(
            original,
            total_work_days=sum(
                1
                for row in rows
                if row.total_work_minutes > 0
                and row.entry_time is not None
                and row.exit_time is not None
            ),
            total_absent_days=sum(
                1
                for row, was_source_protected in zip(rows, source_protected_rows)
                if (row.entry_time is None or row.exit_time is None)
                and row.work_date.weekday() != 5
                and row.work_date not in rules.holiday_dates
                and not was_source_protected
            ),
            total_work_minutes=total_work_minutes,
            total_100_minutes=sum(row.overtime_100_minutes for row in rows),
            total_125_minutes=sum(row.overtime_125_minutes for row in rows),
            total_150_minutes=sum(row.overtime_150_minutes for row in rows),
            total_saturday_minutes=sum(row.saturday_minutes for row in rows),
            total_payment=total_payment,
        )

    def _resolve_break_minutes(self, row: AttendanceRow) -> int:
        """מחזירה את משך ההפסקה בדקות מתוך מודל הנתונים."""
        return row.break_duration_minutes

    def _normalize_clock_minutes(
        self, minutes: int, rules: TransformationRules
    ) -> int:
        """מנרמלת דקות שעון לטווח של יום אחד."""
        return minutes % rules.minutes_per_day

    def _resolve_exit_minutes(
        self,
        row: AttendanceRow,
        entry_min: int,
        exit_min: int,
        rules: TransformationRules,
    ) -> int:
        resolved_exit = exit_min
        if exit_min <= entry_min:
            resolved_exit += rules.minutes_per_day

        elapsed = resolved_exit - entry_min
        if elapsed <= 0 or elapsed > rules.maximum_shift_duration_minutes:
            raise InvalidTransformedRowError(
                f"Row {row.work_date.isoformat()}: exit time is invalid relative "
                "to entry time."
            )
        return resolved_exit

    def _resolve_shift_minutes(
        self,
        row: AttendanceRow,
        rules: TransformationRules,
        seed: int,
    ) -> tuple[int, int, int]:
        if row.entry_time is None or row.exit_time is None:
            raise TransformationError(
                "Cannot calculate a shift without entry and exit times."
            )
        entry_min = row.entry_time
        exit_min = self._resolve_exit_minutes(
            row,
            entry_min,
            row.exit_time,
            rules,
        )
        break_minutes = self._resolve_break_minutes(row)

        if rules.simulation:
            break_minutes = max(
                0, min(break_minutes, rules.maximum_break_minutes)
            )
            minimum = rules.min_shift_minutes
            maximum = rules.max_shift_minutes

            rng = random.Random(seed)

            def offset() -> int:
                if maximum == 0:
                    return 0
                magnitude = rng.randint(minimum, maximum)
                return magnitude * rng.choice((-1, 1))

            base_net_minutes = max(
                rules.minimum_simulated_work_minutes,
                min(
                    rules.maximum_simulated_work_minutes,
                    exit_min - entry_min - break_minutes,
                ),
            )
            entry_min = max(
                rules.minimum_clock_minute,
                min(
                    rules.maximum_clock_minute,
                    entry_min + offset(),
                ),
            )
            new_net_minutes = max(
                rules.minimum_simulated_work_minutes,
                min(
                    rules.maximum_simulated_work_minutes,
                    base_net_minutes + offset(),
                ),
            )
            exit_min = entry_min + new_net_minutes + break_minutes
        elif rules.time_shift_minutes is not None:
            shift = rules.time_shift_minutes
            entry_min += shift
            exit_min += shift

        return entry_min, exit_min, break_minutes

    @staticmethod
    def _split_overtime(
        total_work_minutes: int, rules: TransformationRules
    ) -> tuple[int, int, int]:
        overtime_100 = min(total_work_minutes, rules.overtime_100_limit_minutes)
        overtime_125 = max(
            0,
            min(
                total_work_minutes - rules.overtime_100_limit_minutes,
                rules.overtime_125_limit_minutes,
            ),
        )
        overtime_150 = max(
            0,
            total_work_minutes
            - rules.overtime_100_limit_minutes
            - rules.overtime_125_limit_minutes,
        )
        return overtime_100, overtime_125, overtime_150


class TypeATransformationStrategy(BaseTransformationStrategy):
    """
    אסטרטגיית טרנספורמציה עבור דוחות מסוג A.
    מטפלת בעדכון זמנים, אכיפת אינווריאנטים, וחישוב שעות נוספות מסוג A.
    """

    def transform_row(
            self,
            row: AttendanceRow,
            rules: TransformationRules,
            seed: int) -> AttendanceRow:
        if row.entry_time is None or row.exit_time is None:
            return row

        entry_min, exit_min, break_mins = self._resolve_shift_minutes(
            row, rules, seed
        )

        # חישוב סה"כ שעות נטו
        net_work_mins = max(0, (exit_min - entry_min) - break_mins)
        total_work_minutes = net_work_mins

        # חלוקה למדרגות שעות בסוג A
        (
            overtime_100_minutes,
            overtime_125_minutes,
            overtime_150_minutes,
        ) = self._split_overtime(total_work_minutes, rules)

        # יצירת אובייקט חדש באמצעות replace בשל Immutability
        return replace(
            row,
            entry_time=self._normalize_clock_minutes(entry_min, rules),
            exit_time=self._normalize_clock_minutes(exit_min, rules),
            total_work_minutes=total_work_minutes,
            overtime_100_minutes=overtime_100_minutes,
            overtime_125_minutes=overtime_125_minutes,
            overtime_150_minutes=overtime_150_minutes,
            saturday_minutes=0 if rules.simulation else row.saturday_minutes,
            break_duration_minutes=break_mins,
        )


class TypeBTransformationStrategy(BaseTransformationStrategy):
    """
    אסטרטגיית טרנספורמציה עבור דוחות מסוג B.
    מטפלת בעדכון זמנים, הפסקות, וחישוב חלוקת שעות לאחוזים (100%, 125%, 150%).
    """

    def transform_row(
            self,
            row: AttendanceRow,
            rules: TransformationRules,
            seed: int) -> AttendanceRow:
        if row.entry_time is None or row.exit_time is None:
            return row

        entry_min, exit_min, break_duration = self._resolve_shift_minutes(
            row, rules, seed
        )
        net_mins = max(0, (exit_min - entry_min) - break_duration)
        total_work_minutes = net_mins

        (
            overtime_100_minutes,
            overtime_125_minutes,
            overtime_150_minutes,
        ) = self._split_overtime(total_work_minutes, rules)

        return replace(
            row,
            entry_time=self._normalize_clock_minutes(entry_min, rules),
            exit_time=self._normalize_clock_minutes(exit_min, rules),
            total_work_minutes=total_work_minutes,
            overtime_100_minutes=overtime_100_minutes,
            overtime_125_minutes=overtime_125_minutes,
            overtime_150_minutes=overtime_150_minutes,
            saturday_minutes=0 if rules.simulation else row.saturday_minutes,
            break_duration_minutes=break_duration,
        )


# ==============================================================================
# רישום אסטרטגיות (Registry) - הוספת סוג דו"ח חדש לא דורשת שינוי ב-main.py
# ==============================================================================

TRANSFORMATION_STRATEGIES: Dict[str, type] = {
    "TYPE_A": TypeATransformationStrategy,
    "TYPE_B": TypeBTransformationStrategy,
}


def get_transformation_strategy(report_type: str) -> BaseTransformationStrategy:
    """מחזירה מופע של אסטרטגיית הטרנספורמציה המתאימה לסוג הדו"ח."""
    try:
        return TRANSFORMATION_STRATEGIES[report_type]()
    except KeyError:
        raise TransformationError(
            f"אין אסטרטגיית טרנספורמציה מוגדרת עבור: {report_type}") from None
