"""Build a self-contained pack another agent can check this work from.

    PYTHONPATH=src python scripts/export_verification_pack.py

Writes one text file per subject containing the full chapter text and every
claim made about it, with instructions to be adversarial. A reviewer using a
different model pastes one file and gets an independent opinion on the answer
key — no repository, no database, no key.

Self-contained on purpose: an agent that has to be told what NCERT chapter 1
says will confabulate it, and an agent given the chapter will not have to.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.evaluation.cases import load_gold_set

ROOT = Path(__file__).parents[1]
ARTIFACTS = ROOT / "artifacts"
GOLD = ARTIFACTS / "gold" / "pilot-2-chapters-v1.json"

CHAPTERS = {
    "science": ("chemical-reactions",
                "NCERT Class 10 Science, chapter 1 — Chemical Reactions and Equations"),
    "mathematics": ("quadratic-equations",
                    "NCERT Class 10 Mathematics, chapter 4 — Quadratic Equations"),
}

INSTRUCTIONS = """You are checking someone else's work, and your job is to find what is
wrong with it. Agreement is not the goal; a careful disagreement is worth more
than a confident endorsement.

Below is the full extracted text of one NCERT chapter, then a numbered list of
claims that another AI system made about that chapter while building a study
tool. Each claim is one of two kinds:

  ANSWERABLE  - the chapter answers this question, and the quoted text is where
                the answer is. The claim is WRONG if the chapter does not really
                answer it, or if the quoted text is not the right evidence, or if
                important evidence is missing.

  NOT ANSWERABLE - this chapter cannot answer the question at all. The claim is
                WRONG if the chapter does teach this. A concept the chapter only
                MENTIONS in passing, without teaching it, still counts as NOT
                ANSWERABLE - and that distinction is the hardest and most
                important judgement here.

Rules for judging:

1. Judge only from the chapter text provided. Do not use what you know about the
   NCERT syllabus in general; this specific chapter is the whole universe.
2. The extraction is imperfect. Mathematical notation in particular is mangled -
   "a  0" means "a is not equal to 0", and fractions and roots are flattened.
   Read past broken notation rather than treating it as missing content.
3. If you are unsure, say WRONG and explain the doubt. An unsure case needs a
   human, and a review that defaults to agreement finds nothing.

For each claim, reply on one line:

  <number>  RIGHT|WRONG|UNSURE  <one sentence: why>

Then finish with the three claims you are least comfortable with and why.
"""


def blocks_for(document: str) -> dict[str, dict]:
    path = ARTIFACTS / f"{document}-quarantine" / "source-blocks.jsonl"
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            block = json.loads(line)
            out[block["block_id"]] = block
    return out


def chapter_text(blocks: dict[str, dict]) -> str:
    ordered = sorted(blocks.values(), key=lambda b: b["order_index"])
    parts = []
    for block in ordered:
        if block["block_type"] in {"page_header", "page_footer"}:
            continue
        text = " ".join((block.get("text") or "").split())
        if text:
            prefix = "## " if block["block_type"] == "heading" else ""
            parts.append(f"{prefix}{text}")
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope", choices=["critical", "rest", "all"], default="critical",
        help="critical: the 47 release-critical cases. rest: everything else, "
             "which no reviewer has ever seen. all: both.",
    )
    args = parser.parse_args()

    gold_set = load_gold_set(GOLD)
    written = []

    for subject, (document, title) in CHAPTERS.items():
        blocks = blocks_for(document)
        if args.scope == "critical":
            selected = [c for c in gold_set.cases if c.is_release_critical]
        elif args.scope == "rest":
            selected = [c for c in gold_set.cases if not c.is_release_critical]
        else:
            selected = list(gold_set.cases)
        cases = [c for c in selected if c.subject == subject]
        if not cases:
            continue

        lines = [
            f"VERIFICATION PACK — {title}",
            "",
            INSTRUCTIONS,
            "",
            "=" * 78,
            "CHAPTER TEXT",
            "=" * 78,
            "",
            chapter_text(blocks),
            "",
            "=" * 78,
            f"CLAIMS TO CHECK ({len(cases)})",
            "=" * 78,
        ]

        for number, case in enumerate(cases, start=1):
            lines.append(f"\n--- CLAIM {number} ({case.case_id}) ---")
            lines.append(f"QUESTION: {case.query}")
            if case.answerable:
                lines.append("CLAIM: ANSWERABLE. The chapter answers this and the text below is the answer.")
                for block_id in case.gold_block_ids:
                    block = blocks.get(block_id)
                    if block:
                        lines.append(f"  QUOTED (page {block['region']['page']}): "
                                     + " ".join((block.get("text") or "").split()))
            else:
                lines.append("CLAIM: NOT ANSWERABLE. This chapter cannot answer this question.")

        suffix = "" if args.scope == "critical" else f"-{args.scope}"
        out = ARTIFACTS / "gold" / f"verify-{subject}{suffix}.txt"
        out.write_text("\n".join(lines), encoding="utf-8")
        written.append((out, len(cases), len("\n".join(lines))))

    for path, cases, size in written:
        print(f"wrote {path.name}: {cases} claims, {size // 1000}k characters")
    print("\nPaste one file into a different model. It needs nothing else.")


if __name__ == "__main__":
    main()
