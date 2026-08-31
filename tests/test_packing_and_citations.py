"""Pack assembly and the citation scorers.

The pack is the boundary the teaching loop sees, so most of this is about what
must be true of it before anything downstream is allowed to read it.
"""

from __future__ import annotations

import pytest

from agts.contracts.common import (
    ApprovalState, AuthorityTier, BlockType, Board, DisclosureClass, Language,
    Modality, ObjectType, PackStatus,
)
from agts.contracts.objects import (
    CurriculumIdentity, LearningObject, Region, SearchRepresentation, SourceBlock, SourceRecord,
)
from agts.contracts.runtime import RetrievedItem
from agts.evaluation.cases import EvalCase, GoldSet
from agts.evaluation.citations import score_citations
from agts.evaluation.corpus import Corpus
from agts.evaluation.planning import plan_for_case
from agts.retrieval.packing import build_pack
from agts.retrieval.sufficiency import SufficiencyDecision

CURRICULUM = CurriculumIdentity(
    board=Board.CBSE, curriculum_version="pilot-0", grade="10",
    subject="science", unit_id="u1", concept_ids=["c1"],
)


def block(index: int, page: int = 1) -> SourceBlock:
    return SourceBlock(
        block_id=f"doc:docling:texts-{index}", source_id="s1", document_id="doc",
        order_index=index, block_type=BlockType.PARAGRAPH,
        region=Region(page=page, x=0.1, y=0.1, width=0.5, height=0.05),
        text=f"Body text number {index}.", parse_strategy="docling", parser_version="1",
    )


@pytest.fixture()
def corpus() -> Corpus:
    blocks = {b.block_id: b for b in (block(0), block(1), block(2, page=2))}
    obj = LearningObject(
        object_id="o1", object_type=ObjectType.DEFINITION, source_id="s1",
        block_ids=list(blocks), curriculum=CURRICULUM, heading_path="1.1 A Section",
        text="body", language=Language.EN, modality=Modality.TEXT,
        authority_tier=AuthorityTier.BOARD_OFFICIAL, disclosure_class=DisclosureClass.PUBLIC,
        composition_version="v1", content_hash="0" * 64,
        approval_state=ApprovalState.QUARANTINED,
    )
    source = SourceRecord(
        source_id="s1", title="T", publisher="NCERT", board=Board.CBSE, edition="2026-27",
        checksum_sha256="a" * 64, authority_tier=AuthorityTier.BOARD_OFFICIAL,
        language=Language.EN, approval_state=ApprovalState.QUARANTINED,
    )

    def rep(number: int, block_ids: list[str]) -> SearchRepresentation:
        return SearchRepresentation(
            representation_id=f"o1:v:{number}", object_id="o1", block_ids=block_ids,
            search_text=" ".join(block_ids), representation_version="v",
            content_hash="0" * 64, heading_path="1.1 A Section",
        )

    return Corpus(
        sources={"s1": source}, blocks=blocks, objects={"o1": obj},
        representations={
            "o1:v:1": rep(1, ["doc:docling:texts-0"]),
            "o1:v:2": rep(2, ["doc:docling:texts-1"]),
            "o1:v:3": rep(3, ["doc:docling:texts-2"]),
        },
    )


@pytest.fixture()
def case() -> EvalCase:
    return EvalCase(
        case_id="c1", query="what is it", grade="10", subject="science",
        question_type="definition", teaching_action="explain", concept_ids=["c1"],
        gold_block_ids=["doc:docling:texts-0", "doc:docling:texts-1"],
    )


def answered(window_scores=None) -> SufficiencyDecision:
    return SufficiencyDecision(
        answerable=True, top_score=0.9, corroboration=2, threshold=0.7,
        items=[RetrievedItem(object_id="o1", block_ids=("doc:docling:texts-0",),
                             score=0.9, representation_id="o1:v:1")],
        window_scores=window_scores or {},
        primary_name="representation-dense",
    )


def pack_for(case, decision, corpus):
    return build_pack(
        plan_for_case(case), decision, corpus,
        pack_id="p1", trace_id="t1", release_manifest_id="unreleased",
    )


