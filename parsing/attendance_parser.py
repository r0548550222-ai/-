"""
attendance_parser.py
--------------------
שכבת הפרסור (Parsing) המיישמת את תבנית Template Method ואת מנגנון ה-Registry.
תומכת בהרחבת סוגי דוחות חדשים ללא פגיעה בקוד הקיים (Open/Closed Principle).
"""

from abc import ABC, abstractmethod
import logging
from typing import Type, Dict, Optional, Callable
from datetime import date
import re
from models import AttendanceReport, AttendanceRow, ReportSummary
from parsing.classifier import classify
from errors import ParsingError

_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})(?!\d)")
_TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3])\s*:\s*([0-5]\d)(?!\d)")
_DECIMAL_RE = re.compile(r"(?<![\d.,])(\d+[.,]\d{1,2})(?![\d])")
# For four clock columns the order is entry, break-out, break-return, exit.
_TIME_COLUMN_ROLES = {
    2: ("entry", "exit"),
    3: ("entry", "exit", "break_duration"),
    4: ("entry", "break_start", "break_end", "exit"),
}
_WEEKDAY_RE = re.compile(r"יום|ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת")
_LOGGER = logging.getLogger(__name__)

# datetime.weekday(): Monday == 0
_HEBREW_DAYS = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]


def clean_text(raw_text: str) -> str:
    """
    Normalize extracted report text and repair common OCR clock formatting.
    """
    if not raw_text:
        return ""

    cleaned = re.sub(
        r'(?<!\d)(\d{1,2})\s*:\s*(\d{2})(?!\d)',
        lambda match: f"{int(match.group(1)):02d}:{match.group(2)}",
        raw_text,
    )
    cleaned = re.sub(r'[^\S\n]+', ' ', cleaned)
    lines = [line.strip() for line in cleaned.splitlines()]
    return "\n".join(line for line in lines if line)


class BaseParser(ABC):
    """
    מחלקת בסיס אבסטרקטית המיישמת את תבנית Template Method עבור תהליך פרסור דוחות.
    מנהלת את זרימת העבודה (Pipeline) המשותפת לכלל סוגי הדוחות.
    """

    def parse(
        self,
        raw_text: str,
        employee_id: str,
        employee_name: str,
        report_period: str
    ) -> AttendanceReport:
        """
        Template Method המרכז את שלבי עיבוד הדו"ח:
        מנקה טקסט גולמי, מפענח שורות נתונים וסיכום ומחזיר AttendanceReport.
        """
        cleaned_text = clean_text(raw_text)
        lines = cleaned_text.splitlines()

        rows: list[AttendanceRow] = []
        for line in lines:
            # שורה שמכילה תאריך היא שורת נתונים - גם אם מופיעה בה המילה "שבת"
            if not _DATE_RE.search(line) and self._is_header_line(line):
                continue
            row = self._parse_row(line)
            if row:
                rows.append(row)

        if not rows:
            raise ParsingError("No attendance rows were parsed from the report.")

        summary = self._parse_summary(rows, lines)
        report_type = self.get_report_type_identifier()

        return AttendanceReport(
            employee_id=employee_id,
            employee_name=employee_name,
            report_period=report_period,
            report_type=report_type,
            rows=tuple(rows),
            summary=summary
        )

    def parse_text(
        self,
        raw_text: str,
        employee_id: str,
        employee_name: str,
        report_period: str,
    ) -> AttendanceReport:
        """Parse extracted report text without accessing its source file."""
        return self.parse(raw_text, employee_id, employee_name, report_period)

    def _time_column_roles(
        self, _line: str, time_positions: list[tuple[int, int]]
    ) -> Optional[tuple[str, ...]]:
        """Return semantic roles in the OCR order of the report's time columns."""
        return _TIME_COLUMN_ROLES.get(len(time_positions))

    def _is_header_line(self, line: str) -> bool:
        return any(keyword in line for keyword in self.header_keywords)

    def _parse_row(self, line: str) -> Optional[AttendanceRow]:
        return self._parse_attendance_row(line)

    def _parse_summary(
        self, rows: list[AttendanceRow], _lines: list[str]
    ) -> ReportSummary:
        return ReportSummary(
            total_work_days=len(rows),
            total_work_minutes=sum(row.total_work_minutes for row in rows),
        )

    def _parse_attendance_row(self, line: str) -> Optional[AttendanceRow]:
        """Parse a row using its time-column positions, logging malformed candidates."""
        date_match = _DATE_RE.search(line)
        time_matches = list(_TIME_RE.finditer(line))
        if not date_match:
            if time_matches:
                _LOGGER.warning("Skipping attendance row: missing date.")
            return None

        if len(time_matches) < 2:
            _LOGGER.warning("Skipping attendance row: fewer than two time values.")
            return None

        day, month, year = (int(value) for value in date_match.groups())
        if year < 100:
            year += 2000
        try:
            work_date = date(year, month, day)
        except ValueError:
            _LOGGER.warning("Skipping attendance row: invalid date.")
            return None

        positions = [(match.start(), match.end()) for match in time_matches]
        roles = self._time_column_roles(line, positions)
        if roles is None:
            _LOGGER.warning(
                "Skipping attendance row: unsupported number of time columns (%d).",
                len(time_matches),
            )
            return None

        # Exclude date and clock values so they cannot be mistaken for duration fields.
        stripped = _TIME_RE.sub(" ", _DATE_RE.sub(" ", line))
        reported_minutes = [
            round(float(value.replace(",", ".")) * 60)
            for value in _DECIMAL_RE.findall(stripped)
        ]
        if not reported_minutes:
            _LOGGER.warning(
                "Skipping attendance row: missing numeric total-hours value."
            )
            return None

        values = {
            role: int(match.group(1)) * 60 + int(match.group(2))
            for role, match in zip(roles, time_matches)
        }
        entry_min = values["entry"]
        exit_min = values["exit"]
        if "break_start" in values and "break_end" in values:
            break_min = (values["break_end"] - values["break_start"]) % (24 * 60)
        else:
            break_min = values.get("break_duration", 0)

        elapsed_minutes = (exit_min - entry_min) % (24 * 60)
        calculated_minutes = max(0, elapsed_minutes - break_min)
        total_work_minutes = min(
            reported_minutes,
            key=lambda value: abs(value - calculated_minutes),
        )
        if total_work_minutes == 0 and calculated_minutes > 0:
            _LOGGER.warning(
                "Skipping attendance row: reported total-hours value is zero "
                "despite nonzero clock duration."
            )
            return None

        return AttendanceRow(
            work_date=work_date,
            day_of_week=_HEBREW_DAYS[work_date.weekday()],
            entry_time=entry_min,
            exit_time=exit_min,
            total_work_minutes=total_work_minutes,
            break_duration_minutes=break_min,
        )

    @abstractmethod
    def get_report_type_identifier(self) -> str:
        """מחזיר את מזהה סוג הדו"ח (למשל 'TYPE_A', 'TYPE_B')."""


