"""Evidence-based classification of extracted attendance-report text."""

from models import ReportType
from errors import ClassificationError


class UnknownReportTypeError(ClassificationError):
    """Raised when extracted text does not identify one report type confidently."""


_EVIDENCE: dict[ReportType, dict[str, int]] = {
    ReportType.TYPE_A: {
        "עבודה לחודש": 3,
        "יום שעת סה\"כ": 3,
        "שעות חודשיות": 2,
        "מחיר לשעה": 2,
        "לתשלום": 2,
        "הערות": 1,
    },
    ReportType.TYPE_B: {
        "הפסקה": 3,
        "125%": 3,
        "150%": 2,
        "מקום": 1,
    },
}
_MIN_SCORE = 4


def classify(raw_text: str) -> ReportType:
    """Classify a report only when evidence from multiple indicators is sufficient."""
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise UnknownReportTypeError("Cannot classify an empty or non-text report.")

    normalized_text = raw_text.strip().lower()
    scores = {
        report_type: sum(
            points
            for phrase, points in evidence.items()
            if phrase in normalized_text
        )
        for report_type, evidence in _EVIDENCE.items()
    }
    best_score = max(scores.values())
    if best_score < _MIN_SCORE:
        score_summary = {
            report_type.value: score for report_type, score in scores.items()
        }
        raise UnknownReportTypeError(
            f"Not enough evidence to classify the report: {score_summary}"
        )

    best_types = [
        report_type for report_type, score in scores.items() if score == best_score
    ]
    if len(best_types) != 1:
        score_summary = {
            report_type.value: score for report_type, score in scores.items()
        }
        raise UnknownReportTypeError(
            "Conflicting evidence produced a tie between report types: "
            f"{score_summary}"
        )
    return best_types[0]
