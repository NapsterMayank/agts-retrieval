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

## Where it stands, 1 September 2026

Two NCERT Class 10 chapters — Science ch1 and Mathematics ch4 — parsed,
composed, chunked, embedded, persisted in Postgres, and served over HTTP.

| | visible 140 | holdout 64 |
|---|---:|---:|
| Unanswerable questions refused | 31/31 | **24/24** — supports ≥88% |
| Answerable questions answered | 106/109 | **38/40** — supports ≥85% |
| Citation ID resolution (§14: 100%) | 100% | 100% |
| Citation completeness (§14: ≥95%) | 96.1% | 97.4% |
| Lineage failures (§14: 0) | 0 | 0 |

Retrieval on the visible set: candidate and pack recall both **99.1%** at 38
blocks per pack, zero invariant violations, zero failing gating slices for the
dense retriever.

Bounds are exact one-sided Clopper-Pearson at 95% (R-039). **Quote the holdout
column**, and quote the bound rather than the fraction.

These were measured on 1 September with `voyage-4-large` (R-058) and the shipped
pair 0.744 / 0.765 (R-060), after the last correction to the corpus. Any change
to a block's text changes the index, so re-embed and re-run both reports before
quoting them again — `scripts/embed_representations.py`, then
`real_content_baseline.py`, `holdout_validation.py` and `citation_report.py`.
They need `VOYAGE_API_KEY`.

**Nothing here is releasable.** No source has a rights record, so the service
refuses to boot without an explicit override; no human has adjudicated a single
case; the gold set is 204 cases against §6.4's 300-500; and every number was
produced under an evaluation licence over quarantined content.

## Start here: the next four tasks, in order

**0. Re-embed and re-measure.** Twelve window texts changed in the decode, so
every number above describes the corpus as it was before. One API call, then two
reports:

```
PYTHONPATH=src python scripts/embed_representations.py
PYTHONPATH=src python scripts/holdout_validation.py
PYTHONPATH=src python scripts/citation_report.py
```

Do not re-tune the thresholds afterwards (R-036). Watch citation completeness in
particular: it sits at 96.1% visible against a 95% bar, and every newly readable
block is another chance to cite incompletely.

**1. Get the answer key adjudicated.** This is the task that changes what every
number here is *worth*, as opposed to what it is. The sheet is already exported
at `artifacts/gold/review-sheet.csv` — **95 release-critical cases**, 50 science
and 45 mathematics, 40 with an answer key and 55 claimed unanswerable. It grew
from 48 when paraphrases inherited release-critical status, so re-export rather
than reuse anything older:

```
PYTHONPATH=src python scripts/export_review_sheet.py     # a spreadsheet, 95 rows
PYTHONPATH=src python scripts/review_cases.py --reviewer "Name"   # or one at a time
PYTHONPATH=src python scripts/import_review_sheet.py a.csv b.csv --apply
```

Mayank and Sumit are named (Q6), neither has started. **Both review every case**
— splitting by subject gives each case one reviewer, which is exactly what the
two-adjudicator rule exists to prevent.

**2. Finish the damaged mathematics.** Two lists, and neither is long:

- **One formula**, `texts-159`, whose crop is clipped at the top. Two
  independent readings disagreed about it twice (R-068, R-073), so it needs a
  person with the page rather than another model.
- **Eight sentences** whose inline mathematics was destroyed and which read as
  ordinary prose: texts-107, 122, 126, 141, 194, 195, 196, 225 (R-074). Six are
  derivable from the equation in the sentence; 141 and 225 need crops.

`scripts/triage_formula_queue.py` reports what is actually outstanding,
`attach_reviewed_formulas.py` writes a verified LaTeX field, and
`attach_reviewed_text.py` corrects a sentence while keeping the original.

Do not trust an older doc saying *39 formulas* or *73*: both counted formulas
lacking a LaTeX field, when most of those read perfectly well without one
(R-054, R-067). And do not build the list by eye — the six corrected on 1
September were found that way, and the scan afterwards found eight more.

**3. Then, and only then, chase acceptance.** It sits at 95% on the holdout and
five ways to raise it have already been measured and rejected. The untried ones
are listed under *Where the remaining acceptance lives* below. Do not start here:
a number improved before the answer key is adjudicated is a number nobody can
believe.

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
| Reranking (`rerank-2`) | moved pack recall by **zero cases** on top of dense, twice: R-027, and again under `voyage-4-large` where it also changed the holdout by nothing (Q4 answered) |
| Putting LaTeX in the search index | costs a case of recall; `rac{-b}{2a}` is not words. Index the text, show the LaTeX (R-069) |
| Making LaTeX outrank text unconditionally | breaks the case where good text sits beside a wrong attachment. The defect was in the discriminator (R-066) |
| Hybrid fusion as a shipped retriever | loses to its own dense half on both recall and abstention, and costs a second retrieval (R-062) |
| Lower abstention floor | leaks an unanswerable case (R-048) |
| Fewer shared objects, or greater depth | leaks (R-045) |
| Expanding the query with the concept name | leaks 3-5 cases (R-051) |
| Counting adjacent windows as agreement | leaks (R-052) |
| Formula enrichment by a generative model | 23% hallucination (R-008) |
| Matching a second parser's LaTeX by page | 2 of 3 wrong when checked (R-043) |

