"""A second opinion on the formulas no match could be attached to (R-068).

    PYTHONPATH=src python scripts/codex_formula_review.py

Three blocks survive `triage_formula_queue`: their extracted text is degraded and
no candidate cleared the confidence and order margins. R-065 refuses to guess
there, and it is right to -- a wrong formula that renders beautifully is the
failure mode the whole matching design exists to avoid.

So this does not attach anything. It asks a second model, from a different
vendor, to read the degraded text and the rejected candidates and say what the
formula is, with its reasoning. The proposals are written to their own file and
compared against the page crops by a person before anything is written to a
block. A model and a crop agreeing is two independent readings; a model alone is
a guess with better grammar.

Section 14 again: an automated judge is never the sole authority. This is the
short list, not the decision.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

ROOT = Path(__file__).parents[1]
ARTIFACTS = ROOT / "artifacts"
CHAPTER = ARTIFACTS / "quadratic-equations-quarantine"
OUT = ARTIFACTS / "gold" / "formula-proposals-codex.json"
SCRATCH = ARTIFACTS / "gold" / ".codex-formula-batch.md"

PROMPT = """Read the file {path} in this repository with `cat`. It is listed in
.gitignore, so search tools will report it missing -- open it by path instead.

It contains formula blocks extracted from an NCERT Class 10 Mathematics chapter
on quadratic equations. Each block's text came out of the PDF degraded: symbols
survived but spacing and reading order did not. For each block you get the
degraded text, the surrounding blocks for context, and the candidate LaTeX a
second parser produced for that page, none of which matched confidently.

For each block, say what the formula actually is, in LaTeX.

Be careful with signs. These are quadratic-formula fragments where a plus and a
minus are both plausible and only one is correct, and the surrounding text is
usually what decides it. If the context does not decide it, say so and set
"confidence": "low" -- a wrong formula that renders beautifully is worse than no
formula at all, because nobody looks at it twice.

Your entire reply must be one JSON array and nothing else. No preamble, no
markdown fence. One object per block, every block_id appearing exactly once:
[{{"block_id": "...", "latex": "...", "confidence": "high" or "low",
"reason": "what in the context decided it, especially the sign"}}]
"""


def main() -> None:
    blocks = [
        json.loads(line)
        for line in (CHAPTER / "source-blocks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    order = {block["block_id"]: i for i, block in enumerate(blocks)}
    queue = json.loads((CHAPTER / "formula-review-queue.json").read_text(encoding="utf-8"))

    # The queue keeps whatever candidates it was built with, and triage drops
    # them for entries it adds later. Read them from the second parse instead,
    # so a block that entered the queue today is not reviewed with less context
    # than one that entered last week.
    chandra: dict[int, list[str]] = {}
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "attach", Path(__file__).parent / "attach_chandra_latex.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        chandra = module.chandra_by_page()
    except Exception as error:  # the second parse is optional, not required
        print(f"  (no second-parser candidates available: {error})")
    if not queue:
        raise SystemExit("the review queue is empty; nothing to propose")

    lines = []
    for item in queue:
        index = order[item["block_id"]]
        # Context on both sides. A quadratic-formula fragment is decided by the
        # sentence that introduces it far more often than by its own symbols.
        neighbours = blocks[max(0, index - 4) : index + 5]
        lines.append(f"BLOCK {item['block_id']}")
        lines.append(f"  DEGRADED TEXT: {item['raw_docling_text']}")
        lines.append("  SURROUNDING BLOCKS, in order:")
        for neighbour in neighbours:
            marker = ">>" if neighbour["block_id"] == item["block_id"] else "  "
            text = " ".join((neighbour.get("text") or "").split())
            latex = neighbour.get("latex")
            lines.append(f"    {marker} {text[:220]}")
            if latex:
                lines.append(f"       (latex already attached: {latex[:150]})")
        candidates = item.get("rejected_candidates") or chandra.get(
            blocks[index]["region"]["page"], []
        )
        lines.append(f"  CANDIDATE LATEX FROM THE SECOND PARSER ({len(candidates)}), none matched:")
        for candidate in candidates:
            lines.append(f"    - {candidate[:220]}")
        lines.append("")

    SCRATCH.write_text("\n".join(lines), encoding="utf-8")

    binary = shutil.which("codex") or shutil.which("codex.cmd")
    if binary is None:
        raise SystemExit("codex CLI not on PATH")

    # Prompt on stdin: a multi-line argument through the Windows .cmd shim loses
    # later flags, --json among them, and the run returns prose with no warning.
    command = [binary, "exec", "-C", str(ROOT), "-s", "read-only",
               "-c", 'model_reasoning_effort="high"', "--json", "-"]
    done = subprocess.run(
        command, input=PROMPT.format(path=SCRATCH.relative_to(ROOT).as_posix()),
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800,
    )

    message = []
    for line in (done.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            message.append(item.get("text") or "")
    text = "\n".join(message)

    start, end = text.find("["), text.rfind("]")
    if start == -1:
        raise SystemExit(f"no JSON array from codex. stderr tail: {(done.stderr or '')[-300:]}")
    proposals = json.loads(text[start : end + 1])

    OUT.write_text(json.dumps(proposals, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    SCRATCH.unlink(missing_ok=True)

    for proposal in proposals:
        print(f"\n{proposal.get('block_id', '?').split(':')[-1]}  "
              f"[{proposal.get('confidence')}]")
        print(f"   latex : {proposal.get('latex')}")
        print(f"   reason: {proposal.get('reason')}")
    print(f"\nwrote {OUT}")
    print("\nProposals only. Compare each against its crop in "
          f"{CHAPTER / 'assets'} before any of it is attached.")


if __name__ == "__main__":
    main()
