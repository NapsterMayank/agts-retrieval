"""In-memory corpus with the authorisation boundary built in.

Rule 5 is structural here, not advisory. :meth:`Corpus.authorised` is the only
sanctioned way to obtain candidates; :meth:`Corpus.unfiltered` exists purely so
the deliberately broken retrievers in :mod:`agts.evaluation.retrievers` can
bypass it and be caught doing so.

One narrow exception exists and is spelled out rather than implied: see
:class:`EvaluationLicence`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from agts.contracts.common import DISCLOSURE_RANK, ApprovalState
from agts.contracts.objects import LearningObject, SourceBlock, SourceRecord
from agts.contracts.runtime import QueryPlan


@dataclass(frozen=True)
class EvaluationLicence:
    """Permission to *measure against* named quarantined sources. Nothing else.

    §5 forbids retrieval from an unapproved source, and that rule is what keeps
    unlicensed content away from a student. But it also means the ruler can only
    ever be run over synthetic fixtures until rights records arrive (Q3) — and a
    scorer proven only on forty invented sentences has proven very little. The
    first real run over real content is exactly where a parse or composition
    defect becomes visible.

    So this permits one thing: quarantined objects from **explicitly named
    sources** may enter the candidate set of an evaluation run. It is not a
    production path and must never be constructed by serving code:

    - sources are named individually; there is no blanket or wildcard form,
    - only ``QUARANTINED`` is unlocked — ``RETIRED`` and ``WITHDRAWN`` stay
      excluded, because withdrawing content is the mechanism a rights holder
      has and an evaluation run is not a reason to ignore it,
    - every other filter still applies, tenant and disclosure included,
    - it carries who granted it and why, so a number produced under it can be
      traced to the decision that allowed it.

    A run using a licence is not evidence of release readiness. `ScoreReport`
    records it so the distinction cannot be lost between the run and the table
    it ends up in.
    """

    reason: str
    granted_by: str
    granted_on: date
    source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.source_ids:
            raise ValueError("an evaluation licence must name at least one source")
        if not self.reason.strip() or not self.granted_by.strip():
            raise ValueError("an evaluation licence needs a reason and a grantor")

    def covers(self, source_id: str) -> bool:
        return source_id in self.source_ids


@dataclass(frozen=True)
class Corpus:
    """Sources, blocks and objects, with the filters that must precede ranking."""

    sources: dict[str, SourceRecord] = field(default_factory=dict)
    blocks: dict[str, SourceBlock] = field(default_factory=dict)
    objects: dict[str, LearningObject] = field(default_factory=dict)
    evaluation_licence: EvaluationLicence | None = None

    def evaluation_licensed(self, obj: LearningObject) -> bool:
        """Whether `obj` is quarantined content this run is licensed to measure.

        Both the object and its source must be quarantined *and* named. An
        object whose source is retired is not covered, however the object itself
        is labelled.
        """
        licence = self.evaluation_licence
        if licence is None or not licence.covers(obj.source_id):
            return False
        source = self.sources.get(obj.source_id)
        if source is None:
            return False
        return (
            obj.approval_state is ApprovalState.QUARANTINED
            and source.approval_state is ApprovalState.QUARANTINED
        )

    def unfiltered(self) -> list[LearningObject]:
        """Every object, authorised or not.

        Only broken retrievers call this. Honest ones call :meth:`authorised`.
        """
        return list(self.objects.values())

    def authorised(self, plan: QueryPlan) -> list[LearningObject]:
        """Candidates the actor in `plan` is permitted to have ranked.

        Applied *before* scoring, so unauthorised content never enters the
        candidate set and cannot influence an ordering it is later removed from.
        """
        ceiling = DISCLOSURE_RANK[plan.disclosure.max_disclosure]
        forbidden = set(plan.disclosure.forbidden_object_ids)
        out: list[LearningObject] = []

        for obj in self.objects.values():
            if obj.object_id in forbidden:
                continue
            licensed = self.evaluation_licensed(obj)
            if obj.approval_state is not ApprovalState.APPROVED and not licensed:
                continue
            if obj.retired_at is not None:
                continue

            source = self.sources.get(obj.source_id)
            if source is None:
                continue
            if source.approval_state is not ApprovalState.APPROVED and not licensed:
                continue

            if obj.tenant_scope is not None and obj.tenant_scope != plan.learner.tenant_id:
                continue

            if obj.curriculum.grade != plan.curriculum.grade:
                continue
            if obj.curriculum.subject != plan.curriculum.subject:
                continue
            if obj.curriculum.board != plan.curriculum.board:
                continue
            if obj.curriculum.curriculum_version != plan.curriculum.curriculum_version:
                continue

            if DISCLOSURE_RANK[obj.disclosure_class] > ceiling:
                continue

            out.append(obj)

        return out

    def blocks_for(self, object_id: str) -> list[str]:
        obj = self.objects.get(object_id)
        return list(obj.block_ids) if obj else []

    def is_authorised(self, obj: LearningObject, plan: QueryPlan) -> bool:
        """Whether a single object would have survived :meth:`authorised`.

        Used by the scorer to count leakage when a retriever bypassed the filter.
        """
        return any(o.object_id == obj.object_id for o in self.authorised(plan))
