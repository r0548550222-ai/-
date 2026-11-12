"""Immutable application defaults and business rules."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ApplicationConfig:
    """Business limits and user-facing defaults shared across the application."""

    default_employee_id: str = "000000000"
    default_employee_name: str = "לא זוהה"
    default_report_period: str = "2026-10"
    default_report_type: str = "TYPE_A"
    default_simulation_seed: int = 42
    default_output_format: str = "pdf"

    min_shift_minutes: int = 20
    max_shift_minutes: int = 30
    maximum_date_shift_days: int = 30
    maximum_allowed_shift_change_minutes: int = 180
    minimum_simulated_work_minutes: int = 4 * 60
    maximum_simulated_work_minutes: int = 12 * 60
    maximum_work_minutes: int = 16 * 60
    maximum_shift_duration_minutes: int = 16 * 60
    overtime_100_limit_minutes: int = 8 * 60
    overtime_125_limit_minutes: int = 2 * 60
    minimum_clock_minute: int = 0
    minutes_per_day: int = 24 * 60
    maximum_break_minutes: int = 180


CONFIG = ApplicationConfig()

# Backwards-compatible names used by existing callers and tests.
DEFAULT_EMPLOYEE_ID = CONFIG.default_employee_id
DEFAULT_EMPLOYEE_NAME = CONFIG.default_employee_name
DEFAULT_REPORT_PERIOD = CONFIG.default_report_period
DEFAULT_REPORT_TYPE = CONFIG.default_report_type
DEFAULT_SIMULATION_SEED = CONFIG.default_simulation_seed
DEFAULT_OUTPUT_FORMAT = CONFIG.default_output_format

# Synthetic clock-time perturbation magnitudes, selected with either sign.
DEFAULT_MIN_SHIFT_MINUTES = CONFIG.min_shift_minutes
DEFAULT_MAX_SHIFT_MINUTES = CONFIG.max_shift_minutes

# Independent date offset used only for synthetic simulations.
DEFAULT_MAXIMUM_DATE_SHIFT_DAYS = CONFIG.maximum_date_shift_days

# Work and clock validation defaults.
DEFAULT_MAXIMUM_ALLOWED_SHIFT_CHANGE_MINUTES = (
    CONFIG.maximum_allowed_shift_change_minutes
)
DEFAULT_MINIMUM_SIMULATED_WORK_MINUTES = CONFIG.minimum_simulated_work_minutes
DEFAULT_MAXIMUM_SIMULATED_WORK_MINUTES = CONFIG.maximum_simulated_work_minutes
DEFAULT_MAXIMUM_WORK_MINUTES = CONFIG.maximum_work_minutes
DEFAULT_MAXIMUM_SHIFT_DURATION_MINUTES = CONFIG.maximum_shift_duration_minutes
DEFAULT_OVERTIME_100_LIMIT_MINUTES = CONFIG.overtime_100_limit_minutes
DEFAULT_OVERTIME_125_LIMIT_MINUTES = CONFIG.overtime_125_limit_minutes
DEFAULT_MINIMUM_CLOCK_MINUTE = CONFIG.minimum_clock_minute
MINUTES_PER_DAY = CONFIG.minutes_per_day
DEFAULT_MAXIMUM_CLOCK_MINUTE = CONFIG.minutes_per_day - 1
DEFAULT_MAXIMUM_BREAK_MINUTES = CONFIG.maximum_break_minutes
