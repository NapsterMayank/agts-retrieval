"""Retrievers, including the four deliberately broken ones §6.5 requires.

The broken retrievers are not a joke fixture. A scorer that cannot separate them
from an honest baseline is not measuring retrieval, and every number downstream
of it is decoration. They are run as a blocking test.

Each broken retriever fails in a *different* way, so a scorer that catches only
one of them is still not trusted:

    RandomRanking   -> ordering is worthless, authorisation intact
    WrongGrade      -> curriculum identity ignored
    AnswerOnly      -> disclosure ceiling ignored (returns solutions)
    CrossTenant     -> tenant boundary ignored
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass
from typing import Protocol

from agts.contracts.common import DISCLOSURE_RANK, DisclosureClass, ObjectType
from agts.contracts.runtime import QueryPlan, RetrievedItem
from agts.evaluation.corpus import Corpus

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


class Retriever(Protocol):
    """Every retriever, honest or broken, answers the same question."""

    name: str

    def retrieve(self, plan: QueryPlan, corpus: Corpus, k: int) -> list[RetrievedItem]:
        ...


def _rank(scored: list[tuple[float, str, tuple[str, ...]]], k: int) -> list[RetrievedItem]:
    """Stable descending rank, ties broken by object id so runs are reproducible."""
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [RetrievedItem(object_id=oid, block_ids=bids, score=s) for s, oid, bids in scored[:k]]


# --------------------------------------------------------------------------
# The honest baseline
# --------------------------------------------------------------------------


class KeywordBaseline:
    """IDF-weighted token overlap over *authorised* candidates only.

    Weak on purpose. Phase 0 needs a floor to measure lift against, not a good
    retriever -- if a component cannot beat this, it has not earned its cost.

    Weighted rather than counted, because a raw overlap count is not a confidence
    signal: matching only "of" and "a" scores a third of a perfect match, so an
    out-of-corpus query never looks unanswerable and the abstention number is
    fiction. IDF costs ten lines and makes the score mean something, which the
    sufficiency gate in §8.4 later depends on.
    """

    name = "keyword-baseline"

    def __init__(self) -> None:
        self._idf_cache: dict[int, dict[str, float]] = {}

    def _idf(self, corpus: Corpus) -> dict[str, float]:
        key = id(corpus)
        cached = self._idf_cache.get(key)
        if cached is not None:
            return cached

        docs = [_tokens(f"{o.heading_path} {o.text}") for o in corpus.unfiltered()]
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
        # An unseen query token is maximally rare, so it cannot be scored against
        # this corpus -- give it the highest observed weight rather than zero.
        default = max(idf.values(), default=1.0)
        query_mass = sum(idf.get(t, default) for t in query) or 1.0

        scored: list[tuple[float, str, tuple[str, ...]]] = []
        for obj in corpus.authorised(plan):
            overlap = query & _tokens(f"{obj.heading_path} {obj.text}")
            if not overlap:
                continue
            matched = sum(idf.get(t, default) for t in overlap)
            scored.append((matched / query_mass, obj.object_id, tuple(obj.block_ids)))
        return _rank(scored, k)


# --------------------------------------------------------------------------
# The four broken retrievers (§6.5)
# --------------------------------------------------------------------------


@dataclass
class RandomRanking:
    """Authorised candidates in a meaningless order.

    Catches a scorer that rewards *returning something* rather than returning the
    right thing. Seeded, so a failure is reproducible.
    """

    seed: int = 20260824
    name: str = "broken-random-ranking"

    def retrieve(self, plan: QueryPlan, corpus: Corpus, k: int) -> list[RetrievedItem]:
        rng = random.Random(self.seed + hash(plan.plan_id) % 100_000)
        candidates = corpus.authorised(plan)
        rng.shuffle(candidates)
        return [
            RetrievedItem(object_id=obj.object_id, block_ids=tuple(obj.block_ids), score=1.0 - i / max(len(candidates), 1))
            for i, obj in enumerate(candidates[:k])
        ]


class WrongGrade:
    """Ignores curriculum identity and prefers the wrong grade.

    Catches a scorer that treats topical similarity as correctness. A grade-7
    passage about reflection is *about* the query and is still the wrong answer.
    """

    name = "broken-wrong-grade"

    def retrieve(self, plan: QueryPlan, corpus: Corpus, k: int) -> list[RetrievedItem]:
        query = _tokens(plan.query_text)
        scored: list[tuple[float, str, tuple[str, ...]]] = []
        for obj in corpus.unfiltered():
            overlap = query & _tokens(f"{obj.heading_path} {obj.text}")
            if not overlap:
                continue
            base = len(overlap) / len(query or {"x"})
            # Actively prefer the wrong grade.
            bonus = 1.0 if obj.curriculum.grade != plan.curriculum.grade else 0.0
            scored.append((base + bonus, obj.object_id, tuple(obj.block_ids)))
        return _rank(scored, k)


class AnswerOnly:
    """Ranks solutions, answers and rubrics first, whatever the disclosure ceiling.

    Catches a scorer with no leakage counter. This retriever can score well on
    recall while being the single most damaging failure in the product.
    """

    name = "broken-answer-only"
    _protected = {
        ObjectType.ASSESSMENT_SOLUTION,
        ObjectType.ANSWER,
        ObjectType.RUBRIC,
    }

    def retrieve(self, plan: QueryPlan, corpus: Corpus, k: int) -> list[RetrievedItem]:
        query = _tokens(plan.query_text)
        scored: list[tuple[float, str, tuple[str, ...]]] = []
        for obj in corpus.unfiltered():
            overlap = query & _tokens(f"{obj.heading_path} {obj.text}")
            base = len(overlap) / len(query or {"x"}) if overlap else 0.0
            bonus = 2.0 if obj.object_type in self._protected else 0.0
            if base == 0.0 and bonus == 0.0:
                continue
            scored.append((base + bonus, obj.object_id, tuple(obj.block_ids)))
        return _rank(scored, k)


class CrossTenant:
    """Ranks another tenant's private content first.

    Catches a scorer with no isolation counter. §14 gates this at zero, so a
    single returned row is a release blocker, not a quality regression.
    """

    name = "broken-cross-tenant"

    def retrieve(self, plan: QueryPlan, corpus: Corpus, k: int) -> list[RetrievedItem]:
        query = _tokens(plan.query_text)
        scored: list[tuple[float, str, tuple[str, ...]]] = []
        for obj in corpus.unfiltered():
            overlap = query & _tokens(f"{obj.heading_path} {obj.text}")
            base = len(overlap) / len(query or {"x"}) if overlap else 0.0
            foreign = (
                obj.tenant_scope is not None
                and obj.tenant_scope != plan.learner.tenant_id
            )
            bonus = 2.0 if foreign else 0.0
            if base == 0.0 and bonus == 0.0:
                continue
            scored.append((base + bonus, obj.object_id, tuple(obj.block_ids)))
        return _rank(scored, k)


def broken_retrievers() -> list[Retriever]:
    """The full §6.5 set. The scorer must rank every one of these below the
    honest baseline, or the evaluation system itself fails."""
    return [RandomRanking(), WrongGrade(), AnswerOnly(), CrossTenant()]


__all__ = [
    "AnswerOnly",
    "CrossTenant",
    "DISCLOSURE_RANK",
    "DisclosureClass",
    "KeywordBaseline",
    "RandomRanking",
    "RetrievedItem",
    "Retriever",
    "WrongGrade",
    "broken_retrievers",
]
