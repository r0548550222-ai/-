"""ממשק Streamlit להעלאה, עיבוד והורדה של דוחות נוכחות."""

import re
import tempfile
from datetime import date
from pathlib import Path

import streamlit as st

from config import (
    DEFAULT_EMPLOYEE_ID,
    DEFAULT_EMPLOYEE_NAME,
    DEFAULT_MAXIMUM_ALLOWED_SHIFT_CHANGE_MINUTES,
    DEFAULT_MAXIMUM_DATE_SHIFT_DAYS,
    DEFAULT_MAX_SHIFT_MINUTES,
    DEFAULT_MIN_SHIFT_MINUTES,
    DEFAULT_REPORT_PERIOD,
    DEFAULT_SIMULATION_SEED,
    DEFAULT_OVERTIME_100_LIMIT_MINUTES,
)
from errors import AttendanceProjectError
from main import process_attendance_pipeline


st.set_page_config(page_title="מערכת עיבוד דוחות נוכחות", layout="wide")
st.title("מערכת ניהול ועיבוד דוחות נוכחות")
st.write("העלה דוח נוכחות בפורמט PDF כדי לחלץ את הנתונים ולהפיק טופס מעובד.")

uploaded_file = st.file_uploader(
    "בחר קובץ PDF של דוח נוכחות",
    type=["pdf"],
)

employee_id = st.text_input("מזהה עובד", value=DEFAULT_EMPLOYEE_ID)
employee_name = st.text_input("שם העובד", value=DEFAULT_EMPLOYEE_NAME)
report_period = st.text_input("תקופת הדוח", value=DEFAULT_REPORT_PERIOD)
report_type = st.selectbox("סוג הדוח", options=["AUTO", "TYPE_A", "TYPE_B"])
processing_mode = st.selectbox(
    "מצב עיבוד",
    options=["עיבוד רגיל", "תרגול — נתונים סינתטיים"],
)
synthetic_simulation = processing_mode == "תרגול — נתונים סינתטיים"

if synthetic_simulation:
    st.warning(
        "הפלט יסומן בכל עמוד כנתונים סינתטיים, וישתמש בזהות דוגמה במקום בפרטי העובד."
    )
    min_shift_minutes = st.number_input(
        "שינוי מינימלי בשעות (דקות)",
        min_value=0,
        max_value=DEFAULT_MAXIMUM_ALLOWED_SHIFT_CHANGE_MINUTES,
        value=DEFAULT_MIN_SHIFT_MINUTES,
    )
    max_shift_minutes = st.number_input(
        "שינוי מרבי בשעות (דקות)",
        min_value=0,
        max_value=DEFAULT_MAXIMUM_ALLOWED_SHIFT_CHANGE_MINUTES,
        value=DEFAULT_MAX_SHIFT_MINUTES,
    )
    overtime_100_limit_minutes = st.number_input(
        "גבול מדרגת 100% (דקות)",
        min_value=0,
        value=DEFAULT_OVERTIME_100_LIMIT_MINUTES,
    )
    maximum_date_shift_days = st.number_input(
        "היסט תאריך מרבי (ימים)",
        min_value=0,
        value=DEFAULT_MAXIMUM_DATE_SHIFT_DAYS,
    )
    simulation_seed = st.number_input(
        "seed לשחזור התרגול", min_value=0, value=DEFAULT_SIMULATION_SEED, step=1
    )
    include_simulation_date = st.checkbox("להציג תאריך הפקה")
    simulation_date = (
        st.date_input("תאריך הפקה", value=date.today()).isoformat()
        if include_simulation_date
        else None
    )
    holiday_text = st.text_input(
        "תאריכי חג ללא שעות בדוח (YYYY-MM-DD, מופרדים בפסיקים)"
    )
    holiday_dates = tuple(
        value.strip() for value in holiday_text.split(",") if value.strip()
    )

if uploaded_file is not None:
    st.info(f"הקובץ '{Path(uploaded_file.name).name}' נקלט בהצלחה.")

    button_label = (
        "הפק דוח תרגול מסומן"
        if synthetic_simulation
        else "הפעל עיבוד והפק טופס"
    )
    if st.button(button_label, type="primary"):
        safe_stem = re.sub(
            r"[^A-Za-z0-9._-]+",
            "_",
            Path(uploaded_file.name).stem,
        ).strip("._") or "attendance"

        try:
            with tempfile.TemporaryDirectory(prefix="attendance_") as temp_dir:
                temp_path = Path(temp_dir)
                input_path = temp_path / "input.pdf"
                output_prefix = "synthetic_practice" if synthetic_simulation else "report"
                output_path = temp_path / f"{output_prefix}_{safe_stem}.pdf"
                input_path.write_bytes(uploaded_file.getvalue())

                with st.spinner("מחלץ נתונים, מחשב שעות ומפיק PDF..."):
                    process_attendance_pipeline(
                        file_path=str(input_path),
                        employee_id=employee_id.strip() or DEFAULT_EMPLOYEE_ID,
                        employee_name=employee_name.strip() or DEFAULT_EMPLOYEE_NAME,
                        period=report_period.strip() or DEFAULT_REPORT_PERIOD,
                        report_type=report_type,
                        output_html_path=str(output_path),
                        synthetic_simulation=synthetic_simulation,
                        seed=(
                            int(simulation_seed)
                            if synthetic_simulation
                            else DEFAULT_SIMULATION_SEED
                        ),
                        min_shift_minutes=(
                            int(min_shift_minutes)
                            if synthetic_simulation
                            else DEFAULT_MIN_SHIFT_MINUTES
                        ),
                        max_shift_minutes=(
                            int(max_shift_minutes)
                            if synthetic_simulation
                            else DEFAULT_MAX_SHIFT_MINUTES
                        ),
                        overtime_100_limit_minutes=(
                            int(overtime_100_limit_minutes)
                            if synthetic_simulation
                            else DEFAULT_OVERTIME_100_LIMIT_MINUTES
                        ),
                        maximum_date_shift_days=(
                            int(maximum_date_shift_days)
                            if synthetic_simulation
                            else DEFAULT_MAXIMUM_DATE_SHIFT_DAYS
                        ),
                        simulation_date=(
                            simulation_date if synthetic_simulation else None
                        ),
                        holiday_dates=holiday_dates if synthetic_simulation else (),
                    )

                output_data = output_path.read_bytes()

            st.success(
                "דוח התרגול הסינתטי מוכן להורדה."
                if synthetic_simulation
                else "הטופס המעובד מוכן להורדה."
            )
            st.download_button(
                label="הורד טופס מעובד",
                data=output_data,
                file_name=f"{output_prefix}_{safe_stem}.pdf",
                mime="application/pdf",
            )
        except (AttendanceProjectError, ValueError, OSError) as exc:
            st.error(f"אירעה שגיאה במהלך עיבוד הנתונים: {exc}")
