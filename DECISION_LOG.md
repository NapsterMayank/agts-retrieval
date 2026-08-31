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

---

### R-022 - A window carries the statement it continues, and nothing else
**Status:** Active - 30 August 2026 - **replaces a wrong diagnosis**

Three maths cases scored below the abstention floor. They were recorded as
formula-text damage (R-008) with Mathpix as the fix. Reading the gold blocks
disproved that: two of the three are clean prose. The cause was a window boundary
- "Example 6 : Find the dimensions of the prayer hall" ended one window and its
answer began the next, which never repeats the phrase.

**Decision:** a window carries forward the last block of the previous window
**only when that block opens a statement** (Example, Activity, Problem,
Question). The carried text goes into `search_text` and never into `block_ids`,
so a window can be found by it and can never cite it.

**Why not carry unconditionally**, which was tried first: pack recall fell from
94% to 90% for dense and 94% to 84% for BM25, because every window became
findable by its neighbour's words and the retriever returned continuations for
queries answered by the block before. Narrowing to statement openers keeps the
recall and the gate improvement.

**Consequence:** `REPRESENTATION_VERSION` is `block-window-v2`. The vector cache
is keyed by text hash, so stale vectors could not be silently reused.

---

### R-023 - Corroboration may be weak when it is anchored on a teaching object
**Status:** Active - 30 August 2026

Requiring two shared objects among the top three refused three textbook
definitions: dense ranks the definition section first, BM25 ranks the exercises
first, and they share only the summary - one shared object, indistinguishable by
count from "completing the square".

**Decision:** answer when the two retrievers share two of their top three, **or**
share at least one *and* either ranks an object typed `DEFINITION` or `CONCEPT`
first. Those types come from the hand-written section map (R-009): a human
curriculum judgement, not a parser output and not a model's opinion.

Measured against every looser alternative on the visible set. Relaxing depth
instead - top-5 overlap, primary-#1-in-top-5, overlap >= 1 - reaches the same
48/50 on answerable cases and lets one unanswerable through every time.
Anchoring is the only variant that keeps 10/10.

**Why it holds:** a concept the chapter teaches has a section that defines it. One
that is merely named does not, so the agreement has nothing to anchor on - which
is the mentioned-versus-taught distinction, asked structurally.

---

### R-024 - The holdout number is the one that gets quoted
**Status:** Active - 30 August 2026

38 cases were written after the gate's constants were fixed and were not
consulted while choosing them. Constants derived from the visible 60 only.

| | unanswerable refused | answerable answered |
|---|---:|---:|
| visible 60 (tuned on) | 10/10 | 48/50 - 96% |
| holdout 38 | 8/8 | 27/30 - 90% |

**Decision:** 90% is the acceptance figure that leaves this repository, not 96%.
The visible number is an upper bound on itself, and is reported beside the
holdout rather than instead of it.

Refusal held at 100% on unseen cases, which is the direction that matters: the
zero-tolerance gates in section 14 are about what gets answered wrongly, not
about what gets refused conservatively. The floor is brittle - one holdout case
missed it by 0.002 - and a larger gold set should re-derive it rather than have
it tightened by hand.

---

### R-025 - The pack completes each section it selected; ranking and citation want opposite things
**Status:** Active - 30 August 2026

Ranking keeps one window per object so five slots hold five distinct sections.
Citation needs the opposite, and the first citation run showed it: completeness
77.1% against a 95% gate, with **31 of 31 missing gold blocks in a sibling window
of a section already in the pack**.

**Decision:** the pack builder pulls in sibling windows of a selected section
**that clear the same floor the section cleared**. Not "adjacent", which reached
93.3% and still failed, and not "every window of the object", which reaches 100%
by handing over 126 blocks a pack - the bloat R-015 exists to prevent. A window
that would have been retrieved on its own merits is evidence; one that would not
is padding.

Sibling scores come from `DenseRetriever.score_windows` through the decision, so
the builder uses real scores rather than a proximity guess, and a retriever that
cannot supply them gets no expansion rather than an invented one.

**Result:** completeness 97.2% visible, 96.3% holdout, at 73 blocks a pack.

---

### R-026 - Citation precision is not measured, and the proxy is named differently
**Status:** Active - 30 August 2026

§14 gates citation precision at >=98%: does a citation support the sentence it is
attached to. There are no sentences - generation is Phase 3, scope-blocked on Q5
- so the row is **unmeasured and explicitly unclaimed**.

