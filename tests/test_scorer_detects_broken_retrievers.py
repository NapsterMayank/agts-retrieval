"""Test the tester (build guide §6.5).

    "The evaluation system fails if these broken systems do not score
     materially worse."

This is the blocking test for Phase 0. Everything measured afterwards inherits
its credibility from here: if the ruler cannot separate an honest retriever from
four differently-broken ones, no later number means anything.
"""

from __future__ import annotations

import pytest

from agts.evaluation.fixtures import build_corpus, build_gold_set
from agts.evaluation.retrievers import (
    AnswerOnly,
    CrossTenant,
    KeywordBaseline,
    RandomRanking,
    WrongGrade,
    broken_retrievers,
)
from agts.evaluation.scorer import calibrate_abstention, score


@pytest.fixture(scope="module")
def corpus():
    return build_corpus()


@pytest.fixture(scope="module")
def gold_set():
    return build_gold_set()


@pytest.fixture(scope="module")
def baseline(corpus, gold_set):
    return score(gold_set, KeywordBaseline(), corpus)


# --------------------------------------------------------------------------
# The honest baseline
# --------------------------------------------------------------------------


def test_baseline_finds_the_gold_blocks(baseline) -> None:
    assert baseline.recall_at_candidates == 1.0
    assert baseline.recall_at_pack == 1.0


def test_baseline_trips_no_invariant(baseline) -> None:
    """An honest retriever ranks only what the plan authorises."""
    assert baseline.violations.total == 0


def test_answerable_and_unanswerable_scores_separate(corpus, gold_set) -> None:
    """The claim that matters. If the two distributions overlap, no threshold
    exists and the abstention number is fiction whatever it reads."""
    calibration = calibrate_abstention(gold_set, KeywordBaseline(), corpus)
    assert calibration.separable, calibration.summary()


def test_baseline_abstains_once_the_threshold_is_calibrated(corpus, gold_set) -> None:
    calibration = calibrate_abstention(gold_set, KeywordBaseline(), corpus)
    report = score(
        gold_set, KeywordBaseline(), corpus, abstain_threshold=calibration.threshold
    )
    assert report.abstention_accuracy == 1.0, calibration.summary()


def test_the_provisional_threshold_is_not_assumed_correct(baseline) -> None:
    """Recorded finding, not a bug.

    The hand-picked default abstains on almost nothing, because a raw score is
    not a confidence: an out-of-corpus query still matches a couple of common
    tokens. This is why `PROVISIONAL_ABSTAIN_THRESHOLD` is named provisional and
    why §15 requires recalibration after every corpus expansion.
    """
    assert baseline.abstention_accuracy is not None
    assert baseline.abstention_accuracy < 1.0


def test_the_candidate_pool_is_much_larger_than_the_pack(corpus, gold_set) -> None:
    """Guards the test below: with a pool barely larger than k_pack, a random
    ranker would look competent by luck and prove nothing."""
    from agts.evaluation.planning import plan_for_case

    authorised = corpus.authorised(plan_for_case(gold_set.cases[0]))
    assert len(authorised) >= 20


# --------------------------------------------------------------------------
# §6.5 - every broken retriever must be detectable
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "broken", broken_retrievers(), ids=lambda r: r.name
)
def test_every_broken_retriever_scores_materially_worse(broken, baseline, corpus, gold_set) -> None:
    report = score(gold_set, broken, corpus)
    assert report.is_materially_worse_than(baseline), (
        f"scorer could not separate {broken.name} from the baseline.\n"
        f"  baseline: {baseline.summary()}\n"
        f"  broken:   {report.summary()}"
    )


def test_random_ranking_is_caught_by_recall_not_by_leakage(corpus, gold_set, baseline) -> None:
    """It stays inside the authorisation boundary, so only recall can expose it."""
    report = score(gold_set, RandomRanking(), corpus)
    assert report.violations.total == 0
    assert report.recall_at_pack < baseline.recall_at_pack


def test_wrong_grade_is_caught_as_unauthorised_content(corpus, gold_set) -> None:
    report = score(gold_set, WrongGrade(), corpus)
    assert report.violations.unauthorised_returned > 0


def test_answer_only_is_caught_as_a_disclosure_breach(corpus, gold_set) -> None:
    """The dangerous case: it can rank gold correctly and still be a release
    blocker, so recall alone would have passed it."""
    report = score(gold_set, AnswerOnly(), corpus)
    assert report.violations.disclosure_violations > 0


def test_cross_tenant_is_caught_as_an_isolation_breach(corpus, gold_set) -> None:
    report = score(gold_set, CrossTenant(), corpus)
    assert report.violations.cross_tenant > 0


# --------------------------------------------------------------------------
# Reporting discipline
# --------------------------------------------------------------------------


def test_every_case_is_reported_on_every_slice_axis(baseline, gold_set) -> None:
    """Rule 9: a blended average may not hide a failing slice."""
    for axis in ("grade", "subject", "language", "question_type", "modality", "answerable"):
        assert any(key.startswith(f"{axis}=") for key in baseline.slices), axis


def test_small_slices_report_but_do_not_gate(baseline) -> None:
    """The fixture set is far below n>=20, so nothing here may gate. The real
    gold set is blocked on the named pilot curriculum (open question Q1)."""
    assert all(not sl.gating for sl in baseline.slices.values())
    assert baseline.failing_slices() == []


def test_holdout_is_not_scored_unless_asked(gold_set, corpus) -> None:
    """A tuning run cannot touch the sealed set by accident."""
    visible = score(gold_set, KeywordBaseline(), corpus)
    everything = score(gold_set, KeywordBaseline(), corpus, include_holdout=True)
    assert visible.n_cases == len(gold_set.visible)
    assert everything.n_cases == len(gold_set.cases)
