# How to continue this work

For whoever picks this up — human or agent. Read this first, then
`EVALUATION_LEDGER.md` for what was measured and `DECISION_LOG.md` for why
anything is the way it is.

## What this is, in one paragraph

A retrieval and evidence system for a grounded teaching tool. It takes a
learner's question and a curriculum scope, and returns either **cited evidence
from an approved textbook** or **a refusal that states its reason**. It does not
generate text: the teaching loop that would write sentences is §9, and whether
this repository builds it is open question Q5. The whole design assumes that
answering wrongly is the expensive failure and refusing is the cheap one.

## Where it stands, 31 August 2026

Two NCERT Class 10 chapters — Science ch1 and Mathematics ch4 — parsed,
composed, chunked, embedded, persisted in Postgres, and served over HTTP.

| | visible 140 | holdout 64 |
|---|---:|---:|
| Unanswerable questions refused | 31/31 | **24/24** — supports ≥88% |
| Answerable questions answered | 90/109 | **34/40** — supports ≥73% |
| Citation ID resolution (§14: 100%) | 100% | 100% |
| Citation completeness (§14: ≥95%) | 95.2% | 97.1% |
| Lineage failures (§14: 0) | 0 | 0 |

Bounds are exact one-sided Clopper-Pearson at 95% (R-039). **Quote the holdout
column**, and quote the bound rather than the fraction.

**Nothing here is releasable.** No source has a rights record, so the service
refuses to boot without an explicit override; no human has adjudicated a single
case; the gold set is 204 cases against §6.4's 300-500; and every number was
produced under an evaluation licence over quarantined content.

## The five rules this repository actually follows

These are not style preferences. Each was earned by something going wrong, and
breaking one has already produced a defect.

**1. Measure before adopting, and declare the rule before looking.** Every
threshold and every design choice here was compared against alternatives on the
*visible* set under a rule stated in advance — no leaks first, then most answers.
The holdout is touched once, at the end. See R-030, R-048, R-051.

**2. Never re-tune after a correctness fix.** When a fix costs acceptance, the
number stays down. Re-tuning converts a fixed defect back into a number (R-036).

**3. Verify a finding before acting on it — including your own.** Two agent
reviewers produced 19 claims; 6 were real. One would have had me "fix" behaviour
that was already correct (R-036, R-040). Reading the code beats trusting the
report, and that applies to this file too.

**4. A number travels with its denominator and its caveat.** `8/8` supports "at
least 69%", not certainty (R-039). A rate quoted without its sample size will be
read as stronger than it is.

**5. Record the hypotheses that failed.** R-022, R-027, R-030, R-051 and R-052
are all things that seemed obviously right and were not. They are written down so
the next person does not spend a day rediscovering them.

## What is already known not to work

Do not spend time on these without new evidence — each was measured:

| idea | result |
|---|---|
| Reranking (`rerank-2`) | moved pack recall by **zero cases** (R-027) |
| Lower abstention floor | leaks an unanswerable case (R-048) |
| Fewer shared objects, or greater depth | leaks (R-045) |
| Expanding the query with the concept name | leaks 3-5 cases (R-051) |
| Counting adjacent windows as agreement | leaks (R-052) |
| Formula enrichment by a generative model | 23% hallucination (R-008) |
| Matching a second parser's LaTeX by page | 2 of 3 wrong when checked (R-043) |

**Five separate relaxations of the gate have now been measured and all five buy
acceptance by leaking a refusal.** That is a frontier, not a mistuned parameter.

## Where the remaining acceptance lives

21 of 25 false refusals are the two retrievers agreeing on the *section* and
disagreeing on the *window*. None of these is free:

1. **Rerank within an object**, so both retrievers pick the same window. The one
   untried use of a reranker, and it attacks the 21 directly.
2. **Overlapping chunk windows**, so adjacency becomes genuine block overlap.
   Re-measures everything, including every stored vector.
3. **A third retriever**, so agreement can be two-of-three rather than
   two-of-two.
4. **Formula repair** — 39 formulas await a human choosing among candidates;
   fixes two of the four below-floor cases.

## What is blocked, and on whom

| | blocks | who |
|---|---|---|
| **Q3** signed rights records | serving anything at all | client |
| **Q1** named pilot curriculum | ingesting beyond two chapters | client |
| **Q5** does this repo build §9 | the teaching loop, and §14's citation *precision* row | client |
| **Q2** holdout seal timing | whether that gate binds | client |
| Two adjudicators | believing any number | Mayank and Sumit, named 31 Aug |
| A working LLM key | the second-model pre-screen | anyone (all three keys 401) |
| Mathpix key | formula recovery, though Chandra covers some | client |
| GPU | curriculum-scale parsing | us |

## Running it

```
pip install -e ".[dev]"
python -m pytest -q                  # 190 pass, 7 skip without a database
docker compose -f docker/compose.yml up -d
```

Then, with `AGTS_DATABASE_URL` and `VOYAGE_API_KEY` set:

```
python scripts/embed_representations.py   # once; cached by content hash
python scripts/holdout_validation.py      # the number that gets quoted
python scripts/citation_report.py         # §14 citation and lineage rows
python scripts/import_corpus.py           # write to Postgres and re-score from it
python scripts/serve.py                   # the HTTP surface
```

Every number in `EVALUATION_LEDGER.md` comes from one of those. If a claim has no
script behind it, treat it as unverified.

## Where the content is

`artifacts/*-quarantine/` holds the parsed chapters, and is **gitignored** — the
blocks are the chapter text and the assets are page crops, all pending rights
records. Regenerate with `scripts/assemble_*_quarantine.py` and
`scripts/compose_*.py`. The same applies to review sheets and verification packs,
which quote the chapter in full.

## If you change one thing

Re-run `holdout_validation.py` and `citation_report.py`, and put the numbers in
`EVALUATION_LEDGER.md` with the date. A change whose effect was not measured is
indistinguishable from a change that did nothing — and this repository has
already shipped two defects that no gate could see.
