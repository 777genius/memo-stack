"""Ingest transcript/interview episodes as canonical evidence chunks."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from memory_core.application.chunker import chunk_text
from memory_core.application.dto import IngestEpisodeCommand, IngestEpisodeResult
from memory_core.application.normalize import (
    estimate_tokens,
    normalize_text,
    scoped_idempotency_key,
    scoped_source_hash,
)
from memory_core.domain.entities import (
    MemoryChunk,
    MemoryChunkId,
    MemoryChunkKind,
    MemoryEpisode,
    MemoryEpisodeId,
    TrustLevel,
)
from memory_core.domain.errors import MemoryConflictError, MemoryInvariantError
from memory_core.domain.events import OutboxEvent
from memory_core.domain.idempotency import IdempotencyRecord
from memory_core.ports.clock import ClockPort
from memory_core.ports.ids import IdGeneratorPort
from memory_core.ports.unit_of_work import UnitOfWorkFactoryPort


def episode_fingerprint(command: IngestEpisodeCommand) -> str:
    raw = (
        f"{command.space_id}:{command.profile_id}:{command.thread_id}:"
        f"{command.source_type}:{command.source_external_id}:{command.text}:"
        f"{command.kind_hint}:{command.language}"
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def durability_for_episode(command: IngestEpisodeCommand) -> str:
    metadata = command.metadata or {}
    if command.source_type == "ai_response" or metadata.get("final_answer") is True:
        return "ignore"
    if (
        command.source_type == "microphone"
        and metadata.get("explicit_interview_context") is not True
    ):
        return "request_scoped_only"
    if (
        command.source_type == "browser_selection"
        and metadata.get("attached_to_prompt") is not True
    ):
        return "request_scoped_only"
    return "durable"


class IngestEpisodeUseCase:
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

    async def execute(self, command: IngestEpisodeCommand) -> IngestEpisodeResult:
        durability = durability_for_episode(command)
        if durability != "durable":
            return IngestEpisodeResult(
                episode=None,
                stored_chunks=0,
                duplicate_chunks=0,
                durability=durability,
            )

        fingerprint = episode_fingerprint(command)
        raw_key = command.idempotency_key or command.source_external_id
        key = scoped_idempotency_key(
            "ingest_episode",
            command.profile_id,
            command.thread_id,
            raw_key,
        )
        async with self._uow_factory() as uow:
            existing = await uow.idempotency.find(space_id=str(command.space_id), key=key)
            if existing:
                if existing.fingerprint != fingerprint:
                    raise MemoryConflictError("Idempotency key was used with different episode")
                return IngestEpisodeResult(
                    episode=None,
                    stored_chunks=0,
                    duplicate_chunks=1,
                    durability=durability,
                )

            now = self._clock.now()
            occurred_at = command.occurred_at if isinstance(command.occurred_at, datetime) else now
            episode = MemoryEpisode.create(
                episode_id=MemoryEpisodeId(self._ids.new_id("episode")),
                space_id=command.space_id,
                profile_id=command.profile_id,
                thread_id=command.thread_id,
                source_type=command.source_type,
                source_external_id=command.source_external_id,
                text=command.text,
                speaker=command.speaker,
                trust_level=_trust_for_source(command.source_type, command.trust_level),
                occurred_at=occurred_at,
                now=now,
                metadata=command.metadata,
            )
            saved_episode = await uow.episodes.create(episode)

            stored = 0
            duplicates = 0
            for piece in chunk_text(command.text):
                kind = command.kind_hint or _kind_for_source(command.source_type)
                chunk = MemoryChunk.create(
                    chunk_id=MemoryChunkId(self._ids.new_id("chunk")),
                    space_id=command.space_id,
                    profile_id=command.profile_id,
                    thread_id=command.thread_id,
                    episode_id=saved_episode.id,
                    document_id=None,
                    source_type=command.source_type,
                    source_external_id=command.source_external_id,
                    source_hash=scoped_source_hash(
                        command.space_id,
                        command.profile_id,
                        command.thread_id,
                        command.source_external_id,
                        piece.sequence,
                        normalize_text(piece.text),
                    ),
                    kind=kind,
                    text=piece.text,
                    normalized_text=normalize_text(piece.text),
                    sequence=piece.sequence,
                    char_start=piece.char_start,
                    char_end=piece.char_end,
                    token_estimate=estimate_tokens(piece.text),
                    now=now,
                    metadata={"language": command.language or "", "source": command.source_type},
                )
                result = await uow.chunks.upsert(chunk)
                if result.duplicate:
                    duplicates += 1
                else:
                    stored += 1
                    await uow.outbox.enqueue(
                        OutboxEvent(
                            event_type="vector.upsert_chunk",
                            aggregate_type="chunk",
                            aggregate_id=result.chunk_id,
                            payload={"chunk_id": result.chunk_id},
                        )
                    )

            await uow.idempotency.save(
                IdempotencyRecord(
                    space_id=str(command.space_id),
                    key=key,
                    fingerprint=fingerprint,
                    result_type="episode",
                    result_id=str(saved_episode.id),
                )
            )
            await uow.commit()

        if stored == 0 and duplicates == 0:
            raise MemoryInvariantError("Durable episode produced no chunks")
        return IngestEpisodeResult(
            episode=saved_episode,
            stored_chunks=stored,
            duplicate_chunks=duplicates,
            durability=durability,
        )


def _trust_for_source(source_type: str, default: TrustLevel) -> TrustLevel:
    if source_type == "ai_response":
        return TrustLevel.LOW
    if source_type in {"manual", "manual_prompt", "focus_copy"}:
        return TrustLevel.HIGH
    return default


def _kind_for_source(source_type: str) -> MemoryChunkKind:
    return {
        "manual_prompt": MemoryChunkKind.USER_PROMPT,
        "focus_copy": MemoryChunkKind.CURRENT_CODE,
        "ai_response": MemoryChunkKind.AI_RESPONSE,
    }.get(source_type, MemoryChunkKind.RAW_TRANSCRIPT_CHUNK)
