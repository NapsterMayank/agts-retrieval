"""Embed the search representations and cache the vectors (§7.3).

    VOYAGE_API_KEY=... python scripts/embed_representations.py

Vectors are cached on disk by text hash, so re-running is free and a scored run
does not depend on a provider being reachable. The cache is not committed.

Note what this does: it sends chapter text to a third-party API. That is a data
egress decision about content whose rights records are still outstanding, and it
is recorded here rather than buried in an adapter.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.evaluation.cases import load_gold_set
from agts.platform.embedding import CachedEmbedding, VoyageEmbedding
from agts.retrieval.chunking import represent_all
from agts.contracts.objects import LearningObject, SourceBlock

ROOT = Path(__file__).parents[1]
ARTIFACTS = ROOT / "artifacts"
CACHE = ARTIFACTS / "embeddings" / "voyage-3.json"
CHAPTERS = ["chemical-reactions-quarantine", "quadratic-equations-quarantine"]


def main() -> None:
    if not os.environ.get("VOYAGE_API_KEY"):
        raise SystemExit("set VOYAGE_API_KEY")

    embedder = CachedEmbedding(VoyageEmbedding(), CACHE)

    texts: list[str] = []
    for name in CHAPTERS:
        directory = ARTIFACTS / name
        blocks = [
            SourceBlock.model_validate_json(line)
            for line in (directory / "source-blocks.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        objects = [
            LearningObject.model_validate_json(line)
            for line in (directory / "learning-objects.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        texts.extend(rep.search_text for rep in represent_all(objects, blocks))

    print(f"embedding {len(texts)} representations with {embedder.model}")
    embedder.embed_documents(texts)

    gold_set = load_gold_set(ARTIFACTS / "gold" / "pilot-2-chapters-v1.json")
    print(f"embedding {len(gold_set.cases)} queries")
    for case in gold_set.cases:
        embedder.embed_query(case.query)

    print(f"cache: {CACHE} ({CACHE.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
