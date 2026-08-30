"""Citation scorers (§14) — and an honest account of which rows they cover.

§14 gates three citation properties. They are not the same measurement and only
two of them can be measured before a generation stage exists:

**Citation ID resolution, 100%** — every citation points at an object that is
actually in the pack, and every span resolves to blocks that exist with a page a
human can turn to. Measurable now, and gated here.

**Citation completeness, ≥95%** — is the evidence that answers the question
actually *in* the pack. Against a gold set this is exact: the fraction of a
case's gold blocks the pack carries. Measurable now.

**Citation precision, ≥98%** — does each citation support the sentence it is
attached to. **This one is not measurable here and is not claimed.** There are no
sentences yet: the teaching loop that writes them is Phase 3 and scope-blocked on
Q5. What *is* measured is a strict lower-bound proxy — the fraction of cited
blocks that are gold — reported under its own name, `evidence_precision`, so it
can never be read as the §14 row it is not.

Calling a proxy by the gate's name is how an unmet gate gets marked green, so
the distinction is in the field names rather than in a footnote.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agts.contracts.common import PackStatus
from agts.contracts.runtime import EvidencePack
from agts.evaluation.cases import EvalCase, GoldSet
from agts.evaluation.corpus import Corpus


@dataclass(frozen=True)
class CitationCaseResult:
    case_id: str
    answered: bool
    resolved: bool
    gold_blocks: int
    gold_blocks_cited: int
    cited_blocks: int

    @property
    def completeness(self) -> float | None:
        """Fraction of the gold blocks this pack carries."""
        if not self.gold_blocks:
            return None
        return self.gold_blocks_cited / self.gold_blocks

    @property
    def evidence_precision(self) -> float | None:
        """Fraction of cited blocks that are gold. A lower bound, not §14's row.

        A block can be genuinely useful and not be gold — surrounding context, a
        second worked example — so this under-reports real precision. It is
        still the number that moves when a pack fills with noise.
        """
        if not self.cited_blocks:
            return None
        return self.gold_blocks_cited / self.cited_blocks


@dataclass(frozen=True)
class CitationReport:
    resolution: float
    #: Fraction of answered cases whose pack contains at least one gold block.
    #: The pack-level counterpart of `recall_at_pack`, and the one that answers
    #: "did the teaching loop receive the evidence" -- `recall_at_pack` scores
    #: the retriever's ranked windows, and the pack adds sibling windows after
    #: ranking (R-025). A case can miss on one and hit on the other.
    delivered_recall: float | None
    completeness: float | None
    evidence_precision: float | None
    packs: int
    answered: int
    abstained: int
    unresolved: list[str] = field(default_factory=list)
    cases: list[CitationCaseResult] = field(default_factory=list)

    def failing_gates(
        self, *, resolution_floor: float = 1.0, completeness_floor: float = 0.95
    ) -> list[str]:
        """§14 rows this run fails. Precision is absent on purpose — see module docstring."""
        failing: list[str] = []
        if self.resolution < resolution_floor:
            failing.append(
                f"citation ID resolution {self.resolution:.1%} below {resolution_floor:.0%}"
            )
        if self.completeness is not None and self.completeness < completeness_floor:
            failing.append(
                f"citation completeness {self.completeness:.1%} below {completeness_floor:.0%}"
            )
        return failing

    def summary(self) -> str:
        def pct(value: float | None) -> str:
            return "n/a" if value is None else f"{value:.1%}"

        return (
            f"packs={self.packs} answered={self.answered} abstained={self.abstained} "
            f"resolution={pct(self.resolution)} delivered_recall={pct(self.delivered_recall)} "
            f"completeness={pct(self.completeness)} "
            f"evidence_precision={pct(self.evidence_precision)}"
        )


def _spans_resolve(pack: EvidencePack, corpus: Corpus) -> bool:
    """Whether every cited span points at blocks that exist, on a real page.

    The pack contract already refuses a citation whose object is absent. This is
    the other half: a citation whose object is present but whose span names
    blocks nobody can find is equally unusable, and nothing else checks it.
    """
    for item in pack.evidence:
        if not item.span.block_ids:
            return False
        for block_id in item.span.block_ids:
            block = corpus.blocks.get(block_id)
            if block is None:
                return False
            if block.region.page != item.span.page and block_id == item.span.block_ids[0]:
                return False
    return True


def score_citations(
    gold_set: GoldSet,
    packs: dict[str, EvidencePack],
    corpus: Corpus,
    *,
    include_holdout: bool = False,
) -> CitationReport:
    """Score the packs produced for a gold set.

    Abstentions are counted and excluded from completeness: a pack that
    correctly refused to answer has no citations to be complete about, and
    folding it in as a zero would make the abstention gate look like a citation
    failure. Packs that carry evidence are all measured, including INSUFFICIENT
    ones — scoring only the clean packs would hide the ones with gaps.
    """
    cases: list[EvalCase] = gold_set.cases if include_holdout else gold_set.visible
    results: list[CitationCaseResult] = []
    unresolved: list[str] = []

    for case in cases:
        pack = packs.get(case.case_id)
        if pack is None:
            continue

        # Any pack that carries evidence is measured, not only a SUFFICIENT one.
        # An INSUFFICIENT pack still has citations, and scoring only the clean
        # packs would hide exactly the ones with gaps.
        answered = pack.status is not PackStatus.ABSTAIN and bool(pack.evidence)
        resolved = _spans_resolve(pack, corpus)
        if not resolved:
            unresolved.append(case.case_id)

        cited = {b for item in pack.evidence for b in item.span.block_ids}
        gold = set(case.gold_block_ids)
        results.append(
            CitationCaseResult(
                case_id=case.case_id,
                answered=answered,
                resolved=resolved,
                gold_blocks=len(gold),
                gold_blocks_cited=len(gold & cited),
                cited_blocks=len(cited),
            )
        )

    answered = [r for r in results if r.answered]
    delivered = [r for r in answered if r.gold_blocks]
    completeness = [r.completeness for r in answered if r.completeness is not None]
    precision = [r.evidence_precision for r in answered if r.evidence_precision is not None]

    return CitationReport(
        resolution=(sum(r.resolved for r in results) / len(results)) if results else 1.0,
        delivered_recall=(
            sum(1 for r in delivered if r.gold_blocks_cited) / len(delivered)
            if delivered else None
        ),
        completeness=(sum(completeness) / len(completeness)) if completeness else None,
        evidence_precision=(sum(precision) / len(precision)) if precision else None,
        packs=len(results),
        answered=len(answered),
        abstained=len(results) - len(answered),
        unresolved=unresolved,
        cases=results,
    )
