"""
tests/test_transformer.py
-------------------------
בדיקות יחידה עבור שכבת הטרנספורמציה והלוגיקה העסקית (Transformation Layer).
מאמת את אסטרטגיות העיבוד, אכיפת אינווריאנטים, דטרמיניזם ואי-שינויות (Immutability).
"""

from datetime import date
from dataclasses import replace
from types import SimpleNamespace

import pytest

from config import (
    DEFAULT_MAXIMUM_DATE_SHIFT_DAYS,
    DEFAULT_MAX_SHIFT_MINUTES,
    DEFAULT_MIN_SHIFT_MINUTES,
    DEFAULT_OVERTIME_100_LIMIT_MINUTES,
)
from models import AttendanceRow, AttendanceReport, ReportSummary
from transformation.transformer import (
    InvalidTransformedRowError,
    TransformationRules,
    TypeATransformationStrategy,
    TypeBTransformationStrategy,
    validate_row,
)


def test_type_a_transformation_and_immutability():
    """
    בודק את אסטרטגיית הטרנספורמציה לסוג A:
    - וידוא אי-שינויות (Immutability): האובייקט המקורי נשאר ללא שינוי.
    - חישוב נכון של שעות עבודה והטורים הייעודיים.
    """
    original_row = AttendanceRow(
        work_date=date(2026, 10, 1),
        day_of_week="רביעי",
        entry_time=8 * 60,
        exit_time=17 * 60,
        break_duration_minutes=60,
    )

    report = AttendanceReport(
        employee_id="001",
        employee_name="ישראל ישראלי",
        report_period="2026-10",
        report_type="TYPE_A",
        rows=(original_row,)
    )

    strategy = TypeATransformationStrategy()
    transformed_report = strategy.transform_report(
        report, rules=TransformationRules(), seed=42
    )

    # וידוא ששכבת המקור לא נפגעה (Immutability)
    assert original_row.total_work_minutes == 0
    assert original_row.exit_time == 17 * 60

    # וידוא שנוצר אובייקט חדש עם חישובים תקינים
    new_row = transformed_report.rows[0]
    assert transformed_report is not report
    assert transformed_report.rows is not report.rows
    assert new_row.total_work_minutes == 480  # (17:00 - 08:00) - 60 דקות הפסקה
    assert isinstance(transformed_report.summary, ReportSummary)
    assert transformed_report.summary.total_work_days == 1


def test_type_b_transformation_determinism():
    """
    בודק דטרמיניזם באסטרטגיית סוג B:
    וידוא ששימוש באותו seed מניב תוצאות זהות ועקביות בשתי הרצות עוקבות.
    """
    row = AttendanceRow(
        work_date=date(2026, 10, 2),
        day_of_week="חמישי",
        entry_time=9 * 60,
        exit_time=18 * 60,
        break_duration_minutes=30
    )

    report = AttendanceReport(
        employee_id="002",
        employee_name="שרה כהן",
        report_period="2026-10",
        report_type="TYPE_B",
        rows=(row,)
    )

    strategy = TypeBTransformationStrategy()

    # הרצה ראשונה ושנייה עם אותו seed
    run_1 = strategy.transform_report(report, rules=TransformationRules(), seed=100)
    run_2 = strategy.transform_report(report, rules=TransformationRules(), seed=100)

    assert run_1.rows[0].total_work_minutes == run_2.rows[0].total_work_minutes
    assert run_1.summary.total_work_minutes == run_2.summary.total_work_minutes