def test_an_abstention_still_produces_a_pack_carrying_its_reasons(case, corpus) -> None:
    """Abstention is a successful outcome (§8.4). An empty response and a
    refusal with a stated cause are different things to whoever debugs it."""
    decision = SufficiencyDecision(
        answerable=False, top_score=0.2, corroboration=0, threshold=0.7,
        reasons=("top score 0.200 below the calibrated floor 0.700",),
    )
    pack = pack_for(case, decision, corpus)

    assert pack.status is PackStatus.ABSTAIN
    assert pack.evidence == [] and pack.citations == []
    assert pack.sufficiency.gap_reasons == [decision.reasons[0]]


def test_every_span_resolves_to_a_real_block_and_page(case, corpus) -> None:
    pack = pack_for(case, answered(), corpus)
    for item in pack.evidence:
        for block_id in item.span.block_ids:
            assert block_id in corpus.blocks
        assert item.span.page == corpus.blocks[item.span.block_ids[0]].region.page
        assert item.span.edition == "2026-27"


def test_citations_resolve_inside_the_pack(case, corpus) -> None:
    """The contract refuses a dangling citation; this asserts the builder never
    produces one, rather than relying on the exception to be seen."""
    pack = pack_for(case, answered(), corpus)
    available = {item.object_id for item in pack.evidence}
    assert all(c.object_id in available for c in pack.citations)


def test_sibling_windows_that_clear_the_floor_are_packed(case, corpus) -> None:
    """31 of 31 missing gold blocks sat in a sibling window of a section the
    pack had already chosen."""
    pack = pack_for(case, answered({"o1:v:1": 0.9, "o1:v:2": 0.8, "o1:v:3": 0.2}), corpus)
    packed = {b for item in pack.evidence for b in item.span.block_ids}

    assert "doc:docling:texts-1" in packed, "sibling above the floor was dropped"
    assert "doc:docling:texts-2" not in packed, "sibling below the floor was packed"


def test_without_window_scores_only_the_ranked_window_is_packed(case, corpus) -> None:
    """A retriever that cannot score windows must not have siblings guessed for it."""
    pack = pack_for(case, answered(), corpus)
    packed = {b for item in pack.evidence for b in item.span.block_ids}
    assert packed == {"doc:docling:texts-0"}


def test_the_evidence_item_names_the_retriever_that_produced_it(case, corpus) -> None:
    pack = pack_for(case, answered(), corpus)
    assert pack.evidence[0].generators == ["representation-dense"]


def test_completeness_counts_gold_blocks_and_ignores_abstentions(case, corpus) -> None:
    gold_set = GoldSet(gold_set_id="g", cases=[case])
    complete = pack_for(case, answered({"o1:v:1": 0.9, "o1:v:2": 0.8}), corpus)
    partial = pack_for(case, answered(), corpus)

    assert score_citations(gold_set, {"c1": complete}, corpus).completeness == 1.0
    assert score_citations(gold_set, {"c1": partial}, corpus).completeness == 0.5

    abstained = pack_for(
        case,
        SufficiencyDecision(answerable=False, top_score=0.1, corroboration=0,
                            threshold=0.7, reasons=("below floor",)),
        corpus,
    )
    report = score_citations(gold_set, {"c1": abstained}, corpus)
    assert report.abstained == 1
    assert report.completeness is None, "an abstention is not a citation failure"


def test_resolution_is_a_hard_gate(case, corpus) -> None:
    gold_set = GoldSet(gold_set_id="g", cases=[case])
    report = score_citations(gold_set, {"c1": pack_for(case, answered(), corpus)}, corpus)
    assert report.resolution == 1.0
    assert "citation ID resolution" not in " ".join(report.failing_gates())


def test_completeness_below_the_floor_is_reported_as_a_failing_gate(case, corpus) -> None:
    gold_set = GoldSet(gold_set_id="g", cases=[case])
    report = score_citations(gold_set, {"c1": pack_for(case, answered(), corpus)}, corpus)
    assert any("completeness" in line for line in report.failing_gates())


