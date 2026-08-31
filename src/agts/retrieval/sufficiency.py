"""The sufficiency gate (§8.4) — the real abstention mechanism (R-019).

Three runs established that no retrieval score separates answerable from
unanswerable on real content, and the diagnostic said why: the queries that
score highest among the unanswerable are the ones these chapters **mention
without teaching** — completing the square, the Pythagoras theorem, the distance
formula. A scorer is right to report a strong match there. The distinction is
not in the score.

So the gate is two-tiered, and corroboration is required only where it is
informative:

**1. Is anything a good enough match?** A calibrated floor on the top score.
Measured from the observed distributions, never picked by hand (§15). Below it,
abstain.

**Above the highest score any unanswerable query achieved**, answer. Nothing is
gained by interrogating a match that no unanswerable query in the set has ever
matched, and requiring corroboration there abstains on textbook questions like
"What is a quadratic equation?" purely because two retrievers ranked two equally
correct sections differently.

**2. In the band between the two — do independent retrievers agree on where the
answer lives?** This is the
part that catches a mention. When a chapter *teaches* a concept it elaborates:
several windows in one section discuss it, so lexical and semantic retrieval
land on the same object. When a chapter merely *names* a concept, they diverge —
lexical retrieval finds the single sentence containing the phrase, while
semantic retrieval drifts to whatever section is actually about something
similar. Corroboration measures that divergence without needing to know which
retriever is right.

A gate is a decision, so it returns its reasons. "Abstained" with no explanation
is indistinguishable from a broken retriever, and the trace §11 requires has to
say which of the two conditions failed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agts.contracts.common import ObjectType
from agts.contracts.runtime import QueryPlan, RetrievedItem
from agts.evaluation.corpus import Corpus

#: How many of the top three objects the two retrievers must share. Two of three
#: is deliberately not three: requiring unanimity would abstain whenever a
#: section is split across windows, which is a property of chunking rather than
#: of the corpus lacking an answer.
MIN_CORROBORATION = 2

#: Depth at which agreement is measured. Small on purpose — agreement at depth
#: twenty is agreement about the corpus, not about the answer.
CORROBORATION_DEPTH = 3

#: Object types that mean "this section teaches the concept" rather than
#: "this section mentions it". They come from the hand-written section map
#: (R-009) — a curriculum judgement made by a human, not a parser or a model.
TEACHING_TYPES = frozenset({ObjectType.DEFINITION, ObjectType.CONCEPT})


def _same_passage(mine: RetrievedItem, theirs: RetrievedItem) -> bool:
    """Whether two retrievers landed on the same passage, not just the same section.

    Same window, or windows sharing a block. Block overlap rather than window
    identity because the two retrievers pick their own best window per object and
    adjacent windows can legitimately carry the same evidence -- but two windows
    with no block in common are two different answers.
    """
    if mine.representation_id and mine.representation_id == theirs.representation_id:
        return True
    return bool(set(mine.block_ids) & set(theirs.block_ids))


@dataclass(frozen=True)
class SufficiencyDecision:
    """Whether the pack may be answered from, and why."""

    answerable: bool
    top_score: float
    corroboration: int
    threshold: float
    high_confidence: float = float("inf")
    anchored_on_teaching_object: bool = False
    #: Which retriever produced `items`. Carried so an evidence item can name
    #: its generator honestly (§11 provenance) instead of saying "retrieval".
    primary_name: str = "retrieval"
    #: Every authorised window's score, when the primary retriever can supply
    #: them. The pack builder uses these to pull in sibling windows that clear
    #: the same floor; without them it packs only the ranked windows.
    window_scores: dict[str, float] = field(default_factory=dict)
    #: The corroborator's view of the same windows. The pack builder needs it to
    #: admit a sibling on two opinions rather than one -- the sibling band is
    #: exactly where the gate itself demands agreement (R-045).
    corroborator_windows: dict[str, float] = field(default_factory=dict)
    items: list[RetrievedItem] = field(default_factory=list)
    reasons: tuple[str, ...] = ()

    @property
    def abstained(self) -> bool:
        return not self.answerable


class SufficiencyGate:
    """Runs two retrievers and decides whether their agreement is good enough.

    `primary` produces the pack that is returned; `corroborator` is only ever
    consulted for agreement, so swapping it cannot silently change what a
    learner is shown.
    """

    name = "sufficiency-gate"

    def __init__(
        self,
        primary,
        corroborator,
        *,
        threshold: float,
        high_confidence: float | None = None,
        min_corroboration: int = MIN_CORROBORATION,
        depth: int = CORROBORATION_DEPTH,
        teaching_types: frozenset = TEACHING_TYPES,
    ) -> None:
        # Checked here because each of these silently disables a condition
        # rather than failing: min_corroboration <= 0 turns the corroboration
        # requirement off, depth <= 0 compares empty sets, and a ceiling below
        # the floor makes the high-confidence branch unreachable while looking
        # configured. All three were reported by an outside review.
        if min_corroboration < 1:
            raise ValueError("min_corroboration below 1 disables corroboration entirely")
        if depth < 1:
            raise ValueError("depth below 1 compares empty candidate sets")
        if high_confidence is not None and high_confidence <= threshold:
            # Equal is the trap, not just below. With a ceiling equal to the
            # floor the band is empty, so every score at or above the floor
            # takes the high-confidence branch and corroboration never runs --
            # a gate that looks fully configured and has one condition switched
            # off. Reported by a second outside reviewer.
            raise ValueError(
                f"high_confidence {high_confidence} is not above the floor {threshold}: "
                "the band between them would be empty and the corroboration rule dead"
            )
        self.primary = primary
        self.corroborator = corroborator
        self.threshold = threshold
        # Default of +inf means "always require corroboration", so an operator
        # who does not supply the ceiling gets the strict gate rather than a
        # silently permissive one.
        self.high_confidence = float("inf") if high_confidence is None else high_confidence
        self.min_corroboration = min_corroboration
        self.depth = depth
        self.teaching_types = teaching_types

    def decide(self, plan: QueryPlan, corpus: Corpus, k: int = 20) -> SufficiencyDecision:
        items = self.primary.retrieve(plan, corpus, k)
        other = self.corroborator.retrieve(plan, corpus, max(k, self.depth))

        top_score = items[0].score if items else 0.0
        # Agreement is on the *passage*, not merely the section. Both retrievers
        # return their own best window per object, so comparing object ids alone
        # counted "we both like this section" as "we both found the answer" --
        # they could be pointing at different paragraphs. A shared object counts
        # only when the two windows are the same, or overlap in blocks.
        mine = {i.object_id: i for i in items[: self.depth]}
        theirs = {i.object_id: i for i in other[: self.depth]}
        shared = {
            object_id
            for object_id in mine.keys() & theirs.keys()
            if _same_passage(mine[object_id], theirs[object_id])
        }
        corroboration = len(shared)

        # Weak agreement is enough when it is anchored on a section the
        # curriculum classifies as *teaching* the concept. Measured, not
        # assumed: "What is a decomposition reaction?" has the definition
        # section ranked first by one retriever and the exercises ranked first
        # by the other, because a definition legitimately appears in the
        # section, the summary and the exercises. Requiring two shared objects
        # there refuses a textbook question. "Completing the square" has no
        # definition section to anchor on -- both retrievers land on the
        # introduction that names it in passing -- so it still abstains.
        # The anchor has to be a *shared* object. An earlier version asked only
        # whether either retriever ranked some teaching object first, which let
        # an unrelated definition at rank 1 bless a match the two retrievers
        # disagreed about -- reported by an outside review, and correct.
        anchored = any(
            object_id in corpus.objects
            and corpus.objects[object_id].object_type in self.teaching_types
            for object_id in shared
        )

        reasons: list[str] = []
        if not items:
            reasons.append("no candidate survived the authorisation filter")
        if items and top_score < self.threshold:
            reasons.append(
                f"top score {top_score:.3f} below the calibrated floor {self.threshold:.3f}"
            )
        if (
            items
            and top_score < self.high_confidence
            and corroboration < self.min_corroboration
            and not anchored
        ):
            reasons.append(
                f"only {corroboration} of the top {self.depth} objects are shared by both "
                f"retrievers, which is what a concept that is named but not taught looks like"
            )

        score_windows = getattr(self.primary, "score_windows", None)
        other_windows = getattr(self.corroborator, "score_windows", None)
        return SufficiencyDecision(
            primary_name=getattr(self.primary, "name", "retrieval"),
            window_scores=score_windows(plan, corpus) if score_windows else {},
            corroborator_windows=other_windows(plan, corpus) if other_windows else {},
            answerable=not reasons,
            top_score=top_score,
            corroboration=corroboration,
            anchored_on_teaching_object=anchored,
            threshold=self.threshold,
            high_confidence=self.high_confidence,
            items=items,
            reasons=tuple(reasons),
        )

    def retrieve(self, plan: QueryPlan, corpus: Corpus, k: int) -> list[RetrievedItem]:
        """Retriever interface: an abstention returns nothing.

        The scorer reads an empty result as an abstention, which is the correct
        reading — a gate that abstains has decided the pack must not be answered
        from, and handing it back anyway would leave the decision advisory.
        """
        decision = self.decide(plan, corpus, k)
        return decision.items if decision.answerable else []
