# Contract registry

Handoffs between workstreams go through these types. Copying an implementation
instead of importing a contract breaks the §4 execution model.

## §6.3 runtime contracts — all eight frozen

| Contract | Module | Invariants enforced at construction |
|---|---|---|
| `QueryPlan` | `contracts/runtime.py` | graded turns cannot request protected evidence; misconception correction needs a hypothesis; at least one evidence slot |
| `EvidenceSlot` | `contracts/runtime.py` | coherent min/max; a required slot needs `min_items >= 1` |
| `EvidencePack` | `contracts/runtime.py` | every citation resolves inside the pack; `SUFFICIENT` requires evidence and a passing gate |
| `TeachingPlan` | `contracts/runtime.py` | — |
| `RetrievalTrace` | `contracts/runtime.py` | at most one corrective retrieval; filters and versions non-empty |
| `VerificationResult` | `contracts/runtime.py` | cannot report `pass` while a gate fails |
| `LearningEvidence` | `contracts/runtime.py` | idempotency key and a named validator required; no mastery field exists |
| `ReleaseManifest` | `contracts/runtime.py` | non-empty object and source sets; checksum shape. Built by hashing the corpus, never by hand (R-033) |
| `RetrievedItem` | `contracts/runtime.py` | a handoff between `retrieval/` and `evaluation/`, so it lives in neither. Carries the blocks a retriever actually used, not its parent object |

## §6.2 typed learning objects

| Contract | Module | Notes |
|---|---|---|
| `RightsRecord` | `contracts/objects.py` | named approver, date and evidence link required; no field for a verbal assurance |
| `SourceRecord` | `contracts/objects.py` | `APPROVED` requires rights **and** a completed scan; default `QUARANTINED` |
| `SourceBlock` | `contracts/objects.py` | must carry text, latex or an image; records its parse strategy |
| `CurriculumIdentity` | `contracts/objects.py` | curriculum truth, defined before embeddings exist |
| `LearningObject` | `contracts/objects.py` | solutions, answers and rubrics may not be `PUBLIC` |
| `SearchRepresentation` | `contracts/objects.py` | non-empty search text; **vector optional** and paired with the model that produced it (R-016); `representation_version` names the chunking function; `context_block_ids` holds what the window is *findable by* but not *made of*, kept separate so it can be cited without inflating recall (R-046) |

## Supporting

| Contract | Module | Notes |
|---|---|---|
| `DisclosurePolicy` | `contracts/runtime.py` | may lower the ceiling implied by assessment state, never raise it |
| `FallbackPolicy` | `contracts/runtime.py` | at most one corrective retrieval; terminal state must be safe |
| `EvalCase` / `GoldSet` | `evaluation/cases.py` | gold matches answerability; unique case ids; `slice_keys` crosses all nine axes pairwise (R-031); `paraphrase_of` and `phrasing` record a rewording and its register, which inherit their parent's label unchanged (R-047) |
| `EvaluationLicence` | `evaluation/corpus.py` | names sources individually, unlocks `QUARANTINED` only, never `RETIRED` or `WITHDRAWN` (R-011) |
| `SufficiencyDecision` | `retrieval/sufficiency.py` | carries the reasons for a refusal, not only the verdict (R-020); carries **both** retrievers' window scores, so the pack admits a sibling on two opinions rather than one (R-045) |

## The serving boundary

`service/app.py` defines `EvidenceRequest`, which is the only shape a caller
controls. It **forbids extra fields**, and the field it most conspicuously lacks
is a tenant: that comes from the bearer token, because a request that names its
own tenant has no tenant boundary (R-034). Everything the service returns is
derived from `EvidencePack`, so the pack contract remains the single description
of what a teaching loop may see.

## Persisted shape

`migrations/001_core.sql` stores these contracts and adds nothing of its own: a
column with no field is a bug rather than a feature. Two invariants are repeated
as CHECK constraints because the database outlives the process that validates —
an `APPROVED` source without rights and a scan cannot exist, and neither can a
`PUBLIC` assessment solution. `002_pgvector.sql` pins embeddings to
`vector(1024)`, so another provider's width cannot be stored by accident.

## Versioning

Contracts are frozen and forbid extra fields, so any change is a visible diff.
A change that removes or weakens a validator needs a `DECISION_LOG.md` entry
naming the gate it affects.
