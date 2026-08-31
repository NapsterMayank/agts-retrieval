"""Attach a second parser's LaTeX to the primary parser's formula blocks (R-008).

R-008 chose Docling as the primary parse and required that "a formula object
stores its **image crop and raw extracted text alongside any LaTeX, never LaTeX
alone**". The crop and the raw text were implemented. **The LaTeX never was** —
the `latex` field has been empty on every block since the first parse, while a
second strategy that produces good LaTeX ran on the same pages and was used only
to count characters for a page-level diff.

The cost of that was measured a week later: 12% of the maths chapter's formula
blocks are unreadable (R-037), and the quadratic formula reaches a learner as
`2 4 , 2 b b ac a`. The second parser had it as
`x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}` the whole time.

**Matching is by symbol content, not by position.** The two parsers do not agree
on how many formula regions a page contains — R-008 recorded that the join is not
one-to-one — so a positional match would be confident and wrong. Instead each
candidate is reduced to the multiset of symbols a reader would see, and the best
overlap wins.

**A weak match is not written.** Below `MIN_CONFIDENCE` the block keeps its
degraded text and goes to the human review queue, because a wrong formula that
renders beautifully is the failure mode R-008 rejected formula enrichment for.
Guessing here would repeat that mistake with a different tool.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

#: Below this, the best candidate is not written. Chosen to be strict: a formula
#: attached wrongly is worse than a formula left visibly broken, because the
#: broken one is obvious to a reviewer and the wrong one is not.
MIN_CONFIDENCE = 0.90

#: And the winner must win clearly. Verified against the page images, the one
#: correct match led its runner-up by 0.76 while a *wrong* match tied its
#: sign-flipped twin at 0.00 -- so the margin separates them where the score
#: alone does not.
MIN_MARGIN = 0.50

#: LaTeX commands that ARE symbols to a reader, restored before the rest of the
#: markup is stripped. Operators were originally discarded along with the markup,
#: which made two candidates differing only in sign identical to this comparison
#: -- and that is exactly how one formula was matched to its own sign-flipped
#: twin with perfect confidence.
_AS_SYMBOLS = {
    "\\pm": " pm ", "\\mp": " pm ", "\\times": " * ", "\\cdot": " * ",
    "\\div": " / ", "\\geq": " > ", "\\leq": " < ", "\\neq": " = ",
    "\\sqrt": " sqrt ", "\\frac": " / ", "\\le": " < ", "\\ge": " > ",
}

#: LaTeX structure a reader does not "see". Stripped after the substitutions.
_COMMANDS = re.compile(r"\\(begin|end)\{[a-z*]+\}|\\[a-zA-Z]+|[{}&\\$]")

#: What counts as a symbol: letters, digits, and the operators that carry the
#: meaning. An equation is not identified by its letters alone.
_SYMBOL = re.compile(r"[a-zA-Z0-9+\-=<>*/^]")


def symbols(text: str) -> Counter:
    """The symbols a reader would take from this, whatever the notation."""
    for command, symbol in _AS_SYMBOLS.items():
        text = text.replace(command, symbol)
    stripped = _COMMANDS.sub(" ", text)
    return Counter(character.lower() for character in stripped if _SYMBOL.match(character))


def similarity(degraded: str, candidate: str) -> float:
    """Symbol overlap, normalised by the degraded text.

    Normalised by the *degraded* side on purpose. A candidate is allowed to
    carry more than the mangled text retained — recovering structure is the
    point — but it must contain what the block actually shows, or it is a
    different formula.
    """
    left, right = symbols(degraded), symbols(candidate)
    if not left:
        return 0.0
    shared = sum((left & right).values())
    return shared / sum(left.values())


@dataclass(frozen=True)
class Match:
    block_id: str
    latex: str
    confidence: float
    margin: float = 0.0

    @property
    def confident(self) -> bool:
        """Both conditions, because either one alone admitted a wrong formula."""
        return self.confidence >= MIN_CONFIDENCE and self.margin >= MIN_MARGIN


def best_match(block_id: str, degraded: str, candidates: list[str]) -> Match | None:
    """The candidate that best explains this block's symbols."""
    scored = [
        (similarity(degraded, candidate), candidate)
        for candidate in candidates
        if candidate.strip()
    ]
    if not scored:
        return None
    scored.sort(key=lambda pair: (-pair[0], len(pair[1])))
    confidence, latex = scored[0]
    runner_up = scored[1][0] if len(scored) > 1 else 0.0
    return Match(
        block_id=block_id,
        latex=latex,
        confidence=confidence,
        margin=confidence - runner_up,
    )