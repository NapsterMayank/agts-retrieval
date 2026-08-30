"""Pairwise slices (section 11.2) and how the abstention floor is placed."""

from __future__ import annotations

from math import comb

import pytest

from agts.evaluation.cases import EvalCase
from agts.evaluation.fixtures import build_corpus, build_gold_set
from agts.evaluation.retrievers import KeywordBaseline
from agts.evaluation.scorer import (
    InvariantViolations,
    ScoreReport,
    SliceScore,
    calibrate_abstention,
)


def case(**overrides) -> EvalCase:
    defaults = dict(
        case_id="c1", query="q", grade="10", subject="science",
        question_type="definition", teaching_action="explain", concept_ids=["c1"],
        gold_block_ids=["b1"],
    )
    return EvalCase(**{**defaults, **overrides})


# --------------------------------------------------------------------------
# Slices
# --------------------------------------------------------------------------


def test_every_pair_of_axes_is_crossed() -> None:
    keys = case().slice_keys()
    axes = case().axes()
    assert len(keys) == len(axes) + comb(len(axes), 2)
    assert keys["subject"] == "science"
    assert keys["modality×subject"] == "text×science"


def test_a_crossing_carries_both_values_in_order() -> None:
    """Otherwise two different crossings collide under one key and their
    numbers are silently averaged together."""
    keys = case(subject="mathematics", modality="equation").slice_keys()
    assert keys["modality×subject"] == "equation×mathematics"
    assert keys["modality×subject"] != case().slice_keys()["modality×subject"]


def test_absent_axes_are_absent_rather_than_constant() -> None:
    """Section 11.2 lists accessibility and provider. Neither has a field on a
    case, and a slice with one value can never fail, which is worse than a
    missing slice because it looks like coverage."""
    axes = case().axes()
    assert "accessibility" not in axes
    assert "provider" not in axes


def report_with(slices: dict[str, SliceScore]) -> ScoreReport:
    return ScoreReport(
        retriever="r", k_candidates=20, k_pack=5, n_cases=100, n_answerable=100,
        recall_at_candidates=0.9, recall_at_pack=0.9, abstention_accuracy=None,
        violations=InvariantViolations(), slices=slices,
    )


def failing_slice(key: str, recall: float = 0.5) -> SliceScore:
    return SliceScore(
        slice_key=key, n=50, n_answerable=50, recall_at_candidates=recall,
        recall_at_pack=recall, abstention_accuracy=None, violations=InvariantViolations(),
    )


def passing_slice(key: str) -> SliceScore:
    return SliceScore(
        slice_key=key, n=50, n_answerable=50, recall_at_candidates=1.0,
        recall_at_pack=1.0, abstention_accuracy=None, violations=InvariantViolations(),
    )


def test_a_crossing_failing_because_its_axis_fails_is_not_reported_twice() -> None:
    """The matrix restates one problem many times. A release that reads sixty
    lines describing one fact starts skimming."""
    report = report_with({
        "subject=mathematics": failing_slice("subject=mathematics"),
        "modality=text": passing_slice("modality=text"),
        "modality×subject=text×mathematics": failing_slice("modality×subject=text×mathematics"),
    })

    assert len(report.failing_slices()) == 2
    distinctive = report.distinctive_failures()
    assert len(distinctive) == 1
    assert distinctive[0].startswith("subject=mathematics")


def test_a_crossing_that_fails_while_both_axes_pass_is_reported() -> None:
    """The hole the pairwise matrix exists to find: science passes, equations
    pass, science equations do not."""
    report = report_with({
        "subject=science": passing_slice("subject=science"),
        "modality=equation": passing_slice("modality=equation"),
        "modality×subject=equation×science": failing_slice("modality×subject=equation×science"),
    })

    distinctive = report.distinctive_failures()
    assert len(distinctive) == 1
    assert "both axes pass alone" in distinctive[0]


# --------------------------------------------------------------------------
# Calibration
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def corpus():
    return build_corpus()


@pytest.fixture(scope="module")
def gold_set():
    return build_gold_set()


def test_the_midpoint_threshold_sits_between_the_two_extremes(corpus, gold_set) -> None:
    calibration = calibrate_abstention(gold_set, KeywordBaseline(), corpus)
    assert calibration.false_abstain_budget is None
    assert (
        calibration.highest_unanswerable
        <= calibration.threshold
        <= calibration.lowest_answerable
    )


def test_a_budgeted_threshold_stays_within_its_budget(corpus, gold_set) -> None:
    calibration = calibrate_abstention(
        gold_set, KeywordBaseline(), corpus, false_abstain_budget=0.2
    )
    assert calibration.false_abstain_budget == 0.2
    assert calibration.false_abstain_rate <= 0.2


def test_a_budgeted_threshold_reports_what_it_buys(corpus, gold_set) -> None:
    """A threshold quoted without what it costs and what it refuses is a number
    with no claim attached."""
    calibration = calibrate_abstention(
        gold_set, KeywordBaseline(), corpus, false_abstain_budget=0.1
    )
    assert 0.0 <= calibration.unanswerable_refused_rate <= 1.0
    assert "budget=10%" in calibration.summary()


def test_an_impossible_budget_is_refused(corpus, gold_set) -> None:
    for budget in (-0.1, 1.0, 2.0):
        with pytest.raises(ValueError):
            calibrate_abstention(
                gold_set, KeywordBaseline(), corpus, false_abstain_budget=budget
            )
