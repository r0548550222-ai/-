"""ממשק שורת הפקודה והמצב האינטראקטיבי."""

import argparse
import os
import shutil
import sys
from pathlib import Path

from config import (
    DEFAULT_EMPLOYEE_ID,
    DEFAULT_EMPLOYEE_NAME,
    DEFAULT_MAXIMUM_DATE_SHIFT_DAYS,
    DEFAULT_MAX_SHIFT_MINUTES,
    DEFAULT_MIN_SHIFT_MINUTES,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_OVERTIME_100_LIMIT_MINUTES,
    DEFAULT_REPORT_PERIOD,
    DEFAULT_REPORT_TYPE,
    DEFAULT_SIMULATION_SEED,
)
from errors import AttendanceProjectError
from main import process_attendance_pipeline


def check_system_dependencies() -> list[str]:
    """מאתר כלי OCR ו-Poppler ומחזיר אזהרות על כלים חסרים."""
    warnings: list[str] = []

    tesseract_cmd = os.environ.get("TESSERACT_CMD")
    if not tesseract_cmd or not (
        shutil.which(tesseract_cmd) or os.path.exists(tesseract_cmd)
    ):
        found = shutil.which("tesseract")
        tesseract_candidates = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            os.path.join(
                os.environ.get("LOCALAPPDATA", ""),
                "Programs",
                "Tesseract-OCR",
                "tesseract.exe",
            ),
        ]
        if not found:
            found = next(
                (candidate for candidate in tesseract_candidates if os.path.exists(candidate)),
                None,
            )
        if found:
            os.environ["TESSERACT_CMD"] = found
        else:
            warnings.append(
                "אזהרה: מנוע Tesseract-OCR לא נמצא. עיבוד קבצי PDF סרוקים ייכשל. "
                "יש להתקין אותו או להגדיר את משתנה הסביבה TESSERACT_CMD."
            )

    poppler_path = os.environ.get("POPPLER_PATH")
    if not shutil.which("pdftoppm") and not (
        poppler_path and os.path.isdir(poppler_path)
    ):
        poppler_candidates = [
            r"C:\poppler\Library\bin",
            os.path.join(
                os.environ.get("LOCALAPPDATA", ""),
                "Microsoft",
                "WinGet",
                "Packages",
            ),
        ]
        found_poppler = next(
            (
                str(path.parent)
                for root in poppler_candidates
                if os.path.isdir(root)
                for path in Path(root).rglob("pdftoppm.exe")
            ),
            None,
        )
        if found_poppler:
            os.environ["POPPLER_PATH"] = found_poppler
        else:
            warnings.append(
                "אזהרה: כלי ה-Poppler (pdftoppm) לא נמצא. עיבוד PDF סרוק ייכשל. "
                "יש להתקין אותו או להגדיר את POPPLER_PATH."
            )

    return warnings


