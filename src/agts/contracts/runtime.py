"""Runtime contracts (build guide §6.3).

    QueryPlan  -> EvidencePack -> TeachingPlan -> VerificationResult
                       |                              |
                  RetrievalTrace                 LearningEvidence

Every invariant that a gate in `docs/01-acceptance-gates.md` depends on is
enforced here as a validator, so a violation is a construction error rather than
something the evaluation suite has to catch later.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import (
    DISCLOSURE_RANK,
    AssessmentState,
    AuthorityTier,
    Board,
    DisclosureClass,
    EvidenceRole,
    Language,
    LearnerStateClass,
    Modality,
    PackStatus,
    Role,
    TeachingAction,
)


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)


#: Disclosure ceiling implied by what the learner is doing. The pedagogy
#: controller may lower a ceiling, never raise it.
CEILING_BY_ASSESSMENT_STATE: dict[AssessmentState, DisclosureClass] = {
    AssessmentState.LEARN: DisclosureClass.WORKED_STEP,
    AssessmentState.GUIDED_PRACTICE: DisclosureClass.HINT_GATED,
    AssessmentState.HOMEWORK: DisclosureClass.HINT_GATED,
    AssessmentState.GRADED: DisclosureClass.PUBLIC,
    AssessmentState.POST_SUBMISSION: DisclosureClass.SOLUTION,
    AssessmentState.REVISION: DisclosureClass.WORKED_STEP,
}


# --------------------------------------------------------------------------
# Plan
# --------------------------------------------------------------------------


class LearnerScope(Frozen):
    """The minimum authorised learner context. Deliberately not a profile."""

    tenant_id: str
    pseudonymous_learner_id: str
    role: Role
    learner_state_class: LearnerStateClass
    entitlements: list[str] = Field(default_factory=list)


class CurriculumScope(Frozen):
    board: Board
    curriculum_version: str
    grade: str
    subject: str
    unit_id: str | None = None
    concept_ids: list[str] = Field(min_length=1)


class DisclosurePolicy(Frozen):
    """Set by the deterministic pedagogy controller, never by a model."""

    assessment_state: AssessmentState
    max_disclosure: DisclosureClass
    forbidden_object_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ceiling_is_not_raised(self) -> DisclosurePolicy:
        implied = CEILING_BY_ASSESSMENT_STATE[self.assessment_state]
        if DISCLOSURE_RANK[self.max_disclosure] > DISCLOSURE_RANK[implied]:
            raise ValueError(
                f"max_disclosure={self.max_disclosure} exceeds the ceiling "
                f"{implied} implied by assessment_state={self.assessment_state}. "
                "A plan may lower a ceiling, never raise it."
            )
        return self


class EvidenceSlot(Frozen):
    """A typed requirement the bundle composer must fill.

    A slot is what makes retrieval action-specific rather than topical: the
    composer fills slots, the reranker only orders candidates.
    """

    slot_id: str
    role: EvidenceRole
    required: bool = True
    min_items: int = Field(default=1, ge=0)
    max_items: int = Field(default=1, ge=1)
    min_authority: AuthorityTier = AuthorityTier.LICENSED_PUBLISHER
    modality: Modality | None = None

    @model_validator(mode="after")
    def _bounds_are_coherent(self) -> EvidenceSlot:
        if self.min_items > self.max_items:
            raise ValueError(f"slot {self.slot_id}: min_items exceeds max_items")
        if self.required and self.min_items < 1:
            raise ValueError(f"slot {self.slot_id}: required slot needs min_items >= 1")
        return self


class FallbackPolicy(Frozen):
    """What happens when the sufficiency gate fails.

    Lowering a threshold to avoid an empty result is prohibited (§8.4), so there
    is no field for it.
    """

    max_corrective_retrievals: int = Field(default=1, ge=0, le=1)
    allow_clarify: bool = True
    allow_action_downgrade: bool = True
    allow_escalate: bool = True
    on_exhausted: PackStatus = PackStatus.ABSTAIN

    @model_validator(mode="after")
    def _terminal_state_is_safe(self) -> FallbackPolicy:
        if self.on_exhausted in {PackStatus.SUFFICIENT, PackStatus.INSUFFICIENT}:
            raise ValueError(
                "on_exhausted must be a terminal safe outcome: "
                "CLARIFY, ABSTAIN or ESCALATE"
            )
        return self


class QueryPlan(Frozen):
    """Deterministic, produced before any search runs (build guide §8.1)."""

    plan_id: str
    interaction_id: str = Field(description="Idempotency key for the whole turn.")
    created_at: datetime
    learner: LearnerScope
    curriculum: CurriculumScope
    query_text: str
    query_language: Language
    response_language: Language
    modalities: list[Modality] = Field(min_length=1)
    teaching_action: TeachingAction
    misconception_hypothesis_id: str | None = None
    disclosure: DisclosurePolicy
    evidence_slots: list[EvidenceSlot] = Field(min_length=1)
    fallback: FallbackPolicy
    latency_budget_ms: int = Field(default=550, gt=0)
    policy_version: str

    @model_validator(mode="after")
    def _graded_turns_cannot_request_answers(self) -> QueryPlan:
        if self.disclosure.assessment_state is AssessmentState.GRADED:
            banned = {EvidenceRole.RUBRIC, EvidenceRole.WORKED_EXAMPLE}
            offending = [s.slot_id for s in self.evidence_slots if s.role in banned]
            if offending:
                raise ValueError(
                    f"graded turn requests protected evidence in slots {offending}. "
                    "Protected material is unaddressable in graded state, not "
                    "filtered out afterwards."
                )
        if self.misconception_hypothesis_id is None and (
            self.teaching_action is TeachingAction.MISCONCEPTION_CORRECTION
        ):
            raise ValueError(
                "misconception_correction requires a misconception_hypothesis_id"
            )
        return self


# --------------------------------------------------------------------------
# Pack
# --------------------------------------------------------------------------


class SourceSpan(Frozen):
    """Where a piece of evidence physically came from."""

    source_id: str
    edition: str
    block_ids: list[str] = Field(min_length=1)
    page: int = Field(ge=1)
    char_offsets: tuple[int, int] | None = None


class EvidenceItem(Frozen):
    object_id: str
    slot_id: str
    role: EvidenceRole
    text: str
    heading_path: str
    span: SourceSpan
    authority_tier: AuthorityTier
    disclosure_class: DisclosureClass
    generators: list[str] = Field(min_length=1)
    rerank_score: float | None = None


class Citation(Frozen):
    citation_id: str
    object_id: str
    char_offsets: tuple[int, int]


class SufficiencyResult(Frozen):
    """Run independently of generation (§8.4)."""

    authority: bool
    coverage: bool
    curriculum_fit: bool
    pedagogical_fit: bool
    no_conflict: bool
    freshness: bool
    disclosure: bool
    modality: bool
    gap_reasons: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(
            (
                self.authority,
                self.coverage,
                self.curriculum_fit,
                self.pedagogical_fit,
                self.no_conflict,
                self.freshness,
                self.disclosure,
                self.modality,
            )
        )


class EvidencePack(Frozen):
    """What the teaching loop is allowed to see. Nothing else."""

    pack_id: str
    plan_id: str
    interaction_id: str
    status: PackStatus
    evidence: list[EvidenceItem] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    sufficiency: SufficiencyResult
    release_manifest_id: str
    trace_id: str

    @model_validator(mode="after")
    def _citations_resolve_inside_the_pack(self) -> EvidencePack:
        available = {item.object_id for item in self.evidence}
        dangling = [c.citation_id for c in self.citations if c.object_id not in available]
        if dangling:
            raise ValueError(
                f"citations {dangling} reference objects absent from the pack. "
                "Citation ID resolution is a 100% gate."
            )
        if self.status is PackStatus.SUFFICIENT:
            if not self.evidence:
                raise ValueError("SUFFICIENT pack with no evidence")
            if not self.sufficiency.passed:
                raise ValueError(
                    "status is SUFFICIENT but the sufficiency gate did not pass: "
                    f"{self.sufficiency.gap_reasons}"
                )
        return self


# --------------------------------------------------------------------------
# Trace, teaching, verification, learner state
# --------------------------------------------------------------------------


class RetrievedItem(Frozen):
    """One ranked candidate, on its way from a retriever to the scorer.

    A handoff between two workstreams, so it lives here rather than inside
    either of them: `agts/retrieval/` produces it and `agts/evaluation/`
    measures it, and neither may redefine it for its own convenience.

    `block_ids` is the lineage, not decoration. Recall is measured on blocks
    (rule 4), so a retriever that ranks a *part* of an object reports the blocks
    it actually used — claiming the whole parent would score a hit for evidence
    it never surfaced.
    """

    object_id: str
    block_ids: tuple[str, ...]
    score: float
    representation_id: str | None = None


class CandidateTrace(Frozen):
    object_id: str
    generator: str
    rank: int = Field(ge=1)
    score: float
    admitted: bool
    rejection_reason: str | None = None


class RetrievalTrace(Frozen):
    """Reproducibility record. A number that cannot name the code that produced
    it is not evidence."""

    trace_id: str
    plan_id: str
    interaction_id: str
    candidates: list[CandidateTrace] = Field(default_factory=list)
    filters_applied: list[str] = Field(min_length=1)
    corrective_retrievals: int = Field(default=0, ge=0, le=1)
    stage_latency_ms: dict[str, float] = Field(default_factory=dict)
    versions: dict[str, str] = Field(min_length=1)
    release_manifest_id: str


class TeachingPlan(Frozen):
    """Chosen by the deterministic controller, not by the model (§9.1)."""

    teaching_plan_id: str
    plan_id: str
    teaching_action: TeachingAction
    max_disclosure: DisclosureClass
    permitted_tool_ids: list[str] = Field(default_factory=list)
    retry_budget: int = Field(default=1, ge=0)
    escalation_target: str | None = None


class VerificationResult(Frozen):
    """Independent gates (§9.3). Silent sentence-stripping is not a pass."""

    verification_id: str
    interaction_id: str
    evidence_sufficient: bool
    citations_resolve: bool
    claims_supported: bool
    math_proof_ok: bool
    child_safe: bool
    accessible: bool
    no_answer_leakage: bool
    policy_compliant: bool
    unsupported_claims: list[str] = Field(default_factory=list)
    action_taken: str = Field(
        description="pass | regenerate | downgrade_action | abstain"
    )

    @property
    def passed(self) -> bool:
        return all(
            (
                self.evidence_sufficient,
                self.citations_resolve,
                self.claims_supported,
                self.math_proof_ok,
                self.child_safe,
                self.accessible,
                self.no_answer_leakage,
                self.policy_compliant,
            )
        )

    @model_validator(mode="after")
    def _failure_is_never_reported_as_pass(self) -> VerificationResult:
        if self.action_taken == "pass" and not self.passed:
            raise ValueError(
                "action_taken='pass' with a failing gate. Unsupported output must "
                "regenerate, downgrade or abstain -- never be stripped and passed."
            )
        return self


class LearningEvidence(Frozen):
    """The only thing that may update canonical learner state (§9.4).

    The model may teach, explain and suggest. It may never declare mastery, so
    there is no confidence or mastery field here -- only what was observed.
    """

    evidence_id: str
    idempotency_key: str = Field(min_length=1)
    tenant_id: str
    pseudonymous_learner_id: str
    concept_id: str
    observed_at: datetime
    item_id: str | None = None
    was_correct: bool | None = None
    response_time_ms: int | None = Field(default=None, ge=0)
    hint_level_used: int | None = Field(default=None, ge=0)
    validated_by: str = Field(
        min_length=1, description="The deterministic validator that admitted this."
    )
    source_interaction_id: str


class ReleaseManifest(Frozen):
    """Signed set of published objects. The serving alias points at exactly one."""

    release_manifest_id: str
    created_at: datetime
    commit_sha: str
    object_ids: list[str] = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    versions: dict[str, str] = Field(min_length=1)
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_by: list[str] = Field(default_factory=list)
    is_serving: bool = False
