"""What a small denominator supports, and what it does not."""

from __future__ import annotations

import pytest

from agts.evaluation.confidence import lower_bound, rate


def test_a_clean_sweep_of_eight_is_not_certainty() -> None:
    """The number this repository reports as 8/8. A system that wrongly answered
    three learners in ten would produce it about one run in twenty."""
    assert lower_bound(8, 8) == pytest.approx(0.688, abs=0.005)


def test_more_of_the_same_result_buys_confidence_slowly() -> None:
    assert lower_bound(10, 10) == pytest.approx(0.741, abs=0.005)
    assert lower_bound(18, 18) == pytest.approx(0.847, abs=0.005)
    assert lower_bound(100, 100) > 0.97


def test_a_bound_never_exceeds_what_was_observed() -> None:
    for successes, trials in ((8, 8), (26, 29), (1, 2), (47, 50)):
        assert lower_bound(successes, trials) <= successes / trials


def test_zero_successes_supports_nothing() -> None:
    assert lower_bound(0, 8) == 0.0


def test_an_empty_denominator_is_not_a_rate() -> None:
    assert lower_bound(3, 0) == 0.0
    assert rate(0, 0).observed is None
    assert str(rate(0, 0)) == "n/a"


def test_impossible_counts_are_refused() -> None:
    with pytest.raises(ValueError):
        lower_bound(9, 8)


def test_the_string_carries_the_denominator_and_the_bound() -> None:
    """A fraction on its own travels into tables and loses its sample size."""
    text = str(rate(8, 8))
    assert "8/8" in text and "69%" in text and "95%" in text