`evidence_precision` is reported instead: the fraction of cited blocks that are
gold. It is a lower bound (a block can be useful without being gold) and it is
2-3%, because a 73-block pack carries two or three gold blocks.

**Decision:** the proxy never borrows the gate's name, in the field names rather
than in a footnote, and `CitationReport.failing_gates` deliberately does not
evaluate the precision row. An unmeasured gate reports as unmeasured; the
alternative is a green tick for something nobody checked.

**Consequence:** 2-3% is the standing argument for reranking and for
sentence-level citation once generation exists.

---

### R-027 - The reranker is built, measured, and switched off
**Status:** Active - 30 August 2026

Voyage `rerank-2` over the top 20, measured on pack recall against an identity
reranker as the control. **No pairing moved pack recall by one case**: dense
94.0% with and without, BM25 92.0% with and without, hybrid 94.0% with and
without.

The cause is in the data rather than in the reranker. `recall@20` and
`recall@pack` are identical for every retriever here, so the gold object is
already in the top five whenever it is retrieved at all - with 38 objects and one
candidate per object, the candidate list is usually shorter than the pack itself.

**Decision:** the port and the Voyage adapter ship, the stage stays off, and
`scripts/rerank_benchmark.py` is the thing to re-run when the corpus is a
curriculum instead of two chapters. Shipping a paid per-query call that provably
changes nothing would be paying for a number that did not move.

---

### R-028 - The gate keeps dense as primary, and pack recall is not why
**Status:** Active - 30 August 2026

The rerank benchmark surfaced an inversion: BM25 has **better pack recall on the
holdout** than dense (83.3% against 76.7%) while losing on the visible set. The
tempting read is that BM25 generalises better and should lead.

Measured instead of assumed:

| gate primary | holdout refuse | holdout answer |
|---|---:|---:|
| dense | **8/8** | **27/30** |
| bm25 | 6/8 | 26/30 |

**Decision:** dense stays primary. BM25 lets two unanswerable questions through
on unseen cases, and a wrong answer is the failure the whole system exists to
prevent.

**The general point:** a retriever is chosen for the decision it supports, not
for its best headline metric. Pack recall improved and the gate got worse.

---

### R-029 - This repository gets its own database container
**Status:** Active - 30 August 2026

The persistence tests needed a server. Three were available: the machine's
native Postgres 17, Foxxy's compose container on 5433, and a new one.

**Decision:** a new container - `docker/compose.yml`, port 5434, pgvector image,
its own volume. Integration tests migrate schemas and roll back transactions,
and "it only touches its own tables" is not a claim worth betting a colleague's
development data on. The pgvector image also means `002_pgvector` is exercised
rather than assumed to work, which is how the width pin was found.

The container password is committed deliberately: it is a local development
credential for a service bound to localhost, holding nothing but quarantined
test content, and a test suite nobody can run is worse than a password nobody
can use.

**Verified end to end:** 728 blocks and 77 representations written and read
back, with retrieval from the database scoring identically to retrieval from
files (bm25 92.0%, dense 94.0% pack recall in both).

---

### R-030 - The abstention floor stays at the midpoint, measured against the alternative
**Status:** Active - 30 August 2026

A holdout case missed the floor by 0.002. The midpoint sits between two single
outliers, so the brittleness is structural, and Foxxy solved the same problem
with a measured false-abstain budget (D-216).

Four budgets were measured against the holdout. **The midpoint won.** A 2% budget
lowers the floor to 0.726, buys one answered question and **leaks one
unanswerable case**; 5% and above refuse more real questions without refusing
more unanswerable ones.

**Decision:** the midpoint stays, and the budgeted calibration ships as an
option that reports what a threshold costs and buys. The 0.002 brittleness is
answered by more gold cases, not by a different formula over the same fifty.

Recorded because the opposite conclusion was expected, and a rejected hypothesis
that leaves no trace gets re-tried by the next person.

---

### R-031 - Slices are pairwise, and the report separates the distinctive failures
**Status:** Active - 30 August 2026

`slice_keys` carried six ad-hoc axes. It now carries nine single axes and all 36
pairwise crossings (section 11.2). Accessibility and provider are **absent
rather than filled with a constant**: a slice with one value cannot fail, and a
slice that cannot fail looks like coverage.

The matrix restates itself - a failing axis drags down every crossing containing
it, turning 12 facts into 63 lines - so `distinctive_failures()` reports a
crossing only when both its axes pass alone, alongside the full list rather than
instead of it.

