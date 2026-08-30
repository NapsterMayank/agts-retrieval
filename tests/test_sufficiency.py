"""The sufficiency gate: both tiers, and the reasons it must give."""

from __future__ import annotations

import pytest

from agts.contracts.runtime import RetrievedItem
from agts.evaluation.corpus import Corpus
from agts.evaluation.fixtures import build_corpus, build_gold_set
from agts.evaluation.planning import plan_for_case
from agts.retrieval.sufficiency import SufficiencyGate


class Fixed:
    """A retriever that returns a scripted list, so the gate is tested and not
    the retriever underneath it."""

    def __init__(self, name: str, items: list[RetrievedItem]) -> None:
        self.name = name
        self._items = items

    def retrieve(self, plan, corpus, k):
        return self._items[:k]


def item(object_id: str, score: float) -> RetrievedItem:
    return RetrievedItem(object_id=object_id, block_ids=(f"{object_id}-b",), score=score)


@pytest.fixture()
def plan():
    return plan_for_case(build_gold_set().visible[0])


@pytest.fixture()
def corpus() -> Corpus:
    return build_corpus()


def gate(primary, corroborator, **kwargs) -> SufficiencyGate:
    return SufficiencyGate(primary, corroborator, threshold=0.5, high_confidence=0.8, **kwargs)


def test_below_the_floor_it_abstains_however_well_the_retrievers_agree(plan, corpus) -> None:
    agreed = [item("a", 0.3), item("b", 0.29), item("c", 0.28)]
    decision = gate(Fixed("p", agreed), Fixed("c", agreed)).decide(plan, corpus)
    assert decision.abstained
    assert "below the calibrated floor" in decision.reasons[0]


def test_in_the_band_agreement_decides(plan, corpus) -> None:
    primary = [item("a", 0.6), item("b", 0.55), item("c", 0.5)]
    agreeing = [item("a", 0.6), item("b", 0.55), item("z", 0.5)]
    diverging = [item("x", 0.6), item("y", 0.55), item("z", 0.5)]

    assert gate(Fixed("p", primary), Fixed("c", agreeing)).decide(plan, corpus).answerable
    diverged = gate(Fixed("p", primary), Fixed("c", diverging)).decide(plan, corpus)
    assert diverged.abstained
    assert "named but not taught" in diverged.reasons[0]


def test_above_the_ceiling_corroboration_is_not_required(plan, corpus) -> None:
    """Otherwise the gate abstains on textbook questions purely because two
    retrievers ranked two equally correct sections differently."""
    primary = [item("a", 0.95), item("b", 0.5), item("c", 0.4)]
    diverging = [item("x", 0.9), item("y", 0.5), item("z", 0.4)]
    assert gate(Fixed("p", primary), Fixed("c", diverging)).decide(plan, corpus).answerable


def test_without_a_ceiling_the_strict_gate_applies(plan, corpus) -> None:
    """An operator who omits the ceiling must get the conservative gate, not a
    silently permissive one."""
    primary = [item("a", 0.99), item("b", 0.5), item("c", 0.4)]
    diverging = [item("x", 0.9), item("y", 0.5), item("z", 0.4)]
    strict = SufficiencyGate(Fixed("p", primary), Fixed("c", diverging), threshold=0.5)
    assert strict.decide(plan, corpus).abstained


def test_an_empty_candidate_set_abstains_with_a_reason(plan, corpus) -> None:
    decision = gate(Fixed("p", []), Fixed("c", [])).decide(plan, corpus)
    assert decision.abstained
    assert "authorisation filter" in decision.reasons[0]


def test_an_abstention_returns_no_items(plan, corpus) -> None:
    """A gate whose pack is handed back anyway is advisory, not a gate."""
    primary = [item("a", 0.6), item("b", 0.55), item("c", 0.5)]
    diverging = [item("x", 0.6), item("y", 0.55), item("z", 0.5)]
    assert gate(Fixed("p", primary), Fixed("c", diverging)).retrieve(plan, corpus, 5) == []


def test_the_corroborator_never_changes_what_is_returned(plan, corpus) -> None:
    primary = [item("a", 0.95), item("b", 0.9), item("c", 0.85)]
    other = [item("a", 0.95), item("q", 0.9), item("r", 0.85)]
    returned = gate(Fixed("p", primary), Fixed("c", other)).retrieve(plan, corpus, 5)
    assert [i.object_id for i in returned] == ["a", "b", "c"]
