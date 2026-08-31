"""Service configuration, read once at boot (section 8, section 14).

Two properties matter more than the rest of this file.

**Thresholds are configuration, not something the service computes.** Calibrating
an abstention floor against live traffic means the gate loosens exactly when the
corpus gets harder, and the number in a trace stops matching the number in the
ledger. The floor and ceiling come from a calibration run, are recorded in
`EVALUATION_LEDGER.md`, and arrive here as environment variables.

**Serving quarantined content requires an explicit, ugly opt-in.** Everything
this repository has measured so far ran under an evaluation licence over
`QUARANTINED` chapters (R-011). That is legitimate for measuring and illegitimate
for serving, and the difference is one boolean nobody should be able to cross by
accident — so the service refuses to boot rather than defaulting to permissive.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


class ConfigurationError(RuntimeError):
    """Raised at boot, never at request time. A service that starts and then
    fails every request is harder to diagnose than one that refuses to start."""


@dataclass(frozen=True)
class ServiceConfig:
    #: Where the corpus comes from. A database URL, or None to read the
    #: quarantine artefacts from disk (development only).
    database_url: str | None

    #: Calibrated on a gold set, recorded in the ledger, never derived here.
    abstain_floor: float
    high_confidence: float

    release_manifest_id: str
    commit_sha: str

    #: Bearer token -> tenant id. The request never names its own tenant: a
    #: caller that can choose its tenant has no tenant boundary at all.
    tenant_tokens: dict[str, str] = field(default_factory=dict)

    #: Serving content that no human has approved. Off unless explicitly set,
    #: and every response says so when it is on.
    allow_quarantined: bool = False

    embedding_cache: str | None = None
    #: With a key the vector cache writes through and unseen questions can be
    #: embedded. Without one the service answers only cached questions and says
    #: so in /health.
    embedding_api_key: str | None = None
    k_pack: int = 5
    k_candidates: int = 20

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> ServiceConfig:
        env = dict(environ if environ is not None else os.environ)

        def required(name: str) -> str:
            value = env.get(name, "").strip()
            if not value:
                raise ConfigurationError(
                    f"{name} is required. Retrieval thresholds are calibrated on a "
                    "gold set and recorded in EVALUATION_LEDGER.md; the service "
                    "does not invent them."
                )
            return value

        tokens: dict[str, str] = {}
        for pair in env.get("AGTS_API_TOKENS", "").split(","):
            pair = pair.strip()
            if not pair:
                continue
            token, _, tenant = pair.partition(":")
            if not token or not tenant:
                raise ConfigurationError(
                    "AGTS_API_TOKENS must be token:tenant pairs separated by commas"
                )
            tokens[token] = tenant
        if not tokens:
            raise ConfigurationError(
                "AGTS_API_TOKENS is required. An open endpoint over curriculum "
                "content has no tenant boundary and no way to honour section 5."
            )

        return cls(
            database_url=env.get("AGTS_DATABASE_URL") or None,
            abstain_floor=float(required("AGTS_ABSTAIN_FLOOR")),
            high_confidence=float(required("AGTS_HIGH_CONFIDENCE")),
            release_manifest_id=required("AGTS_RELEASE_MANIFEST_ID"),
            commit_sha=env.get("AGTS_COMMIT_SHA", "unknown"),
            tenant_tokens=tokens,
            allow_quarantined=env.get("AGTS_ALLOW_QUARANTINED_CONTENT") == "yes-i-accept-unapproved-content",
            embedding_cache=env.get("AGTS_EMBEDDING_CACHE") or None,
            embedding_api_key=env.get("VOYAGE_API_KEY") or None,
            k_pack=int(env.get("AGTS_K_PACK", "5")),
            k_candidates=int(env.get("AGTS_K_CANDIDATES", "20")),
        )