**It found one on the first run:** `single_hop × explain` fails pack recall at
0.875 while `single_hop` and `explain` each pass. That interaction is invisible
to single-axis reporting, which is the entire argument for the matrix.

**Consequence:** 166 slices, 66 gating at n >= 20 and 100 reporting only. The
report-only crossings are a map of the gold set's gaps: the four largest sit at
n = 18 or 19, one or two cases short of gating.

---

### R-032 - Ranking recall and delivered recall are different numbers, and both are reported
**Status:** Active - 30 August 2026

The pairwise matrix flagged `single_hop x explain` failing pack recall while both
axes passed. The cause was not retrieval: `maths-004`'s gold block sits in window
2 of a section whose window 1 outranked it, so the retriever's ranked list missed
it - **and the delivered pack contained it**, because sibling expansion runs
after ranking (R-025).

**Decision:** `CitationReport.delivered_recall` measures the pack, beside
`recall_at_pack` which measures the ranking. Neither replaces the other: one
answers "did the retriever order it correctly", the other answers "did the
teaching loop receive it", and they are allowed to disagree.

Delivered recall is 100% visible and 96.3% holdout, against 94.0% and 76.7% for
ranking. The whole gap is sibling expansion doing what it was built to do, which
had never been measured end to end.

**The general point:** a slice that fails is a question, not a verdict. This one
turned out to be a gap in the ruler rather than a defect in the system, and
tuning retrieval to satisfy it would have optimised against a number that does
not describe what a learner receives.

---

### R-033 - The release manifest is computed from the corpus, and signed by nobody until it is
**Status:** Active - 30 August 2026

Section 14 gates approved-source and lineage resolution at 100%, and nothing
enforced it. A `ReleaseManifest` is now built by **hashing the corpus** - source
checksums, object content hashes, representation hashes and their embedding
model - rather than by recording what someone believed was in it. A hand-written
manifest agrees with the corpus exactly until the first time it does not.

`lineage_failures()` fails a pack three ways, each of which produces a plausible
answer with an unaccountable origin: citing an object outside the serving
release, citing an object whose source is not in the manifest, or claiming a
manifest it was not built against. **0 failures over 98 packs.**

`approved_by` stays empty until named humans sign it, and the report prints
`approved by NOBODY (unsigned)`. The manifest is still useful unsigned - it
answers "which corpus produced this" - and treating its existence as approval is
how a release gate becomes decorative.

Traces record the corpus checksum, commit, thresholds, primary retriever and
every filter applied, including the evaluation licence. Rejected candidates carry
a reason - 1,045 of them across 98 packs - because a trace of only the winners
cannot answer why a passage was not used.

---

### R-034 - The service refuses to serve unapproved content, and the override authorises as well as boots
**Status:** Active - 31 August 2026

Everything measured so far is `QUARANTINED` under an evaluation licence (R-011),
which is legitimate for measuring and not for serving. The service therefore
**refuses to boot** against a corpus with unapproved sources rather than
defaulting to permissive, and the override is a full phrase
(`AGTS_ALLOW_QUARANTINED_CONTENT=yes-i-accept-unapproved-content`) so it cannot
be set by a habitual `=true`.

**A bug worth recording, because the first version had it.** The override
originally only permitted *booting*. `Corpus.authorised` still admitted nothing,
so the service started cleanly and then abstained on every question with "no
candidate survived the authorisation filter" - an override that looks enabled and
is not. It now attaches a named serving permission as well, and every response
carries `unapproved_content: true`.

Three further boundaries, each a deliberate refusal rather than an omission:

- **The tenant comes from the bearer token**, never from the body, which forbids
  the field outright. A caller that names its own tenant has no tenant boundary.
- **Thresholds are configuration.** The service will not start without a
  calibrated floor and ceiling, and never derives them from live traffic - a gate
  that recalibrates itself loosens exactly when the corpus gets harder.
- **Lineage is checked at serve time**, not only in reports. A pack whose
  lineage does not resolve is withheld with a 500 rather than returned with a
  note attached.

---

### R-035 - The gate is sensitive to phrasing, and the gold set could not show it
**Status:** Active - 31 August 2026 - **found by running the service, not by scoring it**

Two paraphrases through the live endpoint flipped both decisions:

| query | outcome |
|---|---|
| *What is the discriminant of a quadratic equation?* | SUFFICIENT |
| *What is the discriminant?* | ABSTAIN |
| *How do you solve a quadratic equation by completing the square?* | ABSTAIN |
| *How do you solve by completing the square?* | **SUFFICIENT** |

The second is a false answer on the exact case the gate exists to refuse.

