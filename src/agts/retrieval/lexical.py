"""Lexical retrieval over search representations (§7.3).

The same IDF scoring as the object-level keyword baseline, over the smaller unit
from :mod:`agts.retrieval.chunking`. Holding the scoring function constant is
the point: the only variable between this and `keyword-baseline` is what gets
ranked, so any difference in the numbers is attributable to the unit and not to
a better matcher.

It still ranks only what `Corpus.authorised_representations` returns, so the §5
boundary is applied before scoring rather than after.
"""

from __future__ import annotations

import math
import re

from agts.contracts.runtime import QueryPlan, RetrievedItem
from agts.evaluation.corpus import Corpus

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


class RepresentationKeyword:
    """IDF-weighted token overlap over representations, best window per object.

    Two decisions worth naming:

    **The document frequency is computed over representations**, not objects. A
    term appearing once in a 4,000-character section looks rare at object level
    and common at window level, and the window number is the honest one — it is
    the unit being ranked.

    **One item per parent object, its best-scoring window.** A pack of five
    slots filled by five windows of the same section is not five pieces of
    evidence, and pack recall would flatter it.
    """

    name = "representation-keyword"

    def __init__(self) -> None:
        self._idf_cache: dict[int, dict[str, float]] = {}

    def _idf(self, corpus: Corpus) -> dict[str, float]:
        key = id(corpus)
        cached = self._idf_cache.get(key)
        if cached is not None:
            return cached

        docs = [_tokens(rep.search_text) for rep in corpus.representations.values()]
        n = len(docs) or 1
        document_frequency: dict[str, int] = {}
        for doc in docs:
            for token in doc:
                document_frequency[token] = document_frequency.get(token, 0) + 1

        idf = {t: math.log(1.0 + n / (1.0 + df)) for t, df in document_frequency.items()}
        self._idf_cache[key] = idf
        return idf

    def retrieve(self, plan: QueryPlan, corpus: Corpus, k: int) -> list[RetrievedItem]:
        idf = self._idf(corpus)
        query = _tokens(plan.query_text)
        default = max(idf.values(), default=1.0)
        query_mass = sum(idf.get(t, default) for t in query) or 1.0

        best: dict[str, RetrievedItem] = {}
        for rep, obj in corpus.authorised_representations(plan):
            overlap = query & _tokens(rep.search_text)
            if not overlap:
                continue
            score = sum(idf.get(t, default) for t in overlap) / query_mass
            current = best.get(obj.object_id)
            if current is None or score > current.score:
                best[obj.object_id] = RetrievedItem(
                    object_id=obj.object_id,
                    block_ids=tuple(rep.block_ids),
                    score=score,
                    representation_id=rep.representation_id,
                )

        ranked = sorted(best.values(), key=lambda item: (-item.score, item.object_id))
        return ranked[:k]
