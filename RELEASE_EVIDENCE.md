# Release evidence

Build guide §12. One reproducible candidate, or nothing.

**No release candidate exists.** This file is the shape the packet must take, and
the empty rows are the honest state.

| Required by §12 | State |
|---|---|
| Commit and immutable artifact IDs | Not committed yet |
| Schema and migration versions | Contracts versioned in code; no migrations exist |
| Source and release manifests | `ReleaseManifest` contract exists; no manifest built |
| Model, embedding, reranker, parser and prompt versions | None wired |
| Decision and contract traceability | `DECISION_LOG.md`, `CONTRACT_REGISTRY.md`, `docs/00-authority.md` |
| Unedited test and benchmark results | `EVALUATION_LEDGER.md` — fixture-only, stated as such |
| RLS / authorization matrix | Not built |
| Hidden-holdout runner config | `score(..., include_holdout=True)`; no holdout sealed |
| Load, failure and recovery evidence | Not built |
| Dashboards, alerts, synthetic checks | Not built |
| Known risks and exceptions | `CONFLICT_REGISTER.md`, `docs/03-open-questions.md` |
| Rollout, rollback and ownership | Not built |
| Required reviewer sign-offs | **None obtained** |

## Human sign-offs required before `PILOT_READY`

No agent may self-approve any of these (§3).

| Sign-off | Named reviewer | Date |
|---|---|---|
| Source rights and lineage | — | — |
| Curriculum concept map and content | — | — |
| Release-critical gold set, two adjudicators | — | — |
| Hindi / Hinglish and diagram review | — | — |
| Privacy, security, assessment boundary | — | — |
| Founder review of the packet and pilot criteria | — | — |

Outcome is `PILOT_READY`, `CONDITIONALLY_BLOCKED` with named corrections, or
`REJECTED`. There is no silent waiver.
