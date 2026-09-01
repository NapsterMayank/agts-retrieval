"""Dense and hybrid retrieval over search representations (§7.3).

Dense retrieval exists here to answer a specific question the lexical runs
raised, not because it is the fashionable component: **the answerable cases at
the bottom of the band are ones whose evidence does not repeat the query's
words** — the atom-count question answered by a table, "why is the negative root
rejected", rancidity. Those are paraphrase failures, which is what an embedding
is actually for.

It is not expected to fix the *unanswerable* cases at the top of the band.
"Completing the square" is genuinely, semantically present in that chapter; it is
simply never taught. Expecting a similarity score to encode a curriculum
judgement is expecting the wrong thing (R-019).

Hybrid fusion is **reciprocal rank fusion**, not a weighted score sum. BM25 and
cosine are not on a common scale, and a weight between them is a hyperparameter
tuned on the gold set — which is tuning on the ruler. RRF uses only rank, has one
constant with a standard value, and cannot be quietly fitted.
"""

from __future__ import annotations

from agts.contracts.runtime import QueryPlan, RetrievedItem
from agts.evaluation.corpus import Corpus
from agts.platform.embedding import EmbeddingPort, cosine
from agts.retrieval.bm25 import BM25Representations
from agts.retrieval.query import search_query

#: RRF's damping constant. 60 is the value from the original paper and is not
#: tuned here on purpose: a constant fitted to sixty cases is a constant fitted
#: to noise.
RRF_K = 60


#: How many windows of one object may stand for it. Not many: five windows of
#: one section are still not five pieces of evidence (R-018), and the point of
#: window-level retrieval was that it packs 43 blocks where object-level packs
#: 143.
#:
#: Two when this was introduced. Three since R-074, because correcting six
#: sentences changed their windows' scores enough to reshuffle which window of a
#: section wins, and recall fell 99.1% to 98.2% on cases whose right *object*
#: was still retrieved. Four measured identically to three, so three is where it
#: saturates rather than a number picked to reach a target. It costs one block
#: per pack: 38.4 against 37.4.
WINDOWS_PER_OBJECT = 3

#: And the second one only when it is this close to the best. Keeping one window
#: per object discarded the gold window of five answerable cases while retrieving
#: the right object every time -- for "discriminant" the window holding the
#: answer scored 0.7846 against 0.7917 for a sibling, a gap of 0.007 deciding
#: which paragraph of the right section a learner saw.
#:
#: 0.02 is roughly three times that gap, and 0.05 admits exactly the same windows
#: on this corpus, so the value is not doing fine-grained work. What it rules out
#: is a genuinely worse window riding in on a good one.
WINDOW_MARGIN = 0.02


def windows_for_object(scored: list[tuple[float, object]]) -> list[tuple[float, object]]:
    """The windows allowed to represent one object, best first.

    A near-tie between two windows of the same section is not a decision about
    which paragraph answers the question; it is the absence of one. Where the
    scores separate, the best window stands alone.
    """
    if not scored:
        return []
    ordered = sorted(scored, key=lambda pair: -pair[0])
    best = ordered[0][0]
    kept = [pair for pair in ordered[:WINDOWS_PER_OBJECT] if pair[0] >= best - WINDOW_MARGIN]
    return kept


