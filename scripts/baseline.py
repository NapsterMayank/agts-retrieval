"""Print the current baseline and the §6.5 detection table.

    python scripts/baseline.py

Everything measured later inherits its credibility from this table. If the four
broken retrievers do not separate from the baseline, no number in
EVALUATION_LEDGER.md means anything.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agts.evaluation.fixtures import build_corpus, build_gold_set  # noqa: E402
from agts.evaluation.retrievers import KeywordBaseline, broken_retrievers  # noqa: E402
from agts.evaluation.scorer import calibrate_abstention, score  # noqa: E402


def _commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parents[1],
            check=False,
        )
        return out.stdout.strip() or "uncommitted"
    except OSError:
        return "unknown"


def _pct(value: float | None) -> str:
    return "   -  " if value is None else f"{value * 100:6.1f}%"


def main() -> int:
    corpus = build_corpus()
    gold_set = build_gold_set()
    baseline_retriever = KeywordBaseline()

    calibration = calibrate_abstention(gold_set, baseline_retriever, corpus)
    baseline = score(
        gold_set, baseline_retriever, corpus, abstain_threshold=calibration.threshold
    )

    print(f"commit    {_commit()}")
    print(f"gold set  {gold_set.gold_set_id}: {len(gold_set.visible)} visible, "
          f"{len(gold_set.holdout)} holdout")
    print(f"corpus    {len(corpus.objects)} objects, {len(corpus.blocks)} blocks, "
          f"{len(corpus.sources)} sources  [SYNTHETIC FIXTURES]")
    print(f"abstain   {calibration.summary()}")
    print()

    header = f"{'retriever':<26} {'recall@20':>10} {'recall@5':>10} {'abstain':>10} {'violations':>11}"
    print(header)
    print("-" * len(header))

    rows = [baseline] + [
        score(gold_set, broken, corpus, abstain_threshold=calibration.threshold)
        for broken in broken_retrievers()
    ]
    for report in rows:
        print(
            f"{report.retriever:<26} "
            f"{_pct(report.recall_at_candidates)} "
            f"{_pct(report.recall_at_pack)} "
            f"{_pct(report.abstention_accuracy)} "
            f"{report.violations.total:>11}"
        )

    print()
    undetected = [
        r.retriever for r in rows[1:] if not r.is_materially_worse_than(baseline)
    ]
    if undetected:
        print(f"FAIL - the scorer could not separate: {', '.join(undetected)}")
        return 1

    print("OK - all four broken retrievers separate from the baseline (§6.5).")
    failing = baseline.failing_slices()
    if failing:
        print("\nFailing gating slices:")
        for line in failing:
            print(f"  {line}")
    else:
        gating = sum(1 for s in baseline.slices.values() if s.gating)
        print(
            f"No gating slice failures ({gating} of {len(baseline.slices)} slices "
            "have n >= 20; the rest report but do not gate - see Q2)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
