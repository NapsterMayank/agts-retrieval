"""Reranking port and adapters (section 8, and Q4).

A reranker reorders candidates a retriever already found. It cannot add recall
at candidate depth and it can destroy it at pack depth, which is exactly the
failure Q4 asks the client to gate: twenty correct candidates, the gold span
ordered into position nine of a five-slot pack, `recall@20` passing at 95% and
the teaching loop receiving nothing usable.

So the number this is judged on is **pack recall**, not candidate recall, and a
reranker that does not improve it does not ship. Same rule as the embedding
adapter: no provider name appears outside this module.

`CachedReranker` keys on the query and the exact candidate texts, so a scored
run is reproducible and re-running costs nothing. Reranking is a paid call per
query, and a benchmark that silently re-bills on every run is a benchmark nobody
repeats.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Protocol, Sequence


class RerankPort(Protocol):
    """What retrieval is allowed to know about reranking."""

    model: str

    def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        """A relevance score per document, in the order given."""
        ...


class VoyageReranker:
    """Voyage rerank over HTTPS.

    The API returns results ordered by relevance with an index into the input;
    they are mapped back into input order here, because a caller that zips a
    reordered response against its own candidate list gets silently wrong
    scores.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "rerank-2",
        *,
        timeout: float = 60.0,
        max_documents: int = 100,
    ) -> None:
        self.model = model
        self.timeout = timeout
        self.max_documents = max_documents
        self._key = api_key or os.environ.get("VOYAGE_API_KEY", "")
        if not self._key:
            raise RuntimeError("no VOYAGE_API_KEY; pass one or use IdentityReranker")

    def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        import requests

        if not documents:
            return []
        batch = list(documents[: self.max_documents])
        for attempt in range(4):
            response = requests.post(
                "https://api.voyageai.com/v1/rerank",
                headers={"Authorization": f"Bearer {self._key}"},
                json={"query": query, "documents": batch, "model": self.model},
                timeout=self.timeout,
            )
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            response.raise_for_status()
            scores = [0.0] * len(batch)
            for row in response.json()["data"]:
                scores[row["index"]] = float(row["relevance_score"])
            # Documents past the cap keep a zero score rather than being dropped,
            # so the caller's list length is never silently changed.
            return scores + [0.0] * (len(documents) - len(batch))
        raise RuntimeError("voyage rerank: giving up after retries")


class IdentityReranker:
    """Preserves the incoming order. The control condition.

    Not a stub: a reranker has to be measured against *not reranking*, and
    "we added a reranker and the number went up" is not that comparison unless
    the same harness ran without one.
    """

    model = "identity"

    def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        n = len(documents)
        return [(n - i) / n for i in range(n)]


class CachedReranker:
    """Disk cache keyed by the query and the exact candidate set."""

    def __init__(self, inner: RerankPort | None, path: Path, *, model: str | None = None) -> None:
        self.inner = inner
        self.model = inner.model if inner is not None else (model or "unknown")
        self.path = Path(path)
        self._cache: dict[str, list[float]] = {}
        if self.path.exists():
            self._cache = json.loads(self.path.read_text(encoding="utf-8"))

    def _key(self, query: str, documents: Sequence[str]) -> str:
        digest = hashlib.sha256()
        digest.update(query.encode("utf-8"))
        for document in documents:
            digest.update(b"\x00")
            digest.update(document.encode("utf-8"))
        return f"{self.model}:{digest.hexdigest()}"

    def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        key = self._key(query, documents)
        if key in self._cache:
            return self._cache[key]
        if self.inner is None:
            raise RuntimeError(
                f"rerank not cached in {self.path.name} and this cache is read-only: "
                f"{query[:60]!r}"
            )
        scores = self.inner.rerank(query, documents)
        self._cache[key] = scores
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._cache), encoding="utf-8")
        return scores
