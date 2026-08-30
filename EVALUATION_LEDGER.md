# Evaluation ledger

Every scored run, with the code that produced it. A number that cannot name its
commit is not evidence.

## Runs

Gold set `fixture-0`: 6 answerable, 3 unanswerable, 0 holdout. Corpus 40 objects
/ 40 blocks / 3 sources, synthetic. Abstain threshold 0.352, calibrated.

| Date | Commit | Retriever | recall@20 | recall@5 | abstention | violations |
|---|---|---|---:|---:|---:|---:|
| 2026-08-24 | *uncommitted* | keyword-baseline (IDF) | 100.0% | 100.0% | 100.0% | 0 |
| 2026-08-24 | *uncommitted* | broken-random-ranking | 100.0% | 16.7% | 0.0% | 0 |
| 2026-08-24 | *uncommitted* | broken-wrong-grade | 100.0% | 66.7% | 33.3% | 115 |
| 2026-08-24 | *uncommitted* | broken-answer-only | 100.0% | 0.0% | 0.0% | 149 |
| 2026-08-24 | *uncommitted* | broken-cross-tenant | 100.0% | 100.0% | 0.0% | 127 |

**These numbers mean nothing about product quality.** The corpus is forty
synthetic sentences and the queries were written against them. The only claim
being made is that the harness runs and separates a working retriever from four
broken ones.

Regenerate with `python scripts/baseline.py`.

### What this table already shows

**`recall@20` discriminated nothing.** Every retriever scored 100%, including all
four broken ones, because depth 20 over a 40-object corpus is half the corpus.
The gate is real at production scale and uninformative here — which is worth
knowing before it is quoted as evidence that something works.

**`broken-cross-tenant` scored 100% on both recall columns.** It returns another
school's private content at rank 1 and the correct answer just behind it. Recall
cannot see that, and no recall threshold ever will. Only the `cross_tenant`
counter caught it, which is why the zero-tolerance counters are separate numbers
rather than a penalty folded into a quality score.

**`broken-answer-only` is the mirror image.** It fails recall@5 outright *and*
trips 149 disclosure violations. Two independent signals for the most damaging
failure in the product is the right amount.

Together these are the argument for Q4: **pack recall and the violation counters
are what discriminate; the headline gate is the one that did not.**

## Abstention calibration

| Date | Retriever | Threshold | Margin | Answerable floor | Unanswerable ceiling |
|---|---|---:|---:|---:|---:|
| 2026-08-24 | keyword-baseline (IDF) | 0.352 | 0.267 | 0.485 | 0.218 |

Recalibrate after every material corpus expansion (§15). A threshold tuned on a
small corpus is not automatically valid at full scale.

## Parser evaluation — 25/26 August 2026

**Document:** NCERT Class 10 Science, chapter 1 *Chemical Reactions and Equations*,
16 pages, `sha256:9d58fa614b2d1064f4ef13423eaf85155b0efc5e74bdf3e8c5e6f15f1b742d36`.
Client-supplied. Registered as a **parser test artefact only** — it is not an
approved source and nothing derived from it may be published (§5, Q3 still open).

Hardware: CPU only, no accelerator. Scripts in `D:\personal\vendor\parse-spike`.

| parser | time | elements | formula | images | tiny | caption | table | PUA | empty pages |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| opendataloader, deterministic | **16.2s** | 987 | 0 | 576 | 530 | 1 | 4 | 42 | 0 |
| opendataloader, hybrid docling-fast | 888.0s | 585 | 30 | 19 | 3 | 0 | 5 | 9 | 0 |
| docling | 760.6s | 498 | 30 | **19** | **0** | **13** | 5 | **0** | 0 |
| docling + formula enrichment | 2841.5s | — | 30 **as LaTeX** | 19 | 0 | 13 | 5 | 0 | 0 |

*tiny* = image under 400 pt², i.e. a glyph fragment rather than a figure.
*PUA* = unmapped symbol-font codepoints inside extracted text.
*empty pages* = §7.1 gate, must be 0. **All four pass it.**

### Findings

**Image shatter is a deterministic-mode artefact.** 576 "images" collapse to 19
real figures under any Docling-backed mode. 366 of the 576 were on page 9 alone —
one *Electrolysis of water* diagram exploded into glyph fragments. Describing
those with a VLM would have cost 576 calls for roughly 12 real diagrams.

