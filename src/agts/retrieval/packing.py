"""Assemble an EvidencePack from a sufficiency decision (§8.3, §8.4).

The pack is the boundary: it is what the teaching loop is allowed to see, and
everything not in it is unavailable by construction rather than by convention.

Three things this stage is responsible for, and one it is not.

**It completes the evidence for each section it selected.** Ranking keeps one
window per object so that five slots hold five different sections. Citation needs
the opposite: 31 of 31 gold blocks the pack was missing sat in a *sibling window
of a section already in the pack*, so citation completeness ran at 77% against a
95% gate while retrieval had found the right section every single time. The
builder therefore pulls in the sibling windows that clear the same floor the
section cleared — measured at 96.9% completeness, against 93.3% for taking
immediate neighbours and 100% for taking whole objects at 126 blocks a pack.

**It fills slots, it does not rank.** `QueryPlan.evidence_slots` says what the
teaching action needs — a definition, a worked example, a visual. The composer
places retrieved items into those slots; the reranker only ordered them. A slot
that cannot be filled is a gap, and a gap is reported rather than papered over
by promoting whatever ranked next.

**Every item carries a resolvable span.** `SourceSpan` needs the source, the
edition, the block ids and the page. That comes from the blocks themselves, so a
citation can be checked against the original PDF by a human without trusting
anything this code says about it.

**An abstention produces a pack too.** `PackStatus.ABSTAIN` with no evidence is a
successful outcome (§8.4), not an error and not an empty response — the trace has
to record that the decision was made and why.

**It never decides sufficiency.** That already happened, in
:mod:`agts.retrieval.sufficiency`. Re-deciding it here, with the pack in hand,
is how a threshold gets quietly lowered to avoid an empty result.
"""

from __future__ import annotations

from collections.abc import Sequence

from agts.contracts.common import EvidenceRole, PackStatus
from agts.contracts.runtime import (
    Citation,
    EvidenceItem,
    EvidencePack,
    QueryPlan,
    SourceSpan,
    SufficiencyResult,
)
from agts.evaluation.corpus import Corpus
from agts.parsing.quality import readable_text
from agts.retrieval.sufficiency import SufficiencyDecision


def _span_for(corpus: Corpus, block_ids: Sequence[str], source_id: str, edition: str) -> SourceSpan:
    """The physical location of the evidence.

    Page comes from the first block that has one. Blocks are ordered by reading
    order within a window, so the first is where a reader would start looking —
    and a span that names a page nobody can turn to is not a citation.
    """
    pages = [corpus.blocks[b].region.page for b in block_ids if b in corpus.blocks]
    return SourceSpan(
        source_id=source_id,
        edition=edition,
        block_ids=list(block_ids),
        page=pages[0] if pages else 1,
    )


def _sibling_blocks(
    decision: SufficiencyDecision, corpus: Corpus, object_ids: set[str]
) -> dict[str, list[str]]:
    """Blocks from other windows of the selected sections that clear the floor.

    "Clears the same floor the section cleared" is the rule, not "is adjacent"
    and not "belongs to the same object": a window that would have been retrieved
    on its own merits is evidence, and one that would not is padding.
    """
    if not decision.window_scores:
        return {}

    # Both retrievers, not one. A sibling clearing the primary's floor entered
    # the pack on a single opinion, in exactly the band where the gate itself
    # requires two -- and was then merged into the same evidence item and
    # covered by the same citation as the corroborated window (R-045).
    corroborated = set(decision.corroborator_windows)

    out: dict[str, list[str]] = {}
    for rep in corpus.representations.values():
        if rep.object_id not in object_ids:
            continue
        score = decision.window_scores.get(rep.representation_id)
        if score is None or score < decision.threshold:
            continue
        # An empty corroborator map means the corroborator cannot score windows
        # at all; requiring its assent then would silently disable expansion.
        if corroborated and rep.representation_id not in corroborated:
            continue
        out.setdefault(rep.object_id, []).extend(rep.block_ids)
    return out


