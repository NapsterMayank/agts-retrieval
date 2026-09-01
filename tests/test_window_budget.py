"""How many windows of one object may represent it (R-070).

Dense retrieval kept the single best window per object. On the visible set that
discarded the gold window of five answerable cases while retrieving the right
object every time: for "discriminant", the window holding the answer scored
0.7846 and ranked third of twenty-four, and was dropped because another window
of the same section scored 0.7917. A gap of 0.007 decided which paragraph of the
right section a learner saw.

The rule is not "return more windows". It is "a near-tie is not a decision".
"""

from __future__ import annotations

from agts.retrieval.dense import WINDOW_MARGIN, WINDOWS_PER_OBJECT, windows_for_object


def scored(*values: float) -> list[tuple[float, str]]:
    return [(value, f"w{index}") for index, value in enumerate(values)]


def test_a_near_tie_admits_the_runner_up() -> None:
    """0.007 apart is the case this exists for.

    Asserts the runner-up is admitted, not the exact count: the budget is a
    measured constant and moved from two to three when correcting six sentences
    reshuffled which window of a section wins (R-074).
    """
    kept = windows_for_object(scored(0.7917, 0.7846, 0.7807))
    names = [name for _, name in kept]
    assert names[:2] == ["w0", "w1"]
    assert len(names) <= WINDOWS_PER_OBJECT


def test_a_clear_winner_stays_alone() -> None:
    """Otherwise every object contributes two windows and the pack doubles."""
    kept = windows_for_object(scored(0.90, 0.60, 0.55))
    assert [name for _, name in kept] == ["w0"]


def test_never_more_than_the_budget_however_close_they_are() -> None:
    """Five windows of one section are still not five pieces of evidence."""
    kept = windows_for_object(scored(0.80, 0.799, 0.798, 0.797, 0.796))
    assert len(kept) == WINDOWS_PER_OBJECT


def test_the_second_window_must_be_inside_the_margin() -> None:
    just_outside = 0.80 - WINDOW_MARGIN - 0.001
    assert len(windows_for_object(scored(0.80, just_outside))) == 1
    just_inside = 0.80 - WINDOW_MARGIN + 0.001
    assert len(windows_for_object(scored(0.80, just_inside))) == 2


def test_the_best_window_is_always_first() -> None:
    kept = windows_for_object(scored(0.70, 0.71))
    assert kept[0][0] == 0.71


def test_no_windows_is_no_items() -> None:
    assert windows_for_object([]) == []
