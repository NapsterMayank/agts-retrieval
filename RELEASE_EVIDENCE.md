# Release evidence

Build guide §12. One reproducible candidate, or nothing.

**No release candidate exists**, and none can: no source is `APPROVED`, so
nothing here may be served to a learner (§5, Q3). What has changed since this
file was written is that most rows now point at something real rather than at an
intention. Updated 30 August 2026.

| Required by §12 | State |
|---|---|
| Commit and immutable artifact IDs | Commits exist; every `ReleaseManifest` carries `commit_sha` and a corpus checksum |
| Schema and migration versions | `migrations/001_core.sql` and `002_pgvector.sql`, applied and tested against Postgres 17 + pgvector 0.8.6 |
| Source and release manifests | **Built** — `provenance.build_manifest` hashes the corpus itself; `rm-pilot-2-chapters-0001` covers 38 objects and 2 sources |
| Model, embedding, reranker, parser and prompt versions | Recorded in every trace: `voyage-3`, `rerank-2`, Docling 2.122.0, `block-window-v2`, no prompt (nothing generates) |
| Decision and contract traceability | `DECISION_LOG.md` (R-001…R-035), `CONTRACT_REGISTRY.md`, `docs/00-authority.md` |
| Unedited test and benchmark results | `EVALUATION_LEDGER.md`, plus `artifacts/gold/*.json` written by the scripts themselves |
| RLS / authorization matrix | Partial — the §5 filter exists in Python **and** in SQL, with a test asserting they agree. No row-level security policy in the database |
| Hidden-holdout runner config | `scripts/holdout_validation.py`, 38 unseen cases. **The seal is not real** — the cases are agent-drafted and unadjudicated (Q2) |
| Load, failure and recovery evidence | Not built |
| Dashboards, alerts, synthetic checks | Not built |
| Known risks and exceptions | `CONFLICT_REGISTER.md`, `docs/03-open-questions.md` |
| Rollout, rollback and ownership | Not built. A serving surface exists (`scripts/serve.py`) and **refuses to start against unapproved content**, which is the opposite of a rollout plan and the right default until there is one |
| Required reviewer sign-offs | **None obtained** |

## What the numbers currently say

Measured over two quarantined chapters, 60 visible and 38 holdout cases. The
holdout column is the one that leaves this repository (R-024).

| | visible | holdout |
|---|---:|---:|
| Unanswerable questions refused | 10/10 | **8/8** |
| Answerable questions answered | 48/50 | **27/30** |
| Citation ID resolution | 100% | 100% |
| Citation completeness (§14 ≥95%) | 97.2% | **96.3%** |
| Delivered recall | 100% | 96.3% |
| Lineage failures | 0 | 0 |
| Zero-tolerance counter violations | 0 | 0 |

**None of this is release evidence.** Every number was produced under an
evaluation licence over `QUARANTINED` content (R-011), the thresholds were fitted
on the visible set, and the gold set is 98 cases against §6.4's 300-500 with zero
adjudicators.

**And the refusal figures are narrower than they look.** Running the service
showed the gate is sensitive to phrasing: dropping four words from *"How do you
solve a quadratic equation by completing the square?"* turns a correct refusal
into an answer (R-035). The table above describes the questions as written, not
the concepts behind them, and the gold set is written in a single register.

## Human sign-offs required before `PILOT_READY`

No agent may self-approve any of these (§3). The release manifest reports
`approved by NOBODY (unsigned)` and will keep doing so until this table is
filled in by people.

| Sign-off | Named reviewer | Date | How it is recorded | What it unblocks |
|---|---|---|---|---|
| Source rights and lineage | — | — | `scripts/register_source.py --rights r.json --file x.pdf --apply` | **Serving anything at all.** The API refuses to boot without it |
| Curriculum concept map and content | — | — | the section map in `scripts/compose_*.py`, reviewed | composition being correct rather than merely consistent |
| Release-critical gold set, two adjudicators | — | — | two routes, same output: `scripts/export_review_sheet.py` (a spreadsheet) or `scripts/review_cases.py` (one case at a time). `scripts/import_review_sheet.py` stamps the names | believing any gate number |
| Hindi / Hinglish and diagram review | — | — | not built — no non-English content exists yet | the language and visual slices |
| Privacy, security, assessment boundary | — | — | not built | Phase 4 |
| Founder review of the packet and pilot criteria | — | — | `ReleaseManifest.approved_by` | `PILOT_READY` |

### What a rights record must contain (section 5)

Owner, legal basis, four permissions (storage, transformation, display, **model
processing**), attribution, territories, term, a **named human**, a date, and a
link to the signed document. There is deliberately no field for a verbal
assurance. `scripts/register_source.py --template` prints the shape.

Registration refuses four ways, each of which is how an approval becomes
meaningless: a checksum that does not match the file (section 5 approves bytes,
not titles), a missing malware scan (section 7.1, and approval means a parser may
read it), a record forbidding model processing while the pipeline embeds through
a third party, and an expired term.

Outcome is `PILOT_READY`, `CONDITIONALLY_BLOCKED` with named corrections, or
`REJECTED`. There is no silent waiver.
