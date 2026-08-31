"""Validate the sufficiency gate against cases it was never tuned on.

The gate's floor, ceiling and corroboration rule were all chosen against the 60
visible cases. A gate scored on the same cases that shaped it reports an upper
bound on itself, so this derives the constants from the **visible** set only and
then scores the **holdout** — cases written afterwards and not consulted while
choosing anything.

    VOYAGE_API_KEY=... python scripts/embed_representations.py   # once
    PYTHONPATH=src python scripts/holdout_validation.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.evaluation.cases import load_gold_set
from agts.evaluation.confidence import rate
from agts.evaluation.corpus import EvaluationLicence
from agts.evaluation.planning import plan_for_case
from agts.evaluation.quarantine import ChapterArtefact, load_corpus
from agts.evaluation.scorer import calibrate_abstention
from agts.platform.embedding import CachedEmbedding
from agts.retrieval import BM25Representations, DenseRetriever
from agts.retrieval.sufficiency import SufficiencyGate

ROOT = Path(__file__).parents[1]
ARTIFACTS = ROOT / "artifacts"
GOLD = ARTIFACTS / "gold" / "pilot-2-chapters-v1.json"
CURRICULUM_VERSION = "2026-27"

#: The pair the service runs with, chosen on the visible set (R-048).
SHIPPED_FLOOR = 0.737
SHIPPED_CEILING = 0.800

CHAPTERS = [
    ChapterArtefact(directory=ARTIFACTS / "chemical-reactions-quarantine",
                    title="Chemical Reactions and Equations", publisher="NCERT",
                    edition="Science, Class X, 2026-27"),
    ChapterArtefact(directory=ARTIFACTS / "quadratic-equations-quarantine",
                    title="Quadratic Equations", publisher="NCERT",
                    edition="Mathematics, Class X, 2026-27"),
]


def report(name, decisions):
    held = [(c, d) for c, d in decisions if not c.answerable]
    askable = [(c, d) for c, d in decisions if c.answerable]
    abstained = sum(1 for _, d in held if d.abstained)
    answered = sum(1 for _, d in askable if d.answerable)
    print(f"\n{name}")
    print(f"  unanswerable correctly abstained: {rate(abstained, len(held))}")
    print(f"  answerable correctly answered   : {rate(answered, len(askable))}")
    for case, decision in decisions:
        if decision.answerable != case.answerable:
            kind = "false ANSWER " if decision.abstained is False else "false abstain"
            print(f"    {kind} — {case.case_id}: {decision.reasons[0] if decision.reasons else 'accepted'}")
    return abstained, len(held), answered, len(askable)


def main() -> None:
    gold_set = load_gold_set(GOLD)
    cache = ARTIFACTS / "embeddings" / "voyage-3.json"
    if not cache.exists():
        raise SystemExit("no vector cache; run scripts/embed_representations.py")
    embedder = CachedEmbedding(None, cache, model="voyage-3")
    licence = EvaluationLicence(
        reason="holdout validation of the sufficiency gate",
        granted_by="mayank", granted_on=date(2026, 8, 30),
        source_ids=tuple(c.manifest()["source_id"] for c in CHAPTERS),
    )
    corpus = load_corpus(CHAPTERS, licence=licence, embedder=embedder)

    missing = sorted(
        b for case in gold_set.cases for b in case.gold_block_ids if b not in corpus.blocks
    )
    if missing:
        print(f"BROKEN GOLD LABELS ({len(missing)}):")
        for block_id in missing:
            print(f"  {block_id}")
        raise SystemExit("fix the answer key first")
    print(f"gold: {len(gold_set.visible)} visible + {len(gold_set.holdout)} holdout, "
          "every gold block id resolves")

    dense, lexical = DenseRetriever(embedder), BM25Representations()

    # Constants from the VISIBLE set only. The holdout must not touch them.
    visible_only = gold_set.model_copy(update={"cases": gold_set.visible})
    calibration = calibrate_abstention(
        visible_only, dense, corpus, curriculum_version=CURRICULUM_VERSION
    )
    tops = sorted(
        dense.retrieve(plan_for_case(c, curriculum_version=CURRICULUM_VERSION), corpus, 20)[0].score
        for c in gold_set.visible if c.answerable
    )
    ceiling = tops[len(tops) // 2]
    # What ships, not what calibration would suggest today. The two differ:
    # calibration re-derives from the current score distribution every run, and
    # a report that silently follows it is scoring a system nobody is running.
    # The shipped pair was chosen on the visible set under a declared rule and
    # is recorded in EVALUATION_LEDGER (R-048).
    shipped_floor, shipped_ceiling = SHIPPED_FLOOR, SHIPPED_CEILING
    print(f"shipped:     floor {shipped_floor:.3f}, ceiling {shipped_ceiling:.3f}")
    print(f"calibration would suggest: floor {calibration.threshold:.3f}, ceiling {ceiling:.3f}"
          f"{'  (same)' if abs(calibration.threshold - shipped_floor) < 1e-9 else ''}")

    gate = SufficiencyGate(dense, lexical, threshold=shipped_floor, high_confidence=shipped_ceiling)

    def decide(cases):
        return [
            (c, gate.decide(plan_for_case(c, curriculum_version=CURRICULUM_VERSION), corpus))
            for c in cases
        ]

    tuned = report("VISIBLE (the gate was tuned on these — upper bound)", decide(gold_set.visible))
    heldout = report("HOLDOUT (never consulted — the honest number)", decide(gold_set.holdout))

    out = ARTIFACTS / "gold" / "holdout-validation.json"
    out.write_text(json.dumps({
        "gold_set": gold_set.gold_set_id,
        "floor": calibration.threshold,
        "ceiling": ceiling,
        "visible": {"abstained": tuned[0], "unanswerable": tuned[1],
                    "answered": tuned[2], "answerable": tuned[3]},
        "holdout": {"abstained": heldout[0], "unanswerable": heldout[1],
                    "answered": heldout[2], "answerable": heldout[3]},
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
