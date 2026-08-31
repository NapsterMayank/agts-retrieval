"""Register a signed rights record and approve a source (sections 5 and 7.1).

This is the mechanism behind the signature. Someone with authority fills in a
rights record, this reads it, checks it against the file it claims to cover, and
moves that source from `QUARANTINED` to `APPROVED` — after which the serving API
will start without an override and the content may reach a learner.

    PYTHONPATH=src python scripts/register_source.py --list
    PYTHONPATH=src python scripts/register_source.py --template > rights.json
    PYTHONPATH=src python scripts/register_source.py --rights rights.json --file chapter.pdf
    PYTHONPATH=src python scripts/register_source.py --rights rights.json --file chapter.pdf --apply

Four things it refuses to do, because each is how an approval becomes
meaningless:

**It will not approve a source whose checksum does not match the file.** §5
approves a *specific checksum and version*, so approval must be tied to bytes
rather than to a title. A revised edition is a new registration.

**It will not accept a rights record without a named human and an evidence
link.** The contract has no field for a verbal assurance and neither does this.

**It will not approve without a recorded malware and injection scan** (§7.1),
because approval means a parser may read the file.

**It will not approve `permits_model_processing: false` while the pipeline
embeds.** Text goes to a third-party embedding provider; a record that forbids
model processing forbids the current design, and that contradiction should stop
a registration rather than be discovered afterwards.

Nothing here approves anything by itself. It is a clerk, not a reviewer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.contracts.common import ApprovalState
from agts.contracts.objects import RightsRecord, SourceRecord
from agts.platform.repository import connect, database_url

TEMPLATE = {
    "source_id": "ncert-class-10-science-ch01-chemical-reactions-and-equations-2026-27",
    "rights": {
        "owner": "NCERT",
        "legal_basis": "state the licence, written permission or statutory basis",
        "permits_storage": True,
        "permits_transformation": True,
        "permits_display": True,
        "permits_model_processing": True,
        "attribution_required": "© NCERT",
        "territories": ["IN"],
        "term_expires": None,
        "approved_by": "the full name of the human who signed",
        "approved_at": "2026-08-31T00:00:00+00:00",
        "evidence_uri": "link to the signed document, not a description of it",
    },
    "scanned_clean_at": "2026-08-31T00:00:00+00:00",
    "scan_tool": "name the scanner used, for the record",
}


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(payload: dict, source: SourceRecord, file_digest: str | None) -> list[str]:
    """Everything that would make this approval meaningless."""
    problems: list[str] = []

    try:
        rights = RightsRecord.model_validate(payload["rights"])
    except Exception as error:
        return [f"rights record does not validate: {error}"]

    if file_digest is not None and file_digest != source.checksum_sha256:
        problems.append(
            f"checksum mismatch: the file is {file_digest[:16]}... and the registered "
            f"source is {source.checksum_sha256[:16]}.... Section 5 approves a specific "
            "checksum and version, so a revised file is a new registration."
        )
    if not payload.get("scanned_clean_at"):
        problems.append(
            "no scanned_clean_at: section 7.1 requires a completed malware and "
            "injection scan before a parser reads the file, and approval means it may."
        )
    if not rights.permits_model_processing:
        problems.append(
            "permits_model_processing is false, and this pipeline sends chapter text "
            "to a third-party embedding provider. That is a contradiction to resolve "
            "before registration, not after."
        )
    if not rights.permits_transformation:
        problems.append("permits_transformation is false: parsing and chunking are transformations.")
    if not rights.permits_display:
        problems.append("permits_display is false: an evidence pack shows extracts to a learner.")
    if rights.term_expires and rights.term_expires < datetime.now(UTC).date():
        problems.append(f"the term expired on {rights.term_expires}.")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rights", type=Path, help="the signed rights record, as JSON")
    parser.add_argument("--file", type=Path, help="the source file the record covers")
    parser.add_argument("--apply", action="store_true", help="write the approval")
    parser.add_argument("--list", action="store_true", help="show every source and its state")
    parser.add_argument("--template", action="store_true", help="print a blank rights record")
    args = parser.parse_args()

    if args.template:
        print(json.dumps(TEMPLATE, indent=2))
        return

    if not database_url():
        raise SystemExit("set AGTS_DATABASE_URL")

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT source_id, title, edition, checksum_sha256, approval_state, "
                "rights IS NOT NULL, scanned_clean_at FROM sources ORDER BY source_id"
            )
            rows = cursor.fetchall()

        if args.list or not args.rights:
            print(f"{'source':<62} {'state':<12} rights scan")
            for source_id, _t, _e, _c, state, has_rights, scanned in rows:
                print(f"{source_id:<62} {state:<12} "
                      f"{'yes' if has_rights else 'no':<6} {'yes' if scanned else 'no'}")
            if not args.rights:
                print("\nPass --rights to register one. --template prints a blank record.")
            return

        payload = json.loads(args.rights.read_text(encoding="utf-8"))
        source_id = payload["source_id"]
        row = next((r for r in rows if r[0] == source_id), None)
        if row is None:
            raise SystemExit(f"{source_id} is not a registered source; import it first")

        source = SourceRecord(
            source_id=row[0], title=row[1], publisher="unknown", edition=row[2],
            checksum_sha256=row[3], authority_tier="board_official", language="en",
            approval_state=ApprovalState(row[4]),
        )
        file_digest = checksum(args.file) if args.file else None
        if args.file is None:
            print("WARNING: no --file given, so the checksum is unverified. Section 5 "
                  "approves a checksum, not a title.\n")

        problems = check(payload, source, file_digest)
        print(f"source:   {source_id}")
        print(f"state:    {source.approval_state.value}")
        print(f"checksum: {source.checksum_sha256[:32]}...")
        if file_digest:
            print(f"file:     {file_digest[:32]}... "
                  f"({'matches' if file_digest == source.checksum_sha256 else 'DOES NOT MATCH'})")

        if problems:
            print(f"\nREFUSED — {len(problems)} problem(s):")
            for problem in problems:
                print(f"  - {problem}")
            raise SystemExit(1)

        rights = RightsRecord.model_validate(payload["rights"])
        print(f"\nrights record is valid: signed by {rights.approved_by} "
              f"on {rights.approved_at:%Y-%m-%d}, evidence at {rights.evidence_uri}")

        if not args.apply:
            print("\nDRY RUN. Nothing was written. Re-run with --apply to approve this source.")
            return

        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE sources SET approval_state = 'APPROVED', rights = %s,
                       scanned_clean_at = %s WHERE source_id = %s""",
                (json.dumps(payload["rights"], default=str), payload["scanned_clean_at"], source_id),
            )
            # Objects are approved with their source: they are derived from it,
            # and an APPROVED source whose objects stay quarantined serves nothing.
            cursor.execute(
                "UPDATE learning_objects SET approval_state = 'APPROVED' WHERE source_id = %s",
                (source_id,),
            )
            objects = cursor.rowcount
        print(f"\nAPPROVED {source_id} and {objects} learning objects.")
        print("The serving API will now start against this source without an override.")


if __name__ == "__main__":
    main()
