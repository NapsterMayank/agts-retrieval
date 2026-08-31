"""What a hybrid score is allowed to mean (R-019, §8.4).

The first real-content run measured `representation-hybrid` at 0.355 abstention
accuracy against dense's 0.903 on the same corpus and the same gold set. The
cause was not the fusion: RRF is the right way to combine two rankings that are
not on a common scale. The cause was reporting the *fused rank statistic* as the
item's score. Reciprocal rank fusion has nine reachable values at depth three,
so 61 of 109 answerable cases tied at exactly 1.0, and a calibrated threshold
placed inside that tie mass decides on rank-1-versus-rank-2 noise.

Ordering is a rank question and stays with RRF. Scoring is a magnitude question
and has to come from a retriever that measures magnitude.
"""

from __future__ import annotations

import pytest

from agts.contracts.runtime import RetrievedItem
from agts.evaluation.fixtures import build_corpus, build_gold_set
from agts.evaluation.planning import plan_for_case
from agts.retrieval.dense import HybridRetriever


class FixedLexical:
    name = "fixed-lexical"

    def __init__(self, items: list[RetrievedItem]) -> None:
        self._items = items

    def retrieve(self, plan, corpus, k):
        return self._items[:k]


class FixedDense(FixedLexical):
    name = "fixed-dense"

    def __init__(self, items: list[RetrievedItem], windows: dict[str, float]) -> None:
        super().__init__(items)
        self._windows = windows

    def score_windows(self, plan, corpus) -> dict[str, float]:
        return dict(self._windows)


def item(object_id: str, score: float) -> RetrievedItem:
    return RetrievedItem(
        object_id=object_id,
        block_ids=(f"{object_id}-b",),
        score=score,
        representation_id=f"{object_id}-rep",
    )


def hybrid(lexical_items, dense_items, windows) -> HybridRetriever:
    fused = HybridRetriever.__new__(HybridRetriever)
    fused.lexical = FixedLexical(lexical_items)
    fused.dense = FixedDense(dense_items, windows)
    fused.rrf_k = 60
    return fused


@pytest.fixture()
def plan():
    return plan_for_case(build_gold_set().visible[0])


@pytest.fixture()
def corpus():
    return build_corpus()


def test_the_top_score_is_the_dense_score_of_the_window_returned(plan, corpus) -> None:
    """Not 1.0 for "both retrievers ranked it first"."""
    lexical = [item("a", 0.31), item("b", 0.22)]
    dense = [item("a", 0.82), item("c", 0.61)]
    windows = {"a-rep": 0.82, "b-rep": 0.55, "c-rep": 0.61}

    ranked = hybrid(lexical, dense, windows).retrieve(plan, corpus, 5)

    assert ranked[0].object_id == "a"
    assert ranked[0].score == pytest.approx(0.82)


def test_two_unanimous_matches_of_different_quality_do_not_tie(plan, corpus) -> None:
    """The failure the real-content run measured: agreement is not confidence.

    Both scenarios have the same rank structure -- one object ranked first by
    both retrievers -- and differ only in how good the match actually is. A
    score that cannot tell them apart cannot carry an abstention threshold.
    """
    strong = hybrid(
        [item("a", 0.31)], [item("a", 0.88)], {"a-rep": 0.88}
    ).retrieve(plan, corpus, 5)
    weak = hybrid(
        [item("a", 0.31)], [item("a", 0.62)], {"a-rep": 0.62}
    ).retrieve(plan, corpus, 5)

    assert strong[0].score > weak[0].score


def test_rrf_still_decides_the_order(plan, corpus) -> None:
    """Scoring changes; ranking does not.

    `b` is second on both lists, so RRF puts it above `c`, which is first on one
    list and absent from the other -- even though `c` has the higher dense
    score. Ordering by the dense score instead would silently turn the hybrid
    into the dense retriever.
    """
    lexical = [item("b", 0.40), item("a", 0.10)]
    dense = [item("c", 0.90), item("b", 0.70)]
    windows = {"a-rep": 0.10, "b-rep": 0.70, "c-rep": 0.90}

    ranked = hybrid(lexical, dense, windows).retrieve(plan, corpus, 5)

    assert [i.object_id for i in ranked][:2] == ["b", "c"]


def test_a_window_the_dense_run_cannot_score_keeps_its_own_score(plan, corpus) -> None:
    """A representation with no vector is skipped by dense, not scored zero.

    Falling back to zero would push a lexical-only hit below every floor and
    turn a missing embedding into an abstention.
    """
    lexical = [item("d", 0.44)]
    dense = [item("a", 0.80)]
    windows = {"a-rep": 0.80}

    ranked = hybrid(lexical, dense, windows).retrieve(plan, corpus, 5)
    by_id = {i.object_id: i for i in ranked}

    assert by_id["d"].score == pytest.approx(0.44)
