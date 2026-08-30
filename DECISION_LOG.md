# Decision log

Authority 4 (build guide §2): why a decision was made, and proof it passed.

---

### R-001 · The client AI-native build guide is the build order
**Status:** Active · 24 August 2026

The client supplied *Alfanumrik Grounded Teaching RAG — AI-Native Build Guide*
(revised 22 August 2026), replacing the 17-19 week plan Track B was written
against.

**Decision:** adopt it as authority 2. The prior spec and build guide in the
Foxxy repository drop to authority 3 — implementation detail, consulted where the
client guide is silent.

**Consequence:** the quality bars did not move. §14's gates are the same numbers
the earlier spec carried. What changed is the execution model and the clock, not
the standard.

---

### R-002 · Contracts are frozen pydantic models with invariants as validators
**Status:** Active

Every gate in `docs/01-acceptance-gates.md` that can be expressed as a
construction rule is expressed as one.

**Decision:** `extra="forbid"`, `frozen=True`, and a `model_validator` for each
invariant. An `APPROVED` source without a rights record does not construct; a
`SUFFICIENT` pack whose sufficiency gate failed does not construct; a
`VerificationResult` reporting `pass` with a failing check does not construct.

**Consequence:** violations surface at the boundary that produced them rather
than in an evaluation report three stages later. It also means widening a
contract is a visible diff, which is the point.

---

### R-003 · Authorisation is a corpus method, not a retriever convention
**Status:** Active

Rule 5 says filter before ranking. A convention would be followed until someone
was in a hurry.

**Decision:** `Corpus.authorised(plan)` is the only sanctioned candidate source.
`Corpus.unfiltered()` exists so the broken retrievers can bypass it and be
caught.

**Consequence:** "did this retriever filter before ranking" becomes a countable
fact — `unauthorised_returned` — rather than a code-review opinion.

---

### R-004 · Gold labels anchor to source block ids
**Status:** Active

Rule 4. `EvalCase.gold_block_ids`, matched against the union of block ids behind
the returned objects.

**Consequence:** re-composing learning objects, changing chunk sizes or swapping
an embedding model leaves the answer key valid. Anchored to object ids instead,
every chunking experiment would cost a full re-label, so the experiments stop
being run.

---

### R-005 · The abstention threshold is calibrated, never hand-picked
**Status:** Active · **arose from a failing test, 24 August 2026**

The first scorer used a hand-picked threshold of 0.05 and reported 33% abstention
accuracy on a baseline that was retrieving perfectly. The threshold was not
mis-tuned; the underlying score was not a confidence signal. A raw token-overlap
count gives an out-of-corpus query a third of a perfect score for matching "of"
and "the".

**Decision:** two changes. The baseline retriever weights overlap by IDF, so a
stopword match is worth almost nothing. And `calibrate_abstention()` derives the
threshold from the measured separation between answerable and unanswerable top
scores, reporting the margin alongside it.

**Evidence:** separation 0.267 (answerable floor 0.485, unanswerable ceiling
0.218) on the fixture set. Calibrated threshold gives 100% abstention accuracy;
the provisional 0.05 gives 33%, and a test asserts that it does — the finding is
pinned, not quietly fixed.

**Consequence:** a threshold quoted without its margin is a guess wearing a
decimal point. §15 requires recalibration after every material corpus expansion,
and `PROVISIONAL_ABSTAIN_THRESHOLD` is named to make an uncalibrated run obvious.

---

### R-006 · The fixture corpus contains four deliberate traps
**Status:** Active

§6.5 requires that broken retrievers score materially worse. A corpus with
nothing to leak cannot demonstrate that.

**Decision:** the synthetic corpus carries grade-7 near-duplicates, protected
solution objects, another tenant's private note, and a quarantined source — one
per broken retriever. Twenty authorised filler objects sit alongside them so the
candidate pool is far larger than `k_pack`; without that, a random ranker scores
well by luck and the detection test passes for the wrong reason.

**Consequence:** all four broken retrievers are caught, each by a different
signal. `AnswerOnly` is the instructive one — it can rank gold correctly and is
still a release blocker, so recall alone would have passed it.

