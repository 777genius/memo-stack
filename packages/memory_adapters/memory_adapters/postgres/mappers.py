"""ORM/domain mapping helpers."""

from __future__ import annotations

from dataclasses import asdict

from memory_core.domain.entities import (
    Confidence,
    FactStatus,
    LifecycleStatus,
    MemoryChunk,
    MemoryChunkId,
    MemoryChunkKind,
    MemoryDocument,
    MemoryDocumentId,
    MemoryEpisode,
    MemoryEpisodeId,
    MemoryFact,
    MemoryFactId,
    MemoryKind,
    MemoryProfile,
    MemorySpace,
    MemorySuggestion,
    MemorySuggestionId,
    ProfileId,
    SourceRef,
    SpaceId,
    SpeakerRole,
    SuggestionStatus,
    ThreadId,
    TrustLevel,
)

from memory_adapters.postgres.models import (
    MemoryChunkRow,
    MemoryDocumentRow,
    MemoryEpisodeRow,
    MemoryFactRow,
    MemoryProfileRow,
    MemorySourceRefRow,
    MemorySpaceRow,
    MemorySuggestionRow,
)


def source_ref_to_json(ref: SourceRef) -> dict[str, object]:
    return {key: value for key, value in asdict(ref).items() if value is not None}


def source_ref_row_to_domain(row: MemorySourceRefRow) -> SourceRef:
    return SourceRef(
        source_type=row.source_type,
        source_id=row.source_id,
        chunk_id=row.chunk_id,
        char_start=row.char_start,
        char_end=row.char_end,
        quote_preview=row.quote_preview,
    )


