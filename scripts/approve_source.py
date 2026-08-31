"""File a rights record against a parsed chapter, and approve it (§5).

    PYTHONPATH=src python scripts/approve_source.py \
        --chapter artifacts/quadratic-equations-quarantine \
        --owner "NCERT" \
        --legal-basis "..." \
        --evidence-uri "https://..." \
        --approved-by "Mayank" \
        --scanned-clean

Approval is a human act against a checksum, which is why this is a script a
person runs and not a flag a pipeline sets. It writes `rights.json` beside the
artefact, records the checksum the record was filed against, and only then
moves the manifest to APPROVED.

**A verbal assurance is not a rights record.** `RightsRecord` has no field for
one on purpose. Every argument below is required because each is something a
rights holder either granted or did not, and "we think it's fine" is not a
value any of them can take. If the answer to `--permits-display` is unknown,
the source is not approvable yet -- that is the question being asked, not
paperwork about it.

Re-parsing a chapter changes its checksum and invalidates the approval, by
design: a rights record filed against different bytes approves a different
source, whatever the directory is called.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.contracts.common import ApprovalState
from agts.contracts.objects import RightsRecord


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chapter", required=True, type=Path,
                        help="artefact directory holding manifest.json")
    parser.add_argument("--owner", required=True,
                        help="who owns the rights, not who is using them")
    parser.add_argument("--legal-basis", required=True,
                        help="the licence, permission or statutory basis relied on")
    parser.add_argument("--evidence-uri", required=True,
                        help="link to the signed record; a claim without one is a claim")
    parser.add_argument("--approved-by", required=True, help="a named human")
    parser.add_argument("--attribution", default=None,
                        help="attribution string the licence requires, if any")
    parser.add_argument("--territories", nargs="*", default=[],
                        help="territories the grant covers; empty means unrestricted")
    parser.add_argument("--term-expires", default=None,
                        help="ISO date the grant lapses, if it does")
    parser.add_argument("--scanned-clean", action="store_true",
                        help="confirm the malware/injection scan completed (§7.1)")
    for permission in ("storage", "transformation", "display", "model-processing"):
        parser.add_argument(f"--no-{permission}", action="store_true",
                            help=f"the grant does NOT permit {permission}")
    args = parser.parse_args()

    manifest_path = args.chapter / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"no manifest at {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if not args.scanned_clean:
        raise SystemExit(
            "refusing to approve without --scanned-clean: §7.1 requires the scan to "
            "have completed before a parser saw the file, and this flag is where you "
            "state that it did."
        )

    record = RightsRecord(
        owner=args.owner,
        legal_basis=args.legal_basis,
        permits_storage=not args.no_storage,
        permits_transformation=not args.no_transformation,
        permits_display=not args.no_display,
        permits_model_processing=not args.no_model_processing,
        attribution_required=args.attribution,
        territories=list(args.territories),
        term_expires=(
            datetime.fromisoformat(args.term_expires).date() if args.term_expires else None
        ),
        approved_by=args.approved_by,
        approved_at=datetime.now(UTC),
        evidence_uri=args.evidence_uri,
    )

    if not record.permits_display:
        print("note: the grant does not permit display. The source can be stored and "
              "measured against, and a pack built from it must not be shown.")

    (args.chapter / "rights.json").write_text(
        record.model_dump_json(indent=2), encoding="utf-8"
    )

    manifest["approval_state"] = ApprovalState.APPROVED.value
    # The checksum the record was filed against, kept separately so a re-parse
    # that changes `sha256` makes the mismatch visible instead of silent.
    manifest["rights_checksum_sha256"] = manifest["sha256"]
    manifest["scanned_clean_at"] = datetime.now(UTC).isoformat()
    manifest["publication"] = "PERMITTED" if record.permits_display else "STORAGE_ONLY"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"{manifest['source_id']}: APPROVED")
    print(f"  rights filed by {record.approved_by} against {manifest['sha256'][:16]}...")
    print(f"  evidence: {record.evidence_uri}")
    print("\nThe evaluation licence is no longer needed for this source. Re-run the "
          "baseline to produce numbers that are not labelled 'measurement only'.")


if __name__ == "__main__":
    main()