---

### R-007 · Recall depth is reported with the corpus size beside it
**Status:** Active · **arose from the first baseline run, 24 August 2026**

The first run scored `recall@20 = 100%` for the baseline **and for all four
broken retrievers**. Depth 20 over a 40-object corpus is half the corpus, so the
metric could not fail. §14's headline gate discriminated nothing.

Worse, `broken-cross-tenant` scored 100% on both recall columns while returning
another school's private content at rank 1 — the correct answer sat just behind
it. No recall threshold at any depth can see that failure.

**Decision:** `recall@k` is never reported without the authorised candidate pool
size, and the zero-tolerance counters stay separate numbers rather than being
folded into a quality score. A test asserts the pool is materially larger than
`k_pack` before the detection suite is believed.

**Consequence:** this is the evidence behind Q4. The two measurements that
actually separated good from broken were pack recall and the violation counters;
the gate the client's §14 leads with was the one that told us nothing. Adding
pack recall to §14 costs one line and closes the gap.

---

### R-008 · Docling parses, OpenDataLoader corroborates, and formula enrichment stays off
**Status:** Active · 26 August 2026 · measurements in `EVALUATION_LEDGER.md`

§7.2 requires at least two parse strategies on representative pages. Four
configurations were run over NCERT Class 10 Science chapter 1.

**Decision:**

| Role | Choice |
|---|---|
| Primary parse | **Docling** — only configuration clean on captions (13), figures (19) and junk codepoints (0) |
| Second strategy (§7.2) | **opendataloader-pdf, deterministic mode** — 16 seconds, strong headings and lists, an independent view for provenance diffing at negligible cost |
| Formula regions | **Mathpix**, pending test — purpose-built OCR rather than a generative model |
| opendataloader hybrid mode | **rejected** — dominated by plain Docling on speed, captions and character cleanliness |
| Docling formula enrichment | **off** — see below |

**Why enrichment is off despite producing correct LaTeX.** It converted 30/30
formulas to LaTeX and correctly recovered `\xrightarrow{340atm}`, which no other
configuration managed. It also invented content in 7 of 30: `\sinh` for the word
"Sunlight" in the photosynthesis equation, a fabricated `\prod(A)`, `\boxed{}`
from table borders, and three tables misread as formulas and expanded into
4,000-character arrays.

Flat text fails visibly and a reviewer catches it. Hallucinated LaTeX renders
beautifully and is wrong. Given the output reaches Class 10 students, the second
failure mode is worse than the first, and 23% is not a rate that human review at
corpus scale absorbs.

**Consequence, and a rule this earns:** a formula object stores its **image crop
and raw extracted text alongside any LaTeX, never LaTeX alone.** A wrong
conversion then stays detectable and re-convertible without re-parsing — which is
the reason blocks exist as a separate table (R-004). Also: CPU parsing costs
47s/page without enrichment and 178s/page with it, so **a GPU is an
infrastructure requirement**, recorded in `DEPENDENCY_MAP.md`.

**Still open:** the decisive test is a Mathematics chapter. Chemical equations
degrade into recoverable text; fractions, roots, integrals and matrices do not.
Blocked on Q1.

---

### R-009 · Block types are layout, object types are pedagogy, and they are separate enums
**Status:** Active · 26 August 2026

`SourceBlock.block_type` originally reused `ObjectType`. Writing the first parser
adapter made the error obvious: a parser reports a heading, a table cell or a
page footer, and none of those are teaching types. `ObjectType` has no member for
any of them.

**Decision:** `BlockType` is its own enum — layout vocabulary only. `ObjectType`
stays pedagogical. A block also keeps `raw_label`, the parser's own string, so an
unrecognised type becomes `UNKNOWN` **and stays diagnosable** rather than being
guessed into the nearest neighbour.

**Consequence:** the parse stage can no longer express a curriculum judgement,
which is correct — nothing at that stage is qualified to make one. Curriculum
identity is assigned later, by S5, with human review.

Two fields were added at the same time, both earning their place from real
parser output:

- `linked_block_id` — opendataloader emits `linked content id` on captions,
  pairing a caption to its figure or table. Our composition rule forbids
  splitting that pair, and reconstructing it later from page proximity is
  guesswork the parser already did properly.
