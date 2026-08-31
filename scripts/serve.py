"""Run the serving API.

    docker compose -f docker/compose.yml up -d
    AGTS_DATABASE_URL=postgresql://agts:agts_dev_password@localhost:5434/agts_dev \
    AGTS_EMBEDDING_CACHE=artifacts/embeddings/voyage-3.json \
    AGTS_ABSTAIN_FLOOR=0.737 \
    AGTS_HIGH_CONFIDENCE=0.800 \
    AGTS_RELEASE_MANIFEST_ID=rm-pilot-2-chapters-0001 \
    AGTS_API_TOKENS=dev-token:tenant-dev \
    VOYAGE_API_KEY=... \
    AGTS_ALLOW_QUARANTINED_CONTENT=yes-i-accept-unapproved-content \
    PYTHONPATH=src python scripts/serve.py

The thresholds are not defaults and not guesses: they are the calibrated floor
and ceiling from `EVALUATION_LEDGER.md`, and the service refuses to start
without them.

`AGTS_ALLOW_QUARANTINED_CONTENT` is only needed while the corpus is
unapproved, which is today and should not be true of anything a learner
touches. Without it the service refuses to boot, on purpose.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.service.app import create_app
from agts.service.config import ConfigurationError, ServiceConfig


def main() -> None:
    os.environ.setdefault(
        "AGTS_COMMIT_SHA",
        subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        or "unknown",
    )
    try:
        config = ServiceConfig.from_env()
    except ConfigurationError as error:
        print(f"refusing to start: {error}", file=sys.stderr)
        raise SystemExit(2)

    import uvicorn

    uvicorn.run(
        create_app(config),
        host=os.environ.get("AGTS_HOST", "127.0.0.1"),
        port=int(os.environ.get("AGTS_PORT", "8000")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
