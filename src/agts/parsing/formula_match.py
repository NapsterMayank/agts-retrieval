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

import difflib
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
#:
#: The margin is measured on **reading order**, not on symbol content, and the
#: two are not interchangeable. Symbol overlap cannot separate a line of algebra
#: from a different line of the same derivation: on one page of the quadratic
#: chapter, 25 blocks scored a perfect 1.0 against several candidates at once,
#: because `x^2 - 45x + 324 = 0` and `-x^2 + 45x - 324 = 0` are the same
#: multiset. Order tells them apart and content cannot.
#:
#: 0.20 is inside the widest gap in the observed distribution over the 43 blocks
#: -- margins run ..0.09, 0.13, 0.13, 0.14, then 0.22, 0.22, 0.25.. -- and any
#: value from 0.15 to 0.20 attaches exactly the same 22 blocks, so it is not
#: fitted to a number someone wanted. The three matches verified wrong by eye
#: lead their rivals by 0.077, 0.042 and 0.037, all far below it.
MIN_ORDER_MARGIN = 0.20

#: Kept for callers that reported it. Content margin no longer gates a match --
#: see MIN_ORDER_MARGIN for why it could not.
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
    #: How well the candidate reproduces the *order* the block shows, 0..1.
    order: float = 0.0

    @property
    def confident(self) -> bool:
        """Both conditions, because either one alone admitted a wrong formula.

        Content decides whether the candidate says what the block shows; order
        decides whether it says it in the same sequence. A wrong formula from
        the same page passes the first and fails the second.
        """
        return self.confidence >= MIN_CONFIDENCE and self.margin >= MIN_ORDER_MARGIN


#: Where one LaTeX block breaks into the lines a reader sees as separate
#: formulas: an explicit row break, or a real newline.
_LINE_BREAK = re.compile('\\\\\\\\|\\n')

#: Environment wrappers and alignment marks that survive the split. `&` is an
#: alignment tab, not a symbol, and a line starting with one reads as `&= x`.
_LINE_NOISE = re.compile('\\\\(begin|end)\\{[a-z*]+\\}|^\\s*&|\\s*&\\s*')


def segments(candidate: str) -> list[str]:
    """The candidate, plus each line it contains as its own candidate.

    The two parsers disagree about what *one formula* is: Docling emits the
    single line a reader sees, the second parser emits the whole derivation as
    one `aligned` block. Comparing a line against the derivation matches on
    content and then dies on the margin, because every other line of the same
    derivation contains the same symbols -- 39 of 43 blocks in the quadratic
    chapter were withheld exactly this way.

    Lines carrying no mathematics are dropped. A sentence is not a formula
    however many of its letters coincide, and admitting prose as a candidate
    would let a caption win on a short degraded string.
    """
    pieces = [candidate, *_LINE_BREAK.split(candidate)]
    out: list[str] = []
    for piece in pieces:
        cleaned = _LINE_NOISE.sub(" ", piece).strip()
        cleaned = " ".join(cleaned.split())
        if not cleaned or cleaned in out:
            continue
        # Prose is text with no operator in it. `symbols` keeps letters, so the
        # test is for the marks that make an expression an expression.
        if not any(character in cleaned for character in "=+-<>/^"):
            continue
        out.append(cleaned)
    return out


def reading_order(text: str) -> str:
    """The symbols in the order a reader meets them.

    `symbols` deliberately throws order away, which is right for asking *does
    this candidate say what the block shows* and useless for asking *which of
    these three lines is it*. Both questions have to be answered.
    """
    for command, symbol in _AS_SYMBOLS.items():
        text = text.replace(command, symbol)
    stripped = _COMMANDS.sub(" ", text)
    return "".join(
        character.lower() for character in stripped if _SYMBOL.match(character)
    )


def order_similarity(degraded: str, candidate: str) -> float:
    """How closely the candidate reproduces the block's sequence, 0..1."""
    return difflib.SequenceMatcher(
        None, reading_order(degraded), reading_order(candidate)
    ).ratio()


def _contains(outer: Counter, inner: Counter) -> bool:
    """Whether `outer` carries everything `inner` does.

    Used to tell a rival from a container. A formula and the derivation it is a
    line of are not competing explanations of the same block -- they are one
    answer at two granularities, and letting the container suppress the line
    through the margin is what withheld a whole chapter's LaTeX.
    """
    return not (inner - outer)


def best_match(block_id: str, degraded: str, candidates: list[str]) -> Match | None:
    """The candidate that best explains this block's symbols.

    Ranked by symbol overlap, tie-broken toward the *tightest* explanation: at
    equal confidence the shorter candidate carries less that the block does not
    show. The margin is then measured only against candidates that genuinely
    disagree -- see `_contains`.
    """
    pool: list[str] = []
    for candidate in candidates:
        if not candidate.strip():
            continue
        for piece in segments(candidate):
            if piece not in pool:
                pool.append(piece)

    scored = [(order_similarity(degraded, piece), piece) for piece in pool]
    if not scored:
        return None
    # Order ranks; the shorter of two equally ordered candidates carries less
    # that the block does not show.
    scored.sort(key=lambda pair: (-pair[0], len(pair[1])))
    order, latex = scored[0]

    chosen = symbols(latex)
    runner_up = 0.0
    for score, other in scored[1:]:
        if _contains(symbols(other), chosen) or _contains(chosen, symbols(other)):
            # A container or a fragment of the same expression. Not a rival.
            continue
        runner_up = score
        break

    return Match(
        block_id=block_id,
        latex=latex,
        confidence=similarity(degraded, latex),
        margin=order - runner_up,
        order=order,
    )