def test_row_seed_is_stable_when_another_row_is_added_before_it():
    row = AttendanceRow(
        work_date=date(2026, 10, 5),
        day_of_week="שני",
        entry_time=8 * 60,
        exit_time=17 * 60,
        break_duration_minutes=30,
    )
    earlier_row = AttendanceRow(
        work_date=date(2026, 10, 4),
        day_of_week="ראשון",
        entry_time=9 * 60,
        exit_time=18 * 60,
        break_duration_minutes=30,
    )
    strategy = TypeBTransformationStrategy()
    rules = TransformationRules(simulation=True)

    baseline = strategy.transform_report(
        AttendanceReport(
            employee_id="1",
            employee_name="בדיקה",
            report_period="2026-10",
            report_type="TYPE_B",
            rows=(row,),
        ),
        rules=rules,
        seed=42,
    )
    repeated = strategy.transform_report(
        AttendanceReport(
            employee_id="1",
            employee_name="בדיקה",
            report_period="2026-10",
            report_type="TYPE_B",
            rows=(row,),
        ),
        rules=rules,
        seed=42,
    )
    with_preceding_row = strategy.transform_report(
        AttendanceReport(
            employee_id="1",
            employee_name="בדיקה",
            report_period="2026-10",
            report_type="TYPE_B",
            rows=(earlier_row, row),
        ),
        rules=rules,
        seed=42,
    )

    assert baseline.rows[0] == repeated.rows[0]
    assert baseline.rows[0] == with_preceding_row.rows[1]


def test_summary_recalculates_derived_fields_and_preserves_other_values():
    row = AttendanceRow(
        work_date=date(2026, 10, 5),
        day_of_week="שני",
        entry_time=8 * 60,
        exit_time=17 * 60,
        break_duration_minutes=60,
    )
    summary = ReportSummary(
        total_work_days=7,
        total_absent_days=2,
        total_work_minutes=300,
        total_100_minutes=100,
        total_125_minutes=100,
        total_150_minutes=100,
        total_saturday_minutes=30,
        hourly_rate=20,
        total_payment=100,
        total_travel_days=3,
        travel_expenses=45.5,
        bonus_amount=12.5,
        summary_notes=("keep this note",),
    )
    report = AttendanceReport(
        employee_id="1",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type="TYPE_A",
        rows=(row,),
        summary=summary,
    )

    transformed = TypeATransformationStrategy().transform_report(
        report, rules=TransformationRules(), seed=42
    )

    assert transformed.summary.total_work_days == 1
    assert transformed.summary.total_absent_days == 0
    assert transformed.summary.total_work_minutes == 480
    assert transformed.summary.total_100_minutes == 480
    assert transformed.summary.total_125_minutes == 0
    assert transformed.summary.total_150_minutes == 0
    assert transformed.summary.total_payment == 160
    assert transformed.summary.hourly_rate == 20
    assert transformed.summary.total_travel_days == 3
    assert transformed.summary.travel_expenses == 45.5
    assert transformed.summary.bonus_amount == 12.5
    assert transformed.summary.summary_notes == ("keep this note",)
    assert transformed.summary.total_work_minutes == sum(
        row.total_work_minutes for row in transformed.rows
    )
    assert transformed.summary.total_100_minutes == sum(
        row.overtime_100_minutes for row in transformed.rows
    )
    assert transformed.summary.total_125_minutes == sum(
        row.overtime_125_minutes for row in transformed.rows
    )
    assert transformed.summary.total_150_minutes == sum(
        row.overtime_150_minutes for row in transformed.rows
    )


def test_changed_hours_with_existing_payment_require_hourly_rate():
    row = AttendanceRow(
        work_date=date(2026, 10, 5),
        day_of_week="שני",
        entry_time=8 * 60,
        exit_time=17 * 60,
        break_duration_minutes=60,
    )
    report = AttendanceReport(
        employee_id="1",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type="TYPE_A",
        rows=(row,),
        summary=ReportSummary(total_work_minutes=300, total_payment=100),
    )

    with pytest.raises(ValueError, match="valid hourly_rate is required"):
        TypeATransformationStrategy().transform_report(
            report, rules=TransformationRules(), seed=42
        )


def test_rules_apply_custom_work_and_overtime_limits():
    row = AttendanceRow(
        work_date=date(2026, 10, 5),
        day_of_week="שני",
        entry_time=8 * 60,
        exit_time=18 * 60,
    )
    report = AttendanceReport(
        employee_id="1",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type="TYPE_B",
        rows=(row,),
    )
    rules = TransformationRules(
        overtime_100_limit_minutes=360,
        overtime_125_limit_minutes=60,
        maximum_simulated_work_minutes=600,
    )

    transformed = TypeBTransformationStrategy().transform_report(
        report, rules=rules, seed=42
    )
    transformed_row = transformed.rows[0]

    assert transformed_row.total_work_minutes == 600
    assert transformed_row.overtime_100_minutes == 360
    assert transformed_row.overtime_125_minutes == 60
    assert transformed_row.overtime_150_minutes == 180
    assert transformed.summary.total_100_minutes == 360
    assert (
        transformed_row.overtime_100_minutes
        + transformed_row.overtime_125_minutes
        + transformed_row.overtime_150_minutes
        == transformed_row.total_work_minutes
    )


