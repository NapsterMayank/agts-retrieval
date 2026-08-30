"""Evaluation cases (build guide §6.4).

A case records what a correct answer would have to be *grounded in*, not what it
should say. Gold is a set of :class:`~agts.contracts.objects.SourceBlock` ids
(rule 4), so re-composing learning objects or swapping an embedding model never
invalidates the answer key.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agts.contracts.common import (
    AssessmentState,
    DisclosureClass,
    EvidenceRole,
    Language,
    LearnerStateClass,
    Modality,
    QuestionType,
    TeachingAction,
)


class EvalCase(BaseModel):
    """One adjudicated evaluation case.

    `answerable=False` cases are not decoration: build guide §14 gates
    abstention, and a gold set of only answerable textbook questions cannot
    measure it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    query: str
    language: Language = Language.EN
    grade: str
    subject: str
    question_type: QuestionType
    teaching_action: TeachingAction
    learner_state: LearnerStateClass = LearnerStateClass.COLD_START
    assessment_state: AssessmentState = AssessmentState.LEARN
    modality: Modality = Modality.TEXT
    concept_ids: list[str] = Field(min_length=1)

    gold_block_ids: list[str] = Field(
        default_factory=list,
        description="Blocks that actually answer the query. Empty iff unanswerable.",
    )
    required_evidence_roles: list[EvidenceRole] = Field(default_factory=list)
    forbidden_disclosure: list[DisclosureClass] = Field(default_factory=list)
    tool_proof_required: bool = False
    reference_answer: str | None = None
    answerable: bool = True

    adjudicators: list[str] = Field(
        default_factory=list,
        description="Named human reviewers. Release-critical cases need two (§6.4).",
    )
    holdout: bool = False
    origin: str = "drafted"

    @model_validator(mode="after")
    def _gold_matches_answerability(self) -> EvalCase:
        if self.answerable and not self.gold_block_ids:
            raise ValueError(
                f"case {self.case_id}: answerable case with no gold blocks. "
                "An unlabelled case measures nothing."
            )
        if not self.answerable and self.gold_block_ids:
            raise ValueError(
                f"case {self.case_id}: unanswerable case carries gold blocks"
            )
        return self

    @property
    def is_release_critical(self) -> bool:
        """Release-critical cases require two adjudicators before they gate."""
        return self.holdout or not self.answerable

    def axes(self) -> dict[str, str]:
        """The single axes of section 11.2 that this repository can currently
        populate.

        Two of section 11.2's axes are deliberately absent rather than faked:
        *accessibility* has no field on a case and no content to vary, and
        *provider* belongs to a run rather than to a case — it is a property of
        the retriever being scored, and the scorer already reports per retriever.
        Inventing a constant value for either would add a slice that can never
        fail, which is worse than not having it.
        """
        return {
            "grade": self.grade,
            "subject": self.subject,
            "language": self.language.value,
            "question_type": self.question_type.value,
            "teaching_action": self.teaching_action.value,
            "learner_state": self.learner_state.value,
            "assessment_state": self.assessment_state.value,
            "modality": self.modality.value,
            "answerable": str(self.answerable).lower(),
        }

    def slice_keys(self) -> dict[str, str]:
        """Single axes **and their pairwise crossings** (section 11.2).

        Rule 9: every slice gets its own number and a blended average may not
        hide a failing one. Single axes alone cannot honour that — "science
        passes" and "equations pass" can both be true while *science equations*
        fail, which is exactly the kind of hole a pairwise matrix exists to
        find.

        Most crossings will sit below `GATING_MIN_N` and report without gating,
        which is the bootstrapping allowance in `docs/01-acceptance-gates.md`
        and open question Q2 — not a standing exemption. A crossing that never
        reaches n=20 is a gap in the gold set, and being able to see which ones
        those are is the reason to compute them now rather than later.
        """
        axes = self.axes()
        keys = dict(axes)
        names = sorted(axes)
        for i, first in enumerate(names):
            for second in names[i + 1:]:
                keys[f"{first}×{second}"] = f"{axes[first]}×{axes[second]}"
        return keys


class GoldSet(BaseModel):
    """A versioned set of cases, split into the visible set and a sealed holdout."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gold_set_id: str
    cases: list[EvalCase] = Field(min_length=1)

    @model_validator(mode="after")
    def _case_ids_are_unique(self) -> GoldSet:
        seen = [c.case_id for c in self.cases]
        duplicates = {c for c in seen if seen.count(c) > 1}
        if duplicates:
            raise ValueError(f"duplicate case ids: {sorted(duplicates)}")
        return self

    @property
    def visible(self) -> list[EvalCase]:
        return [c for c in self.cases if not c.holdout]

    @property
    def holdout(self) -> list[EvalCase]:
        return [c for c in self.cases if c.holdout]

    def unadjudicated_release_critical(self) -> list[str]:
        """Release-critical cases without the two reviewers §6.4 requires.

        This is the list that decides whether a holdout seal is real. Open
        question Q2 to the client: §6.4 seals the holdout at Hour 8 but §13
        schedules adjudication for Days 4-7.
        """
        return [
            c.case_id
            for c in self.cases
            if c.is_release_critical and len(c.adjudicators) < 2
        ]


def load_gold_set(path: "os.PathLike[str] | str") -> GoldSet:
    """Read a gold set from JSON.

    Keys beginning with an underscore are metadata for the humans reading and
    adjudicating the file — provenance, drafting notes, why a case exists — and
    are stripped before validation. `GoldSet` forbids extra fields, which is
    correct: an unexpected field in a case is a mistake, while a documented note
    beside the cases is not.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    payload = {k: v for k, v in payload.items() if not k.startswith("_")}
    payload["cases"] = [
        {k: v for k, v in case.items() if not k.startswith("_")}
        for case in payload.get("cases", [])
    ]
    return GoldSet.model_validate(payload)
