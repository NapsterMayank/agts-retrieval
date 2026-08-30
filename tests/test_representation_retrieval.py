"""Retrieval over representations, and the authorisation boundary underneath it.

A child unit is a new way to reach content. If authorisation is not resolved
through the parent, representations become the hole in §5 — so most of this file
is about what the retriever must *not* return.
"""

from __future__ import annotations

import pytest

from agts.evaluation.corpus import Corpus
from agts.evaluation.fixtures import build_corpus, build_gold_set
from agts.evaluation.planning import plan_for_case
from agts.evaluation.scorer import score
from agts.retrieval import RepresentationKeyword, represent_all


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


def test_every_object_is_represented(corpus) -> None:
    represented = {rep.object_id for rep in corpus.representations.values()}
    assert represented == set(corpus.objects)


def test_representations_of_unauthorised_objects_are_never_ranked(corpus, gold_set) -> None:
    """The parent decides. A quarantined source, another tenant's material and a
    wrong-grade passage all stay out, however well their text matches."""
    retriever = RepresentationKeyword()
    for case in gold_set.visible:
        plan = plan_for_case(case)
        allowed = {obj.object_id for obj in corpus.authorised(plan)}
        for item in retriever.retrieve(plan, corpus, 20):
            assert item.object_id in allowed


def test_a_returned_item_claims_only_the_blocks_of_its_window(corpus, gold_set) -> None:
    """Claiming the whole parent would score a recall hit for evidence the pack
    never surfaced."""
    retriever = RepresentationKeyword()
    plan = plan_for_case(gold_set.visible[0])
    for item in retriever.retrieve(plan, corpus, 20):
        rep = corpus.representations[item.representation_id]
        assert tuple(rep.block_ids) == item.block_ids
        parent = corpus.objects[item.object_id]
        assert set(rep.block_ids) <= set(parent.block_ids)


def test_one_item_per_parent_object(corpus, gold_set) -> None:
    """Five windows of one section are not five pieces of evidence."""
    retriever = RepresentationKeyword()
    plan = plan_for_case(gold_set.visible[0])
    ids = [item.object_id for item in retriever.retrieve(plan, corpus, 20)]
    assert len(ids) == len(set(ids))


def test_it_trips_no_invariant_on_the_fixture_traps(corpus, gold_set) -> None:
    report = score(gold_set, RepresentationKeyword(), corpus)
    assert report.violations.total == 0


def test_it_reports_less_evidence_per_pack_than_object_level_retrieval(corpus, gold_set) -> None:
    """The reason the unit changed. Recall is not comparable between units
    without this number beside it."""
    from agts.evaluation.retrievers import KeywordBaseline

    windows = score(gold_set, RepresentationKeyword(), corpus)
    objects = score(gold_set, KeywordBaseline(), corpus)
    assert windows.blocks_per_pack is not None
    assert objects.blocks_per_pack is not None
    assert windows.blocks_per_pack <= objects.blocks_per_pack
