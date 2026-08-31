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


def teaching_corpus():
    """Two objects: one the curriculum classifies as a definition, one not."""
    from agts.contracts.common import (
        ApprovalState, AuthorityTier, Board, DisclosureClass, Language, Modality, ObjectType,
    )
    from agts.contracts.objects import CurriculumIdentity, LearningObject

    curriculum = CurriculumIdentity(
        board=Board.CBSE, curriculum_version="pilot-0", grade="10",
        subject="science", unit_id="u1", concept_ids=["c1"],
    )

    def make(object_id: str, object_type: ObjectType, heading: str) -> LearningObject:
        return LearningObject(
            object_id=object_id, object_type=object_type, source_id="s1",
            block_ids=[f"{object_id}-b"], curriculum=curriculum, heading_path=heading,
            text="body", language=Language.EN, modality=Modality.TEXT,
            authority_tier=AuthorityTier.BOARD_OFFICIAL,
            disclosure_class=DisclosureClass.PUBLIC, composition_version="v1",
            content_hash="0" * 64, approval_state=ApprovalState.QUARANTINED,
        )

    return Corpus(objects={
        "definition": make("definition", ObjectType.DEFINITION, "1.2.2 Decomposition Reaction"),
        "prose": make("prose", ObjectType.EXPLANATION, "4.1 Introduction"),
        "other": make("other", ObjectType.EXPLANATION, "E X E R C I S E S"),
    })


def test_weak_agreement_is_enough_when_the_shared_object_is_a_definition(plan) -> None:
    """"What is a decomposition reaction?": the retrievers order things
    differently but both surface the definition section. Requiring two shared
    objects there refuses a textbook question."""
    corpus = teaching_corpus()
    primary = [item("definition", 0.6), item("other", 0.55), item("prose", 0.5)]
    corroborator = [item("other", 0.6), item("definition", 0.55), item("y", 0.5)]

    decision = gate(Fixed("p", primary), Fixed("c", corroborator)).decide(plan, corpus)
    assert decision.answerable
    assert decision.anchored_on_teaching_object


def test_a_definition_ranked_first_but_not_shared_does_not_anchor(plan) -> None:
    """Reported by an outside review, and it was right: the earlier rule asked
    only whether *either* retriever ranked some teaching object first, so an
    unrelated definition at rank 1 could bless a match the two retrievers
    disagreed about."""
    corpus = teaching_corpus()
    primary = [item("definition", 0.6), item("other", 0.55), item("z", 0.5)]
    corroborator = [item("other", 0.6), item("x", 0.55), item("y", 0.5)]

    decision = gate(Fixed("p", primary), Fixed("c", corroborator)).decide(plan, corpus)
    assert not decision.anchored_on_teaching_object
    assert decision.abstained


def test_the_gate_refuses_a_configuration_that_disables_its_own_conditions() -> None:
    """Each of these silently switches a condition off rather than failing."""
    args = (Fixed("p", []), Fixed("c", []))
    with pytest.raises(ValueError):
        SufficiencyGate(*args, threshold=0.5, min_corroboration=0)
    with pytest.raises(ValueError):
        SufficiencyGate(*args, threshold=0.5, depth=0)
    with pytest.raises(ValueError):
        SufficiencyGate(*args, threshold=0.8, high_confidence=0.5)


def test_weak_agreement_on_prose_alone_still_abstains(plan) -> None:
    """"Completing the square" has no definition section to anchor on: both
    retrievers land on the introduction that names it in passing."""
    corpus = teaching_corpus()
    primary = [item("prose", 0.6), item("other", 0.55), item("z", 0.5)]
    corroborator = [item("prose", 0.6), item("q", 0.55), item("r", 0.5)]
    # They share one object, and it is prose, so the anchor does not apply;
    # sharing only one object is below the corroboration floor.
    corroborator = [item("y", 0.6), item("prose", 0.55), item("r", 0.5)]

    decision = gate(Fixed("p", primary), Fixed("c", corroborator)).decide(plan, corpus)
    assert decision.abstained
    assert not decision.anchored_on_teaching_object


def test_the_anchor_still_requires_some_agreement(plan) -> None:
    """A definition ranked first with zero overlap is one retriever's opinion."""
    corpus = teaching_corpus()
    primary = [item("definition", 0.6), item("a", 0.55), item("b", 0.5)]
    corroborator = [item("x", 0.6), item("y", 0.55), item("z", 0.5)]

    assert gate(Fixed("p", primary), Fixed("c", corroborator)).decide(plan, corpus).abstained


def test_a_ceiling_equal_to_the_floor_is_refused() -> None:
    """Reported by a second outside reviewer. An equal ceiling empties the band,
    so every score above the floor skips corroboration -- a gate that looks
    configured with one condition silently off."""
    args = (Fixed("p", []), Fixed("c", []))
    with pytest.raises(ValueError):
        SufficiencyGate(*args, threshold=0.7, high_confidence=0.7)
