# Workstream ownership

Build guide §4. Exclusive file and domain ownership; handoffs go through
versioned contracts, never copied implementations.

| Workstream | Owns (paths) | Must not own |
|---|---|---|
| Architecture and contracts | `src/agts/contracts/`, `docs/`, `CONTRACT_REGISTRY.md`, `DECISION_LOG.md` | Production approval |
| Content and curriculum | `src/agts/content/`, source registry, parsing, curriculum graph | Rights or academic self-approval |
| Retrieval and verification | `src/agts/retrieval/`, `src/agts/verification/` | Learner mastery |
| Teaching and assessment | `src/agts/teaching/` — **pending the scope answer in Q5** | Unrestricted answer generation |
| Platform and security | `src/agts/platform/`, migrations, jobs, adapters, observability | Curriculum decisions |
| Evaluation and assurance | `src/agts/evaluation/`, `tests/`, `EVALUATION_LEDGER.md` | Sole model-as-judge release authority |

Six directories exist now:

| Path | Workstream | State |
|---|---|---|
| `src/agts/contracts/` | Architecture and contracts | frozen, versioned |
| `src/agts/evaluation/` | Evaluation and assurance | ruler, licence, citation scorers |
| `src/agts/parsing/` | Content and curriculum | two strategies, dual-parse diff |
| `src/agts/retrieval/` | Retrieval and verification | chunking, BM25, dense, hybrid, rerank, sufficiency, packing, provenance |
| `src/agts/platform/` | Platform and security | embedding and rerank ports, Postgres repository, migrations |
| `src/agts/service/` | Platform and security | the HTTP surface. Owns no retrieval logic: it builds a plan, calls the gate, and refuses (R-034) |

`src/agts/teaching/` does not exist and will not until Q5 answers whether this
repository builds §9 or consumes it.

**One boundary was crossed knowingly.** The same agent has been writing both the
retrieval stages and the ruler that scores them, which is exactly what the
workstream split exists to prevent. The mitigation is that every retrieval change
was measured against an unchanged scorer and a control (an identity reranker, a
no-carry-in baseline, four floor derivations), and that the §6.5 detection suite
never stopped passing. It is a weaker guarantee than two teams and it is written
down rather than assumed away.

## The boundary that matters most

Evaluation owns the ruler and does not own the thing being measured. A retrieval
change that also edits `src/agts/evaluation/scorer.py` is marking its own
homework, and the §6.5 detection suite is the check on that — it is the one test
that must keep passing no matter which workstream is touching what.

## Human approval is not a workstream

No agent may approve copyright rights, curriculum correctness, child-data policy,
assessment boundaries or evidence of student learning (§3). Those are named human
sign-offs recorded in `RELEASE_EVIDENCE.md`.