- `raw_label` — as above.

---

### R-010 · Adapters are validated against real parser output, not only fixtures
**Status:** Active · 26 August 2026 · **arose from a bug a passing test suite missed**

The opendataloader adapter passed its unit tests and then rendered **every table
in the real NCERT chapter as an empty grid** — `|  |  |` for all four.

Cause: the hand-written fixture put cell text in the cell's `content` field. Real
cells have **no `content`**; their text sits in nested `kids`. The fixture
encoded an assumption about the parser rather than the parser's actual output, so
the test confirmed the assumption instead of the behaviour.

**Decision:** every parser adapter is exercised against a stored sample of real
output before it is trusted, and fixtures are derived from real output rather
than written from memory. The regression test now uses the real nested shape.

**Consequence:** this failure mode is quiet by construction. An empty table
renders as a table with no data — it does not raise, does not fail the §7.1 page
gate, and would have reached the corpus as four tables of nothing. The same class
of defect is what the §7.2 dual-parse diff exists to surface at scale.

---

### R-011 · Quarantined content may be *measured* under a named licence, never served
**Status:** Active · 30 August 2026

§5 forbids retrieval from an unapproved source, and `Corpus.authorised` enforces
it. Taken literally it also means the ruler can only ever run over synthetic
fixtures until rights records arrive (Q3) — and a scorer proven on forty invented
sentences has proven very little. The first real run is exactly where a parse or
composition defect becomes visible.

**Decision:** `EvaluationLicence` permits objects from **explicitly named**
quarantined sources into the candidate set of an evaluation run. It is not a
production path:

- sources are named individually, there is no wildcard, and construction fails
  without a reason and a grantor;
- only `QUARANTINED` is unlocked. `RETIRED` and `WITHDRAWN` stay excluded —
  withdrawal is the mechanism a rights holder has, and an evaluation run is not
  a reason to ignore it;
- every other filter still applies: tenant, grade, subject, disclosure;
- `ScoreReport.evaluation_licence` travels with the number, so a licensed run
  cannot be quoted later as release evidence by accident.

The scorer's `unapproved_source` counter also consults the licence. Without
that, every object of every real-content run trips it and a zero-tolerance
counter becomes background noise — which is worse than not having it.

**Consequence:** the first real numbers exist (`EVALUATION_LEDGER.md`,
30 August), and they immediately falsified the abstention calibration.

---

### R-012 · Block ids carry their parser collection, because gold labels anchor on them
**Status:** Active · 30 August 2026 · **found by real content, not by a test**

Block ids were built from the last path segment of Docling's `self_ref`, so
`#/texts/0` and `#/tables/0` both produced `…:docling:0`. Docling numbers each
collection independently, so this collides by construction: **19 duplicate ids in
the science chapter, 4 in the maths chapter.**

Rule 4 makes a block id the anchor for every gold label and every citation. Two
blocks sharing one id means a citation resolves to either of them, and a corpus
keyed by id silently keeps whichever loaded last. It raises nothing, fails no
gate, and would have shown up as unexplained recall loss.

**Decision:** the id is `{document}:docling:{collection}-{index}` —
`texts-7`, `tables-0`, `pictures-3`.

**Consequence:** both chapters' artefacts were regenerated. Cheap now; after a
gold set is sealed against the old ids, it would not have been.

---

### R-013 · A Docling table's content is in `data.table_cells`, and is rendered as markdown
**Status:** Active · 30 August 2026 · **same defect class as R-010, one parser over**

The adapter read `orig`/`text` for every item. A Docling table has neither: its
content is in `data.table_cells`, each cell carrying its own row and column
offsets. The first real chapter with tables in it failed validation — five tables
that carried nothing at all.

R-010 said adapters are validated against real parser output rather than
fixtures. That rule had been applied to opendataloader-pdf and not to Docling.

**Decision:** tables render to markdown (§7.4 — structure preserved, not
flattened into prose), and a block with neither text nor image is skipped with a
warning instead of raising. The regression test uses the real nested shape.

---

