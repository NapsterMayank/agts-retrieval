"""Export the formulas that still need a human, with candidates to choose between.

    PYTHONPATH=src python scripts/export_formula_sheet.py

Three formulas cannot be fixed automatically (R-054). Each is scrambled in
reading *order* rather than encoding, so no rule recovers them and the strict
matcher (R-043) correctly refuses to guess -- when it was allowed to guess by
page it was wrong two times in three.

This does not choose. It puts the broken text beside the LaTeX the second
parser found nearby, ranked by the same symbol overlap the strict matcher uses,
so the choice takes a minute instead of an afternoon. Picking the wrong line
teaches a student the wrong formula, so the person picks, not the script.

The ranking also shows *why* the matcher refuses. For texts-153 the top two
candidates score 1.00 and are each other's sign flip -- a margin of zero, which
is the case R-043 was written for. A reader spots that instantly; a threshold
cannot.

Writes `artifacts/gold/formula-sheet.md`, which is gitignored: it quotes the
chapter.
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.parsing.formula_match import similarity
from agts.parsing.quality import is_unusable

ROOT = Path(__file__).parents[1]
BLOCKS = ROOT / "artifacts" / "quadratic-equations-quarantine" / "source-blocks.jsonl"
CHANDRA = Path(r"D:\Downloads\quadratic-chandra\quadratic.json")
OUT = ROOT / "artifacts" / "gold" / "formula-sheet.md"


def chandra_by_page() -> dict[int, list[str]]:
    document = json.loads(CHANDRA.read_text(encoding="utf-8"))
    pages: dict[int, list[str]] = {}
    for number, page in enumerate(document["children"], start=1):
        found = re.findall(r"<math[^>]*>(.*?)</math>", page["html"], re.DOTALL)
        seen, unique = set(), []
        for item in found:
            expression = " ".join(html.unescape(item).split())
            # A page repeats the same expression many times; a chooser needs the
            # distinct options, not every occurrence.
            if expression and expression not in seen and len(expression) > 2:
                seen.add(expression)
                unique.append(expression)
        pages[number] = unique
    return pages


def main() -> None:
    blocks = [
        json.loads(line)
        for line in BLOCKS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    broken = [
        block
        for block in blocks
        if block.get("block_type") == "formula"
        and not block.get("latex")
        and is_unusable(block.get("text") or "")
    ]

    candidates = chandra_by_page() if CHANDRA.exists() else {}

    lines = [
        "# Formulas that still need a person",
        "",
        f"{len(broken)} left. Each one below is a formula the parser read in the wrong",
        "order, so the characters are right and their sequence is not. Nothing can fix",
        "that automatically without risking teaching the wrong formula.",
        "",
        "**What to do:** open the page crop, look at the real formula, and write the",
        "matching line number under CHOICE. If none of the candidates is right, write",
        "the correct LaTeX yourself under CHOICE. If you are not sure, write `unsure`",
        "-- that is a valid answer and better than a guess.",
        "",
        f"Crops: `artifacts/quadratic-equations-quarantine/assets/`",
        "",
    ]

    for block in broken:
        page = block["region"]["page"]
        text = " ".join((block.get("text") or "").split())
        lines += [
            "---",
            "",
            f"## `{block['block_id']}` — page {page}",
            "",
            "What the parser read (scrambled):",
            "",
            f"```\n{text}\n```",
            "",
            f"Candidates from pages {page - 1}–{page + 1}, best symbol overlap first.",
            "The two parsers disagree on page boundaries, so neighbours are included:",
            "",
        ]
        # The two parsers do not agree on page boundaries, so a candidate for
        # this block may sit on the page either side of it. Widening the net
        # costs a chooser nothing; missing the right line costs them the task.
        pool: list[str] = []
        for nearby in (page, page - 1, page + 1):
            for option in candidates.get(nearby, []):
                if option not in pool:
                    pool.append(option)

        # Ranked by the same symbol overlap the strict matcher uses, so the
        # likely answer is near the top. The ranking is a convenience only --
        # every one of these scored below the threshold that would let the
        # matcher write it unattended, which is why a person is reading this.
        ranked = sorted(
            ((similarity(text, option), option) for option in pool),
            key=lambda pair: (-pair[0], len(pair[1])),
        )

        if not ranked:
            lines += ["_none found — write the LaTeX by hand_", ""]
        else:
            lines += ["| # | overlap | candidate |", "|---:|---:|---|"]
            lines += [
                f"| {index} | {score:.2f} | `{option}` |"
                for index, (score, option) in enumerate(ranked[:8], start=1)
            ]
            if len(ranked) > 8:
                lines += ["", f"_{len(ranked) - 8} weaker candidates not shown._"]
            lines += [""]
        lines += ["**CHOICE:** ", ""]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote {OUT}")
    print(f"  {len(broken)} formulas, ranked candidates from each page and its neighbours")
    if not CHANDRA.exists():
        print(f"  WARNING no Chandra output at {CHANDRA} — sheet has no candidates")


if __name__ == "__main__":
    main()
