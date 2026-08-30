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

Only two directories exist so far. The rest are created by the workstream that
owns them, when it starts.

## The boundary that matters most

Evaluation owns the ruler and does not own the thing being measured. A retrieval
change that also edits `src/agts/evaluation/scorer.py` is marking its own
homework, and the §6.5 detection suite is the check on that — it is the one test
that must keep passing no matter which workstream is touching what.

## Human approval is not a workstream

No agent may approve copyright rights, curriculum correctness, child-data policy,
assessment boundaries or evidence of student learning (§3). Those are named human
sign-offs recorded in `RELEASE_EVIDENCE.md`.
