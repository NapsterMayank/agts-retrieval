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
from agts.evaluation.planning import plan_for_case
from agts.evaluation.quarantine import ChapterArtefact, load_corpus
from agts.evaluation.retrievers import KeywordBaseline, broken_retrievers
from agts.platform.embedding import CachedEmbedding
from agts.retrieval import (
    BM25Representations,
    DenseRetriever,
    HybridRetriever,
    RepresentationKeyword,
)
from agts.retrieval.sufficiency import SufficiencyGate
from agts.evaluation.scorer import calibrate_abstention, score


ROOT = Path(__file__).parents[1]
ARTIFACTS = ROOT / "artifacts"
GOLD = ARTIFACTS / "gold" / "pilot-2-chapters-v1.json"
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

    # Read-only vector cache: this run reaches no network and spends nothing.
    # Populate it with scripts/embed_representations.py.
    cache_path = ARTIFACTS / "embeddings" / "voyage-3.json"
    embedder = (
        CachedEmbedding(None, cache_path, model="voyage-3") if cache_path.exists() else None
    )
    corpus = load_corpus(CHAPTERS, licence=LICENCE, embedder=embedder)

    print(f"corpus: {len(corpus.sources)} sources / {len(corpus.blocks)} blocks / "
          f"{len(corpus.objects)} objects / {len(corpus.representations)} representations"
          "   (all QUARANTINED, under evaluation licence)")
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

    # One calibration per honest retriever. A threshold is a property of a score
    # distribution, so quoting one retriever's threshold against another's
    # scores measures nothing.
    calibrations = {}
    honest = [KeywordBaseline(), RepresentationKeyword(), BM25Representations()]
    if embedder is not None:
        honest += [DenseRetriever(embedder), HybridRetriever(embedder)]
    for retriever in honest:
        calibration = calibrate_abstention(
            gold_set, retriever, corpus, curriculum_version=CURRICULUM_VERSION
        )
        calibrations[retriever.name] = calibration
        print(f"\nabstention calibration — {retriever.name}: {calibration.summary()}")
        print(f"  separable: {calibration.separable}")

    default_threshold = calibrations["keyword-baseline"].threshold

    rows = []
    retrievers = [*honest, *broken_retrievers()]
    for retriever in retrievers:
        calibration = calibrations.get(retriever.name)
        report = score(
            gold_set,
            retriever,
            corpus,
            abstain_threshold=(
                calibration.threshold if calibration else default_threshold
            ),
            curriculum_version=CURRICULUM_VERSION,
        )
        rows.append(report)
        print(f"\n{report.summary()}")
        failing = report.failing_slices()
        distinctive = report.distinctive_failures()
        if failing:
            print(f"  failing gating slices: {len(failing)} "
                  f"({len(distinctive)} distinctive — the rest restate a failing axis)")
            for line in distinctive:
                print(f"    {line}")

    if embedder is not None:
        dense = DenseRetriever(embedder)
        calibration = calibrations["representation-dense"]
        answerable_tops = sorted(
            dense.retrieve(
                plan_for_case(case, curriculum_version=CURRICULUM_VERSION), corpus, 20
            )[0].score
            for case in gold_set.visible
            if case.answerable
        )
        ceiling = answerable_tops[len(answerable_tops) // 2]
        gate = SufficiencyGate(
            dense,
            BM25Representations(),
            threshold=calibration.threshold,
            high_confidence=ceiling,
        )
        print(
            f"\nsufficiency gate (§8.4): floor {calibration.threshold:.3f} calibrated, "
            f"ceiling {ceiling:.3f} = median answerable top score, "
            f"corroboration {gate.min_corroboration} of top {gate.depth}"
        )
        decisions = [
            (case, gate.decide(plan_for_case(case, curriculum_version=CURRICULUM_VERSION), corpus))
            for case in gold_set.visible
        ]
        held = [(c, d) for c, d in decisions if not c.answerable]
        askable = [(c, d) for c, d in decisions if c.answerable]
        abstained = sum(1 for _, d in held if d.abstained)
        answered = sum(1 for _, d in askable if d.answerable)
        print(f"  unanswerable correctly abstained: {abstained}/{len(held)}")
        print(f"  answerable correctly answered   : {answered}/{len(askable)}")
        for case, decision in askable:
            if decision.abstained:
                print(f"    false abstain — {case.case_id}: {decision.reasons[0]}")

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
        "corpus_representations": len(corpus.representations),
        "abstention": {
            name: {
                "threshold": c.threshold,
                "margin": c.margin,
                "answerable_floor": c.lowest_answerable,
                "unanswerable_ceiling": c.highest_unanswerable,
                "separable": c.separable,
            }
            for name, c in calibrations.items()
        },
        "runs": [
            {
                "retriever": r.retriever,
                "recall_at_candidates": r.recall_at_candidates,
                "recall_at_pack": r.recall_at_pack,
                "abstention_accuracy": r.abstention_accuracy,
                "violations": r.violations.total,
                "blocks_per_pack": r.blocks_per_pack,
                "failing_slices": r.failing_slices(),
            }
            for r in rows
        ],
        "gold_blocks_not_in_any_object": orphans,
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
