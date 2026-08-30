# Authority and conflict order

Transcribed from the client build guide §2. If documents disagree, the higher
authority wins.

| Priority | Authority | Purpose |
|---:|---|---|
| 1 | Founder-approved Alfanumrik Grounded Teaching System architecture | Product, learning, safety and governance invariants |
| 2 | Client AI-native build guide (22 August 2026) | Implementation order, gates and delivery clock |
| 3 | Versioned implementation specifications | Schemas, APIs, algorithms, thresholds, provider adapters |
| 4 | Decision log and release evidence | Why a decision was made, and proof it passed |

**No older local specification may silently override the approved clean-sheet
architecture.**

## What that demotes

`foxxy/docs/superpowers/specs/2026-08-20-ncert-rag-design.md` (v2, 21 August) and
`foxxy/docs/superpowers/plans/2026-08-21-rag-build-guide.md` were authority-1 and
-2 for Track B until 22 August. They are now **authority 3** — implementation
detail, consulted where the client guide is silent, overridden where it is not.

Both documents remain useful and neither should be deleted:

| Still load-bearing | Where |
|---|---|
| pgvector HNSW pre-filter recall trap, `ef_search` per pool | old spec §3.1 |
| block/object separation rationale | old spec §4.1 |
| composition rules, small-to-big sizes | old spec §5.2 |
| runnable Phase 0 parse/chunk/embed/score code | `2026-08-21-phase-0-howto.md` |

## Traceability

Every implementation specification in this repository must carry a table mapping
its sections back to the architecture and to the client build guide. A schema
that cannot name the requirement it serves is not traceable, and §12 requires
decision and contract traceability in the release packet.

## Foxxy

Foxxy is a **post-design comparator only** (build guide §1). Its retrieval module
must not shape a decision here. Its *defect history* is a different thing and is
legitimately used as test material — a corpus that was 25% exact duplicates, and
objects published with no vector, are both real failure modes worth a gate.
