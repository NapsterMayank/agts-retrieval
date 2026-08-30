# AGTS retrieval and evidence fabric

Implementation of the client's **Alfanumrik Grounded Teaching RAG — AI-Native
Build Guide** (revised 22 August 2026).

This repository is Track B. It does not modify, refactor or migrate Foxxy's
`retrieval` module, which stays live and demoed.

## Status — 30 August 2026

A grounded retrieval pipeline runs end to end over two real NCERT chapters:
parse, compose, chunk, embed, rank, decide whether the question can be answered
at all, assemble a cited evidence pack, and record what produced it.

| | visible 60 | holdout 38 |
|---|---:|---:|
| Unanswerable questions refused | 10/10 | **8/8** |
| Answerable questions answered | 48/50 | **27/30** |
| Citation completeness (§14 bar ≥95%) | 97.2% | **96.3%** |
| Citation ID resolution (§14 bar 100%) | 100% | **100%** |
| Lineage failures (§14 bar 0) | 0 | **0** |

The holdout cases were written after every threshold was fixed and were not
consulted while choosing any of them, so **the holdout column is the one that
should be quoted** (R-024).

**Nothing here is releasable.** Every number was produced under an evaluation
licence over `QUARANTINED` content (R-011), no source has a rights record, the
gold set is 98 cases against §6.4's 300-500, and no human has adjudicated any of
it. See `RELEASE_EVIDENCE.md`.

## What is built

| Build guide | Delivered here |
|---|---|
| §6.2 typed learning objects | `src/agts/contracts/objects.py` |
| §6.3 runtime contracts | `src/agts/contracts/runtime.py` |
| §6.4 evaluation cases, §6.5 test the tester | `src/agts/evaluation/` |
| §7.1 / §7.2 parsing, two strategies, dual-parse diff | `src/agts/parsing/` |
| §7.4 composition | `src/agts/composition.py` |
| §7.3 search representations, BM25, embeddings, hybrid, rerank | `src/agts/retrieval/` |
| §8.3 evidence packs, §8.4 sufficiency gate | `src/agts/retrieval/packing.py`, `sufficiency.py` |
| §11 traces, §14 lineage gate | `src/agts/retrieval/provenance.py` |
| §7.1 persistence | `migrations/`, `src/agts/platform/repository.py` |
| Provider ports (no provider name escapes them) | `src/agts/platform/` |

Not built, and why: **generation and the teaching loop** (§9) are scope-blocked
on Q5, which also makes §14's citation *precision* row unmeasurable — it asks
whether a citation supports a sentence, and there are no sentences (R-026).

## Run it

```
pip install -e ".[dev]"
python -m pytest -q                      # 131 pass, 7 skip without a database
python scripts/baseline.py               # the §6.5 detection suite on fixtures
```

Against the real chapters (they are not committed — see below):

```
VOYAGE_API_KEY=... python scripts/embed_representations.py   # once, then cached
python scripts/real_content_baseline.py    # retrievers, gate, slices
python scripts/holdout_validation.py       # the number that gets quoted
python scripts/citation_report.py          # §14 citation and lineage rows
python scripts/rerank_benchmark.py         # measured, and switched off (R-027)
```

With a database:

```
docker compose -f docker/compose.yml up -d
AGTS_DATABASE_URL=postgresql://agts:agts_dev_password@localhost:5434/agts_dev \
    python scripts/import_corpus.py        # imports, reads back, re-scores
```

## The content is not committed

`artifacts/*-quarantine/` holds the parsed chapters. The blocks **are** the
chapter text and the assets are page crops, both quarantined pending rights
records, so they are gitignored: a local commit is not publication, but history
outlives the decision to push. Regenerate with
`scripts/assemble_*_quarantine.py` and `scripts/compose_*.py`.

`src/agts/evaluation/fixtures.py` is synthetic, carries no curriculum content and
must never reach a student.

## Layout

```
src/agts/contracts/     frozen schemas - every workstream handoff goes through these
src/agts/evaluation/    the ruler: cases, corpus, retrievers, scorer, citations
src/agts/parsing/       Docling and opendataloader adapters, dual-parse diff
src/agts/retrieval/     chunking, BM25, dense, hybrid, rerank, sufficiency, packing
src/agts/platform/      embedding and rerank ports, Postgres repository
migrations/             core schema, and pgvector as a separate opt-in
tests/                  contract invariants, the §6.5 suite, integration tests
docs/                   authority order, gates, workstreams, open questions
scripts/                every number in the ledger is reproducible from one of these
```

## Where to start reading

`EVALUATION_LEDGER.md` for what was measured and what it cost, `DECISION_LOG.md`
for why each thing is the way it is — including the hypotheses that were wrong
(R-022, R-027, R-030, R-032), which are recorded so they are not re-tried.