**Five separate relaxations of the gate have now been measured and all five buy
acceptance by leaking a refusal.** That is a frontier, not a mistuned parameter.

## Where the remaining acceptance lives

**The section-versus-window problem is solved.** It was not a ranking failure:
dense retrieval kept one window per object, so a 0.007 score difference decided
which paragraph of the right section a learner saw. An object may now be
represented by up to three windows when their scores tie (R-070, R-074), and
candidate recall went 95.4% to 99.1% with the dense retriever's failing gating
slices going 22 to 0.

Three false refusals remain on the visible set, and they are not one problem:

1. `maths-023` misses the floor by **0.0015** and `maths-024-p1` by 0.021. A
   lower floor leaks an unanswerable case, measured four ways (R-030, R-048).
2. `maths-022-p1` fails corroboration. Relaxing that leaks two (R-063).

So the cheap moves are gone. What is left that is not a relaxation:

1. **Generation** (§9, Q5). Until something writes an answer, citation
   *precision* cannot be measured at all — a pack spans 38 blocks and about one
   is gold, which reads as 3.5% and is really "nobody has narrowed it yet".
2. **A third retriever**, so agreement can be two-of-three rather than
   two-of-two.
3. **More corpus.** Everything here is calibrated on two chapters and 204 cases
   against §6.4's 300-500. Adding chapters three and four moves every threshold
   and is the real test of whether any of this generalises.
4. **Formula and sentence repair.** One formula awaits a human (`texts-159`,
   whose crop is clipped), and a scan on 1 September found eight more sentences
   whose inline mathematics is destroyed — see R-074. Picking these by eye finds
   instances; only the scan finds the class.

## What is blocked, and on whom

| | blocks | who |
|---|---|---|
| **Q3** signed rights records | serving anything at all | client |
| **Q1** named pilot curriculum | ingesting beyond two chapters | client |
| **Q5** does this repo build §9 | the teaching loop, and §14's citation *precision* row | client |
| **Q2** holdout seal timing | whether that gate binds | client |
| **Q6** two adjudicators | believing any number here | Mayank and Sumit, named 31 Aug |
| A working LLM key | the second-model pre-screen | anyone (all three keys 401) |
| Mathpix key | formula recovery, though Chandra covers some | client |
| GPU | curriculum-scale parsing | us |

## Running it

```
pip install -e ".[dev]"
python -m pytest -q                  # 248 pass; 7 skip without a database
docker compose -f docker/compose.yml up -d
```

Then, with `AGTS_DATABASE_URL` and `VOYAGE_API_KEY` set:

```
python scripts/decode_symbol_font.py      # once per parse; see R-054
python scripts/embed_representations.py   # once; cached by content hash
python scripts/real_content_baseline.py   # retrieval, the ruler, the gate
python scripts/holdout_validation.py      # the number that gets quoted
python scripts/citation_report.py         # §14 citation and lineage rows
python scripts/import_corpus.py           # write to Postgres and re-score from it
python scripts/triage_formula_queue.py    # what damage is actually outstanding
```

**Scripts do not need `PYTHONPATH`** — each inserts `src` itself. An older
instruction said otherwise, and on PowerShell `PYTHONPATH=src python ...` is a
parse error rather than a setting.

To try it by hand, in two terminals:

```
.\scripts\serve.ps1                                  # PowerShell; reads .env
python scripts/ask.py "what is the nature of roots"
python scripts/ask.py --subject science "what is rancidity"
python scripts/ask.py "how do I solve by completing the square"   # refuses
```

The third is the one worth watching: that phrase appears in the chapter and is
never taught there, and the gate refuses it anyway. `ask.py` prints the refusal
reason, and prints no passage when it refuses.

Every number in `EVALUATION_LEDGER.md` comes from one of those scripts. If a
claim has no script behind it, treat it as unverified.

## The repository is public

Pushed to `github.com/NapsterMayank/agts-retrieval` on 31 August, with full
history, by operator decision after the exposure was measured and a private
squashed push was recommended instead (R-053).

**What that means for you.** History carries five review sheets with roughly
twenty-five verbatim NCERT passages each — files removed from the working tree
the same day, since removal takes a file out of future commits and not out of
history. Assume anything you commit here is published. The gitignore covers the
chapter artefacts, review sheets and verification packs; check it before adding
a file that quotes the source.

**Publishing changed no approval state.** No source is `APPROVED`, every manifest
still reads `FORBIDDEN_PENDING_RIGHTS_RECORD`, and the service still refuses to
boot without an explicit override. The repository being visible is a disclosure
of working material, not an approval of content.

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
