"""Re-derive the formula review queue from what is actually wrong (R-065).

    PYTHONPATH=src python scripts/triage_formula_queue.py            # dry run
    PYTHONPATH=src python scripts/triage_formula_queue.py --apply

The queue was built as "every formula block carrying no LaTeX", which is not
the same question as "every formula a reader cannot trust". It read 73 across
two chapters. Thirty of those are the chemistry chapter, where the extracted
text says `Mg + O 2 -> MgO` -- correct, and missing LaTeX only because the
second parser there labels no formulas at all and never could supply any.

A backlog that counts work nobody can do is worse than no backlog: it hides the
items a person actually has to look at. Three dispositions, each of which is a
different decision by a different party:

ATTACHED
    LaTeX was matched from a second parse above the confidence and order
    margins. Nothing to review.

READABLE_NO_LATEX_SOURCE
    The extracted text is usable and no second parse offers LaTeX for it. Not
    pending anything: there is no queue a human could drain here. It becomes
    work again only if a LaTeX-producing parser is run over that chapter.

NEEDS_HUMAN
    The text is degraded and no candidate could be attached safely. This is the
    queue. It is meant to be short enough that somebody reads every entry.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.contracts.common import BlockType
from agts.contracts.objects import SourceBlock
from agts.parsing.quality import is_unusable

ROOT = Path(__file__).parents[1]
ARTIFACTS = ROOT / "artifacts"
CHAPTERS = ["chemical-reactions-quarantine", "quadratic-equations-quarantine"]


def triage(directory: Path) -> tuple[list[dict], dict[str, int]]:
    blocks = [
        SourceBlock.model_validate_json(line)
        for line in (directory / "source-blocks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    previous = {}
    queue_path = directory / "formula-review-queue.json"
    if queue_path.exists():
        for item in json.loads(queue_path.read_text(encoding="utf-8")):
            previous[item["block_id"]] = item

    pending, counts = [], {"ATTACHED": 0, "READABLE_NO_LATEX_SOURCE": 0, "NEEDS_HUMAN": 0}
    for block in blocks:
        if block.block_type is not BlockType.FORMULA:
            continue
        text = " ".join((block.text or "").split())
        if block.latex:
            counts["ATTACHED"] += 1
            continue
        if not is_unusable(text):
            counts["READABLE_NO_LATEX_SOURCE"] += 1
            continue
        counts["NEEDS_HUMAN"] += 1
        was = previous.get(block.block_id, {})
        pending.append({
            "block_id": block.block_id,
            "crop": was.get("crop"),
            "page": block.region.page,
            "raw_docling_text": block.text,
            # Kept so the reviewer sees what was rejected and why it was close,
            # rather than starting from the crop alone.
            "rejected_candidates": was.get("chandra_page_candidates", []),
            "review_status": "NEEDS_HUMAN",
            "latex": None,
        })
    return pending, counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    for name in CHAPTERS:
        directory = ARTIFACTS / name
        pending, counts = triage(directory)
        total = sum(counts.values())
        print(f"\n{name}: {total} formula blocks")
        for disposition, count in counts.items():
            print(f"    {disposition:26} {count}")
        for item in pending:
            print(f"      -> {item['block_id'].split(':')[-1]} p{item['page']}: "
                  f"{(item['raw_docling_text'] or '')[:60]}")

        if not args.apply:
            continue

        (directory / "formula-review-queue.json").write_text(
            json.dumps(pending, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        manifest_path = directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["formula_review_queue"] = counts["NEEDS_HUMAN"]
        manifest["formula_latex_attached"] = counts["ATTACHED"]
        manifest["formula_readable_without_latex"] = counts["READABLE_NO_LATEX_SOURCE"]
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"    wrote queue and manifest")

    if not args.apply:
        print("\nDRY RUN. Nothing written. Re-run with --apply.")


if __name__ == "__main__":
    main()