**Cause:** every gold case is a full sentence naming its subject, because that is
how questions get written while looking at a chapter. A shorter query carries
less signal, so both quantities the two-tier gate reads - the dense top score and
the top-3 overlap - move together.

**Consequence for the published numbers:** 8/8 refused and 27/30 answered hold
for the phrasings measured, which are not how learners type. The result is about
the question as written, not about the concept. Not retracted, and scoped.

**Decision:** the next gold-set work is paraphrases of existing cases rather than
new concepts, written by someone other than the author of the originals, and the
floor is re-derived afterwards. Adding more cases in the same register would grow
the set without widening it.

---

### R-036 - An outside review found three wrong answer keys and three code defects
**Status:** Active - 31 August 2026

The gold set was written by the agent that built the system, so an independent
model was given the chapter text and every release-critical claim, instructed to
find errors rather than agree. **Science 24 right, 3 wrong; mathematics 21 of 21
right.** Each objection was checked against the chapter before being accepted,
and all three held:

- `h-chem-17` cited one of four observations. Fixed.
- `h-chem-11` cited a block that says an equation must be balanced; the block
  that actually **defines** a skeletal equation was missing. Fixed.
- `h-chem-16` asks how to identify the electrolysis gases, and the chapter gives
  the method while withholding the result. **Removed** rather than resolved: a
  case that turns on a judgement two careful readers can split on is a bad test
  item whichever way it goes.

Three code defects, all real, all fixed:

- **the anchor did not require the shared object to be the teaching object**, so
  an unrelated definition at rank 1 could bless a disputed match;
- **a caption extracted before its figure split the pair**, because grouping only
  attached to a target already seen - the documented invariant broken by reading
  order;
- **configurations that disabled the gate's own conditions were accepted**
  (`min_corroboration=0`, `depth=0`, ceiling below floor).

One finding is accepted and open: `calibrate_abstention` calibrates the primary
retriever's top score, not the gate that actually ships, which also reads BM25
overlap and object types.

**Consequence:** acceptance fell from 48/50 to 47/50 visible and 27/30 to 26/29
holdout, and **the constants were not re-tuned to recover them**. Retuning after
a correctness fix would convert a fixed defect back into a number.

**The general lesson:** three of the four checks a reviewer was given found
something. The one that found most was the one with the chapter text and the
instruction to disagree - not the one asking for an opinion about the
architecture.

---

### R-037 - A gate that finds the right block cannot tell whether the block says anything
**Status:** Active - 31 August 2026 - **found by an outside reviewer, invisible to every existing gate**

Asked to check "the maths chapter answers *what is the quadratic formula*", an
outside reviewer agreed with the claim and objected anyway: the extracted
evidence reads `2 4 , 2 b b ac a    provided b 2 - 4 ac`, and no student can
reconstruct the quadratic formula from that.

Recall passed. Pack recall passed. Delivered recall passed. Citation completeness
passed. Lineage passed. **Every measurement in this repository asks whether the
right block was found; none asks whether the block says anything.**

**Decision:** `parsing/quality.py` measures usability as a reader's test - a
formula is unusable when almost every token is a single character *and* no
relation survives, because an equation without `=`, `<`, `>` or an arrow states
nothing whatever symbols remain. Both conditions must hold, since chemical
equations survive extraction far better than algebra and their arrows are why.

**Measured:** 0 of 30 formula blocks unusable in the science chapter, **5 of 43
(12%) in the maths chapter.**

**Consequence:** R-008 predicted this and left it open for a week because nothing
measured it. The case for a formula recogniser is no longer an assumption, and
`maths-012` is the demonstration to attach to any request for a Mathpix key.

The blocks are not dropped. The crop is still there, the citation still resolves,
and a reviewer can still see what was meant - what this produces is a work list
and an honest denominator.

---

### R-038 - The same key defect appeared twice, so it was systematic
**Status:** Active - 31 August 2026

`h-chem-17` and `chem-021` ask nearly the same question and both cited a subset
of the four observations the chapter lists. The first round caught one; the
second round caught the other only because the previously unreviewed half of the
set was finally sent out.

**Two things follow.** A defect found once in a set drafted by one author should
be searched for across the whole set rather than fixed where it was seen. And
scoping a review to the release-critical cases left 50 cases - more than half -
checked by nobody, while the report of that review read like coverage.

**Decision:** `export_verification_pack.py --scope rest|all`, and no review is
described as complete while any case in the set is unreviewed.

---

