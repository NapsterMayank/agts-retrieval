"""Attach Chandra's LaTeX to the quadratic chapter's formula blocks (R-008).

    PYTHONPATH=src python scripts/attach_chandra_latex.py            # dry run
    PYTHONPATH=src python scripts/attach_chandra_latex.py --apply

R-008 required that a formula block carry crop, raw text **and** LaTeX. The crop
and the raw text shipped; the LaTeX did not, while a second parser that produces
good LaTeX ran on the same pages and was used only to count characters.

This writes the missing field. It does not replace the degraded text — both are
kept, exactly as R-008 requires, so a wrong attachment stays detectable and the
block can be re-matched without re-parsing anything.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.contracts.common import BlockType
from agts.contracts.objects import SourceBlock
from agts.parsing.formula_match import MIN_CONFIDENCE, best_match
from agts.parsing.quality import is_unusable

ROOT = Path(__file__).parents[1]
BLOCKS = ROOT / "artifacts" / "quadratic-equations-quarantine" / "source-blocks.jsonl"
CHANDRA = Path(r"D:\Downloads\quadratic-chandra\quadratic.json")


def chandra_by_page() -> dict[int, list[str]]:
    document = json.loads(CHANDRA.read_text(encoding="utf-8"))
    pages: dict[int, list[str]] = {}
    for number, page in enumerate(document["children"], start=1):
        found = re.findall(r"<math[^>]*>(.*?)</math>", page["html"], re.DOTALL)
        pages[number] = [" ".join(html.unescape(item).split()) for item in found]
    return pages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the blocks back")
    args = parser.parse_args()

    if not CHANDRA.exists():
        raise SystemExit(f"no Chandra output at {CHANDRA}")

    blocks = [
        SourceBlock.model_validate_json(line)
        for line in BLOCKS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    candidates = chandra_by_page()

    attached, weak, updated = 0, 0, []
    for block in blocks:
        if block.block_type is not BlockType.FORMULA:
            updated.append(block)
            continue
        degraded = " ".join((block.text or "").split())
        match = best_match(block.block_id, degraded, candidates.get(block.region.page, []))
        if match and match.confident:
            attached += 1
            updated.append(block.model_copy(update={"latex": match.latex}))
            if is_unusable(degraded):
                print(f"  RECOVERED p{block.region.page} {block.block_id.split(':')[-1]}")
                print(f"      was: {degraded[:74]}")
                print(f"      now: {match.latex[:74]}")
        else:
            weak += 1
            updated.append(block)

    formulas = sum(1 for b in blocks if b.block_type is BlockType.FORMULA)
    unusable_before = sum(
        1 for b in blocks
        if b.block_type is BlockType.FORMULA and is_unusable(" ".join((b.text or "").split()))
    )
    unusable_after = sum(
        1 for b in updated
        if b.block_type is BlockType.FORMULA
        and is_unusable(" ".join((b.text or "").split()))
        and not b.latex
    )
    print(f"\nformula blocks: {formulas}")
    print(f"  LaTeX attached at >= {MIN_CONFIDENCE:.0%} confidence: {attached}")
    print(f"  left for human review: {weak}")
    print(f"  unusable before: {unusable_before}   still unusable and unattached: {unusable_after}")

    if not args.apply:
        print("\nDRY RUN. Nothing written. Re-run with --apply.")
        return

    BLOCKS.write_text(
        "\n".join(block.model_dump_json() for block in updated) + "\n", encoding="utf-8"
    )
    print(f"\nwrote {BLOCKS}")


if __name__ == "__main__":
    main()
