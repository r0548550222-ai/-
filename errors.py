"""Typed errors raised by attendance-project processing stages."""


class AttendanceProjectError(Exception):
    """Base class for expected, user-facing application errors."""


class OCRProcessingError(RuntimeError, AttendanceProjectError):
    """An expected PDF extraction or OCR failure."""


class ClassificationError(ValueError, AttendanceProjectError):
    """Extracted text cannot be confidently classified."""


class ParsingError(ValueError, AttendanceProjectError):
    """Extracted report text cannot be parsed into attendance rows."""


class TransformationError(ValueError, AttendanceProjectError):
    """Report transformation or its business invariants failed."""
