"""Compare two parse strategies over the same document (§7.2).

Two readings are only worth having if something looks at the disagreement. A
page where one strategy extracts 400 characters and the other extracts 4,000 is
a page where one of them is wrong, and finding that before the content is
embedded costs a report; finding it afterwards costs a re-parse of the corpus.

This does not decide which strategy is right. It decides which pages a human
should look at.
"""

from __future__ import annotations

from dataclasses import dataclass

from agts.contracts.common import BlockType
from agts.parsing.base import ParseOutcome

#: A page is flagged when one strategy recovers less than this fraction of the
#: other's text. Chosen to catch a page that largely failed, not a page where
#: the two disagree about a header.
TEXT_RATIO_FLOOR = 0.5


@dataclass(frozen=True)
class PageDiff:
    page: int
    blocks_a: int
    blocks_b: int
    chars_a: int
    chars_b: int
    reasons: tuple[str, ...]

    @property
    def flagged(self) -> bool:
        return bool(self.reasons)


@dataclass(frozen=True)
class ParseDiff:
    strategy_a: str
    strategy_b: str
    pages: list[PageDiff]
    #: Document-level facts about the pairing itself, reported once. A property
    #: of a strategy is not evidence about a page.
    notes: tuple[str, ...] = ()

    @property
    def flagged_pages(self) -> list[PageDiff]:
        return [p for p in self.pages if p.flagged]

    def summary(self) -> str:
        flagged = self.flagged_pages
        return (
            f"{self.strategy_a} vs {self.strategy_b}: "
            f"{len(flagged)}/{len(self.pages)} pages flagged for review"
        )

    def report(self) -> str:
        lines = [self.summary()]
        lines += [f"  note: {note}" for note in self.notes]
        for page in self.flagged_pages:
            lines.append(
                f"  p{page.page}: {self.strategy_a} {page.blocks_a} blocks / "
                f"{page.chars_a} chars, {self.strategy_b} {page.blocks_b} / "
                f"{page.chars_b} - {'; '.join(page.reasons)}"
            )
        return "\n".join(lines)


def _chars(blocks) -> int:
    return sum(len(b.text or "") for b in blocks)


def diff_outcomes(a: ParseOutcome, b: ParseOutcome) -> ParseDiff:
    """Compare two readings page by page."""
    by_page_a = a.blocks_by_page()
    by_page_b = b.blocks_by_page()
    pages = max(a.pages, b.pages, *(list(by_page_a) or [0]), *(list(by_page_b) or [0]))

    # Whether a strategy labels formulas *at all* is a property of the strategy,
    # not of any page. opendataloader-pdf in deterministic mode labels none, so
    # comparing per page flags every page carrying an equation and buries the
    # pages that genuinely disagree. Said once, as a note.
    formulas_total_a = sum(1 for x in a.blocks if x.block_type is BlockType.FORMULA)
    formulas_total_b = sum(1 for x in b.blocks if x.block_type is BlockType.FORMULA)
    compare_formulas = bool(formulas_total_a) and bool(formulas_total_b)
    notes: list[str] = []
    if not compare_formulas and (formulas_total_a or formulas_total_b):
        blind = b.strategy if formulas_total_a else a.strategy
        seeing = a.strategy if formulas_total_a else b.strategy
        notes.append(
            f"{blind} labels no formulas anywhere in this document; "
            f"{seeing} found {formulas_total_a or formulas_total_b}. "
            "Formula presence is not compared page by page."
        )

    diffs: list[PageDiff] = []
    for page in range(1, pages + 1):
        blocks_a = by_page_a.get(page, [])
        blocks_b = by_page_b.get(page, [])
        chars_a, chars_b = _chars(blocks_a), _chars(blocks_b)
        reasons: list[str] = []

        # The strongest signal: one strategy saw nothing at all.
        if bool(blocks_a) != bool(blocks_b):
            missing = a.strategy if not blocks_a else b.strategy
            reasons.append(f"{missing} produced no blocks")
        elif chars_a and chars_b:
            ratio = min(chars_a, chars_b) / max(chars_a, chars_b)
            if ratio < TEXT_RATIO_FLOOR:
                thin = a.strategy if chars_a < chars_b else b.strategy
                reasons.append(f"{thin} recovered {ratio:.0%} of the text")

        if compare_formulas:
            formulas_a = sum(1 for x in blocks_a if x.block_type is BlockType.FORMULA)
            formulas_b = sum(1 for x in blocks_b if x.block_type is BlockType.FORMULA)
            if (formulas_a == 0) != (formulas_b == 0):
                found = a.strategy if formulas_a else b.strategy
                reasons.append(f"only {found} found formulas")

        diffs.append(
            PageDiff(
                page=page,
                blocks_a=len(blocks_a),
                blocks_b=len(blocks_b),
                chars_a=chars_a,
                chars_b=chars_b,
                reasons=tuple(reasons),
            )
        )

    return ParseDiff(
        strategy_a=a.strategy,
        strategy_b=b.strategy,
        pages=diffs,
        notes=tuple(notes),
    )