### R-014 · A property of a parse strategy is reported once, not flagged on every page
**Status:** Active · 30 August 2026

The dual-parse diff flagged 11 of 16 science pages and 10 of 11 maths pages, and
every single flag read "only docling found formulas". Neither second strategy
labels formulas at all — opendataloader-pdf in deterministic mode found zero in
the bake-off, and Chandra emits none. So the rule fired on every page carrying an
equation and buried the pages that genuinely disagree.

**Decision:** formula presence is compared per page only when *both* strategies
label formulas somewhere in the document. Otherwise it becomes one
document-level note on the report.

**Consequence:** both chapters now flag **0 pages**, and that is a real result —
the text volumes agree page by page. A diff that flags everything says nothing,
and is worse than no diff because it looks like diligence.

---

### R-015 · A learning object is not a retrieval unit
**Status:** Active · 30 August 2026 · **this is the next build step, and it is now evidenced**

Composition produces one object per chapter section. On real content that is 728
blocks collapsed into 38 objects, several of them thousands of characters. The
consequences showed up on the first scored run:

- **Abstention stopped separating.** Answerable and unanswerable score
  distributions inverted — margin **−0.497**, where synthetic fixtures gave
  +0.267. An object that large contains a plausible lexical match for almost any
  in-subject query, so "What is the pH of lemon juice?" scores 0.93 against a
  chapter that never mentions pH. No threshold exists, and §14's abstention gate
  cannot be built on top of this.
- **`recall@20` measured nothing**, again. Twenty candidates out of thirty-eight
  objects is over half the corpus.

**Decision:** section-level objects stay as the *composition* unit — they are the
pedagogical object §6.2 describes and they carry the citation lineage. Retrieval
gets its own unit: §7.3 search representations, derived from blocks, with the
object as the parent for citation. That work is now the next step rather than a
later phase.

**What this does not mean.** The scorer is not at fault and neither is the
keyword baseline — 96% pack recall against random ranking's 36% is a working
retriever over a corpus shaped wrongly. Swapping in embeddings before fixing the
unit would have moved the number without touching the cause.

---

### R-016 · A search representation may exist before it is embedded
**Status:** Active · 30 August 2026

`SearchRepresentation` required `vector`, `embedding_model` and
`embedding_version`. That folds chunking and embedding into one step, and §7.3
asks for provider independence — which is only real if a representation can be
re-embedded by a different provider **without being re-chunked**.

**Decision:** the three embedding fields are optional and validated in pairs (a
vector without its model, or a model without a vector, is unreproducible and
raises). `representation_version` names the chunking function, so two chunkings
can coexist in one store and be compared on the same gold set. Rechunking bumps
it; re-embedding does not.

**Consequence:** the lexical run needs no fake vectors, and "which provider" is
a decision recorded per representation rather than baked into the schema.

---

### R-017 · Windows are block-aligned, and four things are never separated
**Status:** Active · 30 August 2026

The §7.3 chunker, deterministic and model-free:

1. **A block is never split** — it is the anchor for every citation (rule 4),
   and a window ending mid-block cannot cite the half it used.
2. **A caption travels with its figure or table** — `linked_block_id` is a
   pairing the parser already resolved; rebuilding it from page proximity later
   is guesswork.
3. **A formula is never alone in a window.** Formula text is degraded by
   construction (R-008): the maths chapter yields `a  0` for *a ≠ 0*. A window
   of nothing but formulas is unsearchable; attached to the prose that
   introduces it, it is reachable and still individually citable.
4. **The heading path prefixes every window** — the one piece of context a small
   window loses, and what makes a paragraph findable by a section name it never
   repeats.

Authorisation resolves through the **parent object**, never through a field
copied onto the child: a duplicated disclosure class is a second answer to "may
this be shown", and the two drift the first time an object is retired.

**Consequence:** 728 blocks → 38 objects → 77 windows. Abstention margin
improved from −0.497 to −0.321 and is still not separable; evidence volume per
pack fell from 143 blocks to 43. Chunking was necessary and is not sufficient —
the scoring function is next.

---

### R-018 · Evidence volume is reported beside recall, never folded into it
**Status:** Active · 30 August 2026

