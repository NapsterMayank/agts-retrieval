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
    PYTHONPATH=src python scripts/model_adjudicate.py --judge codex

**Two judges, and the second is the better one for this.** The gold set was
written by Claude, so a Claude screen shares the blind spots that produced it --
the objection this docstring already raises against itself. Codex is a different
vendor on a different corpus that has never seen the reasoning behind these
cases, which is what independent was supposed to mean.

It is still a screen. Section 14 says an automated judge is never the sole
release authority, and two models agreeing is two models, not two humans.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
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


CODEX_BATCH_PROMPT = """You are checking someone else's answer key for a Class 10 study tool. Read the file {path} in this repository. It holds one NCERT chapter as extracted, then a list of questions each with a claim about it.

Judge only from the chapter text in that file. Formula and symbol extraction is imperfect, so read past mangled notation rather than treating it as absent content.

Each claim is one of two kinds:
- ANSWERABLE: the chapter answers the question, and specific quoted text is the answer.
  It is wrong if the chapter does not really answer the question, or if the quoted text
  is not where the answer is.
- NOT ANSWERABLE: this chapter cannot answer the question at all. It is wrong if the
  chapter does teach this, even briefly. A concept the chapter only *mentions in passing*
  without teaching still counts as NOT ANSWERABLE.

If you are unsure about a case, answer "disagree" and say why. An unsure case needs a human, and a screen that defaults to agreement finds nothing.

Your entire reply must be one JSON array and nothing else. No preamble, no summary
sentence, no closing remark, no markdown fence. A reply that begins with any word
other than "[" is a failed run and the whole batch is discarded, so do not narrate
what you found -- put it in the "reason" fields.

One object per case, and every case_id given to you must appear exactly once:
[{{"case_id": "...", "verdict": "agree" or "disagree", "confidence": "high" or "low", "reason": "one sentence"}}]
"""


def _codex_message(stream: str) -> str:
    """The assistant's final text, pulled out of Codex's JSONL event stream.

    Only `agent_message` items count. Reasoning traces and command echoes also
    carry text, and one of them quoting a bracket would be read as the verdict.
    """
    parts = []
    for line in stream.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            parts.append(item.get("text") or "")
    return "\n".join(parts)


def ask_codex(batch, chapter, scratch):
    """Screen a batch of cases with the Codex CLI.

    Batched because every call spawns a session and re-sends the chapter; one
    call per case would send the same thirty thousand characters ninety-five
    times. The chapter goes to a file rather than an argument -- a chapter does
    not fit in a Windows command line, and quoting it into one corrupts it
    quietly, which is the worst way for an answer key check to fail.
    """
    lines = ["--- CHAPTER TEXT ---", chapter, "--- END CHAPTER ---", ""]
    for item in batch:
        lines.append("CASE " + item["case_id"])
        lines.append("  QUESTION: " + item["question"])
        lines.append("  CLAIM: " + item["claim"])
        if item["evidence"]:
            lines.append("  " + item["evidence"].strip())
        lines.append("")
    scratch.write_text("\n".join(lines), encoding="utf-8")

    # shutil.which, because on Windows the npm shim is codex.cmd and bare
    # "codex" is a shell script CreateProcess cannot launch.
    binary = shutil.which("codex") or shutil.which("codex.cmd")
    if binary is None:
        return [_codex_error(i, "codex CLI not on PATH") for i in batch]

    command = [
        binary, "exec",
        "-C", str(ROOT), "-s", "read-only",
        "-c", 'model_reasoning_effort="medium"',
        # JSONL, because plain stdout carries the CLI's own chatter and a screen
        # that scrapes prose will eventually scrape a sentence containing a
        # bracket.
        "--json",
        # The prompt arrives on stdin, not as an argument. On Windows the npm
        # shim is a .cmd, and a multi-line argument passed through it breaks
        # argument parsing badly enough that later flags are lost -- `--json`
        # among them, so the run silently returns prose and every case in the
        # batch is recorded as an error. Nothing warns; the output is simply a
        # different shape.
        "-",
    ]
    prompt = CODEX_BATCH_PROMPT.format(path=scratch.relative_to(ROOT).as_posix())
    try:
        done = subprocess.run(
            command, input=prompt, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=1200,
        )
    except subprocess.TimeoutExpired:
        return [_codex_error(i, "codex timed out after 1200s") for i in batch]

    text = _codex_message(done.stdout or "")
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        detail = (done.stderr or text)[-200:].replace("\n", " ")
        return [_codex_error(i, "no JSON array from codex: " + detail) for i in batch]
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError as error:
        return [_codex_error(i, "unparseable codex JSON: " + str(error)) for i in batch]

    # Matched on case_id, never on position. A judge that drops or reorders a
    # case must produce a missing verdict rather than a verdict against the
    # wrong question.
    by_id = {row.get("case_id"): row for row in parsed if isinstance(row, dict)}
    return [by_id.get(i["case_id"]) or _codex_error(i, "codex returned no verdict")
            for i in batch]


