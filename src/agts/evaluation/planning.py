"""Phase-0 deterministic plan builder.

A seed for the real §8.1 query planner, not a replacement for it. It exists so
the scorer can drive retrievers through the same `QueryPlan` contract the
production path will use -- which is what makes a Phase-0 number comparable to a
Phase-2 one instead of a throwaway.

Deliberately has no model in it. A planner that can widen its own filters is a
vulnerability, not a planner.
"""

from __future__ import annotations

from datetime import UTC, datetime

from agts.contracts.common import (
    AssessmentState,
    AuthorityTier,
    Board,
    EvidenceRole,
    Modality,
    Role,
    TeachingAction,
)
from agts.contracts.runtime import (
    CEILING_BY_ASSESSMENT_STATE,
    CurriculumScope,
    DisclosurePolicy,
    EvidenceSlot,
    FallbackPolicy,
    LearnerScope,
    QueryPlan,
)
from agts.evaluation.cases import EvalCase

#: Minimum evidence composition per teaching action. Retrieval must satisfy the
#: composition, not merely return topical passages.
SLOTS_BY_ACTION: dict[TeachingAction, tuple[EvidenceRole, ...]] = {
    TeachingAction.EXPLAIN: (EvidenceRole.DEFINITION, EvidenceRole.EXPLANATION),
    TeachingAction.EXPLAIN_SIMPLER: (EvidenceRole.EXPLANATION, EvidenceRole.EXAMPLE),
    TeachingAction.PREREQUISITE_REPAIR: (
        EvidenceRole.PREREQUISITE,
        EvidenceRole.EXPLANATION,
    ),
    TeachingAction.MISCONCEPTION_CORRECTION: (
        EvidenceRole.MISCONCEPTION,
        EvidenceRole.CORRECTION,
        EvidenceRole.COUNTEREXAMPLE,
    ),
    TeachingAction.SOCRATIC_QUESTION: (EvidenceRole.EXPLANATION,),
    TeachingAction.HINT_1: (EvidenceRole.HINT,),
    TeachingAction.HINT_2: (EvidenceRole.HINT,),
    TeachingAction.HINT_3: (EvidenceRole.HINT,),
    TeachingAction.WORKED_EXAMPLE: (EvidenceRole.WORKED_EXAMPLE,),
    TeachingAction.PRACTICE_ITEM: (EvidenceRole.PRACTICE_ITEM,),
    TeachingAction.ANSWER_FEEDBACK: (EvidenceRole.EXPLANATION,),
    TeachingAction.REVISION: (EvidenceRole.DEFINITION, EvidenceRole.EXAMPLE),
    TeachingAction.ENRICHMENT: (EvidenceRole.EXAMPLE,),
    TeachingAction.ESCALATION: (EvidenceRole.EXPLANATION,),
}

#: Roles that a graded turn may never request. Mirrors the QueryPlan validator;
#: kept here so the planner never constructs an invalid plan in the first place.
_GRADED_BANNED_ROLES = {EvidenceRole.RUBRIC, EvidenceRole.WORKED_EXAMPLE}


def plan_for_case(
    case: EvalCase,
    *,
    tenant_id: str = "tenant-pilot",
    board: Board = Board.CBSE,
    curriculum_version: str = "pilot-0",
    policy_version: str = "phase0-0",
) -> QueryPlan:
    """Build the deterministic plan an evaluation case implies."""
    roles = SLOTS_BY_ACTION[case.teaching_action]
    if case.assessment_state is AssessmentState.GRADED:
        roles = tuple(r for r in roles if r not in _GRADED_BANNED_ROLES) or (
            EvidenceRole.EXPLANATION,
        )

    slots = [
        EvidenceSlot(
            slot_id=f"{case.case_id}-s{i}",
            role=role,
            required=True,
            min_items=1,
            max_items=2,
            min_authority=AuthorityTier.LICENSED_PUBLISHER,
            modality=case.modality if case.modality is not Modality.TEXT else None,
        )
        for i, role in enumerate(roles)
    ]

    hypothesis = (
        f"{case.concept_ids[0]}-misconception"
        if case.teaching_action is TeachingAction.MISCONCEPTION_CORRECTION
        else None
    )

    return QueryPlan(
        plan_id=f"plan-{case.case_id}",
        interaction_id=f"turn-{case.case_id}",
        created_at=datetime(2026, 8, 24, tzinfo=UTC),
        learner=LearnerScope(
            tenant_id=tenant_id,
            pseudonymous_learner_id=f"learner-{case.case_id}",
            role=Role.LEARNER,
            learner_state_class=case.learner_state,
        ),
        curriculum=CurriculumScope(
            board=board,
            curriculum_version=curriculum_version,
            grade=case.grade,
            subject=case.subject,
            concept_ids=list(case.concept_ids),
        ),
        query_text=case.query,
        query_language=case.language,
        response_language=case.language,
        modalities=[case.modality],
        teaching_action=case.teaching_action,
        misconception_hypothesis_id=hypothesis,
        disclosure=DisclosurePolicy(
            assessment_state=case.assessment_state,
            max_disclosure=CEILING_BY_ASSESSMENT_STATE[case.assessment_state],
        ),
        evidence_slots=slots,
        fallback=FallbackPolicy(),
        policy_version=policy_version,
    )