def fact_row_to_domain(row: MemoryFactRow, source_refs: list[MemorySourceRefRow]) -> MemoryFact:
    return MemoryFact(
        id=MemoryFactId(row.id),
        space_id=SpaceId(row.space_id),
        profile_id=ProfileId(row.profile_id),
        thread_id=ThreadId(row.thread_id) if row.thread_id else None,
        text=row.text,
        kind=MemoryKind(row.kind),
        source_refs=tuple(source_ref_row_to_domain(ref) for ref in source_refs),
        status=FactStatus(row.status),
        version=row.version,
        confidence=Confidence(row.confidence),
        trust_level=TrustLevel(row.trust_level),
        classification=row.classification,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def space_row_to_domain(row: MemorySpaceRow) -> MemorySpace:
    return MemorySpace(
        id=SpaceId(row.id),
        slug=row.slug,
        name=row.name,
        status=LifecycleStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def profile_row_to_domain(row: MemoryProfileRow) -> MemoryProfile:
    return MemoryProfile(
        id=ProfileId(row.id),
        space_id=SpaceId(row.space_id),
        external_ref=row.external_ref,
        name=row.name,
        status=LifecycleStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def apply_fact_to_row(fact: MemoryFact, row: MemoryFactRow) -> None:
    row.space_id = str(fact.space_id)
    row.profile_id = str(fact.profile_id)
    row.thread_id = str(fact.thread_id) if fact.thread_id else None
    row.kind = fact.kind.value
    row.text = fact.text
    row.status = fact.status.value
    row.confidence = fact.confidence.value
    row.trust_level = fact.trust_level.value
    row.classification = fact.classification
    row.version = fact.version
    row.created_at = fact.created_at
    row.updated_at = fact.updated_at


def episode_to_row(episode: MemoryEpisode) -> MemoryEpisodeRow:
    return MemoryEpisodeRow(
        id=str(episode.id),
        space_id=str(episode.space_id),
        profile_id=str(episode.profile_id),
        thread_id=str(episode.thread_id),
        source_type=episode.source_type,
        source_external_id=episode.source_external_id,
        text=episode.text,
        speaker=episode.speaker.value,
        trust_level=episode.trust_level.value,
        status=episode.status.value,
        occurred_at=episode.occurred_at,
        created_at=episode.created_at,
        metadata_json=episode.metadata,
    )


def episode_row_to_domain(row: MemoryEpisodeRow) -> MemoryEpisode:
    return MemoryEpisode(
        id=MemoryEpisodeId(row.id),
        space_id=SpaceId(row.space_id),
        profile_id=ProfileId(row.profile_id),
        thread_id=ThreadId(row.thread_id),
        source_type=row.source_type,
        source_external_id=row.source_external_id,
        text=row.text,
        speaker=SpeakerRole(row.speaker),
        trust_level=TrustLevel(row.trust_level),
        status=LifecycleStatus(row.status),
        occurred_at=row.occurred_at,
        created_at=row.created_at,
        metadata=dict(row.metadata_json or {}),
    )


def document_to_row(document: MemoryDocument) -> MemoryDocumentRow:
    return MemoryDocumentRow(
        id=str(document.id),
        space_id=str(document.space_id),
        profile_id=str(document.profile_id),
        thread_id=str(document.thread_id) if document.thread_id else None,
        title=document.title,
        source_type=document.source_type,
        source_external_id=document.source_external_id,
        content_hash=document.content_hash,
        classification=document.classification,
        status=document.status.value,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def document_row_to_domain(row: MemoryDocumentRow) -> MemoryDocument:
    return MemoryDocument(
        id=MemoryDocumentId(row.id),
        space_id=SpaceId(row.space_id),
        profile_id=ProfileId(row.profile_id),
        thread_id=ThreadId(row.thread_id) if row.thread_id else None,
        title=row.title,
        source_type=row.source_type,
        source_external_id=row.source_external_id,
        content_hash=row.content_hash,
        classification=row.classification,
        status=LifecycleStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def chunk_to_row(chunk: MemoryChunk) -> MemoryChunkRow:
    return MemoryChunkRow(
        id=str(chunk.id),
        space_id=str(chunk.space_id),
        profile_id=str(chunk.profile_id),
        thread_id=str(chunk.thread_id) if chunk.thread_id else None,
        document_id=str(chunk.document_id) if chunk.document_id else None,
        episode_id=str(chunk.episode_id) if chunk.episode_id else None,
        source_type=chunk.source_type,
        source_external_id=chunk.source_external_id,
        source_hash=chunk.source_hash,
        kind=chunk.kind.value,
        text=chunk.text,
        normalized_text=chunk.normalized_text,
        status=chunk.status.value,
        sequence=chunk.sequence,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        token_estimate=chunk.token_estimate,
        classification=chunk.classification,
        created_at=chunk.created_at,
        updated_at=chunk.updated_at,
        metadata_json=chunk.metadata,
    )


def chunk_row_to_domain(row: MemoryChunkRow) -> MemoryChunk:
    return MemoryChunk(
        id=MemoryChunkId(row.id),
        space_id=SpaceId(row.space_id),
        profile_id=ProfileId(row.profile_id),
        thread_id=ThreadId(row.thread_id) if row.thread_id else None,
        document_id=MemoryDocumentId(row.document_id) if row.document_id else None,
        episode_id=MemoryEpisodeId(row.episode_id) if row.episode_id else None,
        source_type=row.source_type,
        source_external_id=row.source_external_id,
        source_hash=row.source_hash,
        kind=MemoryChunkKind(row.kind),
        text=row.text,
        normalized_text=row.normalized_text,
        status=LifecycleStatus(row.status),
        sequence=row.sequence,
        char_start=row.char_start,
        char_end=row.char_end,
        token_estimate=row.token_estimate,
        classification=row.classification,
        created_at=row.created_at,
        updated_at=row.updated_at,
        metadata=dict(row.metadata_json or {}),
    )


def source_ref_from_json(ref: dict[str, object]) -> SourceRef:
    return SourceRef(
        source_type=str(ref["source_type"]),
        source_id=str(ref["source_id"]),
        chunk_id=str(ref["chunk_id"]) if ref.get("chunk_id") else None,
        char_start=int(ref["char_start"]) if ref.get("char_start") is not None else None,
        char_end=int(ref["char_end"]) if ref.get("char_end") is not None else None,
        quote_preview=str(ref["quote_preview"]) if ref.get("quote_preview") is not None else None,
    )


def suggestion_to_row(suggestion: MemorySuggestion) -> MemorySuggestionRow:
    return MemorySuggestionRow(
        id=str(suggestion.id),
        space_id=str(suggestion.space_id),
        profile_id=str(suggestion.profile_id),
        candidate_text=suggestion.candidate_text,
        kind=suggestion.kind.value,
        status=suggestion.status.value,
        source_refs_json=[source_ref_to_json(ref) for ref in suggestion.source_refs],
        confidence=suggestion.confidence.value,
        trust_level=suggestion.trust_level.value,
        safe_reason=suggestion.safe_reason,
        target_fact_id=str(suggestion.target_fact_id) if suggestion.target_fact_id else None,
        target_fact_version=suggestion.target_fact_version,
        review_reason=suggestion.review_reason,
        created_at=suggestion.created_at,
        updated_at=suggestion.updated_at,
        reviewed_at=suggestion.reviewed_at,
    )


def suggestion_row_to_domain(row: MemorySuggestionRow) -> MemorySuggestion:
    return MemorySuggestion(
        id=MemorySuggestionId(row.id),
        space_id=SpaceId(row.space_id),
        profile_id=ProfileId(row.profile_id),
        candidate_text=row.candidate_text,
        kind=MemoryKind(row.kind),
        status=SuggestionStatus(row.status),
        source_refs=tuple(source_ref_from_json(ref) for ref in row.source_refs_json),
        confidence=Confidence(row.confidence),
        trust_level=TrustLevel(row.trust_level),
        safe_reason=row.safe_reason,
        target_fact_id=MemoryFactId(row.target_fact_id) if row.target_fact_id else None,
        target_fact_version=row.target_fact_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
        reviewed_at=row.reviewed_at,
        review_reason=row.review_reason,
    )


def apply_suggestion_to_row(suggestion: MemorySuggestion, row: MemorySuggestionRow) -> None:
    row.candidate_text = suggestion.candidate_text
    row.kind = suggestion.kind.value
    row.status = suggestion.status.value
    row.source_refs_json = [source_ref_to_json(ref) for ref in suggestion.source_refs]
    row.confidence = suggestion.confidence.value
    row.trust_level = suggestion.trust_level.value
    row.safe_reason = suggestion.safe_reason
    row.target_fact_id = str(suggestion.target_fact_id) if suggestion.target_fact_id else None
    row.target_fact_version = suggestion.target_fact_version
    row.review_reason = suggestion.review_reason
    row.updated_at = suggestion.updated_at
    row.reviewed_at = suggestion.reviewed_at