### R-039 - Every rate carries its denominator and a lower bound
**Status:** Active - 31 August 2026 - **asked for by `codex`**

Asked what single measurement would most change confidence in the 8/8 refusal
figure, codex answered: report a bound and a denominator rather than a bare
fraction.

**Measured:** 8/8 supports a true refusal rate of **at least 69%** at 95%
confidence, exact one-sided Clopper-Pearson. A system that wrongly answered three
learners in ten produces 8/8 on eight cases about one run in twenty. 18/18 across
both sets supports at least 85%.

**Decision:** `evaluation/confidence.py`, and every rate a runner prints carries
its bound. Clopper-Pearson rather than a normal approximation, because at n=8 the
approximation produces intervals extending past 1.0.

Nothing about the system changed. What changed is what this repository may claim,
and it is markedly less than the fractions implied.

---

### R-040 - A ceiling equal to the floor silently disables corroboration
**Status:** Active - 31 August 2026 - **found by `opencode`**

The constructor guard added in R-036 refused a ceiling *below* the floor. Equal
was still accepted and is the worse case: the band between floor and ceiling is
empty, so every score at or above the floor takes the high-confidence branch and
corroboration never runs. The gate reads as fully configured with one of its two
conditions switched off.

It now raises. Separately, a slotless plan - which `QueryPlan` forbids and
`model_copy` bypasses - records a gap rather than producing a `SUFFICIENT` pack
of items tagged with a role nobody asked for.

**On the reviewer:** eight claims, three checkable, one and a half survived. Its
strongest contribution was closing with the observation that it should verify its
own claims first. Findings are checked here before being accepted, and this round
is why that rule exists.

---

### R-041 - The pack serves `text or latex`, because it was citing content it did not show
**Status:** Active - 31 August 2026 - **found by `opencode`, reproduced before fixing**

`chunking._text_of` makes a block searchable on `text or latex`. `build_pack`
rendered `text` alone. A latex-only formula was therefore ranked on its formula,
entered the span, was covered by the citation, and reached the teaching loop as
an empty line: prose promising a formula, no formula, and a citation vouching for
the block that held one.

Distinct from R-037, which measures whether *recovered formula text* is readable.
This is the pack never reading the field.

**It changed no number**, because no gold block in this corpus is latex-only -
the parser recovered symbol text for every formula, badly. The defect would have
activated the first time a formula recogniser populated `latex` properly, which
means **fixing R-037 would have triggered R-041**.

Also fixed alongside: the unfilled-slot check keyed on role rather than slot id,
so two required slots of the same role were satisfied by one item and the pack
still reported `SUFFICIENT`.

---

### R-042 - Three findings accepted and left open, because half-fixing them is worse
**Status:** Open · Accepted · 31 August 2026

From the same review, all three verified as real:

**Corroboration compares objects while retrievers rank windows.** The gate exists
to ask whether independent retrievers agree on *where the answer lives*, and it
compares `object_id`. Two retrievers can agree on a section while pointing at
different passages within it. The docstring promises more than the code measures.

**Sibling expansion consults only the primary.** R-025 admits sibling windows
clearing the floor using the primary's scores alone, in precisely the band where
the gate requires two retrievers to agree - and merges them into one evidence
item under one citation spanning the concatenation.

**A carried statement is findable and never served.** Rule 5's context reaches
`search_text` and not `block_ids`, so the pack can contain an answer without the
question it answers.

**Why open rather than fixed:** the last two interact. Requiring corroboration on
siblings would drop evidence that citation completeness currently depends on
(96.2% holdout), and serving carried context would put uncitable text into a pack
whose whole discipline is that everything shown can be cited. Either change alone
moves a published number for reasons unrelated to quality.

Recorded with the numbers they would move, so the next person changes them
deliberately rather than discovering the interaction afterwards.

---

### R-043 - The second parser's LaTeX is attached only when it cannot be a guess
**Status:** Active - 31 August 2026

R-008 required crop, raw text **and** LaTeX on every formula block. The `latex`
field was never populated, while Chandra produced clean LaTeX for the same pages
and was used only to count characters in a page diff. The 12% unreadable rate in
R-037 was measured against a gap that a file on disk had already closed.

**The first attempt attached 35 of 43 formulas and was wrong.** Three were
checked against the page images: one correct, one matched to its own sign-flipped
twin, one to a different formula on the same page. R-008 rejected Docling's
enrichment because hallucinated LaTeX renders beautifully and is wrong; this was
the same failure with a different tool, and 35-of-43 looked like success.