class DenseRetriever:
    """Cosine similarity over pre-embedded representations.

    Representations without a vector are skipped rather than silently scored at
    zero, and the count is available as `skipped` after a call — an index that
    is half embedded should look like a broken index, not like poor recall.
    """

    def __init__(self, embedder: EmbeddingPort, name: str = "representation-dense") -> None:
        self.embedder = embedder
        self.name = name
        self.skipped = 0

    def score_windows(self, plan: QueryPlan, corpus: Corpus) -> dict[str, float]:
        """Every authorised window's score, keyed by representation id.

        `retrieve` keeps one window per object, which is right for ranking and
        wrong for citation: 31 of 31 missing gold blocks turned out to sit in a
        sibling window of an object the pack had already selected. The pack
        builder needs the siblings' scores to decide which of them clear the
        same bar, so they are exposed rather than recomputed from a guess.
        """
        query_vector = self.embedder.embed_query(search_query(plan))
        return {
            rep.representation_id: (cosine(query_vector, rep.vector) + 1.0) / 2.0
            for rep, _ in corpus.authorised_representations(plan)
            if rep.vector is not None and rep.embedding_model == self.embedder.model
        }

    def retrieve(self, plan: QueryPlan, corpus: Corpus, k: int) -> list[RetrievedItem]:
        query_vector = self.embedder.embed_query(search_query(plan))
        by_object: dict[str, list[tuple[float, object]]] = {}
        skipped = 0

        for rep, obj in corpus.authorised_representations(plan):
            if rep.vector is None or rep.embedding_model != self.embedder.model:
                skipped += 1
                continue
            # Cosine sits in [-1, 1]; map to [0, 1] so it is comparable with the
            # normalised BM25 score and can be thresholded the same way.
            score = (cosine(query_vector, rep.vector) + 1.0) / 2.0
            by_object.setdefault(obj.object_id, []).append((score, rep))

        items = [
            RetrievedItem(
                object_id=object_id,
                block_ids=tuple(rep.block_ids),
                score=score,
                representation_id=rep.representation_id,
            )
            for object_id, scored in by_object.items()
            for score, rep in windows_for_object(scored)
        ]

        self.skipped = skipped
        return sorted(items, key=lambda i: (-i.score, i.object_id))[:k]


class HybridRetriever:
    """Reciprocal rank fusion of BM25 and dense.

    **Fusion decides the order; it does not decide the score.** RRF is the right
    way to merge two rankings that share no scale, and the wrong thing to hand a
    calibrated abstention floor. `sum(1 / (k + rank))` at corroboration depth has
    nine reachable values, so on the first real-content run 61 of 109 answerable
    cases tied at exactly 1.0 — "both retrievers ranked it first" — and a
    threshold placed inside that tie mass decided on rank-1-versus-rank-2 noise.
    Hybrid scored 0.355 abstention accuracy where its own dense half scored
    0.903 on the same cases.

    So an item keeps a magnitude: the dense score of the window being returned.
    Ordering stays rank-fused, scoring comes from the retriever that measures
    similarity rather than agreement. A window the dense run cannot score — no
    vector, or embedded by another model — keeps the score of whichever run did
    rank it, because a missing embedding is an index defect and must not read as
    a weak match.
    """

    name = "representation-hybrid"

    def __init__(self, embedder: EmbeddingPort, *, rrf_k: int = RRF_K) -> None:
        self.lexical = BM25Representations()
        self.dense = DenseRetriever(embedder)
        self.rrf_k = rrf_k

    def retrieve(self, plan: QueryPlan, corpus: Corpus, k: int) -> list[RetrievedItem]:
        depth = max(k, 20)
        runs = [
            self.lexical.retrieve(plan, corpus, depth),
            self.dense.retrieve(plan, corpus, depth),
        ]

        fused: dict[str, float] = {}
        source: dict[str, RetrievedItem] = {}
        for run in runs:
            # Rank objects, not items. Dense may return two windows of one
            # object (R-070), and RRF scores by position: leaving both in
            # pushes every later object down a rank it did not earn, which cost
            # this retriever four points of pack recall the day window budgets
            # went in.
            seen: set[str] = set()
            deduped = []
            for item in run:
                if item.object_id in seen:
                    continue
                seen.add(item.object_id)
                deduped.append(item)
            for rank, item in enumerate(deduped, start=1):
                fused[item.object_id] = fused.get(item.object_id, 0.0) + 1.0 / (self.rrf_k + rank)
                # Keep the lineage of whichever run ranked it highest, so the
                # blocks reported are the ones some retriever actually chose.
                best = source.get(item.object_id)
                if best is None or item.score > best.score:
                    source[item.object_id] = item

        # Rank order from the fusion, magnitude from the dense run.
        ceiling = sum(1.0 / (self.rrf_k + 1) for _ in runs) or 1.0
        windows = self.dense.score_windows(plan, corpus)

        items = []
        for object_id, total in fused.items():
            chosen = source[object_id]
            items.append(
                (
                    total / ceiling,
                    RetrievedItem(
                        object_id=object_id,
                        block_ids=chosen.block_ids,
                        score=windows.get(chosen.representation_id, chosen.score),
                        representation_id=chosen.representation_id,
                    ),
                )
            )

        # Sorting on the fused rank, not on the reported score: they answer
        # different questions and only the first one orders the pack.
        items.sort(key=lambda pair: (-pair[0], pair[1].object_id))
        return [item for _, item in items[:k]]
