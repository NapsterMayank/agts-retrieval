# AGTS retrieval and evidence fabric

Implementation of the client's **Alfanumrik Grounded Teaching RAG — AI-Native
Build Guide** (revised 22 August 2026).

This repository is Track B. It does not modify, refactor or migrate Foxxy's
`retrieval` module, which stays live and demoed.

## Status — 31 August 2026

A grounded retrieval pipeline runs end to end over two real NCERT chapters:
parse, compose, chunk, embed, rank, decide whether the question can be answered
at all, assemble a cited evidence pack, record what produced it — and serve the
whole thing over HTTP.

| | visible 140 | holdout 64 |
|---|---:|---:|
| Unanswerable questions refused | 31/31 | **24/24** — supports ≥88% |
| Answerable questions answered | 90/109 | **34/40** — supports ≥73% |
| Citation completeness (§14 bar ≥95%) | 95.2% | **97.1%** |
| Citation ID resolution (§14 bar 100%) | 100% | **100%** |
| Lineage failures (§14 bar 0) | 0 | **0** |

The bounds are exact one-sided Clopper-Pearson at 95% (R-039). The set covers
four phrasings of the same questions — textbook, short, spoken and
mistyped — because refusing a full sentence and answering its four-word
version is not refusing the concept (R-047).

An outside model reviewed all 48 release-critical claims against the chapter
text and found **three wrong answer keys** and three code defects (R-036). All
were verified and fixed; the numbers above are after those fixes, and the
thresholds were **not** re-tuned to recover the case each fix cost.

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
| §8 serving surface | `src/agts/service/` |

Not built, and why: **generation and the teaching loop** (§9) are scope-blocked
on Q5, which also makes §14's citation *precision* row unmeasurable — it asks
whether a citation supports a sentence, and there are no sentences (R-026).

## Run it

```
pip install -e ".[dev]"
python -m pytest -q                      # 148 pass, 7 skip without a database
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

## Serving

```
docker compose -f docker/compose.yml up -d
AGTS_DATABASE_URL=postgresql://agts:agts_dev_password@localhost:5434/agts_dev \
AGTS_EMBEDDING_CACHE=artifacts/embeddings/voyage-3.json \
AGTS_ABSTAIN_FLOOR=0.737 AGTS_HIGH_CONFIDENCE=0.800 \
AGTS_RELEASE_MANIFEST_ID=rm-pilot-2-chapters-0001 \
AGTS_API_TOKENS=dev-token:tenant-dev VOYAGE_API_KEY=... \
PYTHONPATH=src python scripts/serve.py
```

`GET /health` reports the manifest, corpus checksum and thresholds.
`POST /v1/evidence` takes a question and a curriculum scope and returns cited
evidence or a refusal with its reason. It **does not generate text** — that is
the teaching loop, which does not exist (Q5).

It will refuse to start against the corpus above, because no source is
`APPROVED`. That is the intended behaviour; the override
(`AGTS_ALLOW_QUARANTINED_CONTENT=yes-i-accept-unapproved-content`) exists for
development and marks every response `unapproved_content: true`.

**Known limit, found by running it (R-035):** the gate is sensitive to phrasing.
*"How do you solve a quadratic equation by completing the square?"* is correctly
refused; *"How do you solve by completing the square?"* is answered. The gold set
is written in one register and the thresholds are fitted to it, so the 8/8
refusal figure describes the questions as written rather than the concepts.

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
src/agts/service/       the HTTP surface: evidence with citations, or a refusal
migrations/             core schema, and pgvector as a separate opt-in
tests/                  contract invariants, the §6.5 suite, integration tests
docs/                   authority order, gates, workstreams, open questions
scripts/                every number in the ledger is reproducible from one of these
```

## Where to start reading

**`docs/04-how-to-continue.md`** — written for whoever picks this up next. What
the system is, where it stands, the five rules this repository follows, what has
already been measured and rejected, and what is blocked on whom.

## The rest

`EVALUATION_LEDGER.md` for what was measured and what it cost, `DECISION_LOG.md`
for why each thing is the way it is — including the hypotheses that were wrong
(R-022, R-027, R-030, R-032), which are recorded so they are not re-tried.
