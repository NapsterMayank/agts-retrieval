"""Parsing: two strategies, one block vocabulary, and a diff between them.

Strategy selection and its measurements are in DECISION_LOG.md R-008.
"""

from .base import ParseOutcome, ParseStrategy
from .diff import PageDiff, ParseDiff, diff_outcomes
from .geometry import (
    DEFAULT_PAGE_SIZE,
    page_sizes_from_pdf,
    pdf_points_to_region,
    region_to_pdf_points,
)
from .opendataloader import blocks_from_json

__all__ = [
    "DEFAULT_PAGE_SIZE",
    "PageDiff",
    "ParseDiff",
    "ParseOutcome",
    "ParseStrategy",
    "blocks_from_json",
    "diff_outcomes",
    "page_sizes_from_pdf",
    "pdf_points_to_region",
    "region_to_pdf_points",
]
