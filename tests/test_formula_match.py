"""Attaching a second parser's LaTeX, and refusing to when it is a guess.

Every threshold here was set by checking matches against the page images. Three
were verified by eye: one correct, one matched to its own sign-flipped twin, and
one matched to a different formula on the same page.
"""

from __future__ import annotations

from agts.parsing.formula_match import best_match, similarity, symbols
from agts.parsing.quality import readable_text


def test_operators_are_symbols() -> None:
    """They were stripped with the markup, which made a formula and its
    sign-flipped twin identical to this comparison -- and that is exactly how a
    wrong formula was attached with perfect confidence."""
    assert symbols("a + b")["+"] == 1
    assert symbols(r"x = -\frac{b}{2a} \pm 0") != symbols(r"x = -\frac{b}{2a} + 0")


def test_the_verified_correct_match_is_attached() -> None:
    """The quadratic formula, checked against assets/208.png."""
    degraded = "2 4 , 2 b b ac a    provided b 2 - 4 ac"
    correct = r"\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}, \text{ provided } b^2 - 4ac \geq 0."
    unrelated = r"AB = 13\text{m}"

    match = best_match("b", degraded, [correct, unrelated])
    assert match.confident
    assert match.latex == correct


def test_a_sign_flipped_twin_is_withheld() -> None:
    """Checked against assets/153.png: the page shows a minus. Both candidates
    score identically on content, so the margin is what refuses them."""
    degraded = "2 4 - 2 2 b ac b a a   ."
    plus = r"-\frac{b}{2a} + \frac{\sqrt{b^2 - 4ac}}{2a}"
    minus = r"-\frac{b}{2a} - \frac{\sqrt{b^2 - 4ac}}{2a}"

    match = best_match("b", degraded, [plus, minus])
    assert not match.confident, "a formula and its twin must not be told apart by a guess"


def test_a_different_formula_on_the_same_page_is_withheld() -> None:
    """Checked against assets/159.png."""
    degraded = "2 a 2 2 a a 2 a"
    elsewhere = r"b^2 - 4ac = (-4)^2 - (4 \times 2 \times 3) = 16 - 24 = -8 < 0"

    match = best_match("b", degraded, [elsewhere])
    assert not match.confident


def test_no_candidates_is_no_match() -> None:
    assert best_match("b", "2 4 b", []) is None


def test_similarity_is_normalised_by_the_degraded_side() -> None:
    """A candidate may carry more than the mangled text kept -- recovering
    structure is the point -- but it must contain what the block shows."""
    assert similarity("a b", "a b c d e") == 1.0
    assert similarity("a b c d e", "a b") < 0.5


def test_readable_text_prefers_latex_only_when_the_text_has_decayed() -> None:
    """`text or latex` shipped for a week and hid every recovered formula behind
    the mangled version of itself."""
    assert readable_text("2 4 , 2 b b ac a", r"\frac{-b}{2a}") == r"\frac{-b}{2a}"
    assert readable_text("Zn + H2SO4 -> ZnSO4 + H2", r"\text{wrong}") == "Zn + H2SO4 -> ZnSO4 + H2"
    assert readable_text(None, r"\frac{1}{2}") == r"\frac{1}{2}"
    assert readable_text("plain prose here", None) == "plain prose here"


# --------------------------------------------------------------------------
# Granularity: the two parsers do not agree on what one formula is
# --------------------------------------------------------------------------


def test_a_formula_is_found_inside_a_multi_line_candidate() -> None:
    """Docling emits one line; the second parser emits the whole derivation.

    Verified against the quadratic chapter, block texts-42: the degraded text is
    one line of a four-line `aligned` block, and the correct LaTeX is sitting
    inside it. Comparing against the block as a whole matches, and then the
    margin refuses it, because every other line of the same derivation contains
    the same symbols. 39 of 43 formula blocks were withheld this way.
    """
    degraded = "= - x 2  + 45 x - 200"
    block = (
        r"\begin{aligned} \text{Therefore, their product} &= (x - 5)(40 - x) \ "
        r"&= 40x - x^2 - 200 + 5x \ &= -x^2 + 45x - 200 \end{aligned}"
    )

    match = best_match("b", degraded, [block])
    assert match is not None and match.confident
    assert "-x^2 + 45x - 200" in match.latex
    assert "aligned" not in match.latex, "the line, not the derivation it came from"


def test_the_tightest_explanation_wins_over_the_block_containing_it() -> None:
    """A line and the block it belongs to are not competing explanations.

    They are the same answer at two granularities, so the margin must not treat
    the container as a rival. It still has to treat a genuinely different
    formula as one -- that is the next test.
    """
    degraded = "x 2 - 45 x + 324 = 0"
    line = r"x^2 - 45x + 324 = 0"
    container = r"\text{i.e., } x^2 - 45x + 324 = 0 \text{, so } x = 9 \text{ or } x = 36"

    match = best_match("b", degraded, [container, line])
    assert match.confident
    assert match.latex == line


def test_a_rival_that_is_not_a_container_still_withholds() -> None:
    """The sign-flip protection has to survive segmentation.

    Both candidates are single lines, neither contains the other, and they
    differ only in a sign the degraded text lost. Segmenting must not turn this
    into a confident match.
    """
    degraded = "2 4 - 2 2 b ac b a a   ."
    plus = r"\begin{aligned} &= -\frac{b}{2a} + \frac{\sqrt{b^2 - 4ac}}{2a} \end{aligned}"
    minus = r"\begin{aligned} &= -\frac{b}{2a} - \frac{\sqrt{b^2 - 4ac}}{2a} \end{aligned}"

    match = best_match("b", degraded, [plus, minus])
    assert not match.confident


def test_prose_only_segments_are_not_candidates() -> None:
    """A sentence is not a formula, however many of its letters coincide."""
    degraded = "x 2 + 2 x = 3"
    prose = r"\text{So, the area of the hall is thirty square metres}"
    formula = r"x^2 + 2x = 3"

    match = best_match("b", degraded, [prose, formula])
    assert match.confident
    assert match.latex == formula
