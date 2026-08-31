"""Is extracted evidence usable by a learner? (R-008, and an outside review)

R-008 recorded that formula extraction degrades and that a crop is kept beside
the text for exactly that reason. What it did not do is measure how often the
text is degraded past use, and "Mathpix might help" stayed an assumption for a
week because of it.

An outside reviewer supplied the missing case. Asked to check the claim that the
maths chapter answers "What is the quadratic formula?", it agreed the chapter
does and objected anyway: the extracted evidence reads

    2 4 , 2 b b ac a    provided b 2 - 4 ac

A student cannot reconstruct the quadratic formula from that. The retrieval was
correct, the citation resolved, the gate answered — and the evidence was
unusable. No gate in this repository could have caught it, because every one of
them measures whether the *right block* was found rather than whether the block
*says anything*.

This is deliberately a reader's test rather than a parser's. Two signals, both
taken from the failures R-008 catalogued:

- **almost every token is a single character**, which is what a formula looks
  like once its structure is gone; and
- **no relation survives** — an equation with no `=`, `<`, `>` or arrow is not
  stating anything, whatever symbols remain.

Both must hold. Chemical equations survive extraction far better than algebra
does, and their arrows are the reason.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from agts.contracts.common import BlockType
from agts.contracts.objects import SourceBlock

#: Above this fraction of single-character tokens, the text has decayed into
#: loose symbols rather than notation.
LOOSE_TOKEN_RATIO = 0.55

#: Below this many tokens there is nothing to judge; a two-symbol formula is
#: terse rather than broken.
MIN_TOKENS = 4

_RELATION = re.compile(r"[=<>≤≥→]|->|xrightarrow|rightarrow")


def is_unusable(text: str | None) -> bool:
    """Whether a reader could reconstruct the mathematics from this text."""
    if not text:
        return True
    tokens = text.split()
    if len(tokens) < MIN_TOKENS:
        return False
    loose = sum(1 for token in tokens if len(token) == 1) / len(tokens)
    return loose > LOOSE_TOKEN_RATIO and not _RELATION.search(text)


def unusable_formulas(blocks: Iterable[SourceBlock]) -> list[SourceBlock]:
    """Formula blocks whose text has decayed past use.

    The blocks are not dropped and must not be: the crop is still there, the
    citation still resolves, and a reviewer can still see what was meant. What
    this produces is a work list for a formula recogniser, and a number to put
    beside "the maths chapter is fine" before believing it.
    """
    return [
        block
        for block in blocks
        if block.block_type is BlockType.FORMULA
        and is_unusable(" ".join((block.text or "").split()))
    ]


def readable_text(text: str | None, latex: str | None) -> str:
    """What to show a reader, given both fields.

    `text or latex` is the wrong precedence and shipped for a week: a block whose
    extracted text has decayed to loose symbols still *has* text, so a correctly
    recovered LaTeX beside it was never reached. The recovered quadratic formula
    sat in the `latex` field while `2 4 , 2 b b ac a` went on being served.

    Degraded text is kept in the block either way (R-008) -- this decides only
    what is shown and searched, never what is stored.
    """
    if text and not is_unusable(" ".join(text.split())):
        return text
    if latex:
        return latex
    return text or ""
