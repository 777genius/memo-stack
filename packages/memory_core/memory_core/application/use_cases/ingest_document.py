"""Ingest text documents into canonical documents and chunks."""

from __future__ import annotations

from memory_core.application.chunker import chunk_text
from memory_core.application.dto import IngestDocumentCommand, IngestDocumentResult
from memory_core.application.normalize import (
    content_hash,
    estimate_tokens,
    normalize_text,
    scoped_idempotency_key,
    scoped_source_hash,
)
from memory_core.domain.entities import (
    MemoryChunk,
    MemoryChunkId,
    MemoryChunkKind,
    MemoryDocument,
    MemoryDocumentId,
)
from memory_core.domain.errors import MemoryConflictError, MemoryInvariantError
from memory_core.domain.events import OutboxEvent
from memory_core.domain.idempotency import IdempotencyRecord
from memory_core.ports.clock import ClockPort
from memory_core.ports.ids import IdGeneratorPort
from memory_core.ports.unit_of_work import UnitOfWorkFactoryPort


class IngestDocumentUseCase:
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactoryPort,
        clock: ClockPort,
        ids: IdGeneratorPort,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._ids = ids

    async def execute(self, command: IngestDocumentCommand) -> IngestDocumentResult:
        body_hash = content_hash(command.text)
        raw_key = command.idempotency_key or (
            f"document:{command.space_id}:{command.profile_id}:"
            f"{command.source_type}:{command.source_external_id}:{body_hash}"
        )
        key = scoped_idempotency_key(
            "ingest_document",
            command.profile_id,
            command.thread_id,
            raw_key,
        )

        async with self._uow_factory() as uow:
            existing = await uow.idempotency.find(space_id=str(command.space_id), key=key)
            if existing:
                if existing.fingerprint != body_hash:
                    raise MemoryConflictError("Idempotency key was used with different document")
                document = await uow.documents.get_by_id(existing.result_id)
                if document is None:
                    raise MemoryInvariantError("Idempotency result points to missing document")
                chunks = await uow.documents.list_chunks(str(document.id))
                return IngestDocumentResult(
                    document=document,
                    chunks=tuple(chunks),
                    duplicate_chunks=len(chunks),
                    indexing_status="already_indexed_or_pending",
                )

            existing_document = await uow.documents.find_active_by_content_hash(
                space_id=str(command.space_id),
                profile_id=str(command.profile_id),
                thread_id=str(command.thread_id) if command.thread_id else None,
                content_hash=body_hash,
            )
            if existing_document is not None:
                chunks = await uow.documents.list_chunks(str(existing_document.id))
                if command.idempotency_key:
                    await uow.idempotency.save(
                        IdempotencyRecord(
                            space_id=str(command.space_id),
                            key=key,
                            fingerprint=body_hash,
                            result_type="document",
                            result_id=str(existing_document.id),
                        )
                    )
                    await uow.commit()
                return IngestDocumentResult(
                    document=existing_document,
                    chunks=tuple(chunks),
                    duplicate_chunks=len(chunks),
                    indexing_status="already_indexed_or_pending",
                )

            now = self._clock.now()
            document = MemoryDocument.create(
                document_id=MemoryDocumentId(self._ids.new_id("doc")),
                space_id=command.space_id,
                profile_id=command.profile_id,
                thread_id=command.thread_id,
                title=command.title,
                source_type=command.source_type,
                source_external_id=command.source_external_id,
                content_hash=body_hash,
                now=now,
                classification=command.classification,
            )
            saved_document = await uow.documents.create(document)
            stored_chunks = []
            duplicate_chunks = 0
            for piece in chunk_text(command.text):
                chunk = MemoryChunk.create(
                    chunk_id=MemoryChunkId(self._ids.new_id("chunk")),
                    space_id=command.space_id,
                    profile_id=command.profile_id,
                    thread_id=command.thread_id,
                    document_id=saved_document.id,
                    episode_id=None,
                    source_type=command.source_type,
                    source_external_id=command.source_external_id,
                    source_hash=scoped_source_hash(
                        command.space_id,
                        command.profile_id,
                        str(saved_document.id),
                        piece.sequence,
                        normalize_text(piece.text),
                    ),
                    kind=MemoryChunkKind.DOCUMENT_SECTION,
                    text=piece.text,
                    normalized_text=normalize_text(piece.text),
                    sequence=piece.sequence,
                    char_start=piece.char_start,
                    char_end=piece.char_end,
                    token_estimate=estimate_tokens(piece.text),
                    now=now,
                    metadata={"title": saved_document.title},
                    classification=saved_document.classification,
                )
                upsert = await uow.chunks.upsert(chunk)
                if upsert.duplicate:
                    duplicate_chunks += 1
                    continue
                stored_chunks.append(chunk)
                await uow.outbox.enqueue(
                    OutboxEvent(
                        event_type="vector.upsert_chunk",
                        aggregate_type="chunk",
                        aggregate_id=upsert.chunk_id,
                        payload={"chunk_id": upsert.chunk_id},
                    )
                )

            await uow.idempotency.save(
                IdempotencyRecord(
                    space_id=str(command.space_id),
                    key=key,
                    fingerprint=body_hash,
                    result_type="document",
                    result_id=str(saved_document.id),
                )
            )
            await uow.commit()

        return IngestDocumentResult(
            document=saved_document,
            chunks=tuple(stored_chunks),
            duplicate_chunks=duplicate_chunks,
            indexing_status="pending",
        )
