# Dependency map

## External dependencies, and what each one gates

| Dependency | Owner | Gates | State |
|---|---|---|---|
| Pilot curriculum named (grade, units, board, edition) | Client | §6.1, §6.4, §7.1 | **Open — Q1** |
| Signed rights record per source | Client / legal | §7.1 and everything downstream | **Open — Q3** |
| Approved source files delivered | Client | §7.2 parsing | Not delivered |
| Curriculum reviewer availability | Client | §6.1 sign-off, §13 adjudication | Unconfirmed |
| Privacy / security reviewer | Client | §13, §14 | Unconfirmed |
| Embedding + rerank credentials (Voyage) | Us | §7.3, §7.4 | **Provisioned and used** — `voyage-3` embeddings and `rerank-2`, both cached to disk so a scored run reaches no network |
| Generation credentials (VLM, teaching model) | Us / client | §9.2 | Not provisioned — nothing generates text yet |
| Postgres with vector support | Us | §7.4, §8.2 | **Provisioned** — own container, `docker/compose.yml` port 5434, pgvector 0.8.6 (R-029) |
| **GPU for parsing** | Us / client | §7.3 at any real corpus size | **Not provisioned — now a requirement, see below** |
| **Mathpix API key** | Client | formula extraction (R-008) | Not provisioned, blocks the deciding test |

### GPU is a requirement, not an optimisation

Measured on CPU over one 16-page chapter (`EVALUATION_LEDGER.md`):

| Configuration | Per page | 5,000 pages |
|---|---:|---:|
| opendataloader deterministic | 1s | ~1.4 hours |
| Docling (August bake-off) | 47s | ~65 hours |
| Docling (re-parse, 30 August) | **8.4s** | ~12 hours |
| Docling + formula enrichment | 178s | ~247 hours |

The 8.4s/page figure is the same document and the same configuration on a
newer Docling and RapidOCR build. It is recorded rather than replacing the
earlier number, because the conclusion depends on which one holds at scale
and one re-parse of one chapter is not enough to retire a measurement.

NCERT 6-12 across subjects is several thousand pages, and §15 expands beyond that.
Parsing is the expensive, effectively irreversible stage, so it is also the one
that cannot be quietly deferred. Note the second strategy is nearly free — running
opendataloader alongside Docling satisfies §7.2's dual-parse requirement for about
1% of the wall clock.

Build guide §4: the clock pauses when one of these is unavailable, and a paused
external dependency is **not** hidden as engineering completion.

## Internal build order

```
contracts  ──▶ evaluation spine ──▶ scorer ──▶ §6.5 detection      [DONE]
                                        │
                                        ▼
             source registry ──▶ parse ──▶ objects ──▶ representations
                    │                                        │
              needs Q1 + Q3                                  ▼
                                              query planning ──▶ candidates
                                                                  │
                                                                  ▼
                                              bundle composer ──▶ sufficiency
                                                                  │
                                                                  ▼
                                                    teaching loop (scope: Q5)
```

Everything through the sufficiency gate is **built and measured on two real
chapters**, held `QUARANTINED` under an evaluation licence (R-011): parsing,
composition, representations, BM25, embeddings, hybrid, the §8.4 gate, evidence
packs, citation scoring, release manifests and traces.

What Q1 and Q3 still gate is **registration and publication**, not construction —
no source can reach `APPROVED`, so nothing here may be served to a learner. The
teaching loop on the right remains scope-blocked on Q5.

## Software

Python 3.12, pydantic 2.12, pytest. Postgres 17 with pgvector, reached through
psycopg2. HTTP to Voyage for embeddings and reranking, through `requests`, behind
ports in `platform/` — **no provider name appears outside that package** (§7.3).

Every provider call is cached to disk by content hash, so a scored run reaches no
network and costs nothing to repeat. The 145 unit tests need neither: 7 of them
are integration tests that skip unless `AGTS_DATABASE_URL` is set, and the rest
run against fixtures and a deterministic fake embedder.
