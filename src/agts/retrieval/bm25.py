"""BM25 over search representations (§7.3).

The IDF baseline scores `matched_idf / query_idf_mass`, which has two defects
that only showed up once real content was measured:

**No length normalisation.** A long window matches more terms than a short one
for reasons that have nothing to do with relevance.

**No term saturation.** A term occurring eight times counts eight times, so one
repeated word outweighs three distinct ones — and the queries a learner asks are
mostly distinct words.

Between them these are why "State Ohm's law and give its mathematical form"
scored 0.63 against a chemistry chapter: credit for *law*, *form* and *give*,
with nothing to say those matches are cheap. BM25 answers both with two
parameters and no model, which makes it the honest thing to try before reaching
for embeddings — an embedding that cannot beat it has not earned its cost.

The score is divided by the query's own maximum attainable score, so it lands in
0..1 and is comparable across queries. Abstention needs that: a threshold over
raw BM25 is a threshold over query length.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from agts.contracts.runtime import QueryPlan, RetrievedItem
from agts.evaluation.corpus import Corpus
from agts.retrieval.query import search_query

_TOKEN = re.compile(r"[a-z0-9]+")

#: Term-frequency saturation. 1.2 is the standard default; above it a repeated
#: term keeps earning, below it the first occurrence is nearly all that counts.
K1 = 1.2

#: Length normalisation strength. 0.75 is the standard default: full
#: normalisation (1.0) over-punishes the long windows that legitimately cover
#: more of a section.
B = 0.75


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class BM25Representations:
    """BM25 over the authorised representations of a corpus.

    Index state is cached per corpus object. The corpus is frozen and the
    representations are immutable, so the cache cannot go stale without a new
    corpus being built.
    """

    name = "representation-bm25"

    def __init__(self, k1: float = K1, b: float = B) -> None:
        self.k1 = k1
        self.b = b
        self._index: dict[int, tuple[dict[str, float], dict[str, Counter], dict[str, int], float]] = {}

    def _build(self, corpus: Corpus):
        key = id(corpus)
        cached = self._index.get(key)
        if cached is not None:
            return cached

        frequencies: dict[str, Counter] = {}
        lengths: dict[str, int] = {}
        document_frequency: Counter = Counter()

        for rep in corpus.representations.values():
            terms = _tokens(rep.search_text)
            counts = Counter(terms)
            frequencies[rep.representation_id] = counts
            lengths[rep.representation_id] = len(terms)
            document_frequency.update(counts.keys())

        n = len(frequencies) or 1
        average_length = (sum(lengths.values()) / n) if lengths else 1.0
        # Robertson/Sparck Jones IDF, the +0.5 form, floored at zero so a term in
        # almost every window cannot contribute a negative score and make a
        # matching window rank below a non-matching one.
        idf = {
            term: max(0.0, math.log(1.0 + (n - df + 0.5) / (df + 0.5)))
            for term, df in document_frequency.items()
        }

        built = (idf, frequencies, lengths, average_length or 1.0)
        self._index[key] = built
        return built

    def score_windows(self, plan: QueryPlan, corpus: Corpus) -> dict[str, float]:
        """Every authorised window's score, keyed by representation id.

        The mirror of `DenseRetriever.score_windows`, added so the pack builder
        can ask *both* retrievers about a sibling window instead of admitting it
        on the primary's word alone -- in precisely the band where the gate
        requires two retrievers to agree (R-045).
        """
        idf, frequencies, lengths, average_length = self._build(corpus)
        query = _tokens(search_query(plan))
        if not query:
            return {}
        default = max(idf.values(), default=1.0)
        weights = {term: idf.get(term, default) for term in set(query)}
        ceiling = sum(w * (self.k1 + 1) / self.k1 for w in weights.values()) or 1.0

        scores: dict[str, float] = {}
        for rep, _ in corpus.authorised_representations(plan):
            counts = frequencies.get(rep.representation_id)
            if counts is None:
                continue
            length = lengths.get(rep.representation_id, 0)
            norm = self.k1 * (1 - self.b + self.b * length / average_length)
            total = sum(
                weight * (counts.get(term, 0) * (self.k1 + 1)) / (counts.get(term, 0) + norm)
                for term, weight in weights.items()
                if counts.get(term, 0)
            )
            if total > 0.0:
                scores[rep.representation_id] = total / ceiling
        return scores

    def retrieve(self, plan: QueryPlan, corpus: Corpus, k: int) -> list[RetrievedItem]:
        idf, frequencies, lengths, average_length = self._build(corpus)
        query = _tokens(search_query(plan))
        if not query:
            return []

        # An unseen query term is maximally rare against this corpus, so it is
        # scored at the highest observed weight rather than dropped. Dropping it
        # would make an out-of-corpus query look like a short in-corpus one.
        default = max(idf.values(), default=1.0)
        weights = {term: idf.get(term, default) for term in set(query)}
        # The ceiling a perfect window would reach: every query term saturated.
        ceiling = sum(w * (self.k1 + 1) / self.k1 for w in weights.values()) or 1.0

        best: dict[str, RetrievedItem] = {}
        for rep, obj in corpus.authorised_representations(plan):
            counts = frequencies.get(rep.representation_id)
            if counts is None:
                continue
            length = lengths.get(rep.representation_id, 0)
            norm = self.k1 * (1 - self.b + self.b * length / average_length)

            total = 0.0
            for term, weight in weights.items():
                tf = counts.get(term, 0)
                if tf:
                    total += weight * (tf * (self.k1 + 1)) / (tf + norm)
            if total <= 0.0:
                continue

            score = total / ceiling
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
