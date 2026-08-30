# Task ledger

## Done — 24 August 2026

- [x] Repository, package layout, test harness
- [x] Authority order transcribed (`docs/00-authority.md`); prior Foxxy spec demoted to authority 3
- [x] §14 gates transcribed with their enforcement point (`docs/01-acceptance-gates.md`)
- [x] Workstream ownership (`docs/02-workstreams.md`)
- [x] §6.2 typed learning objects
- [x] §6.3 runtime contracts, all eight
- [x] §6.4 evaluation case and gold-set schema
- [x] §8.1 plan builder seed, deterministic, no model in it
- [x] Corpus with the authorisation boundary as a method, not a convention
- [x] Scorer: recall at candidate and pack depth, abstention, five zero-tolerance counters, per-slice
- [x] Abstention calibration derived from measured separation
- [x] §6.5 four broken retrievers, all detected — 34 tests passing
- [x] Four open questions drafted for the client (`docs/03-open-questions.md`)

## Done — 26 August 2026

- [x] Parser bake-off, four configurations over a real NCERT chapter (R-008, `EVALUATION_LEDGER.md`)
- [x] §7.1 page-coverage gate verified against real content — all four parsers pass
- [x] Established that formula enrichment hallucinates in 23% of cases and stays off
- [x] Established GPU as an infrastructure requirement with measured per-page cost

## Done — 30 August 2026

- [x] Science ch1 driven through the repository's own adapters — 493 blocks, 30
      learning objects, §7.1 page gate PASS, dual-parse diff 0 pages flagged
- [x] Dual parse wired as Docling + opendataloader-pdf (§7.2), the pairing R-008
      actually chose
- [x] Three parsing defects found by real content and fixed: colliding block ids
      (R-012), empty Docling tables (R-013), a diff that flagged every page
      (R-014)
- [x] `EvaluationLicence` — quarantined sources may be measured, never served
      (R-011), with the ways around it tested
- [x] `pilot-2-chapters-v0`: 60 real cases over both chapters, 50 answerable,
      10 unanswerable. Drafted, **not adjudicated**
- [x] First real-content scored run (`EVALUATION_LEDGER.md`, 30 August): all four
      broken retrievers still detected; **abstention does not separate on real
      content**, margin −0.497

## Blocked

- [ ] **Q1** Pilot curriculum named → §6.1 spine, §6.4 gold set, §7.1 registration
- [ ] **Q3** Signed rights records per source → all parsing
- [ ] **Q2** Holdout seal timing confirmed → whether §14's holdout gate binds at 72h
- [ ] **Q5** Scope: does this repository build §9, or consume it?

- [x] **§7.3 search representations built** (R-016, R-017) — 77 block-aligned
      windows over 38 objects, deterministic, unembedded, parent-resolved
      authorisation. 14 new tests
- [x] Evidence volume in the ruler (R-018): 143 blocks/pack at object level
      against 43 at window level, which is what makes the two comparable
- [x] Recalibrated and re-ran: abstention margin −0.497 → **−0.321, still not
      separable**. Chunking necessary, not sufficient

- [x] BM25 over representations (R-019) — pack recall 86% → **94%** at 40
      blocks/pack, and it is now the floor every later component must beat
- [x] Diagnosed the abstention overlap case by case: the offenders are concepts
      the chapters *mention without teaching*, which no lexical scorer separates

## Next, unblocked

- [ ] **§8.4 sufficiency gate** — the real abstention mechanism (R-019). Does the
      pack answer the query, asked of the evidence rather than of a score
- [ ] Provider-independent embedding adapter, measured against BM25 and judged
      on the bottom of the answerable band (the table case, the paraphrased ones)
- [ ] Reranking, tuned on pack recall (Q4)
- [ ] Postgres schema for sources, blocks, objects, representations
- [ ] Extend the gold set past 60 cases, and get two named reviewers onto the 10
      release-critical ones

- [ ] Real slice axes wired to §11.2's pairwise matrix rather than the six ad-hoc axes now in `EvalCase.slice_keys`
- [ ] Postgres schema + migrations for `sources`, `blocks`, `learning_objects`, `search_representations`
- [ ] Dual-parse harness (§7.2) wired into the repo — Docling + opendataloader, both writing `SourceBlock`, with the bbox conversion (PDF points bottom-left → normalised top-left) and parse-strategy provenance
- [ ] Formula objects carry crop + raw text + LaTeX, never LaTeX alone (R-008)
- [ ] Mathpix comparison over the same 30 formula crops — needs an API key
- [ ] Provider-independent embedding adapter, so no provider is hardcoded as architectural truth (§7.3)
- [ ] Citation precision and completeness scorers (§14, currently unenforced)

## Next, needs Q1

- [ ] 300-500 adjudicated cases across the §6.4 conditions
- [ ] Seal the holdout
- [ ] First embedding/reranker benchmark on real content