@pytest.mark.parametrize(
    ("strategy", "report_type"),
    [
        (TypeATransformationStrategy(), "TYPE_A"),
        (TypeBTransformationStrategy(), "TYPE_B"),
    ],
)
def test_common_validator_runs_for_both_report_types(strategy, report_type):
    row = AttendanceRow(
        work_date=date(2026, 10, 5),
        day_of_week="שני",
        entry_time=8 * 60,
        exit_time=18 * 60,
    )
    report = AttendanceReport(
        employee_id="1",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type=report_type,
        rows=(row,),
    )

    with pytest.raises(InvalidTransformedRowError, match="exceeds the configured"):
        strategy.transform_report(
            report,
            rules=TransformationRules(
                maximum_work_minutes=500,
                maximum_simulated_work_minutes=500,
            ),
            seed=42,
        )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"entry_time": None}, "both be present or absent"),
        ({"total_work_minutes": 1000}, "total work exceeds"),
        ({"break_duration_minutes": 181}, "break duration exceeds"),
        ({"overtime_100_minutes": 100}, "overtime tiers do not sum"),
    ],
)
def test_validate_row_rejects_each_invalid_invariant(changes, message):
    row = AttendanceRow(
        work_date=date(2026, 10, 5),
        day_of_week="שני",
        entry_time=8 * 60,
        exit_time=16 * 60,
        total_work_minutes=450,
        break_duration_minutes=30,
        overtime_100_minutes=450,
    )
    invalid_row = replace(row, **changes)

    with pytest.raises(InvalidTransformedRowError, match=message):
        validate_row(invalid_row, TransformationRules())


def test_validate_row_rejects_clock_outside_configured_range():
    row = AttendanceRow(
        work_date=date(2026, 10, 5),
        day_of_week="שני",
        entry_time=8 * 60,
        exit_time=16 * 60,
        total_work_minutes=450,
        break_duration_minutes=30,
        overtime_100_minutes=450,
    )

    with pytest.raises(InvalidTransformedRowError, match="clock range"):
        validate_row(
            row,
            TransformationRules(maximum_clock_minute=900),
        )


def test_validate_row_rejects_exit_outside_allowed_shift_duration():
    row = AttendanceRow(
        work_date=date(2026, 10, 5),
        day_of_week="שני",
        entry_time=10 * 60,
        exit_time=9 * 60,
        total_work_minutes=60,
        overtime_100_minutes=60,
    )

    with pytest.raises(InvalidTransformedRowError, match="exit time is invalid"):
        validate_row(row, TransformationRules())


def test_validate_row_accepts_valid_overnight_shift():
    row = AttendanceRow(
        work_date=date(2026, 10, 5),
        day_of_week="שני",
        entry_time=22 * 60,
        exit_time=6 * 60,
        total_work_minutes=450,
        break_duration_minutes=30,
        overtime_100_minutes=450,
    )

    validate_row(row, TransformationRules())


def test_validate_row_rejects_work_without_clock_times():
    row = AttendanceRow(
        work_date=date(2026, 10, 5),
        day_of_week="שני",
        total_work_minutes=60,
        overtime_100_minutes=60,
    )

    with pytest.raises(InvalidTransformedRowError, match="without clock times"):
        validate_row(row, TransformationRules())


def test_validate_row_rejects_negative_minute_values():
    row = SimpleNamespace(
        work_date=date(2026, 10, 5),
        entry_time=480,
        exit_time=960,
        total_work_minutes=-1,
        break_duration_minutes=30,
        overtime_100_minutes=0,
        overtime_125_minutes=0,
        overtime_150_minutes=0,
        saturday_minutes=0,
    )

    with pytest.raises(InvalidTransformedRowError, match="non-negative integer"):
        validate_row(row, TransformationRules())  # type: ignore[arg-type]


