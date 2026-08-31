"""Export the release-critical cases as a sheet a human can mark (section 13).

    PYTHONPATH=src python scripts/export_review_sheet.py

Writes `artifacts/gold/review-sheet.csv`: one row per case, with the question,
what I claimed, and the exact text I claimed as the answer. A reviewer fills in
two columns and hands it back; `scripts/import_review_sheet.py` reads it and
stamps their name onto each case.

The evidence text is included in full rather than as block ids, because a
reviewer should be able to judge without opening the parser output — and because
"trust the ids" is exactly the thing being checked.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.evaluation.cases import load_gold_set

ROOT = Path(__file__).parents[1]
ARTIFACTS = ROOT / "artifacts"
GOLD = ARTIFACTS / "gold" / "pilot-2-chapters-v1.json"
OUT = ARTIFACTS / "gold" / "review-sheet.csv"

CHAPTERS = {
    "chemical-reactions": "NCERT Class 10 Science, ch1 Chemical Reactions and Equations",
    "quadratic-equations": "NCERT Class 10 Mathematics, ch4 Quadratic Equations",
}


def load_blocks() -> dict[str, dict]:
    blocks: dict[str, dict] = {}
    for name in CHAPTERS:
        path = ARTIFACTS / f"{name}-quarantine" / "source-blocks.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                block = json.loads(line)
                blocks[block["block_id"]] = block
    return blocks


def main() -> None:
    gold_set = load_gold_set(GOLD)
    blocks = load_blocks()
    critical = [c for c in gold_set.cases if c.is_release_critical]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "case_id",
            "chapter",
            "question",
            "my_claim",
            "evidence_I_cited",
            "pages",
            "VERDICT (agree / disagree / unsure)",
            "NOTES (required if you disagree)",
            "REVIEWER NAME",
        ])
        for case in critical:
            document = "chemical-reactions" if case.subject == "science" else "quadratic-equations"
            if case.answerable:
                claim = "ANSWERABLE - the chapter answers this, and the text beside it is the answer"
                cited = "\n\n".join(
                    " ".join((blocks[b].get("text") or "").split())
                    for b in case.gold_block_ids if b in blocks
                )
                pages = ", ".join(
                    str(blocks[b]["region"]["page"]) for b in case.gold_block_ids if b in blocks
                )
            else:
                claim = "NOT ANSWERABLE - this chapter cannot answer this question"
                cited = ""
                pages = ""
            writer.writerow([
                case.case_id, CHAPTERS[document], case.query, claim, cited, pages, "", "", "",
            ])

    answerable = sum(1 for c in critical if c.answerable)
    print(f"wrote {OUT}")
    print(f"  {len(critical)} cases to review: {answerable} with an answer key, "
          f"{len(critical) - answerable} claimed unanswerable")
    print(f"  {sum(1 for c in critical if c.subject == 'science')} science, "
          f"{sum(1 for c in critical if c.subject == 'mathematics')} mathematics")
    print("\nA reviewer fills in VERDICT, NOTES and REVIEWER NAME, and nothing else.")


if __name__ == "__main__":
    main()
