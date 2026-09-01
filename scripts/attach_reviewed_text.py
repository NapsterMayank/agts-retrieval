"""Restore mathematics that PDF extraction destroyed inside a sentence (R-074).

    PYTHONPATH=src python scripts/attach_reviewed_text.py            # dry run
    PYTHONPATH=src python scripts/attach_reviewed_text.py --apply

`attach_reviewed_formulas` writes the `latex` field of a formula block and never
touches its text. This edits the text itself, which is heavier and needs a
heavier justification.

These blocks are prose whose inline mathematics did not survive: fraction bars,
square roots and exponents were dropped, leaving the digits loose in the
sentence. "Therefore, the roots of 6 x 2 - x - 2 = 0 are 2 1 . and - 3 2" reads
as a sentence while both of its answers are unreadable, so no gate flags it --
`is_unusable` sees plenty of words and passes it. A learner asking for the roots
gets that.

Three rules make this a correction rather than an edit:

**The original is kept.** Every entry records the text it replaces, and the
script refuses to run when what is on disk is neither -- a re-parse invalidates
a correction the way it invalidates an approval. The originals also go to
`text-corrections.json` beside the artefact, so the difference between what the
parser produced and what is served stays readable.

**Notation, not wording.** Restoring `2/3` where the parser left `2 1 .`
recovers a character the PDF had. Rewriting the sentence would not, and is not
done here.

**Plain notation, not LaTeX.** The search index reads this field (R-069), and
`\\frac{2}{3}` is not words. Unicode is readable to a person and to an embedding.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.contracts.objects import SourceBlock

ROOT = Path(__file__).parents[1]
CHAPTER = ROOT / "artifacts" / "quadratic-equations-quarantine"
RECORD = CHAPTER / "text-corrections.json"

#: "derivation" means the value was computed from the equation in the same
#: sentence and checked against a neighbour that already carries verified LaTeX.
#: Those four paragraphs have no page crop, so there is no image to read, and
#: the entry says so rather than implying one was consulted.
CORRECTIONS = {
    "quadratic-equations:docling:texts-106": {
        "was": "In other words, 1 and 3 2 are the roots of the equation 2 x 2 - 5 x + 3 = 0.",
        "now": "In other words, 1 and 3/2 are the roots of the equation 2x² − 5x + 3 = 0.",
        "source": "derivation: 2x^2 - 5x + 3 = (2x - 3)(x - 1), so the roots are 3/2 and 1",
        "read_by": "claude-opus-5, by solving the equation in the sentence",
        "cross_checked_by": "codex, from the surrounding text only",
        "countersigned_by": None,
    },
    "quadratic-equations:docling:texts-120": {
        "was": "Therefore, the roots of 6 x 2 - x - 2 = 0 are 2 1 . and - 3 2",
        "now": "Therefore, the roots of 6x² − x − 2 = 0 are 2/3 and −1/2.",
        "source": "derivation: 6x^2 - x - 2 = (3x - 2)(2x + 1), so the roots are 2/3 and -1/2",
        "read_by": "claude-opus-5, by solving the equation in the sentence",
        "cross_checked_by": "codex, from the surrounding text only",
        "countersigned_by": None,
    },
    "quadratic-equations:docling:texts-121": {
        "was": "We verify the roots, by checking that 2 1 and 3 2 − satisfy 6 x 2 - x - 2 = 0.",
        "now": "We verify the roots, by checking that 2/3 and −1/2 satisfy 6x² − x − 2 = 0.",
        "source": "derivation: the same two roots as texts-120, one sentence earlier",
        "read_by": "claude-opus-5, by solving the equation in the sentence",
        "cross_checked_by": "codex, from the surrounding text only",
        "countersigned_by": None,
    },
    "quadratic-equations:docling:texts-127": {
        "was": "Therefore, the roots of 2 3 2 6 2 0 x x − + = are 2 3 , 2 3 .",
        "now": "Therefore, the roots of 3x² − 2√6x + 2 = 0 are √(2/3), √(2/3).",
        "source": "derivation: texts-123 factorises it to (√3x - √2)^2, and the texts-125 crop shows x = √(2/3)",
        "read_by": "claude-opus-5, by solving the equation in the sentence",
        "cross_checked_by": "codex, from the surrounding text only",
        "countersigned_by": None,
    },
    "quadratic-equations:docling:texts-152": {
        # The sentence really does stop at "and": the second root is texts-153,
        # which already carries verified LaTeX. Codex completed it with both
        # roots, which is the mathematics and not this block.
        "was": "If b 2 - 4 ac > 0, we get two distinct real roots 2 4 2 2 b ac b a a − − + and",
        "now": "If b² − 4ac > 0, we get two distinct real roots −b/2a + √(b² − 4ac)/2a and",
        "source": "crop assets/152.png",
        "read_by": "claude-opus-5, from the crop",
        "cross_checked_by": "codex, from the surrounding text only",
        "countersigned_by": None,
    },
    "quadratic-equations:docling:texts-157": {
        # Codex dropped the repeated root and moved the +/- 0 into the
        # numerator. The crop shows both, and the repetition is the point of the
        # sentence: when the discriminant is zero the two roots coincide.
        "was": "If b 2 - 4 ac = 0, then x = 0 b − ± , i.e., or - b b x = − ⋅",
        "now": "If b² − 4ac = 0, then x = −b/2a ± 0, i.e., x = −b/2a or −b/2a.",
        "source": "crop assets/157.png",
        "read_by": "claude-opus-5, from the crop",
        "cross_checked_by": "codex, from the surrounding text only",
        "countersigned_by": None,
    },
}

REQUIRED = ("was", "now", "source", "read_by", "cross_checked_by")


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

    pending: dict[str, dict] = {}
    already: list[str] = []
    for block_id, entry in CORRECTIONS.items():
        missing = [field for field in REQUIRED if not entry.get(field)]
        if missing:
            raise SystemExit("%s: an entry needs %s" % (block_id, ", ".join(missing)))
        if block_id not in by_id:
            raise SystemExit("%s is not in %s" % (block_id, path.name))

        current = " ".join((by_id[block_id].text or "").split())
        if current == " ".join(entry["now"].split()):
            already.append(block_id)
            continue
        if current != " ".join(entry["was"].split()):
            raise SystemExit(
                "%s: the text on disk is neither the recorded original nor the "
                "correction. A re-parse invalidates a correction; re-read the block "
                "before writing.%s  on disk : %s%s  expected: %s"
                % (block_id, chr(10), current[:88], chr(10), entry["was"][:88])
            )

        pending[block_id] = entry
        print("%s%s  (%s)" % (chr(10), block_id.split(":")[-1], entry["source"][:66]))
        print("   was: %s" % entry["was"][:94])
        print("   now: %s" % entry["now"][:94])

    if already:
        names = ", ".join(block.split(":")[-1] for block in already)
        print("%s%d already corrected: %s" % (chr(10), len(already), names))
    if not pending:
        print("%snothing to do" % chr(10))
        return
    if not args.apply:
        print("%sDRY RUN. Nothing written. Re-run with --apply." % chr(10))
        return

    updated = [
        block.model_copy(update={"text": CORRECTIONS[block.block_id]["now"]})
        if block.block_id in pending
        else block
        for block in blocks
    ]
    path.write_text(
        chr(10).join(block.model_dump_json() for block in updated) + chr(10),
        encoding="utf-8",
    )

    record = json.loads(RECORD.read_text(encoding="utf-8")) if RECORD.exists() else {}
    record.update(dict(pending))
    RECORD.write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + chr(10), encoding="utf-8"
    )

    print("%swrote %s" % (chr(10), path))
    print("wrote %s -- the originals, so the edit stays auditable" % RECORD.name)
    print("%sThe index reads this field: re-embed and re-run the baseline." % chr(10))


if __name__ == "__main__":
    main()