**Hybrid mode is dominated.** Slower than plain Docling (888s vs 761s), **zero**
captions against 13, and 9 junk codepoints against 0. Worse on every axis that
matters. Not carried forward.

**Formula enrichment produces real LaTeX and hallucinates in 23% of cases.**
It genuinely fixes structure — `H_{2}SO_{4}` subscripts are correct and
`\xrightarrow{340atm}` recovers an over-arrow reaction condition that came out as
scrambled tokens without it. But **7 of 30 formulas carry invented content**:

- `\sinh` in place of the word "Sunlight", twice, in the photosynthesis equation
- `\prod(A)` and a spurious `^{+}` appended to `ZnSO_{4}`
- `\boxed{}` around reactants, from table cell borders read as boxes
- three formulas of ~4,075 characters — tables misclassified as formulas and
  expanded into `\begin{array}` with dozens of columns
- OCR errors *inside* the LaTeX: `Magnsium`, `Oxyge`, `oide`, `a i d` for "acid"
- character spacing throughout: `M g` renders in math mode as *M·g*, two
  variables, not the element Mg

Without enrichment a bad formula looks obviously flat and a reviewer catches it.
With enrichment it is confident, well-formed LaTeX that renders beautifully and
states something false. For material shown to a Class 10 student that is a worse
failure, not a better one. It is a generative vision model writing plausible
LaTeX, not an OCR engine reading symbols.

**Cost.** 178 seconds per page with enrichment, 47s/page without, on CPU. NCERT
6-12 across subjects is several thousand pages. **A GPU is a requirement, not an
optimisation.**

### OCR costs 84% of the runtime and cannot be switched off

One option changed, same library, same document:

| config | time | text items | formulas | formula text |
|---|---:|---:|---:|---|
| `do_ocr=True` | 760.6s | 474 | 30 | plain text |
| `do_ocr=False` | **119.8s** | **381** | 30 | **all empty strings** |

6.3× faster, and it loses two things:

1. **Every formula comes back empty.** Regions are still detected; the text is
   gone. OCR was producing the formula text all along.
2. **93 text items disappear**, about 20% of the text. Docling runs with
   `force_ocr=False`, so it only OCRs where there is no text layer — meaning
   those 93 items have **no text layer at all**. This PDF carries real content
   that exists only as images, which is normal for NCERT activity boxes and
   in-figure labels.

The second is the dangerous one. That content would simply be absent from
retrieval, and **no gate would catch it**: the pages still yield blocks, so §7.1
passes, and recall would quietly sit lower than it should with nothing pointing
at why.

**Decision: OCR stays on.** 84% of the runtime for 20% of the text and all
formula content is not a trade worth taking. The runtime problem is answered with
a GPU, not with a flag.

## First real-content run — 30 August 2026

**The corpus is real for the first time.** Two chapters, parsed, composed and
scored: NCERT Class 10 Science ch1 *Chemical Reactions and Equations*
(`sha256:9d58fa61…`, 16 pages, 493 blocks) and Class 10 Mathematics ch4
*Quadratic Equations* (`sha256:9aca4b28…`, 11 pages, 235 blocks). 728 blocks, 38
learning objects, 2 sources.

Both sources are `QUARANTINED`. The run therefore carries an
`EvaluationLicence` (R-011) naming both source ids — **these numbers are a
measurement, not release evidence**, and `ScoreReport.evaluation_licence`
carries that with them.

Gold set `pilot-2-chapters-v0`: 60 cases, 50 answerable, 10 unanswerable, 0
holdout. Drafted by an agent from the chapter text, **adjudicated by nobody** —
all 10 release-critical cases are unadjudicated against §6.4's two reviewers.
Reproduce with `PYTHONPATH=src python scripts/real_content_baseline.py`.

| Date | Commit | Retriever | recall@20 | recall@5 | abstention | violations |
|---|---|---|---:|---:|---:|---:|
| 2026-08-30 | *uncommitted* | keyword-baseline (IDF) | 100.0% | 96.0% | 90.0% | 0 |
| 2026-08-30 | *uncommitted* | broken-random-ranking | 88.0% | 36.0% | 0.0% | 0 |
| 2026-08-30 | *uncommitted* | broken-wrong-grade | 98.0% | 94.0% | 70.0% | 484 |
| 2026-08-30 | *uncommitted* | broken-answer-only | 98.0% | 94.0% | 70.0% | 484 |
| 2026-08-30 | *uncommitted* | broken-cross-tenant | 98.0% | 94.0% | 70.0% | 484 |

