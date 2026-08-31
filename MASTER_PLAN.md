# Master plan

Build guide §18 bands, with what is actually done.

| Band | Target | State |
|---|---|---|
| Phase 0 — ruler and contracts | Hour 0-8 | **Partially done.** Contracts, evaluation spine and the §6.5 detection suite are built and passing. The 300-500 case gold set is blocked on Q1. |
| Phase 1 — governed content | Hour 8-24 | **Blocked** on Q1 and Q3 for *registration*. Parsing and composition are built and exercised on two real chapters, held `QUARANTINED`; nothing is registered or publishable. |
| Phase 2 — retrieval fabric | Hour 16-36 | **Built, holdout-validated, served over HTTP, reviewed by two outside agents.** Representations (R-017, R-022), BM25 (R-019), embeddings and hybrid (R-021), the §8.4 gate with passage-level corroboration (R-020, R-045), query scoping (R-049). On 64 unseen cases in four phrasings: **24/24 unanswerable refused, 34/40 answered**. Five ways to raise acceptance were measured and all five leak (R-052). |
| Phase 3 — grounded teaching loop | Hour 24-48 | Not started, scope pending (Q5). **The retrieval half is now served over HTTP** (R-034): evidence with citations, or a refusal with reasons. Nothing generates text. |
| Phase 4 — security and operations | Hour 36-56 | **Started.** Release manifests, retrieval traces and the §14 lineage gate are built and passing (R-033). Rollback, secrets and abuse handling are not. |
| Phase 5 — combinatorial assurance | Hour 48-68 | Not started. |
| Phase 6 — release candidate | Hour 68-72 | Not started. |
| Human assurance | Days 4-7 | Not started. Needs named reviewers. |

## Phase 0 detail

| §6 requirement | State |
|---|---|
| 6.1 Canonical curriculum spine | Schema done (`CurriculumIdentity`). Content blocked on Q1. |
| 6.2 Typed learning objects | **Done** — `contracts/objects.py` |
| 6.3 Runtime contracts | **Done** — `contracts/runtime.py`, all eight |
| 6.4 Evaluation corpus | Schema done. 9 fixture cases plus **204 real cases** over two chapters in four phrasings, against a target of 300-500. Two model reviews found six wrong keys, all fixed. **Zero of 95 release-critical cases adjudicated** — Q6. |
| 6.5 Test the tester | **Done** — four broken retrievers, all detected |

**Phase 0 exit** is contracts versioned, holdout sealed, reproducible baseline,
scorer demonstrably detects broken retrieval. Three of four met against synthetic
fixtures. The holdout seal is real only once there is a real gold set.

## The clock

Build guide §4: *"The build clock pauses when a required credential, source,
approval or infrastructure dependency is unavailable. A paused external
dependency is not hidden as engineering completion."*

Paused since Hour ~3 on Q1 and Q3. Engineering continues on everything that runs
against synthetic fixtures.
