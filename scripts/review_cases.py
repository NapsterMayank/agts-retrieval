"""Walk a reviewer through the release-critical cases, one at a time (section 13).

    PYTHONPATH=src python scripts/review_cases.py --reviewer "Asha Menon"
    PYTHONPATH=src python scripts/review_cases.py --reviewer "Asha Menon" --subject mathematics

The same 48 cases as `export_review_sheet.py`, and it writes the same CSV shape,
so the two routes are interchangeable and a reviewer picks whichever suits them:
a spreadsheet for someone who wants to see everything at once, this for someone
who would rather be asked one question at a time.

**It saves after every answer.** A reviewer who stops at case 20 and comes back
tomorrow resumes at 21. Losing an hour of someone else's careful judgement to a
closed terminal is not a risk worth taking to save five lines.
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
ARTIFACTS = ROOT / "artifacts"
GOLD = ARTIFACTS / "gold" / "pilot-2-chapters-v1.json"

FIELDS = [
    "case_id", "chapter", "question", "my_claim", "evidence_I_cited", "pages",
    "VERDICT (agree / disagree / unsure)", "NOTES (required if you disagree)",
    "REVIEWER NAME",
]
CHAPTERS = {
    "science": "NCERT Class 10 Science, ch1 Chemical Reactions and Equations",
    "mathematics": "NCERT Class 10 Mathematics, ch4 Quadratic Equations",
}
VERDICTS = {"a": "agree", "d": "disagree", "u": "unsure"}


def load_blocks() -> dict[str, dict]:
    blocks: dict[str, dict] = {}
    for name in ("chemical-reactions", "quadratic-equations"):
        path = ARTIFACTS / f"{name}-quarantine" / "source-blocks.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                block = json.loads(line)
                blocks[block["block_id"]] = block
    return blocks


def wrap(text: str, width: int = 76, indent: str = "    ") -> str:
    words, lines, current = text.split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    lines.append(current)
    return "\n".join(indent + line for line in lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewer", required=True, help="your full name, recorded on each case")
    parser.add_argument("--subject", choices=["science", "mathematics"],
                        help="review one subject only")
    parser.add_argument("--out", type=Path, help="where to save (default: reviewed-<name>.csv)")
    args = parser.parse_args()

    out = args.out or Path(f"reviewed-{args.reviewer.split()[0].lower()}.csv")
    gold_set = load_gold_set(GOLD)
    blocks = load_blocks()

    cases = [c for c in gold_set.cases if c.is_release_critical]
    if args.subject:
        cases = [c for c in cases if c.subject == args.subject]

    done: dict[str, dict] = {}
    if out.exists():
        done = {
            row["case_id"]: row
            for row in csv.DictReader(out.open(encoding="utf-8-sig"))
            if (row.get("VERDICT (agree / disagree / unsure)") or "").strip()
        }
        print(f"resuming: {len(done)} already reviewed in {out.name}\n")

    remaining = [c for c in cases if c.case_id not in done]
    print(f"{len(remaining)} of {len(cases)} cases left. Reviewer: {args.reviewer}")
    print("For each one: [a]gree  [d]isagree  [u]nsure  [s]kip  [q]uit and save.\n")

    for number, case in enumerate(remaining, start=1):
        print("=" * 78)
        print(f"{case.case_id}   ({number} of {len(remaining)})   {CHAPTERS[case.subject]}")
        print(f"\n  QUESTION")
        print(wrap(case.query))
        if case.answerable:
            print(f"\n  MY CLAIM: the chapter answers this, and this is the answer")
            for block_id in case.gold_block_ids:
                block = blocks.get(block_id)
                if block:
                    text = " ".join((block.get("text") or "").split())
                    print(f"\n  [page {block['region']['page']}]")
                    print(wrap(text))
        else:
            print(f"\n  MY CLAIM: this chapter CANNOT answer this question.")
            print("            Is that true?")

        answer = ""
        while answer not in {*VERDICTS, "s", "q"}:
            answer = input("\n  [a]gree / [d]isagree / [u]nsure / [s]kip / [q]uit: ").strip().lower()
        if answer == "q":
            break
        if answer == "s":
            continue

        note = ""
        if answer == "d":
            while not note:
                note = input("  what is wrong with it? ").strip()
        elif answer == "u":
            note = input("  note (optional): ").strip()

        document = "chemical-reactions" if case.subject == "science" else "quadratic-equations"
        cited = "\n\n".join(
            " ".join((blocks[b].get("text") or "").split())
            for b in case.gold_block_ids if b in blocks
        )
        pages = ", ".join(
            str(blocks[b]["region"]["page"]) for b in case.gold_block_ids if b in blocks
        )
        done[case.case_id] = {
            "case_id": case.case_id,
            "chapter": CHAPTERS[case.subject],
            "question": case.query,
            "my_claim": ("ANSWERABLE - the chapter answers this, and the text beside it is the answer"
                         if case.answerable else
                         "NOT ANSWERABLE - this chapter cannot answer this question"),
            "evidence_I_cited": cited,
            "pages": pages,
            "VERDICT (agree / disagree / unsure)": VERDICTS[answer],
            "NOTES (required if you disagree)": note,
            "REVIEWER NAME": args.reviewer,
        }

        # Written after every answer: a closed terminal must not cost an hour of
        # someone else's careful judgement.
        with out.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(done.values())

    reviewed = len(done)
    disagreed = sum(1 for r in done.values() if r["VERDICT (agree / disagree / unsure)"] == "disagree")
    print(f"\nsaved {out} — {reviewed} of {len(cases)} reviewed, {disagreed} disagreements.")
    if reviewed < len(cases):
        print("Run the same command again to carry on where you stopped.")
    else:
        print("Hand this file back. Two reviewers' files together adjudicate the set:")
        print(f"  python scripts/import_review_sheet.py {out.name} reviewed-<other>.csv --apply")


if __name__ == "__main__":
    main()