def test_validate_row_checks_overtime_tiers_on_saturday_rows():
    row = AttendanceRow(
        work_date=date(2026, 10, 3),
        day_of_week="שבת",
        entry_time=8 * 60,
        exit_time=16 * 60,
        total_work_minutes=450,
        break_duration_minutes=30,
    )

    with pytest.raises(InvalidTransformedRowError, match="overtime tiers do not sum"):
        validate_row(row, TransformationRules())


def test_validate_row_allows_recorded_work_on_protected_dates():
    row = AttendanceRow(
        work_date=date(2026, 10, 3),
        day_of_week="שבת",
        entry_time=8 * 60,
        exit_time=16 * 60,
        total_work_minutes=450,
        overtime_100_minutes=450,
    )

    validate_row(row, TransformationRules())


def test_transformation_rules_use_configured_shift_defaults():
    rules = TransformationRules()

    assert rules.min_shift_minutes == DEFAULT_MIN_SHIFT_MINUTES == 20
    assert rules.max_shift_minutes == DEFAULT_MAX_SHIFT_MINUTES == 30
    assert rules.overtime_100_limit_minutes == DEFAULT_OVERTIME_100_LIMIT_MINUTES
    assert rules.maximum_date_shift_days == DEFAULT_MAXIMUM_DATE_SHIFT_DAYS


def test_default_overtime_tier_uses_configured_eight_hour_threshold():
    row = AttendanceRow(
        work_date=date(2026, 10, 5),
        day_of_week="שני",
        entry_time=8 * 60,
        exit_time=18 * 60,
    )
    transformed = TypeATransformationStrategy().transform_report(
        AttendanceReport(
            employee_id="1",
            employee_name="בדיקה",
            report_period="2026-10",
            report_type="TYPE_A",
            rows=(row,),
        ),
        rules=TransformationRules(),
        seed=42,
    )

    assert transformed.rows[0].overtime_100_minutes == DEFAULT_OVERTIME_100_LIMIT_MINUTES
    assert transformed.rows[0].overtime_125_minutes == 120
    assert transformed.rows[0].total_work_minutes == 600


@pytest.mark.parametrize(
    ("work_date", "holiday_dates"),
    [
        (date(2026, 10, 3), frozenset()),
        (date(2026, 10, 5), frozenset({date(2026, 10, 5)})),
    ],
)
@pytest.mark.parametrize("simulation", [False, True])
def test_protected_dates_are_cleared_only_in_synthetic_simulation(
    work_date, holiday_dates, simulation
):
    row = AttendanceRow(
        work_date=work_date,
        day_of_week="שבת" if work_date.weekday() == 5 else "שני",
        entry_time=8 * 60,
        exit_time=16 * 60,
        total_work_minutes=450,
        break_duration_minutes=30,
        overtime_100_minutes=450,
        saturday_minutes=450 if work_date.weekday() == 5 else 0,
    )
    report = AttendanceReport(
        employee_id="1",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type="TYPE_A",
        rows=(row,),
        summary=ReportSummary(
            total_work_days=1,
            total_work_minutes=450,
            total_100_minutes=450,
            total_saturday_minutes=450 if work_date.weekday() == 5 else 0,
        ),
    )

    transformed = TypeATransformationStrategy().transform_report(
        report,
        rules=TransformationRules(
            simulation=simulation,
            min_shift_minutes=30,
            max_shift_minutes=30,
            holiday_dates=holiday_dates,
        ),
        seed=42,
    )

    if simulation:
        assert transformed.rows[0].work_date != row.work_date
    else:
        assert transformed.rows[0].work_date == row.work_date
    if simulation:
        assert transformed.rows[0].entry_time is None
        assert transformed.rows[0].exit_time is None
        assert transformed.rows[0].total_work_minutes == 0
        assert transformed.rows[0].break_duration_minutes == 0
        assert transformed.rows[0].overtime_100_minutes == 0
        assert transformed.rows[0].overtime_125_minutes == 0
        assert transformed.rows[0].overtime_150_minutes == 0
        assert transformed.rows[0].saturday_minutes == 0
        assert transformed.summary.total_work_minutes == 0
        assert transformed.summary.total_100_minutes == 0
        assert transformed.summary.total_125_minutes == 0
        assert transformed.summary.total_150_minutes == 0
        assert transformed.summary.total_saturday_minutes == 0
        assert transformed.summary.total_work_days == 0
        assert transformed.summary.total_absent_days == 0
    else:
        assert transformed.rows[0].entry_time == 8 * 60
        assert transformed.rows[0].exit_time == 16 * 60
        assert transformed.rows[0].total_work_minutes == 450
        assert transformed.rows[0].saturday_minutes == (
            450 if work_date.weekday() == 5 else 0
        )
        assert transformed.summary.total_work_minutes == 450
        assert transformed.summary.total_work_days == 1
        assert transformed.summary.total_absent_days == 0


