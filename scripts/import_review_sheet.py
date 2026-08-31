"""Read a marked review sheet back into the gold set (section 13).

    PYTHONPATH=src python scripts/import_review_sheet.py reviewed-by-asha.csv
    PYTHONPATH=src python scripts/import_review_sheet.py reviewed-by-asha.csv --apply

Each reviewer marks their own copy and both are imported. A case gates only once
**two** names agree on it, which is section 6.4's rule and the reason one
reviewer plus my draft is not enough — that is still one opinion checking
another.

What it does with a disagreement: nothing automatic. It lists them and stops
short of the answer key, because a disagreement means either the question or my
key is wrong, and deciding which is the reviewers' job. A tool that silently
took the reviewer's side would be replacing one unverified judgement with
another.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.evaluation.cases import load_gold_set

ROOT = Path(__file__).parents[1]
GOLD = ROOT / "artifacts" / "gold" / "pilot-2-chapters-v1.json"

AGREE = {"agree", "yes", "y", "ok", "correct"}
DISAGREE = {"disagree", "no", "n", "wrong", "incorrect"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sheets", nargs="+", type=Path, help="one marked CSV per reviewer")
    parser.add_argument("--apply", action="store_true", help="write the gold set")
    args = parser.parse_args()

    gold_set = load_gold_set(GOLD)
    known = {case.case_id for case in gold_set.cases}

    agreed: dict[str, list[str]] = {}
    disputed: list[tuple[str, str, str, str]] = []
    unsure: list[tuple[str, str]] = []
    problems: list[str] = []

    for sheet in args.sheets:
        rows = list(csv.DictReader(sheet.open(encoding="utf-8-sig")))
        reviewers = {(r.get("REVIEWER NAME") or "").strip() for r in rows}
        reviewers.discard("")
        if len(reviewers) != 1:
            problems.append(
                f"{sheet.name}: expected exactly one reviewer name, found {sorted(reviewers) or 'none'}. "
                "One sheet is one person's judgement."
            )
            continue
        reviewer = reviewers.pop()

        for row in rows:
            case_id = (row.get("case_id") or "").strip()
            verdict = (row.get("VERDICT (agree / disagree / unsure)") or "").strip().lower()
            note = (row.get("NOTES (required if you disagree)") or "").strip()
            if not case_id or not verdict:
                continue
            if case_id not in known:
                problems.append(f"{sheet.name}: {case_id} is not in the gold set")
                continue
            if verdict in AGREE:
                agreed.setdefault(case_id, []).append(reviewer)
            elif verdict in DISAGREE:
                if not note:
                    problems.append(
                        f"{sheet.name}: {case_id} is marked disagree with no note. "
                        "A rejection without a reason cannot be acted on."
                    )
                disputed.append((case_id, reviewer, note, verdict))
            else:
                unsure.append((case_id, reviewer))

    critical = [c for c in gold_set.cases if c.is_release_critical]
    two = [c for c in critical if len(agreed.get(c.case_id, [])) >= 2]

    print(f"sheets read: {len(args.sheets)}")
    print(f"release-critical cases: {len(critical)}")
    print(f"  adjudicated by two reviewers: {len(two)}")
    print(f"  disputed: {len({d[0] for d in disputed})}")
    print(f"  marked unsure: {len({u[0] for u in unsure})}")

    if disputed:
        print("\nDISPUTED — the question or my answer key is wrong, and which one is your call:")
        for case_id, reviewer, note, _ in disputed:
            case = next(c for c in gold_set.cases if c.case_id == case_id)
            print(f"  {case_id} ({reviewer}): {case.query}")
            print(f"      {note or '(no note given)'}")

    if problems:
        print("\nPROBLEMS:")
        for problem in problems:
            print(f"  - {problem}")

    if not args.apply:
        print("\nDRY RUN. Nothing written. Re-run with --apply to record the adjudications.")
        return

    payload = json.loads(GOLD.read_text(encoding="utf-8"))
    stamped = 0
    for case in payload["cases"]:
        names = agreed.get(case["case_id"], [])
        if names:
            case["adjudicators"] = sorted(set(names))
            stamped += 1
    GOLD.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nrecorded adjudicators on {stamped} cases in {GOLD.name}.")
    print(f"{len(two)} of {len(critical)} release-critical cases now have the two "
          "reviewers section 6.4 requires.")


if __name__ == "__main__":
    main()
