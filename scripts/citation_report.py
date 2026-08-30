"""Build an EvidencePack per gold case and score the §14 citation rows.

    PYTHONPATH=src python scripts/citation_report.py

Reports citation ID resolution and completeness, which are gated, and
`evidence_precision`, which is a named proxy and not §14's precision row — see
`agts.evaluation.citations`.
"""

from __future__ import annotations

import json
import sys
from datetime import date
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
from agts.retrieval.packing import build_pack
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
    gate = SufficiencyGate(
        dense, lexical, threshold=calibration.threshold, high_confidence=tops[len(tops) // 2]
    )

    packs = {}
    for case in gold_set.cases:
        plan = plan_for_case(case, curriculum_version=CURRICULUM_VERSION)
        decision = gate.decide(plan, corpus)
        packs[case.case_id] = build_pack(
            plan, decision, corpus,
            pack_id=f"pack-{case.case_id}",
            trace_id=f"trace-{case.case_id}",
            release_manifest_id="unreleased-quarantined",
        )

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
        "completeness": everything.completeness,
        "evidence_precision": everything.evidence_precision,
        "packs": everything.packs,
        "answered": everything.answered,
        "abstained": everything.abstained,
        "unresolved": everything.unresolved,
        "note": (
            "evidence_precision is a lower-bound proxy over gold blocks, NOT §14's "
            "citation precision row, which needs generated sentences (Phase 3, Q5)."
        ),
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