def test_simulation_clears_stale_hours_on_unworked_saturday():
    row = AttendanceRow(
        work_date=date(2026, 10, 3),
        day_of_week="שבת",
        total_work_minutes=300,
        overtime_100_minutes=300,
        saturday_minutes=300,
    )
    report = AttendanceReport(
        employee_id="1",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type="TYPE_B",
        rows=(row,),
    )

    transformed = TypeBTransformationStrategy().transform_report(
        report,
        rules=TransformationRules(simulation=True),
        seed=42,
    )

    assert transformed.rows[0].total_work_minutes == 0
    assert transformed.rows[0].saturday_minutes == 0
    assert transformed.summary.total_work_minutes == 0
    assert transformed.summary.total_saturday_minutes == 0


def test_simulation_clears_work_on_holiday_date():
    row = AttendanceRow(
        work_date=date(2026, 10, 5),
        day_of_week="שני",
        entry_time=8 * 60,
        exit_time=16 * 60,
        total_work_minutes=480,
        break_duration_minutes=30,
        overtime_100_minutes=480,
    )
    report = AttendanceReport(
        employee_id="1",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type="TYPE_B",
        rows=(row,),
    )

    transformed = TypeBTransformationStrategy().transform_report(
        report,
        rules=TransformationRules(
            simulation=True,
            maximum_date_shift_days=0,
            holiday_dates=frozenset({row.work_date}),
        ),
        seed=42,
    )

    assert transformed.rows[0].entry_time is None
    assert transformed.rows[0].exit_time is None
    assert transformed.rows[0].total_work_minutes == 0
    assert transformed.rows[0].break_duration_minutes == 0
    assert transformed.rows[0].overtime_100_minutes == 0
    assert transformed.summary.total_work_minutes == 0
    assert transformed.summary.total_absent_days == 0


def test_simulation_shifts_source_holiday_but_keeps_it_without_work():
    holiday = date(2026, 10, 5)
    row = AttendanceRow(
        work_date=holiday,
        day_of_week="שני",
        entry_time=8 * 60,
        exit_time=16 * 60,
        total_work_minutes=450,
        break_duration_minutes=30,
        overtime_100_minutes=450,
    )
    report = AttendanceReport(
        employee_id="1",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type="TYPE_B",
        rows=(row,),
    )

    transformed = TypeBTransformationStrategy().transform_report(
        report,
        rules=TransformationRules(
            simulation=True,
            min_shift_minutes=0,
            max_shift_minutes=0,
            holiday_dates=frozenset({holiday}),
        ),
        seed=42,
    )

    shifted = transformed.rows[0]
    assert shifted.work_date != holiday
    assert shifted.entry_time is None
    assert shifted.exit_time is None
    assert shifted.total_work_minutes == 0
    assert shifted.break_duration_minutes == 0
    assert transformed.summary.total_work_minutes == 0
    assert transformed.summary.total_100_minutes == 0
    assert report.rows[0] == row


