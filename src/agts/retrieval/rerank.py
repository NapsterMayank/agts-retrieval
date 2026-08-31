"""Reranked retrieval (section 8, Q4).

Wraps a retriever: take its candidates at depth, reorder them with a reranker,
return the top k. Two decisions worth stating.

**It reranks windows, not objects.** The candidate that gets scored is the exact
text a citation would quote. Reranking whole sections would score text the pack
never shows.

**It keeps the retriever's candidate set.** A reranker that could add documents
would be a retriever, and the reason to separate the two stages is that recall
and ordering fail differently and must be measured apart — `recall@20` is the
retriever's number, `recall@pack` is this stage's.
"""

from __future__ import annotations

from agts.contracts.runtime import QueryPlan, RetrievedItem
from agts.evaluation.corpus import Corpus
from agts.platform.reranking import RerankPort
from agts.retrieval.query import search_query

#: How many candidates are handed to the reranker. Deeper costs money per query
#: and cannot help beyond the retriever's own recall at that depth.
RERANK_DEPTH = 20


class RerankedRetriever:
    """A retriever plus a reranker, measured as one stage."""

    def __init__(
        self,
        retriever,
        reranker: RerankPort,
        *,
        depth: int = RERANK_DEPTH,
        name: str | None = None,
    ) -> None:
        self.retriever = retriever
        self.reranker = reranker
        self.depth = depth
        self.name = name or f"{getattr(retriever, 'name', 'retriever')}+rerank"

    def score_windows(self, plan: QueryPlan, corpus: Corpus) -> dict[str, float]:
        """Delegated unchanged.

        The pack builder uses these to pull in sibling windows that clear the
        abstention floor, and that floor is calibrated on the *retriever's*
        score distribution. Substituting rerank scores here would compare a
        number against a threshold derived from a different scale.
        """
        inner = getattr(self.retriever, "score_windows", None)
        return inner(plan, corpus) if inner else {}

    def retrieve(self, plan: QueryPlan, corpus: Corpus, k: int) -> list[RetrievedItem]:
        candidates = self.retriever.retrieve(plan, corpus, max(k, self.depth))
        if len(candidates) < 2:
            return candidates[:k]

        documents = []
        for item in candidates:
            rep = corpus.representations.get(item.representation_id or "")
            if rep is not None:
                documents.append(rep.search_text)
            else:
                obj = corpus.objects.get(item.object_id)
                documents.append(obj.text if obj else "")

        scores = self.reranker.rerank(search_query(plan), documents)
        reranked = [
            RetrievedItem(
                object_id=item.object_id,
                block_ids=item.block_ids,
                score=score,
                representation_id=item.representation_id,
            )
            for item, score in zip(candidates, scores)
        ]
        reranked.sort(key=lambda item: (-item.score, item.object_id))
        return reranked[:k]
