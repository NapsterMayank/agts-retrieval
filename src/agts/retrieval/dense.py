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
        best: dict[str, RetrievedItem] = {}
        skipped = 0

        for rep, obj in corpus.authorised_representations(plan):
            if rep.vector is None or rep.embedding_model != self.embedder.model:
                skipped += 1
                continue
            # Cosine sits in [-1, 1]; map to [0, 1] so it is comparable with the
            # normalised BM25 score and can be thresholded the same way.
            score = (cosine(query_vector, rep.vector) + 1.0) / 2.0
            current = best.get(obj.object_id)
            if current is None or score > current.score:
                best[obj.object_id] = RetrievedItem(
                    object_id=obj.object_id,
                    block_ids=tuple(rep.block_ids),
                    score=score,
                    representation_id=rep.representation_id,
                )

        self.skipped = skipped
        return sorted(best.values(), key=lambda i: (-i.score, i.object_id))[:k]


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
            for rank, item in enumerate(run, start=1):
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
