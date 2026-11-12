"""צינור עיבוד דוחות נוכחות: חילוץ, סיווג, פרסור, טרנספורמציה ורינדור."""

import os
from collections.abc import Mapping
from dataclasses import replace
from datetime import date
from pathlib import Path

from config import (
    DEFAULT_MAXIMUM_DATE_SHIFT_DAYS,
    DEFAULT_MAX_SHIFT_MINUTES,
    DEFAULT_MIN_SHIFT_MINUTES,
    DEFAULT_OVERTIME_100_LIMIT_MINUTES,
    DEFAULT_SIMULATION_SEED,
)
from errors import ClassificationError, ParsingError, TransformationError
from generation.generator import Renderer
from ocr.ocr import extract_text_from_pdf
from models import ReportType
from parsing.attendance_parser import ParserRegistry
from parsing.classifier import UnknownReportTypeError, classify
from parsing.parser import parse_report
from transformation.transformer import (
    BaseTransformationStrategy,
    TransformationRules,
)


def process_attendance_pipeline(
    file_path: str,
    employee_id: str,
    employee_name: str,
    period: str,
    report_type: str,
    output_html_path: str,
    synthetic_simulation: bool = False,
    seed: int = DEFAULT_SIMULATION_SEED,
    min_shift_minutes: int = DEFAULT_MIN_SHIFT_MINUTES,
    max_shift_minutes: int = DEFAULT_MAX_SHIFT_MINUTES,
    simulation_date: str | None = None,
    holiday_dates: tuple[str, ...] = (),
    overtime_100_limit_minutes: int = DEFAULT_OVERTIME_100_LIMIT_MINUTES,
    maximum_date_shift_days: int = DEFAULT_MAXIMUM_DATE_SHIFT_DAYS,
    *,
    strategies: Mapping[str, BaseTransformationStrategy],
    renderers: Mapping[str, Renderer],
) -> str:
    """מנהל את צינור העבודה המלא: חילוץ -> סיווג -> פרסור -> טרנספורמציה -> רנדור."""
    if not file_path:
        raise ValueError("יש לספק נתיב לקובץ קלט.")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"קובץ הקלט לא נמצא: {file_path}")
    if not file_path.lower().endswith(".pdf"):
        raise ValueError("קובץ הקלט חייב להיות בפורמט PDF.")
    if os.path.normcase(os.path.realpath(file_path)) == os.path.normcase(
        os.path.realpath(output_html_path)
    ):
        raise ValueError("קובץ הפלט חייב להיות נפרד מקובץ המקור.")
    if os.path.exists(output_html_path):
        raise FileExistsError(f"קובץ הפלט כבר קיים: {output_html_path}")
    output_suffix = Path(output_html_path).suffix.lower()
    renderer = renderers.get(output_suffix)
    if renderer is None:
        raise ValueError("סיומת קובץ הפלט חייבת להיות .pdf או .html.")

    if synthetic_simulation and (
        not isinstance(seed, int) or isinstance(seed, bool)
    ):
        raise ValueError("ה-seed חייב להיות מספר שלם.")
    parsed_holiday_dates = frozenset(
        date.fromisoformat(holiday_date) for holiday_date in holiday_dates
    )
    if simulation_date is not None:
        simulation_date = date.fromisoformat(simulation_date).isoformat()

    rules = TransformationRules(
        simulation=synthetic_simulation,
        min_shift_minutes=min_shift_minutes,
        max_shift_minutes=max_shift_minutes,
        overtime_100_limit_minutes=overtime_100_limit_minutes,
        maximum_date_shift_days=maximum_date_shift_days,
        holiday_dates=parsed_holiday_dates,
    )

    normalized_type = report_type.strip().upper()
    if (
        normalized_type != "AUTO"
        and normalized_type not in ParserRegistry.list_supported_types()
    ):
        supported = ", ".join(ParserRegistry.list_supported_types())
        raise ValueError(
            f"סוג דוח לא מוכר או לא רשום: '{normalized_type}'. "
            f"סוגים נתמכים: {supported}, AUTO"
        )

    raw_text = extract_text_from_pdf(file_path)
    try:
        selected_type = (
            classify(raw_text)
            if normalized_type == "AUTO"
            else ReportType(normalized_type)
        )
    except ClassificationError as exc:
        raise ClassificationError(
            f"לא ניתן לסווג את קובץ הקלט '{file_path}': {exc}"
        ) from exc
    if selected_type is ReportType.UNKNOWN:
        raise UnknownReportTypeError(
            "לא ניתן לזהות את סוג הדוח מתוך הטקסט שחולץ. "
            "בחר TYPE_A או TYPE_B במפורש."
        )
    try:
        report = parse_report(
            text=raw_text,
            report_type=selected_type,
            employee_id=employee_id,
            employee_name=employee_name,
            report_period=period,
        )
    except ParsingError as exc:
        raise ParsingError(f"שגיאה בפרסור '{file_path}': {exc}") from exc

    if not report.rows:
        raise ParsingError(
            "לא זוהו שורות נוכחות בקובץ. בדוק את הקובץ ואת סוג הדוח לפני הפקת הפלט."
        )

    strategy = strategies.get(report.report_type)
    if strategy is None:
        raise TransformationError(
            f"אין אסטרטגיית טרנספורמציה מוגדרת עבור: {report.report_type}"
        )
    if synthetic_simulation:
        report = replace(
            report,
            employee_id="DEMO",
            employee_name="עובד/ת לדוגמה",
            is_synthetic=True,
            simulation_seed=seed,
            simulation_date=simulation_date,
        )
    try:
        transformed_report = strategy.transform_report(report, rules=rules, seed=seed)
    except TransformationError as exc:
        raise TransformationError(
            f"שגיאה בטרנספורמציה של דוח {report.report_type}: {exc}"
        ) from exc
    if synthetic_simulation:
        first_month = min(row.work_date for row in transformed_report.rows).strftime(
            "%Y-%m"
        )
        last_month = max(row.work_date for row in transformed_report.rows).strftime(
            "%Y-%m"
        )
        report_period = (
            first_month
            if first_month == last_month
            else f"{first_month} עד {last_month}"
        )
        transformed_report = replace(
            transformed_report,
            report_period=report_period,
        )

    renderer.render(transformed_report, output_html_path)
    output_file = str(output_html_path)
    print(f"הדוח עובד בהצלחה ונשמר בנתיב: {output_html_path}")
    return output_file