Comparing the two units exposed a hole in the ruler. Object-level retrieval
scores 96% pack recall by handing over **143 blocks per pack**; window-level
scores 86% with 43. On recall alone the first looks better, and it is not — it is
a larger claim, and the teaching loop receiving most of a chapter as "evidence"
is the failure §14's citation-precision gate exists to catch, arriving early.

**Decision:** `CaseResult.blocks_at_pack` and `ScoreReport.blocks_per_pack`.
Reported, never blended into a quality score — the same reason the
zero-tolerance counters are separate numbers.

**Consequence:** a recall improvement bought by returning more material is now
visible as one. This is the same argument as Q4 (pack recall) one level down,
and worth putting to the client alongside it.

---

### R-019 · BM25 is the lexical floor, and abstention is not a scoring problem
**Status:** Active · 30 August 2026

BM25 over representations, normalised by the query's attainable ceiling so
scores are comparable across queries. It recovers pack recall from 86% to 94%
against the object baseline's 96%, on 40 blocks per pack against 143.

**Decision:** BM25 replaces IDF overlap as the lexical floor. Every later
component — embeddings, hybrid fusion, reranking — is measured against it, and
one that cannot beat it has not earned its cost or its dependency.

**And the more important finding.** Three successive improvements moved the
abstention margin −0.497 → −0.321 → −0.219 without crossing zero, and the
diagnostic says why: the unanswerable cases that score highest are the ones the
chapters *mention without teaching* — completing the square, Pythagoras,
distance. A lexical scorer is correct to report a strong match there. The
distinction between mentioned and taught is not in the tokens.

**Consequence:** the abstention gate is built at §8.4 as a **sufficiency**
decision over the retrieved pack, not as a threshold on a retrieval score.
Chasing it with a better matcher would have kept producing improvements that
never arrive at a working gate — which is exactly what the last three runs look
like if the margin is read as a trend instead of a diagnosis.

---

### R-020 · Abstention is a two-tier gate with corroboration, not a threshold
**Status:** Active · 30 August 2026 · **the answer to the problem R-019 diagnosed**

Below a calibrated floor, abstain. Above a ceiling defined as the median top
score over answerable cases, answer. Between them, require that two independent
retrievers — BM25 and dense — share two of their top three objects.

**Why corroboration works where a score does not.** Teaching elaborates: a taught
concept is discussed across several windows of one section, so lexical and
semantic retrieval converge on it. A mention does not: BM25 finds the single
sentence carrying the phrase while the embedding drifts to the section that is
actually about something similar. The divergence is measurable without knowing
which retriever is right, which is what makes it usable as a gate rather than as
a preference.

**Why the ceiling is a statistic of the answerable side.** It was first defined
as the highest score any unanswerable query achieved — which let the worst case
through by construction, since that case *was* the maximum. A threshold defined
by the example it must catch is not a threshold. The median answerable top score
is independent of the cases being caught.

**Result on the two chapters:** 10/10 unanswerable refused, 44/50 answerable
answered. The three cases that motivated this — completing the square,
Pythagoras, the distance formula — are refused with a stated reason.

**Limits, recorded because the number is quotable and the caveat is not.** Both
constants are fitted to the 60 visible cases with no holdout (Q2) and no
adjudication. Three of the six false abstains are maths questions whose evidence
is mangled formula text (R-008) rather than a gate defect. The other three are
definitional queries where both retrievers found *different correct* sections —
agreement at concept level rather than object level is the next refinement.

---

### R-021 · Rank fusion is for ranking, never for the abstention decision
**Status:** Active · 30 August 2026

Hybrid RRF posts the best abstention margin in the table (−0.024) and it is an
artefact. Reciprocal rank fusion sums `1/(k+rank)`, so every query's top result
scores near the ceiling whatever the match quality — the numbers compress into
0.976–1.000. Its abstention accuracy is 50% against dense's 90%.

**Decision:** hybrid may order candidates; the sufficiency gate reads dense and
BM25 scores directly. Any future fusion feeding a gate must be calibrated on its
own distribution first, and a margin that improves while accuracy falls is the
signature to look for.
