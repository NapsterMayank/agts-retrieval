# Dependency map

## External dependencies, and what each one gates

| Dependency | Owner | Gates | State |
|---|---|---|---|
| Pilot curriculum named (grade, units, board, edition) | Client | §6.1, §6.4, §7.1 | **Open — Q1** |
| Signed rights record per source | Client / legal | §7.1 and everything downstream | **Open — Q3** |
| Approved source files delivered | Client | §7.2 parsing | Not delivered |
| Curriculum reviewer availability | Client | §6.1 sign-off, §13 adjudication | Unconfirmed |
| Privacy / security reviewer | Client | §13, §14 | Unconfirmed |
| Provider credentials and quota (embedding, rerank, VLM, generation) | Us / client | §7.3, §7.4, §9.2 | Not provisioned |
| Postgres with vector support | Us | §7.4, §8.2 | Not provisioned |
| **GPU for parsing** | Us / client | §7.3 at any real corpus size | **Not provisioned — now a requirement, see below** |
| **Mathpix API key** | Client | formula extraction (R-008) | Not provisioned, blocks the deciding test |

### GPU is a requirement, not an optimisation

Measured on CPU over one 16-page chapter (`EVALUATION_LEDGER.md`):

| Configuration | Per page | 5,000 pages |
|---|---:|---:|
| opendataloader deterministic | 1s | ~1.4 hours |
| Docling | 47s | ~65 hours |
| Docling + formula enrichment | 178s | ~247 hours |

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

Nothing to the right of the source registry can start on real content until Q1
and Q3 land. Everything to the left of it is done.

## Software

Python 3.12, pydantic 2.12, pytest. No database, no provider SDK and no network
call yet — deliberately, so the contracts and the ruler are provable in isolation
before anything expensive is wired to them.
