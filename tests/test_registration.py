"""Registering a signed rights record (sections 5 and 7.1).

The checks here are the ones that decide whether an approval means anything.
Each test is a way an approval could be recorded and be worthless.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from agts.contracts.common import ApprovalState, AuthorityTier, Board, Language
from agts.contracts.objects import SourceRecord

_spec = importlib.util.spec_from_file_location(
    "register_source", Path(__file__).parents[1] / "scripts" / "register_source.py"
)
register_source = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(register_source)


def source(checksum: str = "a" * 64) -> SourceRecord:
    return SourceRecord(
        source_id="s1", title="T", publisher="NCERT", board=Board.CBSE,
        edition="2026-27", checksum_sha256=checksum,
        authority_tier=AuthorityTier.BOARD_OFFICIAL, language=Language.EN,
        approval_state=ApprovalState.QUARANTINED,
    )


def payload(**overrides):
    rights = {
        "owner": "NCERT",
        "legal_basis": "written permission",
        "permits_storage": True,
        "permits_transformation": True,
        "permits_display": True,
        "permits_model_processing": True,
        "approved_by": "A Named Human",
        "approved_at": datetime(2026, 8, 31, tzinfo=UTC).isoformat(),
        "evidence_uri": "file://signed.pdf",
    }
    rights.update(overrides.pop("rights", {}))
    body = {"source_id": "s1", "rights": rights,
            "scanned_clean_at": datetime(2026, 8, 31, tzinfo=UTC).isoformat()}
    body.update(overrides)
    return body


def test_a_complete_record_against_the_right_file_passes() -> None:
    assert register_source.check(payload(), source(), "a" * 64) == []


def test_a_checksum_mismatch_is_refused() -> None:
    """Section 5 approves a specific checksum and version. A revised edition is
    a new registration, not an update to this one."""
    problems = register_source.check(payload(), source(), "b" * 64)
    assert any("checksum mismatch" in p for p in problems)


def test_a_missing_scan_is_refused() -> None:
    """Approval means a parser may read the file, so the scan precedes it."""
    problems = register_source.check(payload(scanned_clean_at=None), source(), "a" * 64)
    assert any("scanned_clean_at" in p for p in problems)


def test_a_record_without_a_named_human_does_not_validate() -> None:
    """The contract has no field for a verbal assurance and neither does this."""
    problems = register_source.check(
        payload(rights={"approved_by": ""}), source(), "a" * 64
    )
    assert problems and "does not validate" in problems[0]


def test_a_record_without_evidence_does_not_validate() -> None:
    problems = register_source.check(
        payload(rights={"evidence_uri": ""}), source(), "a" * 64
    )
    assert problems and "does not validate" in problems[0]


def test_forbidding_model_processing_is_a_contradiction_not_a_footnote() -> None:
    """Chapter text goes to a third-party embedding provider. A record that
    forbids that forbids the current design."""
    problems = register_source.check(
        payload(rights={"permits_model_processing": False}), source(), "a" * 64
    )
    assert any("permits_model_processing" in p for p in problems)


def test_forbidding_transformation_or_display_is_refused() -> None:
    assert any("transformation" in p for p in register_source.check(
        payload(rights={"permits_transformation": False}), source(), "a" * 64))
    assert any("display" in p for p in register_source.check(
        payload(rights={"permits_display": False}), source(), "a" * 64))


def test_an_expired_term_is_refused() -> None:
    expired = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
    problems = register_source.check(
        payload(rights={"term_expires": expired}), source(), "a" * 64
    )
    assert any("term expired" in p for p in problems)


def test_an_unverified_checksum_is_allowed_but_only_when_no_file_is_given() -> None:
    """The script warns loudly instead. Refusing outright would block
    registering a source whose file lives somewhere the operator cannot mount."""
    assert register_source.check(payload(), source(), None) == []
