"""A model pre-screen of the gold set, to shorten human review (sections 13, 14).

**This does not adjudicate anything.** Section 14 is explicit that automated
judges may assist evaluation and are never the sole release authority, and the
reason is visible in this script's own design: the cases and their answer keys
were written by a model, so a model checking them shares the blind spots that
produced them.

What it is good for is **triage**. A second model, given the chapter text and
none of my reasoning, marks each claim agree or disagree. Where it agrees, a
human is confirming something two independent passes already support. Where it
disagrees, a human is looking at a case that deserves the attention. That turns
a two-hour review into a short list plus a skim.

Three things make it a check rather than a rubber stamp:

- **It reads the chapter, not my answer key.** For an "unanswerable" claim it
  gets the whole chapter text and decides for itself.
- **It is told to disagree when unsure**, because a screen that defaults to
  agreement finds nothing.
- **Its verdicts are written to their own column.** They never enter
  `EvalCase.adjudicators`, which takes human names only.

    ANTHROPIC_API_KEY=... PYTHONPATH=src python scripts/model_adjudicate.py --limit 5
    ANTHROPIC_API_KEY=... PYTHONPATH=src python scripts/model_adjudicate.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.evaluation.cases import load_gold_set

ROOT = Path(__file__).parents[1]
ARTIFACTS = ROOT / "artifacts"
GOLD = ARTIFACTS / "gold" / "pilot-2-chapters-v1.json"
OUT = ARTIFACTS / "gold" / "model-screen.json"
MODEL = "claude-sonnet-5"

CHAPTER_OF = {
    "science": ("chemical-reactions", "NCERT Class 10 Science, chapter 1, Chemical Reactions and Equations"),
    "mathematics": ("quadratic-equations", "NCERT Class 10 Mathematics, chapter 4, Quadratic Equations"),
}

PROMPT = """You are checking someone else's answer key for a Class 10 study tool. \
Below is the full text of one NCERT chapter, exactly as extracted, then a question \
and a claim about it. Decide whether the claim is correct.

Judge only from the chapter text below. Formula and symbol extraction is imperfect, \
so read past mangled notation rather than treating it as absent content.

The claim being checked is one of two kinds:
- ANSWERABLE: the chapter answers the question, and specific quoted text is the answer.
  It is wrong if the chapter does not really answer the question, or if the quoted text
  is not where the answer is.
- NOT ANSWERABLE: this chapter cannot answer the question at all. It is wrong if the
  chapter does teach this, even briefly. A concept the chapter only *mentions in passing*
  without teaching still counts as NOT ANSWERABLE.

If you are unsure, answer "disagree" and say why. An unsure case needs a human, and a \
screen that defaults to agreement finds nothing.

Reply with JSON only: {{"verdict": "agree" or "disagree", "confidence": "high" or "low", \
"reason": "one sentence"}}

--- CHAPTER TEXT ---
{chapter}
--- END CHAPTER ---

QUESTION: {question}

CLAIM: {claim}
{evidence}"""


def chapter_text(document: str) -> str:
    path = ARTIFACTS / f"{document}-quarantine" / "source-blocks.jsonl"
    parts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        block = json.loads(line)
        if block["block_type"] in {"page_header", "page_footer"}:
            continue
        text = " ".join((block.get("text") or "").split())
        if text:
            parts.append(text)
    return "\n".join(parts)


def blocks_for(document: str) -> dict[str, dict]:
    path = ARTIFACTS / f"{document}-quarantine" / "source-blocks.jsonl"
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            block = json.loads(line)
            out[block["block_id"]] = block
    return out


def ask(client, prompt: str) -> dict:
    for attempt in range(4):
        try:
            message = client.messages.create(
                model=MODEL, max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            text = message.content[0].text.strip()
            start, end = text.find("{"), text.rfind("}")
            return json.loads(text[start : end + 1])
        except Exception as error:  # pragma: no cover - network
            if attempt == 3:
                return {"verdict": "error", "confidence": "low", "reason": str(error)[:200]}
            time.sleep(2 ** attempt)
    return {"verdict": "error", "confidence": "low", "reason": "unreachable"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="screen only the first N cases")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("set ANTHROPIC_API_KEY")

    import anthropic

    client = anthropic.Anthropic()
    gold_set = load_gold_set(GOLD)
    cases = [c for c in gold_set.cases if c.is_release_critical]
    if args.limit:
        cases = cases[: args.limit]

    chapters = {subject: chapter_text(document) for subject, (document, _) in CHAPTER_OF.items()}
    blocks = {subject: blocks_for(document) for subject, (document, _) in CHAPTER_OF.items()}

    results = []
    if OUT.exists():
        results = json.loads(OUT.read_text(encoding="utf-8"))
    seen = {r["case_id"] for r in results}

    for number, case in enumerate(cases, start=1):
        if case.case_id in seen:
            continue
        if case.answerable:
            claim = "ANSWERABLE - the chapter answers this, and the quoted text below is the answer."
            quoted = "\n\n".join(
                " ".join((blocks[case.subject][b].get("text") or "").split())
                for b in case.gold_block_ids if b in blocks[case.subject]
            )
            evidence = f"\nQUOTED AS THE ANSWER:\n{quoted}"
        else:
            claim = "NOT ANSWERABLE - this chapter cannot answer this question."
            evidence = ""

        verdict = ask(client, PROMPT.format(
            chapter=chapters[case.subject], question=case.query, claim=claim, evidence=evidence,
        ))
        results.append({
            "case_id": case.case_id,
            "subject": case.subject,
            "question": case.query,
            "my_claim": "answerable" if case.answerable else "not answerable",
            "model_verdict": verdict.get("verdict"),
            "model_confidence": verdict.get("confidence"),
            "model_reason": verdict.get("reason"),
        })
        OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
        mark = {"agree": "ok", "disagree": "FLAG", "error": "err"}.get(verdict.get("verdict"), "?")
        print(f"  [{number}/{len(cases)}] {case.case_id:<12} {mark:<5} {str(verdict.get('reason'))[:74]}")

    flagged = [r for r in results if r["model_verdict"] == "disagree"]
    errors = [r for r in results if r["model_verdict"] == "error"]
    print(f"\nscreened {len(results)} cases with {MODEL}")
    print(f"  agrees with my key: {sum(1 for r in results if r['model_verdict'] == 'agree')}")
    print(f"  disagrees (needs a human first): {len(flagged)}")
    if errors:
        print(f"  errors: {len(errors)}")
    for row in flagged:
        print(f"\n  FLAG {row['case_id']} [{row['subject']}] — I said {row['my_claim']}")
        print(f"       {row['question']}")
        print(f"       model: {row['model_reason']}")
    print(f"\nwrote {OUT}")
    print("\nThese are not adjudications. Section 14 forbids a model being the sole "
          "release authority, and this model shares the blind spots of the one that "
          "wrote the cases. It is a shorter list for the humans, nothing more.")


if __name__ == "__main__":
    main()