Two causes, both avoidable. The symbol comparison **stripped operators with the
markup**, making a formula and its sign-flipped twin identical. And it assumed a
per-page join that R-008 had already recorded as **not one-to-one** - page 4 has
two Docling formulas against zero Chandra display equations.

**Decision:** operators count as symbols, and a match must beat its runner-up by
0.50 as well as scoring 0.90. **4 of 43 attach; 39 go to human review.** A far
worse yield, and the one that survives being checked. Both fields are kept on the
block, so a wrong attachment stays detectable.

---

### R-044 - `text or latex` is the wrong precedence
**Status:** Active - 31 August 2026

A block whose text has decayed to loose symbols still *has* text, so `text or
latex` would have hidden every recovered formula behind the mangled version of
itself. `quality.readable_text` prefers LaTeX only when the text is unusable, and
both fields are still stored either way (R-008).

**Consequence:** the window a learner receives for "what is the quadratic
formula" now carries the formula. **No score moved** - which is the finding, not
a footnote. Nothing measured here would have caught the formula being wrong, and
nothing measured here noticed it being fixed. Content quality sits outside every
gate in this repository, and R-037's usability measure is the only thing that
looks at it.

---

### R-045 - Corroboration is agreement on a passage, and siblings need two opinions
**Status:** Active - 31 August 2026 - **closes two thirds of R-042**

**Agreement was measured on `object_id`** while both retrievers return their own
best window per object, so two retrievers pointing at different paragraphs of the
same section counted as agreeing. A shared object now counts only when the
windows match or share a block.

Measured on the visible set alone, every relaxation that recovers the lost
acceptance leaks an unanswerable case: 1-of-3 and 2-of-5 both drop refusal to
9/10. The strict rule stays. **Acceptance fell 47/50 to 42/50 visible and 26/29
to 23/29 holdout; refusal held at 10/10 and 8/8.**

That trade is deliberate. A refusal costs a learner a question; a wrong answer
costs them the thing the gate exists to prevent. And the number fell because the
claim became true, not because the system got worse.

**Sibling expansion asked only the primary**, in the band where the gate itself
requires two opinions, then merged the result into one evidence item under one
citation. `BM25Representations.score_windows` mirrors the dense method, and a
sibling must now clear the floor *and* be ranked by the corroborator. Completeness
held at 95.7% holdout, above the 95% gate.

---

### R-046 - Context is served and cited, or it is not context
**Status:** Active - 31 August 2026 - **closes the last third of R-042**

Rule 5 (R-022) carries a worked-example statement into `search_text` and never
into `block_ids`, so the window that continues an example is findable by it. The
consequence, unwritten until an outside reviewer named it: the pack could serve
*"the breadth of the hall is 12 m"* with no trace of the problem it answers, and
a teaching model restating that problem would have been making an unsupported
claim while holding a citation.

**Decision:** `SearchRepresentation.context_block_ids`, a separate field rather
than more `block_ids`. The distinction is the whole point - these blocks are real
and on real pages, so the pack **serves and cites** them, while recall continues
to score only the blocks the window is made of. Counting them as the window's own
evidence would inflate every recall number in this repository.

---

### R-047 - A paraphrase inherits its label, so its author may be the author of the case
**Status:** Active - 31 August 2026 - **closes R-035**

Every gold case was a full sentence naming its subject. The set now carries 107
rewordings of 77 parents in three registers, doubling it to 204 cases.

**Why this is not more marking my own homework.** A paraphrase inherits its
parent's answer and gold blocks unchanged; only the wording differs. Writing one
introduces no new judgement about what a chapter teaches, which is exactly the
judgement an author cannot check for themselves. Writing new *cases* would be a
different act, and is not what happened here.

Two rules the expansion follows: a reworded holdout case stays in the holdout, or
thresholds would be fitted to a question whose twin is meant to be unseen; and
adjudication does not inherit, because a human would have approved the parent's
wording rather than this one.

**Measured before changing anything:** refusal is register-proof (54/54 across
all registers) and acceptance is not (82% textbook, 56% short, 62% spoken). The
failure mode of a short question is conservatism rather than invention, which is
the better half of a bad situation.

---

### R-048 - The re-derived floor was rejected; only the ceiling moved
**Status:** Active - 31 August 2026

Calibration on the wider visible set moved floor 0.737 -> 0.715 and ceiling
0.827 -> 0.800. Four combinations were scored on the visible set alone under a
rule declared before looking - no leaks first, then most answers.