@pytest.mark.parametrize(
    ("source_date", "protected_date", "holiday_dates"),
    [
        (date(2026, 10, 2), date(2026, 10, 3), frozenset()),
        (
            date(2026, 10, 5),
            date(2026, 10, 6),
            frozenset({date(2026, 10, 6)}),
        ),
    ],
)
def test_simulation_clears_rows_moved_to_saturday_or_holiday(
    source_date, protected_date, holiday_dates, monkeypatch
):
    class FixedDateOffset:
        def __init__(self, seed):
            self.seed = seed

        def randint(self, minimum, maximum):
            return minimum if minimum <= maximum else maximum

        def choice(self, values):
            return values[-1]

    monkeypatch.setattr("transformation.transformer.random.Random", FixedDateOffset)
    row = AttendanceRow(
        work_date=source_date,
        day_of_week=(
            "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"
        )[source_date.weekday()],
        entry_time=8 * 60,
        exit_time=16 * 60,
        total_work_minutes=450,
        break_duration_minutes=30,
        overtime_100_minutes=450,
        saturday_minutes=25,
    )
    report = AttendanceReport(
        employee_id="1",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type="TYPE_A",
        rows=(row,),
        summary=ReportSummary(
            total_work_days=1,
            total_work_minutes=450,
            total_100_minutes=450,
            total_saturday_minutes=25,
        ),
    )

    transformed = TypeATransformationStrategy().transform_report(
        report,
        rules=TransformationRules(
            simulation=True,
            min_shift_minutes=0,
            max_shift_minutes=0,
            holiday_dates=holiday_dates,
        ),
        seed=42,
    )

    shifted_row = transformed.rows[0]
    assert shifted_row.work_date == protected_date
    assert shifted_row.day_of_week == (
        "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"
    )[protected_date.weekday()]
    assert shifted_row.entry_time is None
    assert shifted_row.exit_time is None
    assert shifted_row.total_work_minutes == 0
    assert shifted_row.break_duration_minutes == 0
    assert shifted_row.overtime_100_minutes == 0
    assert shifted_row.overtime_125_minutes == 0
    assert shifted_row.overtime_150_minutes == 0
    assert shifted_row.saturday_minutes == 0
    assert transformed.summary.total_work_minutes == 0
    assert transformed.summary.total_100_minutes == 0
    assert transformed.summary.total_saturday_minutes == 0


def test_simulation_changes_hours_on_a_regular_workday():
    row = AttendanceRow(
        work_date=date(2026, 10, 5),
        day_of_week="שני",
        entry_time=8 * 60,
        exit_time=17 * 60,
        break_duration_minutes=30,
    )
    report = AttendanceReport(
        employee_id="1",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type="TYPE_A",
        rows=(row,),
    )

    transformed = TypeATransformationStrategy().transform_report(
        report,
        rules=TransformationRules(
            simulation=True,
            min_shift_minutes=30,
            max_shift_minutes=30,
        ),
        seed=42,
    )

    assert transformed.rows[0].entry_time != row.entry_time
    assert transformed.rows[0].total_work_minutes != 0


@pytest.mark.parametrize(
    ("strategy", "report_type"),
    [
        (TypeATransformationStrategy(), "TYPE_A"),
        (TypeBTransformationStrategy(), "TYPE_B"),
    ],
)
def test_invalid_exit_is_reported_instead_of_repaired(strategy, report_type):
    invalid_row = AttendanceRow(
        work_date=date(2026, 10, 5),
        day_of_week="שני",
        entry_time=10 * 60,
        exit_time=9 * 60,
    )
    report = AttendanceReport(
        employee_id="003",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type=report_type,
        rows=(invalid_row,),
    )

    with pytest.raises(InvalidTransformedRowError, match="exit time is invalid"):
        strategy.transform_report(report, rules=TransformationRules(), seed=42)


def test_overnight_shift_is_preserved_when_reported_hours_match():
    for strategy, report_type in (
        (TypeATransformationStrategy(), "TYPE_A"),
        (TypeBTransformationStrategy(), "TYPE_B"),
    ):
        row = AttendanceRow(
            work_date=date(2026, 10, 5),
            day_of_week="שני",
            entry_time=22 * 60,
            exit_time=6 * 60,
            total_work_minutes=450,
            break_duration_minutes=30,
        )
        report = AttendanceReport(
            employee_id="004",
            employee_name="בדיקת לילה",
            report_period="2026-10",
            report_type=report_type,
            rows=(row,),
        )

        transformed = strategy.transform_report(
            report, rules=TransformationRules(), seed=42
        )

        assert transformed.rows[0].entry_time == 22 * 60
        assert transformed.rows[0].exit_time == 6 * 60
        assert transformed.rows[0].total_work_minutes == 450