def interactive_mode() -> None:
    """מנהל ממשק משתמש אינטראקטיבי כאשר לא מועברים ארגומנטים ב-CLI."""
    print("=== מערכת עיבוד דוחות נוכחות - מצב אינטראקטיבי ===")

    input_dir = Path("input_pdfs")
    if not input_dir.exists() or not any(input_dir.glob("*.pdf")):
        print(f"תיקיית הקלט '{input_dir}' ריקה או אינה קיימת.")
        sys.exit(1)

    pdf_files = list(input_dir.glob("*.pdf"))
    print("\nקבצי PDF זמינים בתיקייה:")
    for idx, file in enumerate(pdf_files, 1):
        print(f"  {idx}. {file.name}")

    choice = input("\nבחר את מספר הקובץ הרצוי: ").strip()
    try:
        selected_file = str(pdf_files[int(choice) - 1])
    except (ValueError, IndexError):
        print("בחירה לא תקינה.")
        sys.exit(1)

    emp_id = (
        input(
            f"הכנס תעודת זהות / מזהה עובד (ברירת מחדל: {DEFAULT_EMPLOYEE_ID}): "
        ).strip()
        or DEFAULT_EMPLOYEE_ID
    )
    emp_name = (
        input(f"הכנס שם עובד (ברירת מחדל: {DEFAULT_EMPLOYEE_NAME}): ").strip()
        or DEFAULT_EMPLOYEE_NAME
    )
    period = (
        input(f"הכנס תקופה/חודש (ברירת מחדל {DEFAULT_REPORT_PERIOD}): ").strip()
        or DEFAULT_REPORT_PERIOD
    )

    print("\nסוגי דוחות זמינים: TYPE_A, TYPE_B, AUTO")
    report_type = (
        input(
            f"הכנס סוג דוח (ברירת מחדל {DEFAULT_REPORT_TYPE}): "
        ).strip().upper()
        or DEFAULT_REPORT_TYPE
    )
    synthetic_answer = input(
        "להפיק תרגול עם נתונים סינתטיים? (y/N): "
    ).strip().lower()
    synthetic_simulation = synthetic_answer in {"y", "yes"}
    seed = DEFAULT_SIMULATION_SEED
    min_shift_minutes = DEFAULT_MIN_SHIFT_MINUTES
    max_shift_minutes = DEFAULT_MAX_SHIFT_MINUTES
    overtime_100_limit_minutes = DEFAULT_OVERTIME_100_LIMIT_MINUTES
    maximum_date_shift_days = DEFAULT_MAXIMUM_DATE_SHIFT_DAYS
    simulation_date = None
    holiday_dates: tuple[str, ...] = ()
    if synthetic_simulation:
        seed_text = input(
            f"seed לשחזור (ברירת מחדל {DEFAULT_SIMULATION_SEED}): "
        ).strip()
        seed = int(seed_text) if seed_text else DEFAULT_SIMULATION_SEED
        minimum_text = input(
            f"שינוי מינימלי בדקות (ברירת מחדל {DEFAULT_MIN_SHIFT_MINUTES}): "
        ).strip()
        maximum_text = input(
            f"שינוי מרבי בדקות (ברירת מחדל {DEFAULT_MAX_SHIFT_MINUTES}): "
        ).strip()
        min_shift_minutes = (
            int(minimum_text) if minimum_text else DEFAULT_MIN_SHIFT_MINUTES
        )
        max_shift_minutes = (
            int(maximum_text) if maximum_text else DEFAULT_MAX_SHIFT_MINUTES
        )
        overtime_text = input(
            "גבול מדרגת 100% בדקות "
            f"(ברירת מחדל {DEFAULT_OVERTIME_100_LIMIT_MINUTES}): "
        ).strip()
        date_shift_text = input(
            "היסט תאריך מרבי בימים "
            f"(ברירת מחדל {DEFAULT_MAXIMUM_DATE_SHIFT_DAYS}): "
        ).strip()
        overtime_100_limit_minutes = (
            int(overtime_text)
            if overtime_text
            else DEFAULT_OVERTIME_100_LIMIT_MINUTES
        )
        maximum_date_shift_days = (
            int(date_shift_text)
            if date_shift_text
            else DEFAULT_MAXIMUM_DATE_SHIFT_DAYS
        )
        simulation_date = input(
            "תאריך הפקה להצגה (YYYY-MM-DD, ריק כדי לא לציין): "
        ).strip() or None
        holiday_text = input(
            "תאריכי חג ללא שעות בדוח (YYYY-MM-DD, מופרדים בפסיקים): "
        ).strip()
        holiday_dates = tuple(
            value.strip() for value in holiday_text.split(",") if value.strip()
        )

    prefix = "synthetic_practice" if synthetic_simulation else "report"
    output_filename = f"{prefix}_{Path(selected_file).stem}.{DEFAULT_OUTPUT_FORMAT}"
    output_path = os.path.join("output", output_filename)

    print("מעבד את הקובץ...")
    try:
        process_attendance_pipeline(
            file_path=selected_file,
            employee_id=emp_id,
            employee_name=emp_name,
            period=period,
            report_type=report_type,
            output_html_path=output_path,
            synthetic_simulation=synthetic_simulation,
            seed=seed,
            min_shift_minutes=min_shift_minutes,
            max_shift_minutes=max_shift_minutes,
            overtime_100_limit_minutes=overtime_100_limit_minutes,
            maximum_date_shift_days=maximum_date_shift_days,
            simulation_date=simulation_date,
            holiday_dates=holiday_dates,
        )
    except (AttendanceProjectError, ValueError, OSError) as exc:
        print(f"שגיאה בתהליך: {exc}", file=sys.stderr)
        sys.exit(1)


def _resolve_output_path(
    output: str | None,
    output_dir: str | None,
    output_format: str | None,
    input_path: str | None,
) -> str:
    if output and output_dir:
        raise ValueError("יש לבחור --output או --output-dir, ולא את שניהם.")

    selected_format = (output_format or DEFAULT_OUTPUT_FORMAT).lower().lstrip(".")
    if selected_format not in {"pdf", "html"}:
        raise ValueError("פורמט הפלט חייב להיות pdf או html.")

    if output_dir:
        stem = Path(input_path).stem if input_path else "report"
        return str(Path(output_dir) / f"{stem}.{selected_format}")
    if output is None:
        return str(Path("output") / f"report.{selected_format}")

    output_path = Path(output)
    suffixes = {".pdf", ".html", ".htm"}
    existing_suffix = output_path.suffix.lower()

    if output_format is None:
        if existing_suffix and existing_suffix not in suffixes:
            # Preserve the explicit output path when it already has a valid suffix.
            return output
        if existing_suffix in {".htm", ".html", ".pdf"}:
            return output
        return output

    if existing_suffix and existing_suffix not in {f".{selected_format}", ".htm" if selected_format == "html" else f".{selected_format}"}:
        raise ValueError("--format אינו תואם לסיומת הנתיב שנבחרה ב--output.")
    if existing_suffix == ".htm" and selected_format == "html":
        return str(output_path)
    return str(output_path.with_suffix(f".{selected_format}"))