class TypeAParser(BaseParser):
    """
    פרסר ספציפי עבור דוחות סוג A (סיכום שכר, תשלום וימי עבודה).
    """

    header_keywords = ("כניסה", "יציאה", "הערות", "סה\"כ שעות")

    def get_report_type_identifier(self) -> str:
        return "TYPE_A"

    def _time_column_roles(
        self, line: str, time_positions: list[tuple[int, int]]
    ) -> Optional[tuple[str, ...]]:
        if len(time_positions) == 3:
            return ("break_duration", "exit", "entry")
        return super()._time_column_roles(line, time_positions)


class TypeBParser(BaseParser):
    """
    פרסר ספציפי עבור דוחות סוג B (כולל מקום עבודה, הפסקה ואחוזי שעות).
    """

    header_keywords = ("מקום עבודה", "הפסקה", "100%", "125%", "150%", "שבת")

    def get_report_type_identifier(self) -> str:
        return "TYPE_B"

    def _time_column_roles(
        self, line: str, time_positions: list[tuple[int, int]]
    ) -> Optional[tuple[str, ...]]:
        roles = super()._time_column_roles(line, time_positions)
        if roles and len(time_positions) == 3:
            duration_column = _DECIMAL_RE.search(line)
            day_match = _WEEKDAY_RE.search(line)
            if day_match:
                reverse_order = day_match.start() > time_positions[-1][1]
            else:
                reverse_order = bool(
                    duration_column
                    and duration_column.end() < time_positions[0][0]
                )
            if reverse_order:
                # Tesseract reverses time-cell order in these two OCR layouts.
                return tuple(reversed(roles))
        elif roles and len(time_positions) == 2:
            day_match = _WEEKDAY_RE.search(line)
            if day_match and day_match.start() > time_positions[-1][1]:
                return tuple(reversed(roles))
        return roles


# ==============================================================================
# מנגנון הרישום הדינמי (Registry Pattern & Factory)
# ==============================================================================

class ParserRegistry:
    """
    אוגדן מרכזי המנהל את רישום הפרסרים במערכת באופן דינמי.
    מאפשר הוספת סוגי דוחות חדשים ללא נגיעה בקוד הקיים.
    """
    _registry: Dict[str, Type[BaseParser]] = {}

    @classmethod
    def register(cls,
                 report_type: str) -> Callable[[Type[BaseParser]],
                                               Type[BaseParser]]:
        """
        דקורטור לרישום מחלקת פרסר חדשה תחת מזהה ייעודי.

        דוגמה לשימוש בעתיד עבור סוג C:
        @ParserRegistry.register("TYPE_C")
        class TypeCParser(BaseParser):
            ...
        """
        def decorator(parser_cls: Type[BaseParser]) -> Type[BaseParser]:
            if report_type in cls._registry:
                raise ValueError(
                    f"Parser for report type '{report_type}' is already registered.")
            cls._registry[report_type] = parser_cls
            return parser_cls
        return decorator

    @classmethod
    def get_parser(cls, report_type: str) -> BaseParser:
        """
        מחזירה מופע של הפרסר המבוקש מתוך הרישום לפי מזהה.
        """
        parser_cls = cls._registry.get(report_type)
        if not parser_cls:
            raise KeyError(
                f"No parser registered for report type: '{report_type}'")
        return parser_cls()

    @classmethod
    def list_supported_types(cls) -> list[str]:
        """מחזירה את מזהי סוגי הדוחות הרשומים."""
        return list(cls._registry.keys())

    @classmethod
    def get_parser_by_content(cls, raw_text: str) -> BaseParser:
        """
        מנגנון זיהוי אוטומטי (Classifier) הבוחן את תוכן הדו"ח ומחזיר את הפרסר המתאים.
        """
        report_type = classify(raw_text)
        return cls.get_parser(report_type.value)


# רישום אוטומטי של הפרסרים הקיימים במערכת
ParserRegistry.register("TYPE_A")(TypeAParser)
ParserRegistry.register("TYPE_B")(TypeBParser)