def test_delivered_recall_counts_what_the_pack_carried_not_what_ranked(case, corpus) -> None:
    """A case can miss `recall_at_pack` and still receive its evidence.

    maths-004 is the real example: the gold block sits in window 2 of a section
    whose window 1 outranked it, so the retriever's ranked list misses, and the
    pack contains it anyway because sibling expansion runs after ranking. The
    ruler has to be able to say which of the two happened.
    """
    gold_set = GoldSet(gold_set_id="g", cases=[case])

    ranked_only = pack_for(case, answered(), corpus)
    with_siblings = pack_for(case, answered({"o1:v:1": 0.9, "o1:v:2": 0.8}), corpus)

    # Both deliver *some* gold, so delivered recall is 1.0 for each...
    assert score_citations(gold_set, {"c1": ranked_only}, corpus).delivered_recall == 1.0
    assert score_citations(gold_set, {"c1": with_siblings}, corpus).delivered_recall == 1.0
    # ...while completeness separates them, which is the point of having both.
    assert score_citations(gold_set, {"c1": ranked_only}, corpus).completeness == 0.5
    assert score_citations(gold_set, {"c1": with_siblings}, corpus).completeness == 1.0


def test_delivered_recall_is_zero_when_the_pack_carries_no_gold(case, corpus) -> None:
    gold_set = GoldSet(gold_set_id="g", cases=[case])
    decision = answered()
    decision = SufficiencyDecision(
        answerable=True, top_score=0.9, corroboration=2, threshold=0.7,
        items=[RetrievedItem(object_id="o1", block_ids=("doc:docling:texts-2",), score=0.9,
                             representation_id="o1:v:3")],
    )
    pack = pack_for(case, decision, corpus)
    assert score_citations(gold_set, {"c1": pack}, corpus).delivered_recall == 0.0


def test_a_block_whose_content_is_latex_is_served_not_just_cited(corpus, case) -> None:
    """Reported by an outside reviewer and reproduced. The chunker makes a block
    searchable on `text or latex`; the pack rendered `text` alone. A latex-only
    formula was therefore ranked on its content, cited in the span, and served as
    an empty line -- prose promising a formula, no formula, and a citation
    vouching for the block that held it."""
    from agts.contracts.objects import Region, SourceBlock

    latex_only = SourceBlock(
        block_id="doc:docling:texts-9", source_id="s1", document_id="doc", order_index=9,
        block_type=BlockType.FORMULA,
        region=Region(page=1, x=0.1, y=0.1, width=0.5, height=0.05),
        text=None, latex="x = (-b +- sqrt(b^2-4ac)) / 2a",
        parse_strategy="docling", parser_version="1",
    )
    corpus.blocks[latex_only.block_id] = latex_only
    decision = SufficiencyDecision(
        answerable=True, top_score=0.9, corroboration=2, threshold=0.7,
        items=[RetrievedItem(object_id="o1", block_ids=("doc:docling:texts-0", latex_only.block_id),
                             score=0.9, representation_id="o1:v:1")],
    )
    pack = pack_for(case, decision, corpus)
    assert "sqrt" in pack.evidence[0].text, "the formula was cited but not served"


def test_two_required_slots_of_the_same_role_are_not_satisfied_by_one_item(corpus, case) -> None:
    """The gap check keyed on role, so a plan asking twice received once and the
    pack still reported SUFFICIENT."""
    from agts.contracts.common import EvidenceRole
    from agts.contracts.runtime import EvidenceSlot

    plan = plan_for_case(case)
    two_slots = [
        EvidenceSlot(slot_id="s1", role=EvidenceRole.EXPLANATION, required=True),
        EvidenceSlot(slot_id="s2", role=EvidenceRole.EXPLANATION, required=True),
    ]
    plan = plan.model_copy(update={"evidence_slots": two_slots})
    pack = build_pack(plan, answered(), corpus, pack_id="p", trace_id="t",
                      release_manifest_id="m")

    assert pack.status is not PackStatus.SUFFICIENT
    assert any("s2" in reason for reason in pack.sufficiency.gap_reasons)
