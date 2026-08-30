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

- [x] Provider-independent embedding port with Voyage, deterministic-fake and
      disk-cache adapters. No provider name outside `platform/`
- [x] Dense and hybrid (RRF) retrieval. Dense matches BM25 on recall and
      separates far better; RRF is ranking-only (R-021)
- [x] **§8.4 sufficiency gate (R-020): 10/10 unanswerable refused, 44/50
      answerable answered.** Completing the square, Pythagoras and the distance
      formula are all correctly refused, with reasons

- [x] Rule 5 in the chunker (R-022) — carries a worked-example statement into the
      window that continues it. **Replaced a wrong diagnosis:** those failures
      were a window boundary, not formula damage, so Mathpix was never the fix
- [x] Anchored corroboration (R-023) — 48/50 on the visible set with refusal
      still at 10/10, where every looser rule leaked one unanswerable case
- [x] 38 holdout cases written after the constants were fixed. **8/8 refused,
      27/30 answered (R-024)** — 90% is the number that gets quoted, not 96%

## Blocked on a credential

- [ ] **Mathpix has no API key anywhere in this repo or Foxxy's env.** Still
      worth doing for the maths formula crops, but its value is now unproven
      rather than assumed — the failures blamed on formula text were not caused
      by it. `maths-023` is the one case where inline formula damage is visibly
      in the evidence

- [x] Evidence packs (§8.3) and the §14 citation gates: resolution 100%,
      completeness 97.2% visible / 96.3% holdout (R-025). Precision is
      unmeasured and unclaimed until generation exists (R-026)
- [x] Postgres schema and repository (§7.1) — §5 as CHECK constraints, the
      authorisation filter in SQL. **Not yet run against a live server**
- [x] Reranking built, measured, and switched off: not one pairing moved pack
      recall (R-027). Gate keeps dense as primary, measured (R-028)

## Next, unblocked

- [x] **Persistence verified against a real server** (R-029) - own container on
      5434, 7 integration tests passing, pgvector migration applied, 728 blocks
      round-tripped with retrieval scoring identically from files and database
- [ ] Re-derive the floor on a larger gold set. One holdout case missed it by
      0.002, which is brittleness, and hand-tightening it would be fitting
- [ ] Real slice axes wired to §11.2's pairwise matrix
- [ ] Two named adjudicators for the 48 release-critical cases (§6.4)
- [ ] Real slice axes wired to §11.2's pairwise matrix rather than the six ad-hoc
      axes now in `EvalCase.slice_keys`
- [ ] Citation precision and completeness scorers (§14, still unenforced)

*(Dual-parse harness, formula crop retention and the provider-independent
embedding adapter were listed here and are done — R-008, R-013, R-016.)*

## Next, needs Q1

- [ ] 300-500 adjudicated cases across the §6.4 conditions
- [ ] Seal the holdout
- [ ] First embedding/reranker benchmark on real content