All four broken retrievers are still detected. Three of them post *identical*
numbers, and that is not a coincidence worth glossing: **this corpus contains
none of their traps.** There is no grade-7 material, no second tenant and no
`SOLUTION`-class object in two chapters of one grade, so wrong-grade, answer-only
and cross-tenant all degrade to the same behaviour — bypass the filter — and are
caught by the same counter. The §6.5 suite keeps its discriminating power only
because the synthetic fixtures still carry those traps.

### Abstention does not separate on real content — margin **−0.497**

| Date | Retriever | Threshold | Margin | Answerable floor | Unanswerable ceiling |
|---|---|---:|---:|---:|---:|
| 2026-08-30 | keyword-baseline (IDF) | 0.685 | **−0.497** | 0.436 | **0.933** |

On synthetic fixtures the two distributions separated by 0.267. On real content
they **invert**: the best-scoring unanswerable query (0.933) outscores every
answerable one, and the worst answerable query sits at 0.436. No threshold
exists. The 90% abstention accuracy in the table above is therefore an artefact
of where the midpoint happened to land, not a working behaviour.

The cause is not the scorer. It is **object granularity**: composition produces
one object per *chapter section*, so 728 blocks became 38 objects, some of them
thousands of characters long. An object that large contains a plausible lexical
match for almost any in-subject query, including one the chapter cannot answer.
"What is the pH of lemon juice?" matches a section discussing acids at 0.93.

Two consequences, both concrete:

1. **`recall@20` measured nothing again**, for a new reason. Twenty candidates
   out of thirty-eight objects is over half the corpus. It was uninformative at
   40 synthetic objects and it is uninformative at 38 real ones. `recall@pack5`
   is the number carrying signal here — 96% against random ranking's 36%.
2. **A retrieval unit is not a section.** §7.3's search representations are not
   an optimisation to schedule later; without them the abstention gate §14
   requires cannot be built at all, and this run is the evidence.

### What this run proved that the fixture runs could not

- The parse → composition → corpus → scorer path works end to end on real
  content, with zero broken gold labels and zero gold blocks stranded outside
  every learning object.
- Three defects in the parsing layer that fixtures had passed over: colliding
  block ids, Docling tables extracting as empty, and a dual-parse diff flagging
  every page for a property of the strategy. See R-012, R-013, R-014.
- The abstention design that looked calibrated at Hour 8 does not survive
  contact with a real chapter.

## Search representations — 30 August 2026

R-015 said a learning object is not a retrieval unit. §7.3 windows now exist:
38 objects become **77 representations**, block-aligned, deterministic, no
embedding involved. Same corpus, same gold set, same IDF scoring function — the
*only* variable is what gets ranked.

| retriever | unit | recall@20 | recall@pack5 | abstain | blocks/pack | violations |
|---|---|---:|---:|---:|---:|---:|
| keyword-baseline | object | 100.0% | 96.0% | 90.0% | **143** | 0 |
| representation-keyword | window | 90.0% | 86.0% | 80.0% | **43** | 0 |
| broken-random-ranking | object | 84.0% | 46.0% | 0.0% | 96 | 0 |
| broken-wrong-grade | object | 98.0% | 94.0% | 70.0% | 147 | 484 |
| broken-answer-only | object | 98.0% | 94.0% | 70.0% | 147 | 484 |
| broken-cross-tenant | object | 98.0% | 94.0% | 70.0% | 147 | 484 |

### Recall went *down*, and that is the finding

Read alone, 96% → 86% says the change made things worse. The new column says
otherwise: **the object-level pack hands the teaching loop 143 blocks** — most
of a chapter — to answer one question. It scores a recall hit by returning
nearly everything. The window pack answers with 43 and gets 86%.

Gold-block coverage, measured directly, says the same: object-level packs
contain 94% of the gold blocks for a case, windows 73%, at a third of the
volume. Neither number is good enough to ship; the honest comparison is that
recall alone cannot rank two retrieval units, which is why `blocks_per_pack` is
now reported beside it and never folded into it (R-018).

### Abstention: better, still broken

