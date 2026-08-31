"""Embedding port and adapters (§7.3).

§7.3 asks for provider independence, which means one thing concretely: **no
provider name appears anywhere except in an adapter.** Retrieval depends on this
protocol, representations record which model produced their vector (R-016), and
swapping Voyage for anything else changes one constructor call and invalidates a
cache, not a schema.

Three implementations:

- :class:`VoyageEmbedding` — the real one, HTTP, batched.
- :class:`DeterministicEmbedding` — hashing, no network, for tests. It is a
  *fake*, not a model: it has no semantics and any recall number produced with
  it is meaningless. It exists so the wiring can be tested without a key.
- :class:`CachedEmbedding` — wraps either and persists vectors to disk, so a
  scored run is reproducible without re-billing and without a network.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from pathlib import Path
from typing import Protocol, Sequence


class EmbeddingPort(Protocol):
    """What retrieval is allowed to know about embeddings."""

    model: str
    version: str

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


#: The embedding model this build ships. It lives here as one name because it
#: was previously eight string literals across the scripts and the service, and
#: R-016 makes the model part of every representation's identity: a run whose
#: cache says one model and whose service says another is not a slower system,
#: it is a wrong one. Cache files are named after it, so switching models leaves
#: the old vectors on disk rather than mixing two models in one file.
#:
#: voyage-4-large replaced voyage-3 on 2026-08-31, measured over the visible set
#: of pilot-2-chapters-v1: recall@pack 0.899 -> 0.954, and the sufficiency gate
#: 95/109 -> 107/109 answerable at 31/31 unanswerable. voyage-3.5 scored the
#: best raw recall of the five tested (0.972) and the second-worst gate outcome
#: (89/109) -- recall the calibration cannot separate is not accuracy.
DEFAULT_EMBEDDING_MODEL = "voyage-4-large"


class VoyageEmbedding:
    """Voyage AI embeddings over HTTPS.

    `input_type` matters and is not cosmetic: Voyage embeds documents and
    queries into deliberately different regions, and using one type for both
    costs real recall. That is exactly the kind of provider detail that belongs
    behind a port.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_EMBEDDING_MODEL,
        *,
        batch_size: int = 64,
        timeout: float = 60.0,
    ) -> None:
        self.model = model
        self.version = model
        self.batch_size = batch_size
        self.timeout = timeout
        self._key = api_key or os.environ.get("VOYAGE_API_KEY", "")
        if not self._key:
            raise RuntimeError("no VOYAGE_API_KEY; pass one or use DeterministicEmbedding")

    def _call(self, texts: Sequence[str], input_type: str) -> list[list[float]]:
        import requests

        out: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = list(texts[start : start + self.batch_size])
            for attempt in range(4):
                response = requests.post(
                    "https://api.voyageai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {self._key}"},
                    json={"input": batch, "model": self.model, "input_type": input_type},
                    timeout=self.timeout,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    time.sleep(2 ** attempt)
                    continue
                response.raise_for_status()
                payload = response.json()
                # Order is not promised by the field order, only by `index`.
                rows = sorted(payload["data"], key=lambda row: row["index"])
                out.extend(row["embedding"] for row in rows)
                break
            else:
                raise RuntimeError(f"voyage: giving up on batch at {start}")
        return out

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._call(texts, "document")

    def embed_query(self, text: str) -> list[float]:
        return self._call([text], "query")[0]


class DeterministicEmbedding:
    """Hashed pseudo-embeddings. No network, no semantics, no meaning.

    Never use it to produce a number anyone will read as quality: two
    paraphrases of one sentence are as distant here as two unrelated ones. It
    exists so that everything *around* the embedding — caching, fusion, the
    scorer — can be tested without a key.
    """

    model = "deterministic-fake"
    version = "1"

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class CachedEmbedding:
    """Disk cache keyed by (model, sha256 of text, input type).

    A scored run has to be reproducible, and re-embedding on every run makes the
    number depend on a provider's mood and the operator's budget. Keying on the
    text hash rather than a representation id means rechunking invalidates only
    what actually changed.
    """

    def __init__(
        self, inner: EmbeddingPort | None, path: Path, *, model: str | None = None
    ) -> None:
        # `inner=None` is a read-only cache: a run that must not reach a network
        # and must not spend money. A miss then raises rather than silently
        # producing a number from a different code path than the one cached.
        self.inner = inner
        self.model = inner.model if inner is not None else (model or "unknown")
        self.version = inner.version if inner is not None else (model or "unknown")
        self.path = Path(path)
        self._cache: dict[str, list[float]] = {}
        if self.path.exists():
            self._cache = json.loads(self.path.read_text(encoding="utf-8"))

    def _key(self, text: str, input_type: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"{self.model}:{input_type}:{digest}"

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._cache), encoding="utf-8")

    def has(self, text: str, input_type: str = "document") -> bool:
        return self._key(text, input_type) in self._cache

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        missing = [t for t in texts if self._key(t, "document") not in self._cache]
        if missing and self.inner is None:
            raise RuntimeError(
                f"{len(missing)} texts are not in {self.path.name} and this cache is "
                "read-only. Run scripts/embed_representations.py first."
            )
        if missing:
            for text, vector in zip(missing, self.inner.embed_documents(missing)):
                self._cache[self._key(text, "document")] = vector
            self._flush()
        return [self._cache[self._key(t, "document")] for t in texts]

    def embed_query(self, text: str) -> list[float]:
        key = self._key(text, "query")
        if key not in self._cache and self.inner is None:
            raise RuntimeError(
                f"query not in {self.path.name} and this cache is read-only: {text[:60]!r}"
            )
        if key not in self._cache:
            self._cache[key] = self.inner.embed_query(text)
            self._flush()
        return self._cache[key]
