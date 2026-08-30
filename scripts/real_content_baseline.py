"""Run the ruler over two real NCERT chapters, under an evaluation licence.

Everything the scorer has measured until now was forty synthetic sentences the
queries were written against — which proved the harness runs and separates a
working retriever from four broken ones, and proved nothing about real content.
This is the first run where the corpus is a real parse of a real chapter.

The content is `QUARANTINED` (Q3: no signed rights records yet), so the run needs
an explicit `EvaluationLicence`. It measures; it does not publish, and its
numbers are not release evidence.

    PYTHONPATH=src python scripts/real_content_baseline.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.evaluation.cases import load_gold_set
from agts.evaluation.corpus import EvaluationLicence
from agts.evaluation.quarantine import ChapterArtefact, load_corpus
from agts.evaluation.retrievers import KeywordBaseline, broken_retrievers
from agts.evaluation.scorer import calibrate_abstention, score


ROOT = Path(__file__).parents[1]
ARTIFACTS = ROOT / "artifacts"
GOLD = ARTIFACTS / "gold" / "pilot-2-chapters-v0.json"
CURRICULUM_VERSION = "2026-27"

CHAPTERS = [
    ChapterArtefact(
        directory=ARTIFACTS / "chemical-reactions-quarantine",
        title="Chemical Reactions and Equations",
        publisher="NCERT",
        edition="Science, Class X, 2026-27",
    ),
    ChapterArtefact(
        directory=ARTIFACTS / "quadratic-equations-quarantine",
        title="Quadratic Equations",
        publisher="NCERT",
        edition="Mathematics, Class X, 2026-27",
    ),
]

LICENCE = EvaluationLicence(
    reason="first real-content evaluation run; content quarantined pending rights records (Q3)",
    granted_by="mayank",
    granted_on=date(2026, 8, 30),
    source_ids=tuple(chapter.manifest()["source_id"] for chapter in CHAPTERS),
)


def check_gold_labels(gold_set, corpus) -> list[str]:
    """Gold block ids that do not exist in the corpus.

    A gold label pointing at nothing scores as a miss, and a miss looks exactly
    like a retrieval failure. Checking first means a recall number is about
    retrieval rather than about typos in the answer key.
    """
    return sorted(
        block_id
        for case in gold_set.cases
        for block_id in case.gold_block_ids
        if block_id not in corpus.blocks
    )


def uncited_gold(gold_set, corpus) -> list[str]:
    """Gold blocks no learning object contains.

    Retrieval ranks objects, so a gold block that composition left out of every
    object can never be reached however good the ranking is. That is a
    composition defect, not a retrieval one, and the two are indistinguishable
    from a recall number alone.
    """
    covered = {block_id for obj in corpus.objects.values() for block_id in obj.block_ids}
    return sorted(
        block_id
        for case in gold_set.cases
        for block_id in case.gold_block_ids
        if block_id in corpus.blocks and block_id not in covered
    )


def main() -> None:
    gold_set = load_gold_set(GOLD)
    corpus = load_corpus(CHAPTERS, licence=LICENCE)

    print(f"corpus: {len(corpus.sources)} sources / {len(corpus.blocks)} blocks / "
          f"{len(corpus.objects)} objects   (all QUARANTINED, under evaluation licence)")
    print(f"gold set: {gold_set.gold_set_id} — {len(gold_set.cases)} cases, "
          f"{sum(c.answerable for c in gold_set.cases)} answerable")

    missing = check_gold_labels(gold_set, corpus)
    if missing:
        print(f"\nBROKEN GOLD LABELS ({len(missing)}) — these ids are not in the corpus:")
        for block_id in missing[:20]:
            print(f"  {block_id}")
        raise SystemExit("fix the answer key before believing any number below")

    orphans = uncited_gold(gold_set, corpus)
    if orphans:
        print(f"\nGOLD BLOCKS NO OBJECT CONTAINS ({len(orphans)}) — unreachable by any retriever:")
        for block_id in orphans:
            print(f"  {block_id}")

    unadjudicated = gold_set.unadjudicated_release_critical()
    print(f"\nunadjudicated release-critical cases: {len(unadjudicated)} "
          "(§6.4 wants two named reviewers each; this set has none)")

    calibration = calibrate_abstention(
        gold_set, KeywordBaseline(), corpus, curriculum_version=CURRICULUM_VERSION
    )
    print(f"\nabstention calibration: {calibration.summary()}")
    print(f"separable: {calibration.separable}")

    rows = []
    retrievers = [KeywordBaseline(), *broken_retrievers()]
    for retriever in retrievers:
        report = score(
            gold_set,
            retriever,
            corpus,
            abstain_threshold=calibration.threshold,
            curriculum_version=CURRICULUM_VERSION,
        )
        rows.append(report)
        print(f"\n{report.summary()}")
        failing = report.failing_slices()
        if failing:
            print("  failing gating slices:")
            for line in failing:
                print(f"    {line}")

    baseline = rows[0]
    print("\n§6.5 — does the ruler still separate broken retrievers on real content?")
    for report in rows[1:]:
        verdict = "detected" if report.is_materially_worse_than(baseline) else "NOT DETECTED"
        print(f"  {report.retriever:<24} {verdict}")

    out = ARTIFACTS / "gold" / "real-content-baseline.json"
    out.write_text(json.dumps({
        "gold_set": gold_set.gold_set_id,
        "curriculum_version": CURRICULUM_VERSION,
        "evaluation_licence": LICENCE.reason,
        "corpus": {
            "sources": len(corpus.sources),
            "blocks": len(corpus.blocks),
            "objects": len(corpus.objects),
        },
        "abstention": {
            "threshold": calibration.threshold,
            "margin": calibration.margin,
            "answerable_floor": calibration.lowest_answerable,
            "unanswerable_ceiling": calibration.highest_unanswerable,
        },
        "runs": [
            {
                "retriever": r.retriever,
                "recall_at_candidates": r.recall_at_candidates,
                "recall_at_pack": r.recall_at_pack,
                "abstention_accuracy": r.abstention_accuracy,
                "violations": r.violations.total,
                "failing_slices": r.failing_slices(),
            }
            for r in rows
        ],
        "gold_blocks_not_in_any_object": orphans,
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
