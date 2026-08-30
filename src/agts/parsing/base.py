"""Parse strategy contract (build guide §7.2).

    "Run at least two parse strategies for representative pages and retain
     parse provenance."

Two strategies means two independent readings of the same bytes, each recording
which parser produced it. That provenance is what makes the readings
comparable — and comparing them is how a parse defect is found before it is
embedded, rather than after a student sees it.

Strategy selection is recorded in DECISION_LOG.md R-008, with measurements in
EVALUATION_LEDGER.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from agts.contracts.objects import SourceBlock


@dataclass(frozen=True)
class ParseOutcome:
    """One strategy's reading of one document."""

    strategy: str
    parser_version: str
    blocks: list[SourceBlock]
    seconds: float = 0.0
    pages: int = 0
    warnings: list[str] = field(default_factory=list)

    def blocks_by_page(self) -> dict[int, list[SourceBlock]]:
        out: dict[int, list[SourceBlock]] = {}
        for block in self.blocks:
            out.setdefault(block.region.page, []).append(block)
        return out

    def empty_pages(self) -> list[int]:
        """Pages yielding no blocks. §7.1 gate: this must be empty.

        A page that produces nothing is either blank or unparsed, and the two
        are indistinguishable from the output alone — which is why it stops the
        run rather than logging a warning.
        """
        seen = self.blocks_by_page()
        return [p for p in range(1, self.pages + 1) if not seen.get(p)]


class ParseStrategy(Protocol):
    """Every strategy answers the same question about the same bytes."""

    name: str

    def parse(
        self,
        pdf_path: str,
        *,
        source_id: str,
        document_id: str,
    ) -> ParseOutcome:
        ...