| Date | Retriever | Threshold | Margin | Answerable floor | Unanswerable ceiling |
|---|---|---:|---:|---:|---:|
| 2026-08-30 | keyword-baseline (object) | 0.685 | −0.497 | 0.436 | 0.933 |
| 2026-08-30 | representation-keyword (window) | 0.472 | **−0.321** | 0.312 | 0.633 |

The unanswerable ceiling fell from 0.933 to 0.633 — smaller units genuinely stop
a whole section matching any query in its subject. But the distributions still
overlap, so **there is still no threshold**, and the 80% abstention figure is
still an artefact of where the midpoint landed.

**Chunking was necessary and is not sufficient.** What remains is the scoring
function: IDF token overlap normalised by query mass gives "State Ohm's law and
give its mathematical form" credit for matching *law*, *form* and *give* against
a chemistry chapter. That is a lexical-matching artefact, and it is the case for
the embedding and reranking stages — now with a number to beat rather than an
assumption that they help.

### Note on the §6.5 comparison

`representation-keyword` reads as "NOT DETECTED" against
`is_materially_worse_than`, which is correct — it is not a broken retriever. It
is a different unit trading recall for precision, and that check exists to catch
sabotage, not to rank honest alternatives.

## BM25, and why abstention is not a scoring problem — 30 August 2026

Same corpus, same gold set, same unit as the previous run. Only the scoring
function changed: IDF token overlap becomes BM25 with term saturation
(`k1=1.2`) and length normalisation (`b=0.75`), divided by the query's own
attainable ceiling so scores land in 0..1 and compare across queries.

| retriever | unit | recall@20 | recall@pack5 | abstain | blocks/pack |
|---|---|---:|---:|---:|---:|
| keyword-baseline | object | 100.0% | 96.0% | 90.0% | 143 |
| representation-keyword | window | 90.0% | 86.0% | 80.0% | 43 |
| **representation-bm25** | window | 94.0% | **94.0%** | 90.0% | **40** |

**BM25 recovers almost all of the recall the smaller unit cost, on a quarter of
the evidence.** 94% pack recall against the object baseline's 96%, with 40
blocks per pack against 143. Free, model-free, and it is now the number an
embedding has to beat.

### Abstention margin, three runs

| unit | scorer | margin | answerable floor | unanswerable ceiling |
|---|---|---:|---:|---:|
| object | IDF overlap | −0.497 | 0.436 | 0.933 |
| window | IDF overlap | −0.321 | 0.312 | 0.633 |
| window | BM25 | **−0.219** | 0.183 | 0.402 |

Each fix roughly halves the overlap and none crosses zero. That pattern is worth
reading properly rather than extrapolating: it does not mean a third improvement
lands it.

### Which cases actually overlap

Ten answerable cases sit below the highest-scoring unanswerable one. The
unanswerable cases at the top of the band are **the four that were designed to be
adjacent**:

| score | case | why it scores |
|---:|---|---|
| 0.402 | *How do you solve a quadratic equation by completing the square?* | the phrase appears in ch4, attributed to Sridharacharya; the method is never taught |
| 0.267 | *State the Pythagoras theorem and prove it* | invoked by name in Example 8, never stated |
| 0.248 | *What is the distance formula between two points?* | "distance" saturates the pole-and-gates problem |
| 0.205 | *State Ohm's law and give its mathematical form* | *law*, *form*, *state* are all cheap matches |

And the answerable cases at the bottom are ones whose evidence does not repeat
the query's words: the atom-count question whose answer is a **table** (0.183),
"why is the negative root rejected" (0.250), rancidity (0.265).

**This is not a scoring-function problem any more.** No lexical scorer
distinguishes a concept that is *mentioned* from one that is *taught* — the
tokens are identical, and BM25 correctly reports a strong lexical match. The
distinction is semantic and structural, which means:

1. **A sufficiency gate (§8.4) is the real answer**, not a better matcher. The
   question "does this evidence actually answer the query" is the one §14 gates,
   and it was always a separate stage — this run is the evidence that it cannot
   be approximated by a retrieval score.
2. **Embeddings should be measured against BM25 on the bottom of the answerable
   band** — the table case, the paraphrased ones — because that is where they
   plausibly help. Expecting them to fix the adjacent-unanswerable cases is
   expecting the wrong thing from them.

## Embeddings, hybrid, and a working sufficiency gate — 30 August 2026

Same corpus, same 60 cases, same windows. Voyage `voyage-3` embeddings over the
77 representations, cached on disk by text hash so a scored run reaches no
network and costs nothing to repeat.

