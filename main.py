"""Application composition root and command-line entry point."""

from functools import partial
from types import MappingProxyType
from typing import Callable

from generation.generator import HtmlRenderer, PdfRenderer, Renderer
from models import ReportType
from pipeline import process_attendance_pipeline as _process_pipeline
from transformation.transformer import (
    BaseTransformationStrategy,
    TypeATransformationStrategy,
    TypeBTransformationStrategy,
)

PIPELINE_STRATEGIES: MappingProxyType[str, BaseTransformationStrategy] = (
    MappingProxyType(
        {
            ReportType.TYPE_A.value: TypeATransformationStrategy(),
            ReportType.TYPE_B.value: TypeBTransformationStrategy(),
        }
    )
)
OUTPUT_RENDERERS: MappingProxyType[str, Renderer] = MappingProxyType(
    {
        ".pdf": PdfRenderer(),
        ".html": HtmlRenderer(),
        ".htm": HtmlRenderer(),
    }
)

process_attendance_pipeline: Callable[..., str] = partial(
    _process_pipeline,
    strategies=PIPELINE_STRATEGIES,
    renderers=OUTPUT_RENDERERS,
)

__all__ = ["main", "process_attendance_pipeline"]


def main() -> None:
    """הפעלת ממשק שורת הפקודה."""
    from cli import main as run_cli

    run_cli()


if __name__ == "__main__":
    main()
