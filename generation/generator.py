"""
יצירת קובצי HTML ו-PDF מתוך AttendanceReport.
"""

import html
import os
import re
from pathlib import Path
from typing import BinaryIO, Optional, Protocol, TextIO

from generation.layouts import ColumnLayout, ReportLayout, get_report_layout
from models import AttendanceReport, AttendanceRow


class Renderer(Protocol):
    """A format-specific writer that consumes an AttendanceReport."""

    def render(self, report: AttendanceReport, output_path: str) -> None:
        """Write a new file without changing the report."""


def to_visual_rtl(value: str) -> str:
    """הופכת מחרוזות עבריות לתצוגה חזותית עבור מנוע PDF ללא תמיכת BiDi."""
    pattern = (
        r"\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}|"
        r"\d+(?:[.,]\d+)?%?|[^\W\d_]+|[^\s]"
    )
    tokens = re.findall(pattern, value, re.UNICODE)
    return " ".join(
        token[::-1] if re.fullmatch(r"[^\W\d_]+", token, re.UNICODE) else token
        for token in reversed(tokens)
    )


def _time_text(minutes: Optional[int]) -> str:
    if minutes is None:
        return "—"
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _duration_text(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}" if minutes else "—"


def _hours_text(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _row_value(row: AttendanceRow, column: ColumnLayout) -> str:
    value = getattr(row, column.field_name)
    if column.value_format == "date":
        return value.isoformat()
    if column.value_format == "time":
        return _time_text(value)
    if column.value_format == "duration":
        return _duration_text(value)
    if column.value_format == "hours":
        return _hours_text(value)
    return value or "—"


def _row_values(row: AttendanceRow, layout: ReportLayout) -> list[str]:
    return [
        _row_value(row, column)
        for column in layout.columns
    ]


def _summary_values(
    report: AttendanceReport, layout: ReportLayout
) -> list[tuple[str, str]]:
    values = []
    for field in layout.summary_fields:
        value = getattr(report.summary, field.field_name)
        if field.value_format == "currency":
            formatted = f"{value:.2f}"
        elif field.value_format == "duration":
            formatted = _duration_text(value)
        elif field.value_format == "hours":
            formatted = _hours_text(value)
        elif field.value_format == "text":
            formatted = " | ".join(value) or "—"
        else:
            formatted = str(value)
        values.append((field.label, formatted))
    return values


def _prepare_output_path(output_path: str) -> Path:
    target = Path(output_path)
    if target.exists():
        raise FileExistsError(f"קובץ הפלט כבר קיים: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _open_new_text_file(target: Path) -> TextIO:
    try:
        return target.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise FileExistsError(f"קובץ הפלט כבר קיים: {target}") from exc


def _open_new_binary_file(target: Path) -> BinaryIO:
    try:
        return target.open("xb")
    except FileExistsError as exc:
        raise FileExistsError(f"קובץ הפלט כבר קיים: {target}") from exc


def _synthetic_label(report: AttendanceReport) -> str:
    return (
        "נתונים סינתטיים — לצורכי לימוד בלבד | "
        f"תאריך הפקה: {report.simulation_date or 'לא צוין'} | "
        f"seed: {report.simulation_seed if report.simulation_seed is not None else 'לא צוין'}"
    )


class HtmlRenderer:
    """מרנדר דוח נוכחות למסמך HTML בעברית ובכיווניות RTL."""

    def render(self, report: AttendanceReport, output_path: str) -> None:
        if not isinstance(report, AttendanceReport):
            raise TypeError("הרנדרר דורש אובייקט AttendanceReport.")

        layout = get_report_layout(report.report_type)
        target = _prepare_output_path(output_path)
        headers = "".join(
            f"<th>{html.escape(column.label)}</th>" for column in layout.columns
        )
        body_rows = []
        for row in report.rows:
            cells = "".join(
                f"<td>{html.escape(value)}</td>"
                for value in _row_values(row, layout)
            )
            body_rows.append(f"<tr>{cells}</tr>")

        summary_items = "".join(
            f"<p><strong>{html.escape(label)}:</strong> "
            f"{html.escape(value)}</p>"
            for label, value in _summary_values(report, layout)
        )
        summary_section = f"<h2>סיכום</h2>\n  {summary_items}"
        table_section = f"""<h2>רישום יומי</h2>
  <table>
    <thead><tr>{headers}</tr></thead>
    <tbody>{''.join(body_rows)}</tbody>
  </table>"""
        report_sections = (
            f"{summary_section}\n  {table_section}"
            if layout.summary_position == "before_table"
            else f"{table_section}\n  {summary_section}"
        )

        synthetic_banner = ""
        if report.is_synthetic:
            synthetic_banner = (
                f'<div class="synthetic-banner">{html.escape(_synthetic_label(report))}</div>'
            )
        body_class = " class=\"synthetic\"" if report.is_synthetic else ""
        title = (
            "תרגול — נתונים סינתטיים"
            if report.is_synthetic
            else layout.title
        )
        content = f"""<!doctype html>
<html lang="he" dir="rtl">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)} - {html.escape(report.report_period)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; direction: rtl; }}
    h1, h2 {{ text-align: right; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #bbb; padding: 0.45rem; text-align: right; }}
    th {{ background: #e8eef5; }}
    tbody tr:nth-child(even) {{ background: #f7f9fb; }}
    .metadata {{ line-height: 1.8; }}
    .synthetic-banner {{ background: #fff0f0; border: 2px solid #a00000;
      color: #8b0000; font-weight: bold; padding: 0.8rem; margin-bottom: 1rem; }}
    body.synthetic::before {{ content: "נתונים סינתטיים — לצורכי לימוד בלבד";
      position: fixed; top: 45%; left: 10%; transform: rotate(-24deg);
      color: rgba(160, 0, 0, 0.16); font-size: 2.4rem; font-weight: bold;
      z-index: 10; pointer-events: none; }}
    @media print {{ .synthetic-banner {{ position: fixed; top: 0; right: 0; left: 0;
      z-index: 20; }} body.synthetic {{ padding-top: 4rem; }} }}
  </style>
</head>
<body{body_class}>
  {synthetic_banner}
  <h1>{html.escape(title)}</h1>
  <div class="metadata">
    <strong>שם העובד:</strong> {html.escape(report.employee_name)}<br>
    <strong>מזהה עובד:</strong> {html.escape(report.employee_id)}<br>
    <strong>תקופה:</strong> {html.escape(report.report_period)}<br>
    <strong>סוג דוח:</strong> {html.escape(report.report_type)}
  </div>
  {report_sections}
</body>
</html>
"""
        with _open_new_text_file(target) as output_file:
            output_file.write(content)


class PdfRenderer:
    """מרנדר דוח נוכחות ל-PDF בעזרת ReportLab וגופן עברי זמין."""

    def _font_path(self) -> str:
        configured = os.environ.get("ATTENDANCE_FONT")
        candidates = [configured] if configured else []
        candidates.extend([
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/Library/Fonts/Arial.ttf",
        ])
        for candidate in candidates:
            if candidate and os.path.isfile(candidate):
                return candidate
        raise RuntimeError(
            "לא נמצא גופן TTF התומך בעברית. התקן Arial או DejaVu Sans, "
            "או הגדר את ATTENDANCE_FONT לנתיב הגופן."
        )

    @staticmethod
    def _paragraph_text(value: str) -> str:
        return html.escape(to_visual_rtl(value))

    def render(self, report: AttendanceReport, output_path: str) -> None:
        if not isinstance(report, AttendanceReport):
            raise TypeError("הרנדרר דורש אובייקט AttendanceReport.")

        layout = get_report_layout(report.report_type)
        target = _prepare_output_path(output_path)
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.enums import TA_RIGHT
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.platypus import (
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )
        except ImportError as exc:
            raise RuntimeError(
                "יצירת PDF דורשת את חבילת reportlab. התקן את התלויות מהקובץ requirements.txt."
            ) from exc

        font_path = self._font_path()
        font_name = "AttendanceHebrew"
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, font_path))

        base_style = getSampleStyleSheet()["Normal"]
        body_style = ParagraphStyle(
            "AttendanceBody",
            parent=base_style,
            fontName=font_name,
            fontSize=8,
            leading=11,
            alignment=TA_RIGHT,
        )
        title_style = ParagraphStyle(
            "AttendanceTitle",
            parent=body_style,
            fontSize=16,
            leading=20,
            spaceAfter=8,
        )
        heading_style = ParagraphStyle(
            "AttendanceHeading",
            parent=body_style,
            fontSize=12,
            leading=16,
            spaceBefore=8,
            spaceAfter=5,
        )
        synthetic_style = ParagraphStyle(
            "AttendanceSynthetic",
            parent=body_style,
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#8b0000"),
            backColor=colors.HexColor("#fff0f0"),
            borderColor=colors.HexColor("#a00000"),
            borderWidth=1.5,
            borderPadding=6,
            spaceAfter=8,
        )

        title = (
            "תרגול — נתונים סינתטיים"
            if report.is_synthetic
            else layout.title
        )
        story = []
        if report.is_synthetic:
            story.append(
                Paragraph(self._paragraph_text(_synthetic_label(report)), synthetic_style)
            )
        story.extend([
            Paragraph(self._paragraph_text(title), title_style),
            Paragraph(
                self._paragraph_text(
                    f"שם העובד: {report.employee_name} | "
                    f"מזהה עובד: {report.employee_id} | "
                    f"תקופה: {report.report_period} | "
                    f"סוג דוח: {report.report_type}"
                ),
                body_style,
            ),
            Spacer(1, 10),
        ])

        # ReportLab מציב את העמודה הראשונה משמאל, לכן הופכים את סדר העמודות.
        table_data = [
            [
                Paragraph(self._paragraph_text(column.label), body_style)
                for column in reversed(layout.columns)
            ]
        ]
        table_data.extend(
            [
                Paragraph(self._paragraph_text(value), body_style)
                for value in reversed(_row_values(row, layout))
            ]
            for row in report.rows
        )

        table = Table(table_data, repeatRows=1, hAlign="RIGHT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef5")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#172b4d")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#aab4c0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.white,
                colors.HexColor("#f7f9fb"),
            ]),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        table_section = [
            Paragraph(self._paragraph_text("רישום יומי"), heading_style),
            table,
        ]
        summary_section = [
            Paragraph(self._paragraph_text("סיכום"), heading_style),
            *(
                Paragraph(
                    self._paragraph_text(f"{label}: {value}"),
                    body_style,
                )
                for label, value in _summary_values(report, layout)
            ),
        ]
        if layout.summary_position == "before_table":
            story.extend(summary_section)
            story.append(Spacer(1, 10))
            story.extend(table_section)
        else:
            story.extend(table_section)
            story.append(Spacer(1, 10))
            story.extend(summary_section)

        if report.is_synthetic:
            watermark_text = to_visual_rtl(_synthetic_label(report))

            def draw_synthetic_mark(canvas, page_document) -> None:
                canvas.saveState()
                page_width, page_height = page_document.pagesize
                canvas.setFont(font_name, 8)
                canvas.setFillColor(colors.HexColor("#8b0000"))
                canvas.drawRightString(
                    page_width - 24, page_height - 18, watermark_text
                )
                canvas.setFillColor(colors.Color(0.65, 0.0, 0.0, alpha=0.13))
                canvas.translate(page_width / 2, page_height / 2)
                canvas.rotate(25)
                canvas.setFont(font_name, 20)
                canvas.drawCentredString(0, 0, watermark_text)
                canvas.restoreState()

        output_file = _open_new_binary_file(target)
        try:
            document = SimpleDocTemplate(
                output_file,
                pagesize=landscape(A4),
                rightMargin=24,
                leftMargin=24,
                topMargin=44 if report.is_synthetic else 24,
                bottomMargin=24,
            )
            if report.is_synthetic:
                document.build(
                    story,
                    onFirstPage=draw_synthetic_mark,
                    onLaterPages=draw_synthetic_mark,
                )
            else:
                document.build(story)
        except Exception:
            output_file.close()
            target.unlink()
            raise
        else:
            output_file.close()

