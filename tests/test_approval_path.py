"""Leaving QUARANTINED, and the checks that make it mean something (§5).

A rights record is what separates "we may measure against this" from "we may
show this to a learner". The contract has no field for a verbal assurance, and
these pin the three ways an approval could be claimed without being real: no
record filed, a record filed against different bytes, and no completed scan.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from agts.contracts.common import ApprovalState
from agts.contracts.objects import RightsRecord
from agts.evaluation.corpus import EvaluationLicence
from agts.evaluation.quarantine import ChapterArtefact, load_corpus

CHECKSUM = "a" * 64
OTHER_CHECKSUM = "b" * 64


def rights_record(**overrides) -> RightsRecord:
    base = dict(
        owner="Example Board",
        legal_basis="written licence, ref 2026/17",
        permits_storage=True,
        permits_transformation=True,
        permits_display=True,
        permits_model_processing=True,
        approved_by="A Named Human",
        approved_at=datetime.now(UTC),
        evidence_uri="https://example.invalid/signed/2026-17.pdf",
    )
    base.update(overrides)
    return RightsRecord(**base)


def build_chapter(tmp_path: Path, **manifest_overrides) -> ChapterArtefact:
    directory = tmp_path / "chapter"
    directory.mkdir()
    manifest = {
        "source_id": "example-ch01",
        "approval_state": ApprovalState.QUARANTINED.value,
        "sha256": CHECKSUM,
    }
    manifest.update(manifest_overrides)
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (directory / "source-blocks.jsonl").write_text("", encoding="utf-8")
    (directory / "learning-objects.jsonl").write_text("", encoding="utf-8")
    return ChapterArtefact(
        directory=directory, title="Chapter One", publisher="Example Board",
        edition="Science, Class X, 2026-27",
    )


def approve(chapter: ChapterArtefact, *, checksum: str = CHECKSUM, scanned: bool = True,
            record: RightsRecord | None = None) -> None:
    (chapter.directory / "rights.json").write_text(
        (record or rights_record()).model_dump_json(), encoding="utf-8"
    )
    manifest = chapter.manifest()
    manifest["approval_state"] = ApprovalState.APPROVED.value
    manifest["rights_checksum_sha256"] = checksum
    if scanned:
        manifest["scanned_clean_at"] = datetime.now(UTC).isoformat()
    (chapter.directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_an_approved_artefact_needs_no_evaluation_licence(tmp_path) -> None:
    chapter = build_chapter(tmp_path)
    approve(chapter)
    corpus = load_corpus([chapter], with_representations=False)
    assert corpus.sources["example-ch01"].approval_state is ApprovalState.APPROVED
    assert corpus.sources["example-ch01"].rights is not None


def test_a_quarantined_artefact_without_a_licence_is_refused(tmp_path) -> None:
    """Not an empty candidate set, which would read as a broken retriever."""
    chapter = build_chapter(tmp_path)
    with pytest.raises(ValueError, match="no evaluation licence"):
        load_corpus([chapter], with_representations=False)


def test_approved_without_a_filed_record_is_refused(tmp_path) -> None:
    """The manifest is a file, and a file can be edited."""
    chapter = build_chapter(
        tmp_path, approval_state=ApprovalState.APPROVED.value,
        rights_checksum_sha256=CHECKSUM,
        scanned_clean_at=datetime.now(UTC).isoformat(),
    )
    with pytest.raises(ValueError, match="no rights.json"):
        chapter.source()


def test_a_record_filed_against_other_bytes_is_refused(tmp_path) -> None:
    """Approval is per checksum: a re-parse invalidates it, by design."""
    chapter = build_chapter(tmp_path)
    approve(chapter, checksum=OTHER_CHECKSUM)
    with pytest.raises(ValueError, match="Re-approve against the current bytes"):
        chapter.source()


def test_approved_without_a_completed_scan_is_refused(tmp_path) -> None:
    chapter = build_chapter(tmp_path)
    approve(chapter, scanned=False)
    with pytest.raises(ValueError, match="requires a completed scan"):
        chapter.source()


def test_a_licence_still_covers_a_quarantined_artefact(tmp_path) -> None:
    """The measuring path does not regress while approval exists beside it."""
    chapter = build_chapter(tmp_path)
    licence = EvaluationLicence(
        reason="measuring",
        granted_by="tester",
        granted_on=date.today(),
        source_ids=("example-ch01",),
    )
    corpus = load_corpus([chapter], licence=licence, with_representations=False)
    assert corpus.sources["example-ch01"].approval_state is ApprovalState.QUARANTINED
