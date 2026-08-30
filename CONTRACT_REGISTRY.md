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
| `ReleaseManifest` | `contracts/runtime.py` | non-empty object and source sets; checksum shape |

## §6.2 typed learning objects

| Contract | Module | Notes |
|---|---|---|
| `RightsRecord` | `contracts/objects.py` | named approver, date and evidence link required; no field for a verbal assurance |
| `SourceRecord` | `contracts/objects.py` | `APPROVED` requires rights **and** a completed scan; default `QUARANTINED` |
| `SourceBlock` | `contracts/objects.py` | must carry text, latex or an image; records its parse strategy |
| `CurriculumIdentity` | `contracts/objects.py` | curriculum truth, defined before embeddings exist |
| `LearningObject` | `contracts/objects.py` | solutions, answers and rubrics may not be `PUBLIC` |
| `SearchRepresentation` | `contracts/objects.py` | non-empty search text and vector; separate from the object |

## Supporting

| Contract | Module | Notes |
|---|---|---|
| `DisclosurePolicy` | `contracts/runtime.py` | may lower the ceiling implied by assessment state, never raise it |
| `FallbackPolicy` | `contracts/runtime.py` | at most one corrective retrieval; terminal state must be safe |
| `EvalCase` / `GoldSet` | `evaluation/cases.py` | gold matches answerability; unique case ids |

## Versioning

Contracts are frozen and forbid extra fields, so any change is a visible diff.
A change that removes or weakens a validator needs a `DECISION_LOG.md` entry
naming the gate it affects.
