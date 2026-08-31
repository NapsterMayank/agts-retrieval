"""Expand the gold set with rewordings of its own cases (R-035, R-047).

    PYTHONPATH=src python scripts/expand_paraphrases.py --apply

Every gold case is a full sentence naming its subject, because that is how
questions get written while looking at a chapter. Learners do not type that way,
and R-035 showed the cost: dropping four words from *"How do you solve a
quadratic equation by completing the square?"* turned a correct refusal into an
answer.

A paraphrase **inherits its parent's answer and gold blocks unchanged**. Only the
wording differs, so adding one invents no new judgement — which is what makes it
legitimate for the same author to write rewordings of cases they labelled, where
writing new cases would not be.

A paraphrase lands in the same set as its parent. A reworded holdout case stays
in the holdout, or the thresholds would be fitted to a question whose twin is
supposed to be unseen.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.evaluation.cases import load_gold_set

ROOT = Path(__file__).parents[1]
GOLD = ROOT / "artifacts" / "gold" / "pilot-2-chapters-v1.json"
PARAPHRASES = ROOT / "artifacts" / "gold" / "paraphrases.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    payload = json.loads(GOLD.read_text(encoding="utf-8"))
    by_id = {case["case_id"]: case for case in payload["cases"]}
    existing = {case["case_id"] for case in payload["cases"]}
    rewordings = json.loads(PARAPHRASES.read_text(encoding="utf-8"))["paraphrases"]

    added: list[dict] = []
    for parent_id, variants in rewordings.items():
        parent = by_id.get(parent_id)
        if parent is None:
            raise SystemExit(f"{parent_id} is not in the gold set")
        for index, (register, query) in enumerate(variants, start=1):
            case_id = f"{parent_id}-p{index}"
            if case_id in existing:
                continue
            child = {
                key: value
                for key, value in parent.items()
                if not key.startswith("_") and key not in {"case_id", "query", "adjudicators"}
            }
            child.update({
                "case_id": case_id,
                "query": query,
                "paraphrase_of": parent_id,
                "phrasing": register,
                # Adjudication does not inherit. A human approved the parent's
                # wording, not this one.
                "adjudicators": [],
            })
            added.append(child)

    print(f"parents reworded: {len(rewordings)} of {len(payload['cases'])} cases")
    print(f"paraphrases to add: {len(added)}")
    print(f"  by register: {dict(Counter(c['phrasing'] for c in added))}")
    print(f"  unanswerable: {sum(1 for c in added if not c.get('answerable', True))}")
    print(f"  holdout: {sum(1 for c in added if c.get('holdout'))}")

    if not args.apply:
        print("\nDRY RUN. Nothing written.")
        return

    payload["cases"].extend(added)
    payload["_provenance"]["paraphrases"] = (
        "31 August: rewordings of existing cases in short, spoken and typo registers. "
        "Each inherits its parent's answer and gold blocks unchanged, so no new judgement "
        "is introduced; a paraphrase stays in its parent's set, and adjudication does not "
        "inherit because a human approved the parent's wording rather than this one."
    )
    GOLD.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    gold_set = load_gold_set(GOLD)
    print(f"\ngold set is now {len(gold_set.cases)} cases: "
          f"{len(gold_set.visible)} visible, {len(gold_set.holdout)} holdout")


if __name__ == "__main__":
    main()
