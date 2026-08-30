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
from dataclasses import dataclass
from pathlib import Path

from agts.contracts.common import ApprovalState, AuthorityTier, Board, Language
from agts.contracts.objects import LearningObject, SourceBlock, SourceRecord
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

    def source(self) -> SourceRecord:
        manifest = self.manifest()
        state = ApprovalState(manifest["approval_state"])
        if state is not ApprovalState.QUARANTINED:
            # Approval is a human act against a checksum (§5). If an artefact
            # ever claims otherwise, that is a defect in whatever wrote it.
            raise ValueError(
                f"{self.directory.name}: manifest claims {state}; artefacts are quarantined"
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
        )


def load_corpus(
    artefacts: list[ChapterArtefact],
    *,
    licence: EvaluationLicence,
    with_representations: bool = True,
    embedder=None,
) -> Corpus:
    """Build a corpus over `artefacts`, licensed for evaluation only.

    The licence is required rather than optional: a corpus of quarantined
    content without one authorises nothing, and returning an empty candidate set
    from every query reads as a broken retriever rather than as a permission the
    caller never asked for.
    """
    sources: dict[str, SourceRecord] = {}
    blocks: dict[str, SourceBlock] = {}
    objects: dict[str, LearningObject] = {}

    for artefact in artefacts:
        source = artefact.source()
        if not licence.covers(source.source_id):
            raise ValueError(
                f"{source.source_id} is not named by the evaluation licence"
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
