"""BM25 over representations: the two properties it exists to add."""

from __future__ import annotations

import pytest

from agts.evaluation.corpus import Corpus
from agts.evaluation.fixtures import build_corpus, build_gold_set
from agts.evaluation.planning import plan_for_case
from agts.evaluation.scorer import score
from agts.retrieval import BM25Representations, represent_all


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    base = build_corpus()
    reps = represent_all(base.objects.values(), list(base.blocks.values()))
    return Corpus(
        sources=base.sources,
        blocks=base.blocks,
        objects=base.objects,
        representations={r.representation_id: r for r in reps},
    )


@pytest.fixture(scope="module")
def gold_set():
    return build_gold_set()


def test_scores_are_bounded_and_comparable_across_queries(corpus, gold_set) -> None:
    """Divided by the query's own ceiling. A threshold over raw BM25 is a
    threshold over query length, which is not a property anyone wants to gate."""
    retriever = BM25Representations()
    for case in gold_set.visible:
        plan = plan_for_case(case)
        for item in retriever.retrieve(plan, corpus, 20):
            assert 0.0 < item.score <= 1.0


def test_a_repeated_term_saturates(corpus) -> None:
    """Eight occurrences of one word must not outrank three distinct matches:
    learner queries are mostly distinct words."""
    retriever = BM25Representations()
    idf, frequencies, lengths, average = retriever._build(corpus)
    term = next(iter(idf))
    weight = idf[term]

    def contribution(tf: int) -> float:
        norm = retriever.k1 * (1 - retriever.b + retriever.b * average / average)
        return weight * (tf * (retriever.k1 + 1)) / (tf + norm)

    assert contribution(8) < 4 * contribution(1)


def test_a_long_window_is_not_rewarded_for_length_alone(corpus) -> None:
    retriever = BM25Representations()
    _, _, _, average = retriever._build(corpus)

    def norm(length: float) -> float:
        return retriever.k1 * (1 - retriever.b + retriever.b * length / average)

    assert norm(4 * average) > norm(average) > norm(average / 4)


def test_it_ranks_only_authorised_representations(corpus, gold_set) -> None:
    retriever = BM25Representations()
    for case in gold_set.visible:
        plan = plan_for_case(case)
        allowed = {obj.object_id for obj in corpus.authorised(plan)}
        for item in retriever.retrieve(plan, corpus, 20):
            assert item.object_id in allowed


def test_it_trips_no_invariant(corpus, gold_set) -> None:
    assert score(gold_set, BM25Representations(), corpus).violations.total == 0


def test_an_empty_query_returns_nothing_rather_than_everything(corpus, gold_set) -> None:
    plan = plan_for_case(gold_set.visible[0]).model_copy(update={"query_text": "   "})
    assert BM25Representations().retrieve(plan, corpus, 20) == []
