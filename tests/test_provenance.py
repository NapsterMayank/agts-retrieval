"""Release manifests, traces, and the section 14 lineage gate."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agts.contracts.common import (
    ApprovalState, AuthorityTier, BlockType, Board, DisclosureClass, Language,
    Modality, ObjectType, PackStatus,
)
from agts.contracts.objects import (
    CurriculumIdentity, LearningObject, Region, SourceBlock, SourceRecord,
)
from agts.contracts.runtime import RetrievedItem
from agts.evaluation.cases import EvalCase
from agts.evaluation.corpus import Corpus
from agts.evaluation.planning import plan_for_case
from agts.retrieval.packing import build_pack
from agts.retrieval.provenance import (
    build_manifest, build_trace, corpus_checksum, lineage_failures,
)
from agts.retrieval.sufficiency import SufficiencyDecision

CURRICULUM = CurriculumIdentity(
    board=Board.CBSE, curriculum_version="pilot-0", grade="10",
    subject="science", unit_id="u1", concept_ids=["c1"],
)
VERSIONS = {"representation": "block-window-v2", "embedding": "voyage-3"}


def make_corpus(*, object_id: str = "o1", content_hash: str = "0" * 64) -> Corpus:
    block = SourceBlock(
        block_id="b1", source_id="s1", document_id="doc", order_index=0,
        block_type=BlockType.PARAGRAPH,
        region=Region(page=1, x=0.1, y=0.1, width=0.5, height=0.05),
        text="Body.", parse_strategy="docling", parser_version="1",
    )
    source = SourceRecord(
        source_id="s1", title="T", publisher="NCERT", board=Board.CBSE, edition="2026-27",
        checksum_sha256="a" * 64, authority_tier=AuthorityTier.BOARD_OFFICIAL,
        language=Language.EN, approval_state=ApprovalState.QUARANTINED,
    )
    obj = LearningObject(
        object_id=object_id, object_type=ObjectType.DEFINITION, source_id="s1",
        block_ids=["b1"], curriculum=CURRICULUM, heading_path="1.1 Section",
        text="body", language=Language.EN, modality=Modality.TEXT,
        authority_tier=AuthorityTier.BOARD_OFFICIAL, disclosure_class=DisclosureClass.PUBLIC,
        composition_version="v1", content_hash=content_hash,
        approval_state=ApprovalState.QUARANTINED,
    )
    return Corpus(sources={"s1": source}, blocks={"b1": block}, objects={object_id: obj})


def manifest_for(corpus: Corpus, manifest_id: str = "rm-1"):
    return build_manifest(
        corpus, manifest_id=manifest_id, created_at=datetime(2026, 8, 30, tzinfo=UTC),
        commit_sha="abc123", versions=VERSIONS,
    )


@pytest.fixture()
def case() -> EvalCase:
    return EvalCase(
        case_id="c1", query="what is it", grade="10", subject="science",
        question_type="definition", teaching_action="explain", concept_ids=["c1"],
        gold_block_ids=["b1"],
    )


def decision(*, answerable: bool = True, object_id: str = "o1") -> SufficiencyDecision:
    if not answerable:
        return SufficiencyDecision(
            answerable=False, top_score=0.1, corroboration=0, threshold=0.7,
            reasons=("top score below the floor",),
        )
    return SufficiencyDecision(
        answerable=True, top_score=0.9, corroboration=2, threshold=0.7,
        high_confidence=0.85, primary_name="representation-dense",
        items=[RetrievedItem(object_id=object_id, block_ids=("b1",), score=0.9)],
    )


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------


def test_the_checksum_follows_the_content_not_the_description() -> None:
    """A manifest written by hand agrees with the corpus exactly until the first
    time it does not."""
    assert corpus_checksum(make_corpus()) == corpus_checksum(make_corpus())
    assert corpus_checksum(make_corpus()) != corpus_checksum(make_corpus(content_hash="1" * 64))


def test_the_checksum_is_order_independent() -> None:
    corpus = make_corpus()
    reordered = Corpus(
        sources=dict(reversed(list(corpus.sources.items()))),
        blocks=corpus.blocks,
        objects=dict(reversed(list(corpus.objects.items()))),
    )
    assert corpus_checksum(corpus) == corpus_checksum(reordered)


def test_a_manifest_is_unsigned_until_a_human_signs_it() -> None:
    """Calling it approved because it exists is how a release gate becomes
    decorative."""
    assert manifest_for(make_corpus()).approved_by == []


# --------------------------------------------------------------------------
# Lineage (section 14)
# --------------------------------------------------------------------------


def test_a_pack_from_the_serving_release_passes(case) -> None:
    corpus = make_corpus()
    manifest = manifest_for(corpus)
    pack = build_pack(plan_for_case(case), decision(), corpus, pack_id="p1",
                      trace_id="t1", release_manifest_id=manifest.release_manifest_id)
    assert lineage_failures(pack, manifest, corpus) == []


def test_citing_an_object_outside_the_release_fails(case) -> None:
    """The failure this gate exists for: a plausible answer whose evidence
    belongs to a corpus nobody released."""
    serving = manifest_for(make_corpus(object_id="o-released"))
    other = make_corpus(object_id="o-unreleased")
    pack = build_pack(plan_for_case(case), decision(object_id="o-unreleased"), other,
                      pack_id="p1", trace_id="t1",
                      release_manifest_id=serving.release_manifest_id)

    failures = lineage_failures(pack, serving, other)
    assert any("not in the release manifest" in f for f in failures)


def test_a_pack_claiming_a_different_manifest_fails(case) -> None:
    corpus = make_corpus()
    pack = build_pack(plan_for_case(case), decision(), corpus, pack_id="p1",
                      trace_id="t1", release_manifest_id="rm-something-else")
    failures = lineage_failures(pack, manifest_for(corpus), corpus)
    assert any("claims manifest" in f for f in failures)


def test_an_abstention_has_no_lineage_to_resolve(case) -> None:
    corpus = make_corpus()
    manifest = manifest_for(corpus)
    pack = build_pack(plan_for_case(case), decision(answerable=False), corpus,
                      pack_id="p1", trace_id="t1",
                      release_manifest_id=manifest.release_manifest_id)
    assert pack.status is PackStatus.ABSTAIN
    assert lineage_failures(pack, manifest, corpus) == []


# --------------------------------------------------------------------------
# Trace
# --------------------------------------------------------------------------


def test_the_trace_names_the_thresholds_that_produced_the_decision(case) -> None:
    """A number that cannot name the code, the corpus and the thresholds behind
    it is not evidence."""
    corpus = make_corpus()
    manifest = manifest_for(corpus)
    trace = build_trace(plan_for_case(case), decision(), corpus,
                        trace_id="t1", manifest=manifest)

    assert trace.versions["abstain_threshold"] == "0.700000"
    assert trace.versions["high_confidence"] == "0.850000"
    assert trace.versions["primary_retriever"] == "representation-dense"
    assert trace.versions["corpus_checksum"] == manifest.checksum_sha256
    assert trace.versions["representation"] == "block-window-v2"


def test_rejected_candidates_are_recorded_with_a_reason(case) -> None:
    """A trace of only the winners cannot answer the question anyone actually
    asks of it: why was that passage not used."""
    corpus = make_corpus()
    many = SufficiencyDecision(
        answerable=True, top_score=0.9, corroboration=2, threshold=0.7,
        primary_name="representation-dense",
        items=[RetrievedItem(object_id=f"o{i}", block_ids=("b1",), score=0.9 - i / 100)
               for i in range(8)],
    )
    trace = build_trace(plan_for_case(case), many, corpus, trace_id="t1",
                        manifest=manifest_for(corpus), k_pack=5)

    admitted = [c for c in trace.candidates if c.admitted]
    rejected = [c for c in trace.candidates if not c.admitted]
    assert len(admitted) == 5
    assert len(rejected) == 3
    assert all("below the pack cut" in c.rejection_reason for c in rejected)


def test_an_abstained_trace_says_why_every_candidate_was_dropped(case) -> None:
    corpus = make_corpus()
    abstained = SufficiencyDecision(
        answerable=False, top_score=0.4, corroboration=1, threshold=0.7,
        primary_name="representation-dense",
        reasons=("top score 0.400 below the calibrated floor 0.700",),
        items=[RetrievedItem(object_id="o1", block_ids=("b1",), score=0.4)],
    )
    trace = build_trace(plan_for_case(case), abstained, corpus, trace_id="t1",
                        manifest=manifest_for(corpus))

    assert all(not c.admitted for c in trace.candidates)
    assert "pack abstained" in trace.candidates[0].rejection_reason


def test_the_trace_records_the_evaluation_licence_as_a_filter(case) -> None:
    """A run over quarantined content must say so in its own trace, not only in
    the report that quotes it."""
    from datetime import date

    from agts.evaluation.corpus import EvaluationLicence

    base = make_corpus()
    licensed = Corpus(
        sources=base.sources, blocks=base.blocks, objects=base.objects,
        evaluation_licence=EvaluationLicence(
            reason="quarantined pilot chapters", granted_by="tests",
            granted_on=date(2026, 8, 30), source_ids=("s1",),
        ),
    )
    trace = build_trace(plan_for_case(case), decision(), licensed, trace_id="t1",
                        manifest=manifest_for(licensed))
    assert any("evaluation_licence" in f for f in trace.filters_applied)
