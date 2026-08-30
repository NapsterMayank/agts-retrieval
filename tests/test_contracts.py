"""Contract invariants (build guide §6.2, §6.3).

Each test names the gate in `docs/01-acceptance-gates.md` it protects. The point
is that a violation is a construction error at the contract boundary, not
something the evaluation suite has to notice three stages later.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agts.contracts import (
    ApprovalState,
    AssessmentState,
    AuthorityTier,
    BlockType,
    Board,
    Citation,
    DisclosureClass,
    DisclosurePolicy,
    EvidenceItem,
    EvidencePack,
    EvidenceRole,
    FallbackPolicy,
    Language,
    LearningObject,
    Modality,
    ObjectType,
    PackStatus,
    Region,
    RightsRecord,
    SourceBlock,
    SourceRecord,
    SourceSpan,
    SufficiencyResult,
    TeachingAction,
    VerificationResult,
)
from agts.contracts.objects import CurriculumIdentity
from agts.evaluation.cases import EvalCase
from agts.evaluation.planning import plan_for_case

NOW = datetime(2026, 8, 24, tzinfo=UTC)
HASH = "0" * 64


def _rights() -> RightsRecord:
    return RightsRecord(
        owner="fixture",
        legal_basis="test",
        permits_storage=True,
        permits_transformation=True,
        permits_display=True,
        permits_model_processing=True,
        approved_by="a-human",
        approved_at=NOW,
        evidence_uri="fixture://record",
    )


def _source_kwargs(**overrides):
    base = dict(
        source_id="s1",
        title="t",
        publisher="p",
        edition="e",
        checksum_sha256=HASH,
        authority_tier=AuthorityTier.BOARD_OFFICIAL,
        language=Language.EN,
    )
    base.update(overrides)
    return base


# --------------------------------------------------------------------------
# Gate: approved-source and lineage resolution = 100%
# --------------------------------------------------------------------------


def test_approved_source_requires_a_rights_record() -> None:
    """§5: verbal assurance is not a rights record."""
    with pytest.raises(ValidationError, match="RightsRecord"):
        SourceRecord(**_source_kwargs(approval_state=ApprovalState.APPROVED, scanned_clean_at=NOW))


def test_approved_source_requires_a_completed_scan() -> None:
    """§7.1: scan before any parser or model sees the file."""
    with pytest.raises(ValidationError, match="scan"):
        SourceRecord(
            **_source_kwargs(approval_state=ApprovalState.APPROVED, rights=_rights())
        )


def test_quarantined_is_the_default() -> None:
    assert SourceRecord(**_source_kwargs()).approval_state is ApprovalState.QUARANTINED


def test_block_must_carry_something() -> None:
    """A block with no text, latex or image cannot anchor a gold label."""
    with pytest.raises(ValidationError, match="anchor a gold label"):
        SourceBlock(
            block_id="b1",
            source_id="s1",
            document_id="d1",
            order_index=0,
            block_type=BlockType.PARAGRAPH,
            region=Region(page=1, x=0.0, y=0.0, width=1.0, height=1.0),
            parse_strategy="fixture",
            parser_version="0",
        )


# --------------------------------------------------------------------------
# Gate: graded-solution leakage = 0
# --------------------------------------------------------------------------


def test_a_solution_object_may_not_be_public() -> None:
    """Answer protection is structural, not a downstream filter."""
    with pytest.raises(ValidationError, match="may not be PUBLIC"):
        LearningObject(
            object_id="o1",
            object_type=ObjectType.ASSESSMENT_SOLUTION,
            source_id="s1",
            block_ids=["b1"],
            curriculum=CurriculumIdentity(
                board=Board.CBSE,
                curriculum_version="v1",
                grade="10",
                subject="science",
                unit_id="u1",
                concept_ids=["c1"],
            ),
            heading_path="h",
            text="t",
            language=Language.EN,
            modality=Modality.TEXT,
            authority_tier=AuthorityTier.BOARD_OFFICIAL,
            disclosure_class=DisclosureClass.PUBLIC,
            composition_version="0",
            content_hash=HASH,
        )


def test_a_plan_may_not_raise_its_own_disclosure_ceiling() -> None:
    """A graded turn cannot promote itself to seeing solutions."""
    with pytest.raises(ValidationError, match="never raise"):
        DisclosurePolicy(
            assessment_state=AssessmentState.GRADED,
            max_disclosure=DisclosureClass.SOLUTION,
        )


def test_a_graded_plan_may_not_request_protected_evidence() -> None:
    case = EvalCase(
        case_id="c-graded",
        query="q",
        grade="10",
        subject="science",
        question_type="single_hop",
        teaching_action=TeachingAction.WORKED_EXAMPLE,
        assessment_state=AssessmentState.GRADED,
        concept_ids=["c1"],
        gold_block_ids=["b1"],
    )
    plan = plan_for_case(case)
    # The planner drops the banned role rather than emitting an invalid plan.
    assert all(s.role is not EvidenceRole.WORKED_EXAMPLE for s in plan.evidence_slots)
    assert plan.disclosure.max_disclosure is DisclosureClass.PUBLIC


# --------------------------------------------------------------------------
# Gate: citation ID resolution = 100%
# --------------------------------------------------------------------------


def _pack(**overrides) -> EvidencePack:
    item = EvidenceItem(
        object_id="o1",
        slot_id="s0",
        role=EvidenceRole.DEFINITION,
        text="t",
        heading_path="h",
        span=SourceSpan(source_id="s1", edition="e", block_ids=["b1"], page=1),
        authority_tier=AuthorityTier.BOARD_OFFICIAL,
        disclosure_class=DisclosureClass.PUBLIC,
        generators=["lexical"],
    )
    passing = SufficiencyResult(
        authority=True,
        coverage=True,
        curriculum_fit=True,
        pedagogical_fit=True,
        no_conflict=True,
        freshness=True,
        disclosure=True,
        modality=True,
    )
    base = dict(
        pack_id="p1",
        plan_id="pl1",
        interaction_id="i1",
        status=PackStatus.SUFFICIENT,
        evidence=[item],
        citations=[Citation(citation_id="c1", object_id="o1", char_offsets=(0, 1))],
        sufficiency=passing,
        release_manifest_id="m1",
        trace_id="t1",
    )
    base.update(overrides)
    return EvidencePack(**base)


def test_a_valid_pack_constructs() -> None:
    assert _pack().status is PackStatus.SUFFICIENT


def test_a_citation_outside_the_pack_is_rejected() -> None:
    with pytest.raises(ValidationError, match="absent from the pack"):
        _pack(citations=[Citation(citation_id="c9", object_id="o-missing", char_offsets=(0, 1))])


def test_sufficient_status_requires_the_gate_to_have_passed() -> None:
    failing = SufficiencyResult(
        authority=True,
        coverage=False,
        curriculum_fit=True,
        pedagogical_fit=True,
        no_conflict=True,
        freshness=True,
        disclosure=True,
        modality=True,
        gap_reasons=["no source span for claim 2"],
    )
    with pytest.raises(ValidationError, match="did not pass"):
        _pack(sufficiency=failing)


# --------------------------------------------------------------------------
# Gate: supported claims >= 95%, no silent stripping
# --------------------------------------------------------------------------


def test_verification_cannot_report_pass_while_a_gate_fails() -> None:
    """§9.3: do not silently strip sentences and report success."""
    with pytest.raises(ValidationError, match="never be stripped and passed"):
        VerificationResult(
            verification_id="v1",
            interaction_id="i1",
            evidence_sufficient=True,
            citations_resolve=True,
            claims_supported=False,
            math_proof_ok=True,
            child_safe=True,
            accessible=True,
            no_answer_leakage=True,
            policy_compliant=True,
            unsupported_claims=["the sky is green"],
            action_taken="pass",
        )


def test_verification_may_report_a_downgrade() -> None:
    result = VerificationResult(
        verification_id="v2",
        interaction_id="i1",
        evidence_sufficient=True,
        citations_resolve=True,
        claims_supported=False,
        math_proof_ok=True,
        child_safe=True,
        accessible=True,
        no_answer_leakage=True,
        policy_compliant=True,
        unsupported_claims=["the sky is green"],
        action_taken="abstain",
    )
    assert result.passed is False


# --------------------------------------------------------------------------
# Gate: abstention behaviour
# --------------------------------------------------------------------------


def test_fallback_may_not_terminate_in_an_unsafe_state() -> None:
    with pytest.raises(ValidationError, match="terminal safe outcome"):
        FallbackPolicy(on_exhausted=PackStatus.SUFFICIENT)


def test_only_one_corrective_retrieval_is_allowed() -> None:
    with pytest.raises(ValidationError):
        FallbackPolicy(max_corrective_retrievals=2)


# --------------------------------------------------------------------------
# Gold set integrity
# --------------------------------------------------------------------------


def test_an_answerable_case_must_carry_gold_blocks() -> None:
    with pytest.raises(ValidationError, match="no gold blocks"):
        EvalCase(
            case_id="c1",
            query="q",
            grade="10",
            subject="science",
            question_type="single_hop",
            teaching_action=TeachingAction.EXPLAIN,
            concept_ids=["c1"],
            gold_block_ids=[],
            answerable=True,
        )


def test_an_unanswerable_case_may_not_carry_gold_blocks() -> None:
    with pytest.raises(ValidationError, match="carries gold blocks"):
        EvalCase(
            case_id="c2",
            query="q",
            grade="10",
            subject="science",
            question_type="single_hop",
            teaching_action=TeachingAction.EXPLAIN,
            concept_ids=["c1"],
            gold_block_ids=["b1"],
            answerable=False,
        )


def test_misconception_correction_requires_a_hypothesis() -> None:
    case = EvalCase(
        case_id="c3",
        query="q",
        grade="10",
        subject="science",
        question_type="misconception",
        teaching_action=TeachingAction.MISCONCEPTION_CORRECTION,
        concept_ids=["c1"],
        gold_block_ids=["b1"],
    )
    assert plan_for_case(case).misconception_hypothesis_id is not None