**The new floor leaks.** 0.715 buys one more answer and lets an unanswerable case
through, so 0.737 stays. The ceiling moves to **0.800**, worth six more answered
questions at no cost in refusals, because the median answerable score is lower
once short questions are in the set.

**Holdout, touched once, on 64 cases across three registers:**

| | before | after |
|---|---|---|
| unanswerable refused | 8/8, supports >= 69% | **24/24, supports >= 88%** |
| answerable answered | 23/29, supports >= 63% | **33/40, supports >= 70%** |

The refusal claim now rests on 24 observations rather than 8, which is the point
of the exercise. `AGTS_HIGH_CONFIDENCE` becomes 0.800 wherever the service is
run.

**Still not established:** the rewordings are mine, so they share my assumptions
about how a learner writes. This measures register sensitivity. It does not
measure real learners.

---

### R-049 - A short question is thin, not wrong, so the plan's scope is restored
**Status:** Active - 31 August 2026

Acceptance was 82% for textbook phrasing and 56% for short. A full sentence
carries its subject with the question; four words do not. Both retrievers now
search `class {grade} {subject}, {query}`, taken from the plan.

**Not query rewriting.** The learner's words survive intact and nothing is
inferred - the scope was already on the plan, because a learner asking from a
Class 10 science lesson is asking inside that scope whether or not they say so.
A rewriter that changed words would need measuring for changing meaning; this
cannot.

Measured on the visible set alone: 90/109 answered against 81/109, refusals
unchanged at 31/31, short-form acceptance 59% -> 76%. Holdout 34/40 against
33/40, refusal 24/24.

**And an existing test caught a regression the change introduced:** with scope
prepended an empty question is no longer empty, so asking nothing would have
returned whatever best matches `class 10 science`. Scope alone is not a question.

---

### R-050 - A report scores what ships, not what calibration suggests today
**Status:** Active - 31 August 2026

Both runners re-derived floor and ceiling from the current score distribution and
scored *those*, while the service runs the pair chosen in R-048. After query
scoping the two diverged - 0.745/0.807 derived against 0.737/0.800 shipped - and
the gap is 83/109 against 90/109 on the visible set.

**Every number reported before this fix described a configuration nobody was
running.** The runners now score the shipped pair and print the derived one
beside it, so a drift between them is visible rather than silently adopted.

**Consequence for citation completeness:** measured on the shipped configuration
it is 95.2% visible and 97.1% holdout, down from 98.4% and 98.6%, because
answering more questions means more chances to answer one incompletely. It still
clears the >= 95% gate and it is now close to it, which is the honest reading:
acceptance and completeness trade against each other, and that trade is visible
for the first time.

---

### R-051 - An expansion may add context, never the answer under test
**Status:** Active - 31 August 2026 - **measured and rejected**

Scope expansion worked (R-049), so concept expansion was measured the same way:
`class 10 science, chemical reactions and equations, {query}`. It buys six to
nine more answers on the visible set and **lets three to five unanswerable
questions through** - 28/31 refusals against 31/31, and 26/31 with concept alone.

**Rejected**, and the reason generalises. Scope says *where the learner is
standing*, which their sentence would have carried anyway, and cannot make an
out-of-chapter question look in-chapter. Concept asserts *what the question is
about*, which is precisely what the gate is deciding.

The cases that leak show it exactly. "What is the function of chlorophyll in
photosynthesis?" rises 0.711 -> 0.778 against a 0.737 floor. Chlorophyll appears
in that chapter once, inside the photosynthesis equation, and its function is
never taught - it is one of the deliberately adjacent cases. Prefixing every
query with "chemical reactions and equations" answers the premise under test.

**The rule:** an expansion may add what the learner's context already implies,
never what the retrieval is being asked to determine.

**And a measurement defect worth recording.** The first run of this experiment
pre-expanded the plan while the retrievers also scope internally, so every query
was scoped twice and the baseline read 87/109 instead of 90/109. It was caught
because the baseline disagreed with a number measured an hour earlier. A
comparison whose control does not reproduce a known figure is measuring
something else.

---

### R-052 - Window adjacency measured and rejected; the frontier is real
**Status:** Active - 31 August 2026

21 of 25 false refusals are two retrievers agreeing on the section and
disagreeing on the window. Counting adjacent windows as the same passage buys
eight answers and leaks one unanswerable case (30/31); within two windows leaks
two.