def test_type_a_uses_break_duration_minutes_and_fills_100_percent_hours():
    row = AttendanceRow(
        work_date=date(2023, 2, 1),
        day_of_week="רביעי",
        entry_time=8 * 60,
        exit_time=16 * 60,
        break_duration_minutes=30,
    )
    report = AttendanceReport(
        employee_id="1", employee_name="בדיקה", report_period="2023-02",
        report_type="TYPE_A", rows=(row,))

    result = TypeATransformationStrategy().transform_report(
        report, rules=TransformationRules(), seed=1
    )

    assert result.rows[0].total_work_minutes == 450
    assert result.rows[0].overtime_100_minutes == 450
    assert result.summary.total_100_minutes == 450


def test_midnight_entry_is_transformed_as_a_valid_clock_time():
    row = AttendanceRow(
        work_date=date(2026, 10, 1),
        day_of_week="חמישי",
        entry_time=0,
        exit_time=8 * 60,
    )
    report = AttendanceReport(
        employee_id="1",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type="TYPE_B",
        rows=(row,),
    )

    result = TypeBTransformationStrategy().transform_report(
        report, rules=TransformationRules(), seed=1
    )

    assert result.rows[0].entry_time == 0
    assert result.rows[0].total_work_minutes == 8 * 60
    assert result.summary.total_work_days == 1
    assert result.summary.total_absent_days == 0


def test_synthetic_simulation_clears_hours_on_saturday_deterministically():
    source_row = AttendanceRow(
        work_date=date(2026, 10, 3),
        day_of_week="שני",
        entry_time=22 * 60,
        exit_time=6 * 60,
        total_work_minutes=450,
        break_duration_minutes=30,
    )
    report = AttendanceReport(
        employee_id="private-id",
        employee_name="private name",
        report_period="2026-10",
        report_type="TYPE_A",
        rows=(source_row,),
    )
    rules = TransformationRules(
        simulation=True,
        min_shift_minutes=30,
        max_shift_minutes=30,
    )

    strategy = TypeATransformationStrategy()
    first = strategy.transform_report(report, rules=rules, seed=42)
    repeat = strategy.transform_report(report, rules=rules, seed=42)
    row = first.rows[0]

    assert row.work_date != source_row.work_date
    assert row.day_of_week == (
        "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"
    )[row.work_date.weekday()]
    assert row == repeat.rows[0]
    assert row.entry_time is None
    assert row.exit_time is None
    assert row.total_work_minutes == 0
    assert row.break_duration_minutes == 0
    assert row.overtime_100_minutes == 0
    assert row.overtime_125_minutes == 0
    assert row.overtime_150_minutes == 0
    assert row.saturday_minutes == 0
    assert first.summary.total_work_minutes == 0
    assert first.summary.total_saturday_minutes == 0
    assert source_row.entry_time == 22 * 60
    assert source_row.total_work_minutes == 450


def test_synthetic_simulation_shifts_dates_and_preserves_rows_deterministically():
    source_rows = [
        AttendanceRow(
            work_date=date(2026, 10, 1),
            day_of_week="חמישי",
            entry_time=8 * 60,
            exit_time=16 * 60,
        ),
        AttendanceRow(
            work_date=date(2026, 10, 31),
            day_of_week="שבת",
            entry_time=8 * 60,
            exit_time=16 * 60,
            total_work_minutes=480,
            overtime_100_minutes=480,
            saturday_minutes=480,
        ),
    ]
    report = AttendanceReport(
        employee_id="1",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type="TYPE_A",
        rows=tuple(source_rows),
    )
    rules = TransformationRules(
        simulation=True,
        min_shift_minutes=0,
        max_shift_minutes=0,
    )

    strategy = TypeATransformationStrategy()
    first = strategy.transform_report(report, rules=rules, seed=17)
    repeat = strategy.transform_report(report, rules=rules, seed=17)

    assert len(first.rows) == len(source_rows)
    assert [row.work_date for row in first.rows] == [
        row.work_date for row in repeat.rows
    ]
    offsets = [
        (transformed.work_date - original.work_date).days
        for original, transformed in zip(source_rows, first.rows)
    ]
    assert offsets[0] != 0
    assert offsets[1] == offsets[0]
    assert first.rows[1].work_date != source_rows[1].work_date
    assert first.rows[1].entry_time is None
    assert first.rows[1].exit_time is None
    assert first.rows[1].total_work_minutes == 0
    assert first.rows[1].break_duration_minutes == 0
    assert first.rows[1].overtime_100_minutes == 0
    assert first.rows[1].overtime_125_minutes == 0
    assert first.rows[1].overtime_150_minutes == 0
    assert first.rows[1].saturday_minutes == 0
    assert first.summary.total_saturday_minutes == 0
    assert [row.report_type for row in (first, repeat)] == ["TYPE_A", "TYPE_A"]
    assert all(
        row.day_of_week
        == ("שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון")[
            row.work_date.weekday()
        ]
        for row in first.rows
    )


