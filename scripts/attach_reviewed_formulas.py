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
#: texts-159 is deliberately absent, for the second review running. Its crop is
#: clipped at the top -- the numerators of three fractions are cut off -- and the
#: two readings disagree the same way both times: the crop shows
#: `-b/2a +/- 0, i.e., x = -b/2a or -b/2a` and Codex proposes only the pair of
#: roots. The mathematics is not in doubt; which characters are in this block is.
#: Writing a formula on that basis is how a wrong one gets in, and a formula
#: nobody can read twice is exactly what the queue is for.
VERIFIED = {
    "quadratic-equations:docling:texts-151": {
        # The quadratic formula itself. The matcher proposed exactly this at
        # confidence 1.000 and withheld it on order margin -- correctly, since
        # the extracted text is scrambled. Crop and Codex agree character for
        # character, which is the only reason it is written here rather than
        # left for the matcher to keep refusing.
        "latex": 'x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}',
        "crop": "assets/151.png",
        "read_by": "claude-opus-5, from the crop",
        "cross_checked_by": "codex, from the surrounding text only",
        "countersigned_by": None,
    },
    "quadratic-equations:docling:texts-119": {
        # The extracted text lost both fraction bars and the minus, leaving
        # "x = 2 3 or x = 1 2 -". Codex derived the negative second root from
        # the factors in the surrounding text without seeing the page.
        "latex": 'x = \\frac{2}{3} \\text{ or } x = -\\frac{1}{2}',
        "crop": "assets/119.png",
        "read_by": "claude-opus-5, from the crop",
        "cross_checked_by": "codex, from the surrounding text only",
        "countersigned_by": None,
    },
    "quadratic-equations:docling:texts-123": {
        # Every square root vanished from the extraction: the page reads
        # 3x^2 - 2*sqrt(6)x + 2 and the text kept "2 3 2 6 2 x x". Three lines
        # of one derivation, which is why it is an aligned block.
        "latex": '\\text{Solution : } \\begin{aligned} 3x^2 - 2\\sqrt{6}x + 2 &= 3x^2 - \\sqrt{6}x - \\sqrt{6}x + 2 \\\\ &= \\sqrt{3}x(\\sqrt{3}x - \\sqrt{2}) - \\sqrt{2}(\\sqrt{3}x - \\sqrt{2}) \\\\ &= (\\sqrt{3}x - \\sqrt{2})(\\sqrt{3}x - \\sqrt{2}) \\end{aligned}',
        "crop": "assets/123.png",
        "read_by": "claude-opus-5, from the crop",
        "cross_checked_by": "codex, from the surrounding text only",
        "countersigned_by": None,
    },
    "quadratic-equations:docling:texts-125": {
        # The square roots are gone here too, which is what made "3 2 3 2 0 x x"
        # out of (sqrt(3)x - sqrt(2))(sqrt(3)x - sqrt(2)) = 0. R-054 counted this
        # block as rescued by the Symbol-font decode; it was not.
        "latex": '(\\sqrt{3}x - \\sqrt{2})(\\sqrt{3}x - \\sqrt{2}) = 0\\text{. Now, } \\sqrt{3}x - \\sqrt{2} = 0 \\text{ for } x = \\sqrt{\\frac{2}{3}}.',
        "crop": "assets/125.png",
        "read_by": "claude-opus-5, from the crop",
        "cross_checked_by": "codex, from the surrounding text only",
        "countersigned_by": None,
    },
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

    already: list[str] = []
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
        if block.latex == entry["latex"]:
            already.append(block_id)
            continue
        if block.latex:
            raise SystemExit(
                f"{block_id} already carries different LaTeX. Attaching over it would "
                "silently replace one reading with another; delete the old one "
                "deliberately if that is what you mean."
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
