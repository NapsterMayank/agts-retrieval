"""Does reranking earn its cost? (Q4)

Judged on pack recall, not candidate recall: a reranker cannot add candidates
and can only reorder them, so the failure it must be checked against is the one
Q4 describes — twenty correct candidates with the gold span ordered into
position nine of a five-slot pack.

    VOYAGE_API_KEY=... PYTHONPATH=src python scripts/rerank_benchmark.py

Rerank scores are cached by query and candidate set, so the second run is free
and produces identical numbers.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.evaluation.cases import load_gold_set
from agts.evaluation.corpus import EvaluationLicence
from agts.evaluation.quarantine import ChapterArtefact, load_corpus
from agts.evaluation.scorer import score
from agts.platform.embedding import CachedEmbedding
from agts.platform.reranking import CachedReranker, IdentityReranker, VoyageReranker
from agts.retrieval import BM25Representations, DenseRetriever, HybridRetriever, RerankedRetriever

ROOT = Path(__file__).parents[1]
ARTIFACTS = ROOT / "artifacts"
GOLD = ARTIFACTS / "gold" / "pilot-2-chapters-v1.json"
CURRICULUM_VERSION = "2026-27"

CHAPTERS = [
    ChapterArtefact(directory=ARTIFACTS / "chemical-reactions-quarantine",
                    title="Chemical Reactions and Equations", publisher="NCERT",
                    edition="Science, Class X, 2026-27"),
    ChapterArtefact(directory=ARTIFACTS / "quadratic-equations-quarantine",
                    title="Quadratic Equations", publisher="NCERT",
                    edition="Mathematics, Class X, 2026-27"),
]


def main() -> None:
    gold_set = load_gold_set(GOLD)
    cache = ARTIFACTS / "embeddings" / "voyage-3.json"
    if not cache.exists():
        raise SystemExit("no vector cache; run scripts/embed_representations.py")

    embedder = CachedEmbedding(None, cache, model="voyage-3")
    licence = EvaluationLicence(
        reason="rerank benchmark over quarantined chapters",
        granted_by="mayank", granted_on=date(2026, 8, 30),
        source_ids=tuple(c.manifest()["source_id"] for c in CHAPTERS),
    )
    corpus = load_corpus(CHAPTERS, licence=licence, embedder=embedder)

    rerank_cache = ARTIFACTS / "embeddings" / "rerank-2.json"
    inner = VoyageReranker() if os.environ.get("VOYAGE_API_KEY") else None
    if inner is None and not rerank_cache.exists():
        raise SystemExit("set VOYAGE_API_KEY once to populate the rerank cache")
    reranker = CachedReranker(inner, rerank_cache, model="rerank-2")

    dense = DenseRetriever(embedder)
    bm25 = BM25Representations()
    hybrid = HybridRetriever(embedder)

    contenders = [
        ("dense (control)", dense),
        ("dense + identity rerank", RerankedRetriever(dense, IdentityReranker())),
        ("dense + rerank-2", RerankedRetriever(dense, reranker)),
        ("bm25 (control)", bm25),
        ("bm25 + rerank-2", RerankedRetriever(bm25, reranker)),
        ("hybrid (control)", hybrid),
        ("hybrid + rerank-2", RerankedRetriever(hybrid, reranker)),
    ]

    rows = []
    for label, retriever in contenders:
        report = score(gold_set, retriever, corpus, curriculum_version=CURRICULUM_VERSION)
        holdout = score(
            gold_set.model_copy(update={"cases": gold_set.holdout}),
            retriever, corpus,
            curriculum_version=CURRICULUM_VERSION, include_holdout=True,
        )
        rows.append({
            "retriever": label,
            "recall_at_20": report.recall_at_candidates,
            "recall_at_pack": report.recall_at_pack,
            "recall_at_pack_holdout": holdout.recall_at_pack,
            "blocks_per_pack": report.blocks_per_pack,
            "violations": report.violations.total,
        })
        print(
            f"{label:<26} recall@20 {report.recall_at_candidates:6.1%}   "
            f"pack {report.recall_at_pack:6.1%}   "
            f"pack(holdout) {holdout.recall_at_pack:6.1%}   "
            f"blocks/pack {report.blocks_per_pack:5.1f}   "
            f"violations {report.violations.total}"
        )

    out = ARTIFACTS / "gold" / "rerank-benchmark.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