| retriever | recall@20 | recall@pack5 | blocks/pack | abstention margin |
|---|---:|---:|---:|---:|
| keyword-baseline (object) | 100.0% | 96.0% | 143 | −0.497 |
| representation-keyword | 90.0% | 86.0% | 43 | −0.321 |
| representation-bm25 | 94.0% | 94.0% | 40 | −0.219 |
| **representation-dense** | 94.0% | 94.0% | 40 | **−0.077** |
| representation-hybrid (RRF) | 94.0% | 94.0% | 40 | −0.024 |

**Dense matches BM25 on recall and is far better separated.** It does not beat
BM25 on retrieval quality here, which is worth stating plainly — on 60 cases over
two chapters, a paid embedding buys separation, not recall.

**Hybrid's margin is the best number in the table and the most misleading.** RRF
scores compress into 0.976–1.000 because rank fusion has no notion of match
quality, so the "margin" is arithmetic, not confidence. Hybrid is usable for
ranking and must never be used for the abstention decision. Its abstention
accuracy of 50% against dense's 90% is that fact showing up.

### The gate (§8.4)

Two tiers, because a single threshold provably cannot work here:

- below a **calibrated floor** (0.725, measured, not chosen) — abstain;
- above a **ceiling** (0.826, the median top score over answerable cases) —
  answer;
- between them — require that the two retrievers **share 2 of their top 3
  objects**.

Corroboration is the part that catches a mention. A chapter that *teaches* a
concept elaborates it, so lexical and semantic retrieval land on the same
section. A chapter that merely *names* one sends them apart: BM25 finds the lone
sentence containing the phrase, the embedding drifts to whatever section is
genuinely about something similar.

| | result |
|---|---|
| unanswerable correctly abstained | **10 / 10** |
| answerable correctly answered | **44 / 50** |

**The three cases that started this** — completing the square (0.763), the
Pythagoras theorem, the distance formula — are all now correctly refused, and
refused with a reason a human can read.

### The six failures, and they are not all the same kind

Three are **below the floor**: the prayer-hall dimensions (0.687), the repeated
factor (0.710), the rejected negative root (0.716).

> **Correction, 30 August.** This entry originally attributed all three to
> mangled formula text and named Mathpix as the fix. That was wrong, and reading
> the actual gold blocks disproved it: for two of the three the evidence is clean
> prose - *"Thus, the breadth of the hall is 12 m. Its length = 2x + 1 = 25 m."*
> The real cause was a **window boundary**: "Example 6 : Find the dimensions of
> the prayer hall" ended one window and its answer began the next, which never
> repeats the phrase. Retrieval ranked the right window first and scored it below
> the floor for want of two words. Fixed by rule 5 in the chunker (R-022), not by
> an OCR engine.

Three are **corroboration failures on definitional queries** — "What is a
balanced chemical equation?", "…decomposition reaction?", "…displacement
reaction?". Both retrievers found good evidence and ranked *different* correct
sections, because a definition appears in the section, in the summary, and in the
exercises. Same-object agreement is the wrong test when a concept legitimately
lives in three places; agreement at concept level rather than object level is the
obvious next refinement.

### What these numbers are not

**The floor and the ceiling are fitted to the visible set.** There is no holdout
(Q2), the set is 60 cases and not the 300-500 §6.4 requires, and nobody has
adjudicated any of it. A gate calibrated on the same cases it is scored against
is an upper bound on its own performance. It is honest as a mechanism and
unvalidated as a number, and the first thing the real gold set must do is
re-derive both constants and re-run this table.

## Carry-in context, anchored corroboration, and a holdout - 30 August 2026

Three changes, each measured before and after, and one hypothesis rejected.

### Rule 5: a window carries the previous window's statement line

**The first attempt carried the previous block unconditionally, and it was
worse.** Every window became findable by its neighbour's words, so the retriever
returned continuations for queries whose evidence was in the block before:

| variant | dense recall@pack | bm25 recall@pack | gate (visible) |
|---|---:|---:|---:|
| no carry-in | 94% | 94% | 44/50 |
| carry previous block always | **90%** | **84%** | 46/50 |
| carry only *statement* openers | 94% | 92% | **45/50** |

Narrowed to blocks opening with Example / Activity / Problem / Question - the
worked-example statements a continuation window is the continuation *of* - it
keeps the recall and takes the gate improvement.

