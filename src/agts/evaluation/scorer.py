"""The ruler (build guide §6, rule 1).

Built before any retrieval is optimised, and proven able to expose a broken
retriever before any of its numbers are believed.

Three things it reports, deliberately never blended:

1. **Recall**, over answerable cases, at candidate depth and again at pack depth.
   The second is the one the teaching loop actually receives, and a reranker can
   pass the first while failing the second.
2. **Abstention**, over unanswerable cases only. A gold set of answerable
   questions cannot measure the behaviour §14 gates at zero leakage.
3. **Invariant violations**, which are counts and not rates, because the gates
   they map to are zero-tolerance.

Rule 9 is enforced structurally: every number is also reported per slice, and
:meth:`ScoreReport.failing_slices` is what a release reads, not the headline.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from agts.contracts.common import DISCLOSURE_RANK, ApprovalState
from agts.evaluation.cases import EvalCase, GoldSet
from agts.evaluation.corpus import Corpus
from agts.evaluation.planning import plan_for_case
from agts.evaluation.retrievers import Retriever

#: A slice with fewer than this many cases is reported but does not gate. This
#: is a bootstrapping allowance, not a standing exemption -- the shipped gold set
#: targets n >= 20 on every slice §14 gates.
GATING_MIN_N = 20

#: Placeholder only. A hand-picked abstention threshold measures nothing: it is
#: an assertion about a score distribution nobody has looked at. Callers should
#: pass a threshold from :func:`calibrate_abstention`, and §15 requires
#: recalibrating it after every material corpus expansion.
PROVISIONAL_ABSTAIN_THRESHOLD = 0.05


@dataclass(frozen=True)
class InvariantViolations:
    """Zero-tolerance counters. Any non-zero value blocks a release."""

    unauthorised_returned: int = 0
    disclosure_violations: int = 0
    cross_tenant: int = 0
    unapproved_source: int = 0
    retired_content: int = 0

    @property
    def total(self) -> int:
        return (
            self.unauthorised_returned
            + self.disclosure_violations
            + self.cross_tenant
            + self.unapproved_source
            + self.retired_content
        )

    def merged_with(self, other: InvariantViolations) -> InvariantViolations:
        return InvariantViolations(
            unauthorised_returned=self.unauthorised_returned + other.unauthorised_returned,
            disclosure_violations=self.disclosure_violations + other.disclosure_violations,
            cross_tenant=self.cross_tenant + other.cross_tenant,
            unapproved_source=self.unapproved_source + other.unapproved_source,
            retired_content=self.retired_content + other.retired_content,
        )


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    answerable: bool
    hit_at_candidates: bool
    hit_at_pack: bool
    abstained_correctly: bool | None
    top_score: float
    violations: InvariantViolations


@dataclass(frozen=True)
class SliceScore:
    slice_key: str
    n: int
    n_answerable: int
    recall_at_candidates: float | None
    recall_at_pack: float | None
    abstention_accuracy: float | None
    violations: InvariantViolations

    @property
    def gating(self) -> bool:
        """Rule 9 with a bootstrapping allowance -- see :data:`GATING_MIN_N`."""
        return self.n >= GATING_MIN_N


@dataclass(frozen=True)
class ScoreReport:
    retriever: str
    k_candidates: int
    k_pack: int
    n_cases: int
    n_answerable: int
    recall_at_candidates: float | None
    recall_at_pack: float | None
    abstention_accuracy: float | None
    violations: InvariantViolations
    slices: dict[str, SliceScore] = field(default_factory=dict)
    cases: list[CaseResult] = field(default_factory=list)
    #: Set when the run measured quarantined content under an
    #: :class:`~agts.evaluation.corpus.EvaluationLicence`. Such a run is a
    #: measurement, never release evidence, and the distinction is easy to lose
    #: once a number reaches a table — so it travels with the number.
    evaluation_licence: str | None = None

    def failing_slices(
        self,
        *,
        candidate_floor: float = 0.95,
        pack_floor: float = 0.90,
    ) -> list[str]:
        """Gating slices below their floor. A blended average may not hide one."""
        failing: list[str] = []
        for key, sl in sorted(self.slices.items()):
            if not sl.gating:
                continue
            if sl.recall_at_candidates is not None and sl.recall_at_candidates < candidate_floor:
                failing.append(f"{key}: recall@{self.k_candidates}={sl.recall_at_candidates:.3f}")
            elif sl.recall_at_pack is not None and sl.recall_at_pack < pack_floor:
                failing.append(f"{key}: recall@pack={sl.recall_at_pack:.3f}")
            elif sl.violations.total:
                failing.append(f"{key}: {sl.violations.total} invariant violations")
        return failing

    def is_materially_worse_than(
        self, baseline: ScoreReport, *, margin: float = 0.15
    ) -> bool:
        """Whether this retriever is detectably worse than `baseline`.

        Two ways to be worse, and either is enough. A retriever that trips a
        zero-tolerance counter the baseline does not is worse *regardless of its
        recall* -- that is the whole point of the answer-only case, which can
        rank gold correctly while leaking the solution beside it.
        """
        if self.violations.total > baseline.violations.total:
            return True
        mine = self.recall_at_pack if self.recall_at_pack is not None else 0.0
        theirs = baseline.recall_at_pack if baseline.recall_at_pack is not None else 0.0
        return mine <= theirs - margin

    def summary(self) -> str:
        def pct(v: float | None) -> str:
            return "n/a" if v is None else f"{v * 100:.1f}%"

        line = (
            f"{self.retriever}: recall@{self.k_candidates}={pct(self.recall_at_candidates)} "
            f"recall@pack{self.k_pack}={pct(self.recall_at_pack)} "
            f"abstain={pct(self.abstention_accuracy)} "
            f"violations={self.violations.total}"
        )
        if self.evaluation_licence:
            line += f"  [quarantined content, evaluation licence: {self.evaluation_licence}]"
        return line


@dataclass(frozen=True)
class AbstentionCalibration:
    """Where answerable and unanswerable top scores actually sit.

    The useful Phase-0 claim is not "the threshold is 0.35". It is "the two
    distributions separate by this much, and here is the number that separates
    them". A threshold quoted without its margin is a guess wearing a decimal
    point.
    """

    threshold: float
    margin: float
    lowest_answerable: float
    highest_unanswerable: float
    n_answerable: int
    n_unanswerable: int

    @property
    def separable(self) -> bool:
        """False means no threshold can work -- the retriever scores an
        out-of-corpus query as confidently as one it can actually answer."""
        return self.margin > 0.0

    def summary(self) -> str:
        return (
            f"threshold={self.threshold:.3f} margin={self.margin:.3f} "
            f"(answerable floor {self.lowest_answerable:.3f}, "
            f"unanswerable ceiling {self.highest_unanswerable:.3f}; "
            f"n={self.n_answerable}/{self.n_unanswerable})"
        )


def calibrate_abstention(
    gold_set: GoldSet,
    retriever: Retriever,
    corpus: Corpus,
    *,
    k_candidates: int = 20,
    include_holdout: bool = False,
    curriculum_version: str = "pilot-0",
) -> AbstentionCalibration:
    """Derive an abstention threshold from the visible set.

    Never run on the holdout: calibrating on the sealed set is tuning on it.
    """
    cases = gold_set.cases if include_holdout else gold_set.visible

    answerable_tops: list[float] = []
    unanswerable_tops: list[float] = []
    for case in cases:
        plan = plan_for_case(case, curriculum_version=curriculum_version)
        items = retriever.retrieve(plan, corpus, k_candidates)
        top = items[0].score if items else 0.0
        (answerable_tops if case.answerable else unanswerable_tops).append(top)

    if not answerable_tops or not unanswerable_tops:
        raise ValueError(
            "calibration needs both answerable and unanswerable cases. A gold "
            "set of only answerable questions cannot measure abstention."
        )

    floor = min(answerable_tops)
    ceiling = max(unanswerable_tops)
    return AbstentionCalibration(
        threshold=(floor + ceiling) / 2.0,
        margin=floor - ceiling,
        lowest_answerable=floor,
        highest_unanswerable=ceiling,
        n_answerable=len(answerable_tops),
        n_unanswerable=len(unanswerable_tops),
    )


def _violations_for(items, corpus: Corpus, plan) -> InvariantViolations:
    authorised_ids = {obj.object_id for obj in corpus.authorised(plan)}
    ceiling = DISCLOSURE_RANK[plan.disclosure.max_disclosure]

    unauthorised = disclosure = cross_tenant = unapproved = retired = 0

    for item in items:
        obj = corpus.objects.get(item.object_id)
        if obj is None:
            unauthorised += 1
            continue
        if obj.object_id not in authorised_ids:
            unauthorised += 1
        if DISCLOSURE_RANK[obj.disclosure_class] > ceiling:
            disclosure += 1
        if obj.tenant_scope is not None and obj.tenant_scope != plan.learner.tenant_id:
            cross_tenant += 1
        source = corpus.sources.get(obj.source_id)
        # A licensed evaluation run is measuring quarantined content on purpose;
        # counting it here would put hundreds of violations on every real-content
        # run and destroy the signal the counter exists to carry.
        if not corpus.evaluation_licensed(obj) and (
            obj.approval_state is not ApprovalState.APPROVED
            or source is None
            or source.approval_state is not ApprovalState.APPROVED
        ):
            unapproved += 1
        if obj.retired_at is not None:
            retired += 1

    return InvariantViolations(
        unauthorised_returned=unauthorised,
        disclosure_violations=disclosure,
        cross_tenant=cross_tenant,
        unapproved_source=unapproved,
        retired_content=retired,
    )


def score_case(
    case: EvalCase,
    retriever: Retriever,
    corpus: Corpus,
    *,
    k_candidates: int = 20,
    k_pack: int = 5,
    abstain_threshold: float = PROVISIONAL_ABSTAIN_THRESHOLD,
    curriculum_version: str = "pilot-0",
) -> CaseResult:
    """Score one case. Gold is matched on block ids, never on object ids.

    `curriculum_version` has to reach the plan: `Corpus.authorised` filters on
    it, so scoring a 2026-27 corpus with the default leaves every candidate set
    empty — which reads as a retriever that finds nothing rather than as a plan
    aimed at a curriculum that is not there.
    """
    plan = plan_for_case(case, curriculum_version=curriculum_version)
    items = retriever.retrieve(plan, corpus, k_candidates)

    gold = set(case.gold_block_ids)
    blocks_at_candidates: set[str] = set()
    for item in items:
        blocks_at_candidates.update(item.block_ids)
    blocks_at_pack: set[str] = set()
    for item in items[:k_pack]:
        blocks_at_pack.update(item.block_ids)

    top_score = items[0].score if items else 0.0

    if case.answerable:
        hit_candidates = bool(gold & blocks_at_candidates)
        hit_pack = bool(gold & blocks_at_pack)
        abstained = None
    else:
        hit_candidates = False
        hit_pack = False
        # With no sufficiency gate yet, "abstained" means the retriever produced
        # nothing it could defend. Phase 2 replaces this with the real gate.
        abstained = (not items) or top_score < abstain_threshold

    return CaseResult(
        case_id=case.case_id,
        answerable=case.answerable,
        hit_at_candidates=hit_candidates,
        hit_at_pack=hit_pack,
        abstained_correctly=abstained,
        top_score=top_score,
        violations=_violations_for(items, corpus, plan),
    )


def _ratio(hits: int, n: int) -> float | None:
    return hits / n if n else None


def score(
    gold_set: GoldSet,
    retriever: Retriever,
    corpus: Corpus,
    *,
    k_candidates: int = 20,
    k_pack: int = 5,
    abstain_threshold: float = PROVISIONAL_ABSTAIN_THRESHOLD,
    include_holdout: bool = False,
    curriculum_version: str = "pilot-0",
) -> ScoreReport:
    """Score a whole gold set, overall and per slice.

    `include_holdout` defaults to False so an ordinary tuning run cannot touch
    the sealed set. The holdout runner passes True explicitly and records the
    result in EVALUATION_LEDGER.
    """
    cases = gold_set.cases if include_holdout else gold_set.visible

    results: list[CaseResult] = []
    by_slice: dict[str, list[tuple[EvalCase, CaseResult]]] = defaultdict(list)

    for case in cases:
        result = score_case(
            case,
            retriever,
            corpus,
            k_candidates=k_candidates,
            k_pack=k_pack,
            abstain_threshold=abstain_threshold,
            curriculum_version=curriculum_version,
        )
        results.append(result)
        for axis, value in case.slice_keys().items():
            by_slice[f"{axis}={value}"].append((case, result))

    answerable = [r for r in results if r.answerable]
    unanswerable = [r for r in results if not r.answerable]

    violations = InvariantViolations()
    for r in results:
        violations = violations.merged_with(r.violations)

    slices: dict[str, SliceScore] = {}
    for key, pairs in by_slice.items():
        rs = [r for _, r in pairs]
        ans = [r for r in rs if r.answerable]
        unans = [r for r in rs if not r.answerable]
        slice_violations = InvariantViolations()
        for r in rs:
            slice_violations = slice_violations.merged_with(r.violations)
        slices[key] = SliceScore(
            slice_key=key,
            n=len(rs),
            n_answerable=len(ans),
            recall_at_candidates=_ratio(sum(r.hit_at_candidates for r in ans), len(ans)),
            recall_at_pack=_ratio(sum(r.hit_at_pack for r in ans), len(ans)),
            abstention_accuracy=_ratio(
                sum(bool(r.abstained_correctly) for r in unans), len(unans)
            ),
            violations=slice_violations,
        )

    return ScoreReport(
        retriever=retriever.name,
        k_candidates=k_candidates,
        k_pack=k_pack,
        n_cases=len(results),
        n_answerable=len(answerable),
        recall_at_candidates=_ratio(
            sum(r.hit_at_candidates for r in answerable), len(answerable)
        ),
        recall_at_pack=_ratio(sum(r.hit_at_pack for r in answerable), len(answerable)),
        abstention_accuracy=_ratio(
            sum(bool(r.abstained_correctly) for r in unanswerable), len(unanswerable)
        ),
        violations=violations,
        slices=slices,
        cases=results,
        evaluation_licence=(
            corpus.evaluation_licence.reason if corpus.evaluation_licence else None
        ),
    )