def build_pack(
    plan: QueryPlan,
    decision: SufficiencyDecision,
    corpus: Corpus,
    *,
    pack_id: str,
    trace_id: str,
    release_manifest_id: str,
    k_pack: int = 5,
) -> EvidencePack:
    """Turn a decision into the pack the teaching loop receives.

    An abstained decision yields an `ABSTAIN` pack carrying the gate's reasons,
    because "no answer" and "no answer, and here is which condition failed" are
    different things to anyone debugging a refusal.
    """
    if not decision.answerable:
        return EvidencePack(
            pack_id=pack_id,
            plan_id=plan.plan_id,
            interaction_id=plan.interaction_id,
            status=PackStatus.ABSTAIN,
            evidence=[],
            citations=[],
            sufficiency=SufficiencyResult(
                authority=True,
                coverage=False,
                curriculum_fit=True,
                pedagogical_fit=True,
                no_conflict=True,
                freshness=True,
                disclosure=True,
                modality=True,
                gap_reasons=list(decision.reasons),
            ),
            release_manifest_id=release_manifest_id,
            trace_id=trace_id,
        )

    slots = list(plan.evidence_slots)
    if not slots:
        # QueryPlan requires at least one slot, but model_copy bypasses
        # validation, so a slotless plan can reach here. Without this the items
        # are tagged EXPLANATION by default and the pack reports SUFFICIENT --
        # evidence presented as answering a requirement nobody expressed.
        gaps_before = ["the plan carries no evidence slots, so nothing here is a considered answer"]
    else:
        gaps_before = []

    items: list[EvidenceItem] = []
    citations: list[Citation] = []
    gaps: list[str] = list(gaps_before)

    ranked = decision.items[:k_pack]
    siblings = _sibling_blocks(decision, corpus, {i.object_id for i in ranked})
    for index, retrieved in enumerate(ranked):
        obj = corpus.objects.get(retrieved.object_id)
        if obj is None:
            # A retriever returned an id the corpus does not have. Not
            # recoverable here and not silently droppable either.
            gaps.append(f"{retrieved.object_id} is not in the corpus")
            continue

        # Slots are filled in rank order; beyond the declared slots the item
        # still travels, tagged with the role of the last slot, because dropping
        # good evidence for want of a slot definition is worse than a coarse role.
        slot = slots[index] if index < len(slots) else (slots[-1] if slots else None)
        source = corpus.sources.get(obj.source_id)
        edition = source.edition if source else "unknown"

        # The ranked window, plus the siblings of this section that cleared the
        # same floor. Order preserved, duplicates dropped.
        # The window's own blocks, its corroborated siblings, and the statement
        # it continues. The statement was findable and unservable, so a pack
        # could carry "the breadth of the hall is 12 m" without the problem it
        # answers -- and any restatement of that problem was unsupported by the
        # evidence it came with (R-046). These are real blocks on real pages, so
        # serving them means citing them.
        context = []
        representation = corpus.representations.get(retrieved.representation_id or "")
        if representation is not None:
            context = [b for b in representation.context_block_ids if b in corpus.blocks]
        block_ids = list(
            dict.fromkeys([*context, *retrieved.block_ids, *siblings.get(obj.object_id, ())])
        )
        # `text or latex`, matching what the chunker made searchable.
        # Rendering only `text` meant a latex-only block was ranked on its
        # formula, cited in the span, and served as an empty line -- prose
        # promising a formula, no formula, and a citation vouching for the
        # block that held it. Reported by a reviewer, reproduced, then fixed.
        text = "\n".join(
            content
            for b in block_ids
            if b in corpus.blocks
            for content in [readable_text(corpus.blocks[b].text, corpus.blocks[b].latex)]
            if content
        )
        item = EvidenceItem(
            object_id=obj.object_id,
            slot_id=slot.slot_id if slot else f"{plan.plan_id}-unslotted-{index}",
            role=slot.role if slot else EvidenceRole.EXPLANATION,
            text=text,
            heading_path=obj.heading_path,
            span=_span_for(corpus, block_ids, obj.source_id, edition),
            authority_tier=obj.authority_tier,
            disclosure_class=obj.disclosure_class,
            generators=[decision.primary_name or "retrieval"],
            rerank_score=retrieved.score,
        )
        items.append(item)
        citations.append(
            Citation(
                citation_id=f"{pack_id}-c{index + 1}",
                object_id=obj.object_id,
                char_offsets=(0, len(text)),
            )
        )

    # Keyed on slot id, not role. Two required slots asking for the same role
    # were both satisfied by one item, so a plan that asked twice received once
    # and the pack still reported SUFFICIENT.
    filled_slots = {item.slot_id for item in items}
    for slot in slots:
        if slot.required and slot.slot_id not in filled_slots:
            gaps.append(f"required slot {slot.slot_id} ({slot.role.value}) is unfilled")

    sufficiency = SufficiencyResult(
        authority=all(item.authority_tier is not None for item in items),
        coverage=bool(items) and not gaps,
        curriculum_fit=True,
        pedagogical_fit=True,
        no_conflict=True,
        freshness=True,
        disclosure=True,
        modality=True,
        gap_reasons=gaps,
    )

    return EvidencePack(
        pack_id=pack_id,
        plan_id=plan.plan_id,
        interaction_id=plan.interaction_id,
        status=PackStatus.SUFFICIENT if sufficiency.passed else PackStatus.INSUFFICIENT,
        evidence=items,
        citations=citations,
        sufficiency=sufficiency,
        release_manifest_id=release_manifest_id,
        trace_id=trace_id,
    )
