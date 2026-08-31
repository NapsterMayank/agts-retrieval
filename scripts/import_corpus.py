"""Import the parsed chapters into Postgres, then score retrieval from the DB.

    docker compose -f docker/compose.yml up -d
    AGTS_DATABASE_URL=postgresql://agts:agts_dev_password@localhost:5434/agts_dev \
        PYTHONPATH=src python scripts/import_corpus.py

The second half is the point. Writing rows proves the schema accepts them;
loading the corpus back and re-running the ruler proves the round trip lost
nothing that retrieval depends on — block order, vectors, curriculum identity.
A persistence layer that stores everything and retrieves differently is worse
than no persistence layer, because the difference shows up as a quality
regression with no obvious cause.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.evaluation.cases import load_gold_set
from agts.evaluation.corpus import EvaluationLicence
from agts.evaluation.quarantine import ChapterArtefact, load_corpus as load_from_files
from agts.evaluation.scorer import score
from agts.platform.embedding import CachedEmbedding, DEFAULT_EMBEDDING_MODEL
from agts.platform.repository import connect, database_url, load_corpus, migrate, save_corpus
from agts.retrieval import BM25Representations, DenseRetriever

ROOT = Path(__file__).parents[1]
ARTIFACTS = ROOT / "artifacts"
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
    if not database_url():
        raise SystemExit("set AGTS_DATABASE_URL")

    cache = ARTIFACTS / "embeddings" / f"{DEFAULT_EMBEDDING_MODEL}.json"
    embedder = CachedEmbedding(None, cache, model=DEFAULT_EMBEDDING_MODEL) if cache.exists() else None
    licence = EvaluationLicence(
        reason="import of quarantined chapters for retrieval from Postgres",
        granted_by="mayank", granted_on=date(2026, 8, 30),
        source_ids=tuple(c.manifest()["source_id"] for c in CHAPTERS),
    )
    from_files = load_from_files(CHAPTERS, licence=licence, embedder=embedder)
    print(f"from files: {len(from_files.sources)} sources / {len(from_files.blocks)} blocks / "
          f"{len(from_files.objects)} objects / {len(from_files.representations)} representations")

    with connect() as connection:
        print("migrations:", migrate(connection, with_pgvector=True))
        print("written:", save_corpus(connection, from_files))
        from_db = load_corpus(connection, licence=licence)

    print(f"from database: {len(from_db.sources)} sources / {len(from_db.blocks)} blocks / "
          f"{len(from_db.objects)} objects / {len(from_db.representations)} representations")

    # Structural equality first: same ids, same block order, same vectors.
    assert set(from_db.blocks) == set(from_files.blocks), "block ids differ"
    assert set(from_db.objects) == set(from_files.objects), "object ids differ"
    assert set(from_db.representations) == set(from_files.representations), "representation ids differ"
    for object_id, obj in from_files.objects.items():
        assert from_db.objects[object_id].block_ids == obj.block_ids, f"{object_id}: block order lost"
    embedded = sum(1 for r in from_db.representations.values() if r.vector)
    print(f"representations carrying a vector: {embedded}/{len(from_db.representations)}")

    # Then behavioural equality: the ruler must not be able to tell them apart.
    gold_set = load_gold_set(ARTIFACTS / "gold" / "pilot-2-chapters-v1.json")
    retrievers = [("bm25", BM25Representations())]
    if embedder is not None:
        retrievers.append(("dense", DenseRetriever(embedder)))
    for name, retriever in retrievers:
        files_report = score(gold_set, retriever, from_files, curriculum_version=CURRICULUM_VERSION)
        db_report = score(gold_set, retriever, from_db, curriculum_version=CURRICULUM_VERSION)
        same = (
            files_report.recall_at_candidates == db_report.recall_at_candidates
            and files_report.recall_at_pack == db_report.recall_at_pack
        )
        print(f"  {name:<6} files pack {files_report.recall_at_pack:.1%} | "
              f"db pack {db_report.recall_at_pack:.1%} | identical: {same}")
        if not same:
            raise SystemExit(f"{name}: retrieval differs between files and database")

    # Retrieval scores run off representations, so they agree even when the
    # blocks behind them do not. `blocks` took ON CONFLICT DO NOTHING: every
    # corrected block -- a Symbol-font decode, a recovered formula -- stopped at
    # the database while this check printed "identical", and the service served
    # the first version ever imported. Compare the text a learner would read.
    drifted = []
    for block_id, block in from_files.blocks.items():
        stored = from_db.blocks.get(block_id)
        if stored is None:
            drifted.append(f"{block_id}: missing from the database")
        elif (stored.text, stored.latex) != (block.text, block.latex):
            drifted.append(f"{block_id}: text or latex differs from the artefact")
    if drifted:
        print(f"\n{len(drifted)} blocks differ between files and database:")
        for line in drifted[:10]:
            print(f"    {line}")
        raise SystemExit(
            "the database is serving different text from the artefacts. A block "
            "correction has not landed."
        )
    print(f"  blocks  {len(from_files.blocks)} compared on text and latex | identical: True")

    print("\nround trip is behaviourally identical")


if __name__ == "__main__":
    main()
