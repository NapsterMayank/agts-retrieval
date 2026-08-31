"""Build an EvidencePack per gold case and score the §14 citation rows.

    PYTHONPATH=src python scripts/citation_report.py

Reports citation ID resolution and completeness, which are gated, and
`evidence_precision`, which is a named proxy and not §14's precision row — see
`agts.evaluation.citations`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.evaluation.cases import load_gold_set
from agts.evaluation.citations import score_citations
from agts.evaluation.corpus import EvaluationLicence
from agts.evaluation.planning import plan_for_case
from agts.evaluation.quarantine import ChapterArtefact, load_corpus
from agts.evaluation.scorer import calibrate_abstention
from agts.platform.embedding import CachedEmbedding
from agts.retrieval import BM25Representations, DenseRetriever
from agts.retrieval.chunking import REPRESENTATION_VERSION
from agts.retrieval.packing import build_pack
from agts.retrieval.provenance import build_manifest, build_trace, lineage_failures
from agts.retrieval.sufficiency import SufficiencyGate

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
        reason="citation scoring over quarantined chapters",
        granted_by="mayank", granted_on=date(2026, 8, 30),
        source_ids=tuple(c.manifest()["source_id"] for c in CHAPTERS),
    )
    corpus = load_corpus(CHAPTERS, licence=licence, embedder=embedder)

    dense, lexical = DenseRetriever(embedder), BM25Representations()
    visible_only = gold_set.model_copy(update={"cases": gold_set.visible})
    calibration = calibrate_abstention(
        visible_only, dense, corpus, curriculum_version=CURRICULUM_VERSION
    )
    tops = sorted(
        dense.retrieve(plan_for_case(c, curriculum_version=CURRICULUM_VERSION), corpus, 20)[0].score
        for c in gold_set.visible if c.answerable
    )
    # The shipped pair, not what calibration suggests today (R-048). Measuring
    # citations against a configuration nobody runs reports on a system that
    # does not exist.
    gate = SufficiencyGate(dense, lexical, threshold=0.737, high_confidence=0.800)

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip() or "unknown"
    manifest = build_manifest(
        corpus,
        manifest_id="rm-pilot-2-chapters-0001",
        created_at=datetime(2026, 8, 30, tzinfo=UTC),
        commit_sha=commit,
        versions={
            "representation": REPRESENTATION_VERSION,
            "composition": "section-v1",
            "embedding": "voyage-3",
        },
    )
    print(f"release manifest {manifest.release_manifest_id}: "
          f"{len(manifest.object_ids)} objects, {len(manifest.source_ids)} sources, "
          f"checksum {manifest.checksum_sha256[:16]}..., "
          f"approved by {manifest.approved_by or 'NOBODY (unsigned)'}")

    packs = {}
    traces = {}
    lineage = []
    for case in gold_set.cases:
        plan = plan_for_case(case, curriculum_version=CURRICULUM_VERSION)
        decision = gate.decide(plan, corpus)
        pack = build_pack(
            plan, decision, corpus,
            pack_id=f"pack-{case.case_id}",
            trace_id=f"trace-{case.case_id}",
            release_manifest_id=manifest.release_manifest_id,
        )
        packs[case.case_id] = pack
        traces[case.case_id] = build_trace(
            plan, decision, corpus, trace_id=f"trace-{case.case_id}", manifest=manifest
        )
        lineage.extend(lineage_failures(pack, manifest, corpus))

    print(f"§14 approved-source and lineage resolution: "
          f"{'PASS' if not lineage else f'FAIL ({len(lineage)})'}")
    for line in lineage[:5]:
        print(f"    {line}")

    for label, holdout in (("VISIBLE", False), ("HOLDOUT", True)):
        subset = gold_set.model_copy(
            update={"cases": gold_set.holdout if holdout else gold_set.visible}
        )
        report = score_citations(subset, packs, corpus, include_holdout=holdout)
        print(f"\n{label}: {report.summary()}")
        failing = report.failing_gates()
        if failing:
            for line in failing:
                print(f"  FAILS §14: {line}")
        else:
            print("  §14 rows measured here: PASS")
        if report.unresolved:
            print(f"  unresolved spans: {report.unresolved}")

    out = ARTIFACTS / "gold" / "citation-report.json"
    everything = score_citations(gold_set, packs, corpus, include_holdout=True)
    out.write_text(json.dumps({
        "resolution": everything.resolution,
        "delivered_recall": everything.delivered_recall,
        "completeness": everything.completeness,
        "evidence_precision": everything.evidence_precision,
        "packs": everything.packs,
        "answered": everything.answered,
        "abstained": everything.abstained,
        "unresolved": everything.unresolved,
        "release_manifest_id": manifest.release_manifest_id,
        "corpus_checksum": manifest.checksum_sha256,
        "commit_sha": manifest.commit_sha,
        "approved_by": manifest.approved_by,
        "lineage_failures": lineage,
        "traced_candidates": sum(len(t.candidates) for t in traces.values()),
        "note": (
            "evidence_precision is a lower-bound proxy over gold blocks, NOT §14's "
            "citation precision row, which needs generated sentences (Phase 3, Q5)."
        ),
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