def test_synthetic_simulation_rejects_invalid_shift_range():
    with pytest.raises(ValueError, match="טווח שינוי"):
        TransformationRules(
            simulation=True,
            min_shift_minutes=61,
            max_shift_minutes=60,
        )


def test_transformation_rules_validate_business_thresholds():
    with pytest.raises(ValueError, match="טווח שעות"):
        TransformationRules(
            minimum_simulated_work_minutes=700,
            maximum_simulated_work_minutes=600,
        )
    with pytest.raises(ValueError, match="טווח דקות השעון"):
        TransformationRules(minimum_clock_minute=100, maximum_clock_minute=99)
    with pytest.raises(ValueError, match="גבולות מדרגות"):
        TransformationRules(overtime_125_limit_minutes=-1)


def test_custom_day_length_and_disabled_date_shift_are_respected():
    row = AttendanceRow(
        work_date=date(2026, 10, 5),
        day_of_week="שני",
        entry_time=8 * 60,
        exit_time=16 * 60,
    )
    report = AttendanceReport(
        employee_id="1",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type="TYPE_B",
        rows=(row,),
    )
    rules = TransformationRules(
        simulation=True,
        min_shift_minutes=0,
        max_shift_minutes=0,
        maximum_simulated_work_minutes=8 * 60,
        maximum_work_minutes=15 * 60,
        maximum_shift_duration_minutes=15 * 60,
        maximum_clock_minute=999,
        minutes_per_day=1000,
        maximum_date_shift_days=0,
    )

    transformed = TypeBTransformationStrategy().transform_report(
        report, rules=rules, seed=42
    )

    assert transformed.rows[0].work_date == row.work_date
    assert transformed.rows[0].entry_time == row.entry_time
    assert transformed.rows[0].exit_time == row.exit_time
    assert transformed.rows[0].total_work_minutes == 8 * 60


def test_synthetic_simulation_does_not_keep_stale_hours_without_clock_times():
    row = AttendanceRow(
        work_date=date(2026, 10, 4),
        day_of_week="ראשון",
        total_work_minutes=300,
        overtime_100_minutes=300,
        saturday_minutes=300,
    )
    report = AttendanceReport(
        employee_id="1",
        employee_name="בדיקה",
        report_period="2026-10",
        report_type="TYPE_B",
        rows=(row,),
    )

    result = TypeBTransformationStrategy().transform_report(
        report,
        rules=TransformationRules(
            simulation=True,
            maximum_date_shift_days=0,
        ),
        seed=3,
    )

    assert result.rows[0].total_work_minutes == 0
    assert result.rows[0].overtime_100_minutes == 0
    assert result.rows[0].saturday_minutes == 0
    assert result.summary.total_work_minutes == 0
    assert result.summary.total_saturday_minutes == 0
    assert result.summary.total_work_days == 0
    assert result.summary.total_absent_days == 1


def test_get_transformation_strategy_registry():
    from transformation.transformer import get_transformation_strategy
    import pytest

    assert isinstance(get_transformation_strategy("TYPE_A"), TypeATransformationStrategy)
    assert isinstance(get_transformation_strategy("TYPE_B"), TypeBTransformationStrategy)
    with pytest.raises(ValueError):
        get_transformation_strategy("TYPE_Z")
