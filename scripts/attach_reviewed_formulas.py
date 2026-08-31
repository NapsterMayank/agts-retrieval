"""Attach the LaTeX a person confirmed against the page crop (R-068).

    PYTHONPATH=src python scripts/attach_reviewed_formulas.py            # dry run
    PYTHONPATH=src python scripts/attach_reviewed_formulas.py --apply

`attach_chandra_latex` writes what a matcher could prove. This writes what a
reviewer read off the crop, which is the only other honest source. The two are
kept apart on purpose: one is reproducible from the artefacts and the other
depends on a person, and a block should say which it got.

Every entry names the crop it was read from, who read it, and who cross-checked
it independently. An entry missing any of the three is refused -- that is the
whole point of the file.

**Both readers here are models**, and the file says so rather than implying a
person signed it. One read the page crop, the other reconstructed the formula
from the surrounding text alone with no access to the image; they are
independent in the way that matters, which is that neither saw the other's
answer. That is stronger than one model, and it is still not what section 14
means by a human reviewer. `countersigned_by` stays null until somebody looks.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.contracts.common import BlockType
from agts.contracts.objects import SourceBlock

ROOT = Path(__file__).parents[1]
CHAPTER = ROOT / "artifacts" / "quadratic-equations-quarantine"

#: Read off the page crops on 1 September 2026 by Claude, each cross-checked
#: against an independent Codex proposal built from the surrounding text alone
#: with no sight of the image (`artifacts/gold/formula-proposals-codex.json`).
#:
#: texts-159 is deliberately absent. Its crop is clipped at the top and the two
#: readings disagree: the crop shows `-b/2a +/- 0, i.e., x = -b/2a or -b/2a`
#: while Codex proposed only the pair of roots. Neither is safe to write, and a
#: formula nobody can read twice is exactly what the queue is for.
VERIFIED = {
    "quadratic-equations:docling:texts-153": {
        # The page shows the two fractions separately rather than over a common
        # denominator. Codex proposed the combined form from the text alone --
        # the same mathematics, and not what the page shows. The sign was the
        # open question, and crop and model reached minus independently.
        "latex": r"-\frac{b}{2a} - \frac{\sqrt{b^2 - 4ac}}{2a}",
        "crop": "assets/153.png",
        "read_by": "claude-opus-5, from the crop",
        "cross_checked_by": "codex, from the surrounding text only",
        "countersigned_by": None,
    },
    "quadratic-equations:docling:texts-198": {
        "latex": (
            r"\text{The roots are } \frac{-b}{2a}, \frac{-b}{2a}"
            r", \text{ i.e., } \frac{2}{6}, \frac{2}{6}"
            r", \text{ i.e., } \frac{1}{3}, \frac{1}{3}."
        ),
        "crop": "assets/198.png",
        "read_by": "claude-opus-5, from the crop",
        "cross_checked_by": "codex, from the surrounding text only",
        "countersigned_by": None,
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    path = CHAPTER / "source-blocks.jsonl"
    blocks = [
        SourceBlock.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_id = {block.block_id: block for block in blocks}

    for block_id, entry in VERIFIED.items():
        missing = [f for f in ("crop", "read_by", "cross_checked_by") if not entry.get(f)]
        if missing:
            raise SystemExit(f"{block_id}: an entry needs {', '.join(missing)}")
        if entry["read_by"] == entry["cross_checked_by"]:
            raise SystemExit(
                f"{block_id}: read and cross-check came from the same reader, which is "
                "one reading written down twice"
            )
        if block_id not in by_id:
            raise SystemExit(f"{block_id} is not in {path.name}")
        block = by_id[block_id]
        if block.block_type is not BlockType.FORMULA:
            raise SystemExit(f"{block_id} is not a formula block")
        if block.latex:
            raise SystemExit(
                f"{block_id} already carries LaTeX. Attaching over it would silently "
                "replace a matched formula with a read one."
            )
        countersign = entry.get("countersigned_by") or "NOBODY YET"
        print(f"{block_id.split(':')[-1]}  ({entry['crop']})")
        print(f"   read by      : {entry['read_by']}")
        print(f"   cross-checked: {entry['cross_checked_by']}")
        print(f"   countersigned: {countersign}")
        print(f"   was: {' '.join((block.text or '').split())[:78]}")
        print(f"   now: {entry['latex'][:78]}")

    if not args.apply:
        print("\nDRY RUN. Nothing written. Re-run with --apply.")
        return

    updated = [
        block.model_copy(update={"latex": VERIFIED[block.block_id]["latex"]})
        if block.block_id in VERIFIED else block
        for block in blocks
    ]
    path.write_text(
        "\n".join(block.model_dump_json() for block in updated) + "\n", encoding="utf-8"
    )
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
