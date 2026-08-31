"""Load a quarantined chapter artefact into a :class:`Corpus`.

The artefacts under `artifacts/*-quarantine/` are the output of the parse and
composition scripts: a manifest, one JSONL of blocks and one of learning
objects. This is the only path from those files into the evaluation harness, and
it constructs sources as `QUARANTINED` — the state they are actually in.

Measuring against them therefore needs an explicit
:class:`~agts.evaluation.corpus.EvaluationLicence`, which is the point: reaching
real content is a decision someone made, not a default.
"""

from __future__ import annotations

import json
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

from agts.contracts.common import ApprovalState, AuthorityTier, Board, Language
from agts.contracts.objects import (
    LearningObject,
    RightsRecord,
    SourceBlock,
    SourceRecord,
)
from agts.evaluation.corpus import Corpus, EvaluationLicence
from agts.retrieval.chunking import represent_all


@dataclass(frozen=True)
class ChapterArtefact:
    """One parsed chapter on disk, with the metadata a `SourceRecord` needs.

    Title, publisher and edition are not in the parse output and are not
    guessable from it, so they are supplied by the caller rather than invented
    here.
    """

    directory: Path
    title: str
    publisher: str
    edition: str
    board: Board = Board.CBSE
    language: Language = Language.EN
    authority_tier: AuthorityTier = AuthorityTier.BOARD_OFFICIAL

    def manifest(self) -> dict:
        return json.loads((self.directory / "manifest.json").read_text(encoding="utf-8"))

    def blocks(self) -> list[SourceBlock]:
        return [
            SourceBlock.model_validate_json(line)
            for line in (self.directory / "source-blocks.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]

    def objects(self) -> list[LearningObject]:
        return [
            LearningObject.model_validate_json(line)
            for line in (self.directory / "learning-objects.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]

    def rights(self) -> RightsRecord | None:
        """The signed rights record beside the manifest, if one has been filed.

        Absent for a quarantined artefact, which is the normal state. Present
        only once a human has filed one against this checksum -- see
        `scripts/approve_source.py`.
        """
        path = self.directory / "rights.json"
        if not path.exists():
            return None
        return RightsRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def source(self) -> SourceRecord:
        manifest = self.manifest()
        state = ApprovalState(manifest["approval_state"])
        if state not in (ApprovalState.QUARANTINED, ApprovalState.APPROVED):
            # RETIRED and WITHDRAWN are how a rights holder takes content back.
            # Neither is a state an evaluation artefact may be loaded in.
            raise ValueError(
                f"{self.directory.name}: manifest claims {state}; "
                "only QUARANTINED or APPROVED artefacts load"
            )

        rights = self.rights()
        scanned = manifest.get("scanned_clean_at")
        if state is ApprovalState.APPROVED:
            # Checked here rather than trusted, because the manifest is a file
            # and a file can be edited. Approval is per *checksum* (§5): a
            # rights record filed against different bytes approves a different
            # source, whatever the directory is called.
            if rights is None:
                raise ValueError(
                    f"{self.directory.name}: manifest says APPROVED but no rights.json "
                    "is filed. Approval is a human act against a checksum (§5); "
                    "run scripts/approve_source.py rather than editing the manifest."
                )
            if manifest.get("rights_checksum_sha256") != manifest["sha256"]:
                raise ValueError(
                    f"{self.directory.name}: the rights record was filed against "
                    f"{manifest.get('rights_checksum_sha256')} but the artefact is "
                    f"{manifest['sha256']}. Re-approve against the current bytes."
                )
            if scanned is None:
                raise ValueError(
                    f"{self.directory.name}: APPROVED requires a completed scan (§7.1)"
                )

        return SourceRecord(
            source_id=manifest["source_id"],
            title=self.title,
            publisher=self.publisher,
            board=self.board,
            edition=self.edition,
            checksum_sha256=manifest["sha256"],
            authority_tier=self.authority_tier,
            language=self.language,
            approval_state=state,
            rights=rights,
            scanned_clean_at=datetime.fromisoformat(scanned) if scanned else None,
        )


def load_corpus(
    artefacts: list[ChapterArtefact],
    *,
    licence: EvaluationLicence | None = None,
    with_representations: bool = True,
    embedder=None,
) -> Corpus:
    """Build a corpus over `artefacts`.

    A licence is required for **quarantined** artefacts and refused for
    approved ones. It is not optional in the sense of "nice to have": a corpus
    of quarantined content without one authorises nothing, and returning an
    empty candidate set from every query reads as a broken retriever rather
    than as a permission the caller never asked for.

    Once a rights record is filed the licence stops being needed, and passing
    one anyway is an error rather than a harmless leftover -- a run that quotes
    a licence has to be a run that needed one, or the caveat "measurement, not
    release evidence" stops meaning anything.
    """
    sources: dict[str, SourceRecord] = {}
    blocks: dict[str, SourceBlock] = {}
    objects: dict[str, LearningObject] = {}

    for artefact in artefacts:
        source = artefact.source()
        if licence is not None and not licence.covers(source.source_id):
            raise ValueError(
                f"{source.source_id} is not named by the evaluation licence"
            )
        if source.approval_state is ApprovalState.QUARANTINED:
            if licence is None:
                raise ValueError(
                    f"{source.source_id} is QUARANTINED and no evaluation licence was "
                    "given. File a rights record with scripts/approve_source.py, or "
                    "pass an EvaluationLicence naming this source to measure against it."
                )
        sources[source.source_id] = source
        for block in artefact.blocks():
            blocks[block.block_id] = block
        for obj in artefact.objects():
            objects[obj.object_id] = obj

    representations = {}
    if with_representations:
        built = represent_all(objects.values(), list(blocks.values()))
        if embedder is not None:
            vectors = embedder.embed_documents([rep.search_text for rep in built])
            built = [
                rep.model_copy(update={
                    "vector": vector,
                    "embedding_model": embedder.model,
                    "embedding_version": embedder.version,
                })
                for rep, vector in zip(built, vectors)
            ]
        for rep in built:
            representations[rep.representation_id] = rep

    return Corpus(
        sources=sources,
        blocks=blocks,
        objects=objects,
        representations=representations,
        evaluation_licence=licence,
    )