**Rejected**, and with it a pattern worth stating: five relaxations have now been
measured - lower floor (R-048), fewer shared objects (R-045), greater depth
(R-045), concept expansion (R-051), window adjacency here - and **every one buys
acceptance by leaking a refusal.** That is a frontier rather than a badly chosen
parameter, and further tuning is not where the remaining acceptance lives.

**Where it does live**, none of it free: reranking *within* an object so both
retrievers choose the same window; overlapping chunk windows so adjacency becomes
genuine block overlap (a re-measure of everything, including every stored
vector); a third retriever so agreement can be two-of-three; and formula repair
for the below-floor maths cases.

---

### R-053 - The repository was published publicly, with the chapter text in its history
**Status:** Active - 31 August 2026 - **an operator decision, recorded rather than argued**

Pushed to `github.com/NapsterMayank/agts-retrieval`, public, full history, 37
commits.

**What that published.** All code, all fourteen documents, every decision in this
log, and the 204 gold cases. It also published, in history, five review sheets
carrying roughly twenty-five verbatim NCERT passages each - `review-sheet.csv`,
`review-for-mayank.csv`, `review-for-sumit.csv` and two simulated reviewer files.
Those files were removed from the working tree on 31 August (R-034's gitignore
work) but removal takes a file out of future commits, not out of history.

**The advice given, and not taken.** A squashed push to a private repository was
recommended: it drops the sheets from history, keeps every document and decision,
and can be made public the moment a rights record exists. The operator chose the
full public push after the exposure was measured and stated. That is their
decision to make - they supplied the source material and carry the relationship
with the rights holder.

**What is still true.** No source is `APPROVED`, every manifest still reads
`FORBIDDEN_PENDING_RIGHTS_RECORD`, and the service still refuses to boot without
an explicit override. Publishing the repository changed none of that: it is a
disclosure of working material, not an approval of content, and nothing in the
pipeline treats it as one.

**If it needs undoing:** GitHub retains blobs after a force-push, so the only
reliable removal is deleting the repository. `gh repo edit --visibility private`
limits further exposure but does not retract what has been fetched.

---

### R-054 - Reading a documented font encoding is a decode, not a guess
**Status:** Active - 31 August 2026

Eleven distinct characters in the parsed chapters sat in the Unicode private-use
area: U+F028, U+F029, U+F02B, U+F02D, U+F03D, U+F061, U+F0B1, U+F0B3, U+F0B9,
U+F0D0, U+F0D7. All eleven are `0xF000 + position` in **Adobe's Symbol
encoding** - a PDF that sets operators in Symbol stores them by font position,
and an extractor that cannot resolve the font passes the position straight
through. A minus sign arrived as U+F02D. Nothing was damaged; it was written in
an encoding nothing downstream read, so the retriever scored noise and the
quality gate saw formulas containing no relation symbol at all.

**Why this is allowed where R-008 and R-043 forbade the neighbouring thing.**
R-008 forbids *inventing* a formula's content and R-043 rejected a matcher that
*inferred* which formula a page's LaTeX belonged to. Symbol encoding is a fixed
published table: U+F02D means the glyph at Symbol position 0x2D and cannot mean
anything else. There is no candidate set and nothing to choose between.

**Corroborated anyway, before adoption.** For each of the eleven, Chandra's
LaTeX for every page where that codepoint occurs was checked for the
corresponding glyph. **Ten of eleven were confirmed on every such page.** The
eleventh, U+F0D7 (dot operator, two occurrences on page 8), has no counterpart
because Chandra wrote that multiplication implicitly - it rests on the published
table alone, and `symbol_font.py` says so.

An unmapped private-use character is **left as itself**, and the script warns.
A new font position must be looked up and corroborated, never approximated.

**Result: 27 blocks decoded, 4 moved from unreadable to readable.**

**And a correction to a number this repository had been repeating.** The docs
said *39 formulas need a human*. That counted formulas **lacking LaTeX**, which
is not the same as formulas that cannot be read: `x 2 - 45 x + 324 = 0` has no
LaTeX and is perfectly legible. Measured against the quality gate rather than
the LaTeX field, the real figure was 4, and after this decode it is **3** -
texts-153, texts-159 and texts-198, all of which are scrambled in reading
*order* rather than in encoding, and so genuinely need a person with the crops.

A test pins that limit open: `test_the_decode_does_not_pretend_to_fix_a_scrambled_formula`
asserts texts-159 stays unusable after decoding. Making a broken thing *look*
recovered is worse than leaving it visibly broken.

**Cost.** Twelve window texts changed, so their embeddings and every number
derived from them must be rebuilt before anything here is quoted again.