def main() -> None:
    """מגדיר את אפשרויות ה-CLI ומפעיל מצב אינטראקטיבי או עיבוד ישיר."""
    parser = argparse.ArgumentParser(description="מערכת עיבוד דוחות נוכחות")
    parser.add_argument("--input", type=str, help="נתיב לקובץ קלט PDF")
    parser.add_argument(
        "--employee-id", type=str, default=DEFAULT_EMPLOYEE_ID, help="מזהה עובד"
    )
    parser.add_argument(
        "--employee-name", type=str, default=DEFAULT_EMPLOYEE_NAME, help="שם העובד"
    )
    parser.add_argument(
        "--period", type=str, default=DEFAULT_REPORT_PERIOD, help="תקופת הדוח"
    )
    parser.add_argument(
        "--report-type",
        type=str,
        default=DEFAULT_REPORT_TYPE,
        help="סוג הדוח (TYPE_A, TYPE_B או AUTO לזיהוי אוטומטי)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="נתיב לקובץ פלט PDF או HTML",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="תיקיית פלט; שם הקובץ ייגזר משם קובץ הקלט",
    )
    parser.add_argument(
        "--format",
        choices=("pdf", "html"),
        help="פורמט פלט; ברירת המחדל היא PDF, או סיומת --output",
    )
    parser.add_argument(
        "--synthetic-simulation",
        action="store_true",
        help="יצירת תרגול מסומן עם נתונים סינתטיים",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SIMULATION_SEED,
        help="seed לשחזור סימולציה סינתטית",
    )
    parser.add_argument(
        "--min-shift-minutes",
        type=int,
        default=DEFAULT_MIN_SHIFT_MINUTES,
        help="שינוי מינימלי בשעות בסימולציה (דקות)",
    )
    parser.add_argument(
        "--max-shift-minutes",
        type=int,
        default=DEFAULT_MAX_SHIFT_MINUTES,
        help="שינוי מרבי בשעות בסימולציה (דקות)",
    )
    parser.add_argument(
        "--overtime-100-limit-minutes",
        type=int,
        default=DEFAULT_OVERTIME_100_LIMIT_MINUTES,
        help="גבול מדרגת מאה בדקות",
    )
    parser.add_argument(
        "--maximum-date-shift-days",
        type=int,
        default=DEFAULT_MAXIMUM_DATE_SHIFT_DAYS,
        help="היסט תאריך מרבי בסימולציה (ימים)",
    )
    parser.add_argument(
        "--simulation-date",
        type=str,
        help="תאריך הפקה להצגה בסימולציה (YYYY-MM-DD); ברירת המחדל אינה מציגה תאריך",
    )
    parser.add_argument(
        "--holiday-date",
        action="append",
        default=[],
        help="תאריך חג שבו יש לנקות שעות (YYYY-MM-DD); ניתן לציין מספר פעמים",
    )

    args = parser.parse_args()

    for warning in check_system_dependencies():
        print(warning, file=sys.stderr)

    if len(sys.argv) == 1:
        try:
            interactive_mode()
        except (AttendanceProjectError, ValueError, OSError) as exc:
            print(f"שגיאה: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    try:
        output_path = _resolve_output_path(
            args.output,
            args.output_dir,
            args.format,
            args.input,
        )
        process_attendance_pipeline(
            file_path=args.input,
            employee_id=args.employee_id,
            employee_name=args.employee_name,
            period=args.period,
            report_type=args.report_type.upper(),
            output_html_path=output_path,
            synthetic_simulation=args.synthetic_simulation,
            seed=args.seed,
            min_shift_minutes=args.min_shift_minutes,
            max_shift_minutes=args.max_shift_minutes,
            overtime_100_limit_minutes=args.overtime_100_limit_minutes,
            maximum_date_shift_days=args.maximum_date_shift_days,
            simulation_date=args.simulation_date,
            holiday_dates=tuple(args.holiday_date),
        )
    except (AttendanceProjectError, ValueError, OSError) as exc:
        print(f"שגיאה: {exc}", file=sys.stderr)
        sys.exit(1)