def _codex_error(item, reason):
    return {"case_id": item["case_id"], "verdict": "error",
            "confidence": "low", "reason": reason}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="screen only the first N cases")
    parser.add_argument("--judge", choices=("anthropic", "codex"), default="anthropic",
                        help="which model screens; codex is the independent one")
    parser.add_argument("--batch", type=int, default=8,
                        help="cases per codex call; each call re-sends the chapter")
    args = parser.parse_args()

    client = None
    if args.judge == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("set ANTHROPIC_API_KEY, or pass --judge codex")
        import anthropic

        client = anthropic.Anthropic()
    judge_name = MODEL if args.judge == "anthropic" else "codex-cli"
    gold_set = load_gold_set(GOLD)
    cases = [c for c in gold_set.cases if c.is_release_critical]
    if args.limit:
        cases = cases[: args.limit]

    chapters = {subject: chapter_text(document) for subject, (document, _) in CHAPTER_OF.items()}
    blocks = {subject: blocks_for(document) for subject, (document, _) in CHAPTER_OF.items()}

    # One file per judge. Overwriting one screen with the other destroys the only
    # thing two judges buy: the cases they disagree about.
    out_path = OUT if args.judge == "anthropic" else OUT.with_name("model-screen-codex.json")
    results = []
    if out_path.exists():
        results = json.loads(out_path.read_text(encoding="utf-8"))
    seen = {r["case_id"] for r in results}

    if args.judge == "codex":
        pending = [c for c in cases if c.case_id not in seen]
        scratch = ARTIFACTS / "gold" / ".codex-screen-batch.md"
        by_subject = {}
        for case in pending:
            by_subject.setdefault(case.subject, []).append(case)

        finished = 0
        for subject, subject_cases in by_subject.items():
            for start in range(0, len(subject_cases), args.batch):
                chunk = subject_cases[start : start + args.batch]
                batch = []
                for case in chunk:
                    if case.answerable:
                        quoted = "\n\n".join(
                            " ".join((blocks[case.subject][b].get("text") or "").split())
                            for b in case.gold_block_ids if b in blocks[case.subject]
                        )
                        claim = ("ANSWERABLE - the chapter answers this, and the quoted "
                                 "text below is the answer.")
                        evidence = "QUOTED AS THE ANSWER:" + "\n" + quoted
                    else:
                        claim = "NOT ANSWERABLE - this chapter cannot answer this question."
                        evidence = ""
                    batch.append({"case_id": case.case_id, "question": case.query,
                                  "claim": claim, "evidence": evidence})
                verdicts = ask_codex(batch, chapters[subject], scratch)
                for case, verdict in zip(chunk, verdicts):
                    results.append({
                        "case_id": case.case_id,
                        "subject": case.subject,
                        "question": case.query,
                        "my_claim": "answerable" if case.answerable else "not answerable",
                        "model_verdict": verdict.get("verdict"),
                        "model_confidence": verdict.get("confidence"),
                        "model_reason": verdict.get("reason"),
                    })
                    finished += 1
                    mark = {"agree": "ok", "disagree": "FLAG", "error": "err"}.get(
                        verdict.get("verdict"), "?")
                    print("  [%d/%d] %-12s %-5s %s" % (
                        finished, len(pending), case.case_id, mark,
                        str(verdict.get("reason"))[:70]))
                out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        scratch.unlink(missing_ok=True)
        cases = []

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
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        mark = {"agree": "ok", "disagree": "FLAG", "error": "err"}.get(verdict.get("verdict"), "?")
        print(f"  [{number}/{len(cases)}] {case.case_id:<12} {mark:<5} {str(verdict.get('reason'))[:74]}")

    flagged = [r for r in results if r["model_verdict"] == "disagree"]
    errors = [r for r in results if r["model_verdict"] == "error"]
    print(f"\nscreened {len(results)} cases with {judge_name}")
    print(f"  agrees with my key: {sum(1 for r in results if r['model_verdict'] == 'agree')}")
    print(f"  disagrees (needs a human first): {len(flagged)}")
    if errors:
        print(f"  errors: {len(errors)}")
    for row in flagged:
        print(f"\n  FLAG {row['case_id']} [{row['subject']}] — I said {row['my_claim']}")
        print(f"       {row['question']}")
        print(f"       model: {row['model_reason']}")
    print(f"\nwrote {out_path}")
    print("\nThese are not adjudications. Section 14 forbids a model being the sole "
          "release authority, and this model shares the blind spots of the one that "
          "wrote the cases. It is a shorter list for the humans, nothing more.")


if __name__ == "__main__":
    main()