### Anchored corroboration

The three definitional false abstains looked identical to a mention under the old
rule: "What is a decomposition reaction?" has the *definition section* ranked
first by dense and the *exercises* ranked first by BM25, sharing only the summary
- one shared object, the same count as "completing the square".

What differs is **what** they share and what sits at rank 1. Five rules were
measured on the visible set:

| rule | unanswerable refused | answerable answered |
|---|---:|---:|
| top3 overlap >= 2 | **10/10** | 45/50 |
| primary #1 in corroborator top 5 | 9/10 | 48/50 |
| top5 overlap >= 2 | 9/10 | 48/50 |
| top3 overlap >= 1 | 9/10 | 48/50 |
| **overlap >= 2, OR overlap >= 1 anchored on a definition** | **10/10** | **48/50** |

Every loosening that reached 48/50 by relaxing depth also let one unanswerable
through. Anchoring gets both, because it asks a different question: is the
agreement resting on a section the *curriculum* classifies as teaching this
concept (R-009's hand-written section map), rather than on prose that names it.
"Completing the square" has no definition section to anchor on - both retrievers
land on the introduction - so it still abstains.

### The holdout

38 cases written **after** the floor, ceiling and corroboration rule were fixed,
and not consulted while choosing any of them. Constants derived from the visible
60 only.

| | unanswerable refused | answerable answered |
|---|---:|---:|
| visible 60 (tuned on - upper bound) | 10/10 | 48/50 - 96% |
| **holdout 38 (never consulted)** | **8/8** | **27/30 - 90%** |

**Refusal generalises perfectly; acceptance loses six points.** That gap is the
cost of fitting two constants to sixty cases, and it is the number to quote - not
the 96%.

The three holdout misses are the two kinds already known: one below the floor by
0.002 (`h-chem-06`, 0.735 against 0.737, which says the floor is brittle rather
than wrong) and two corroboration failures. **No unanswerable case was answered
in either set.**

**Still true:** 98 cases against the 300-500 of section 6.4, agent-drafted, and
adjudicated by nobody. This validates the mechanism, not the curriculum judgement.

## Citation gates, first measurement - 30 August 2026

Evidence packs are now assembled per case (§8.3) and the §14 citation rows are
scored. Two of the three rows can be measured before a generation stage exists;
the third is not claimed.

| §14 row | bar | visible 60 | holdout 38 |
|---|---:|---:|---:|
| Citation ID resolution | 100% | **100%** | **100%** |
| Citation completeness | >=95% | **97.2%** | **96.3%** |
| Citation precision | >=98% | not measurable yet | not measurable yet |
| *(proxy)* evidence precision | - | 3.4% | 2.4% |

**Citation precision is not measured and is not claimed.** It asks whether a
citation supports the sentence it is attached to, and there are no sentences: the
teaching loop is Phase 3, scope-blocked on Q5. The proxy reported instead is the
fraction of cited blocks that are gold, under its own name, because calling a
proxy by the gate's name is how an unmet gate gets marked green.

### Completeness failed first, at 77%, and the cause was structural

The first run scored 77.1% against the 95% bar. Locating the misses rather than
tuning: **31 of 31 missing gold blocks sat in a sibling window of a section the
pack had already selected.** Retrieval had found the right section every single
time; the one-window-per-object rule that keeps five slots holding five distinct
sections had dropped the rest of each one.

Four expansion strategies were measured:

| strategy | completeness | evidence precision | blocks/pack |
|---|---:|---:|---:|
| best window per object (before) | 77.3% | 3.7% | 40 |
| plus immediate neighbour windows | 93.3% | 2.1% | 80 |
| **plus siblings that clear the floor** | **96.9%** | 3.0% | 73 |
| plus every window of the object | 100.0% | 1.5% | 126 |

Taking whole objects passes completeness by returning most of a chapter again -
the failure R-015 was written about. Taking siblings that independently clear the
same floor the section cleared passes the gate at 73 blocks a pack.

**The evidence-precision proxy at 2-3% is not reassuring and is not meant to
be.** A pack of 73 blocks carrying 2 gold ones is mostly context. That number is
the argument for reranking and for per-sentence citation at generation time, and
it is recorded here so the completeness pass is not read as citations being
solved.

## Reranking earns nothing at this scale - 30 August 2026

Voyage `rerank-2` over the retriever's top 20, judged on pack recall because
that is the failure Q4 describes: twenty correct candidates with the gold span
ordered into position nine of a five-slot pack.

| retriever | recall@20 | pack (visible) | pack (holdout) | blocks/pack |
|---|---:|---:|---:|---:|
| dense (control) | 94.0% | 94.0% | 76.7% | 39.6 |
| dense + identity rerank | 94.0% | 94.0% | 76.7% | 39.6 |
| dense + rerank-2 | 94.0% | 94.0% | 76.7% | 37.5 |
| bm25 (control) | 92.0% | 92.0% | **83.3%** | 39.2 |
| bm25 + rerank-2 | 92.0% | 92.0% | 83.3% | 39.4 |
| hybrid (control) | 94.0% | 94.0% | 76.7% | 39.8 |
| hybrid + rerank-2 | 94.0% | 94.0% | 38.2 blocks | 76.7% |

**Not one pairing moved pack recall by a single case.** The reason is visible in
the first column: `recall@20` and `recall@pack` are identical for every
retriever, which means the gold object is already inside the top five whenever it
is retrieved at all. There is nothing for a reranker to reorder. With 38 objects
and one candidate per object, the candidate list is usually shorter than the
pack.

**Decision: the adapter ships, the stage does not** (R-027). It is wired,
cached, tested and switched off, and the benchmark is the thing to re-run when
the corpus is a curriculum rather than two chapters.

An identity reranker was run alongside as the control, because "we added a
reranker and the number went up" is not evidence unless the same harness ran
without one. Here nothing went up, which is a cleaner answer.

### The holdout column disagrees with the visible column

BM25 beats dense on unseen cases - 83.3% against 76.7% pack recall - while
losing on the cases the thresholds were fitted to. That inversion is worth more
than the rerank result, so the obvious question was asked directly: should the
sufficiency gate use BM25 as its primary retriever?

| gate primary | visible refuse | visible answer | holdout refuse | holdout answer |
|---|---:|---:|---:|---:|
| **dense (current)** | 10/10 | 48/50 | **8/8** | **27/30** |
| bm25 | 10/10 | 45/50 | 6/8 | 26/30 |

**No.** Dense keeps the gate accurate on unseen cases where BM25 lets two
unanswerable questions through. Better pack recall did not translate into a
better gate, which is a reminder that a retriever is chosen for the decision it
supports and not for its headline number.

## Persistence, verified against a real server - 30 August 2026

The corpus now lives in Postgres, in its own container (`docker/compose.yml`,
port 5434, pgvector image) rather than in Foxxy's development database or the
machine's native server. An integration test that migrates or truncates someone
else's database is a bad afternoon.

| | value |
|---|---|
| written | 2 sources, 728 blocks, 38 objects, 77 representations |
| read back | identical ids, identical block order, 77/77 vectors |
| bm25 pack recall, files vs database | 92.0% vs 92.0% |
| dense pack recall, files vs database | 94.0% vs 94.0% |

Writing rows only proves the schema accepts them. The check that matters is the
second half: load the corpus back out and re-run the ruler over it. A
persistence layer that stores everything and retrieves differently surfaces as a
quality regression with no obvious cause, months later.

### Two defects the real server caught that a mock would not

**The pgvector width pin is real.** `002_pgvector` pins the column to
`vector(1024)`. The fixtures used a convenient three-element vector, which
passes on the core schema and fails the moment the migration is applied:
`expected 1024 dimensions, not 3`. That is the constraint doing its job - a
different provider's embeddings cannot be stored by accident - and there is now
a test asserting it, skipped on the core schema where float8[] accepts any
width.

**A pgvector column reads back as a string.** Without the pgvector adapter
registered, psycopg2 returns `"[0.1,0.2,...]"`, and handing that to a contract
expecting numbers produces two thousand validation errors about individual
characters. Parsed explicitly in the repository rather than by adding a
dependency for one column.

Both are exactly the class of defect R-010 records: a fixture that encodes an
assumption about a system instead of that system's actual behaviour. The test
suite was green against SQLite-shaped expectations and wrong.

## Holdout

**Not yet sealed.** `fixture-0` has no holdout cases, because a holdout drawn
from synthetic fixtures would prove nothing. Sealing happens when the real gold
set exists — see Q1 and Q2.

`score()` refuses to touch holdout cases unless `include_holdout=True` is passed
explicitly, so a tuning run cannot contaminate the seal by accident.
