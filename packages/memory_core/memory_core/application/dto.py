"""Application command/result DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from memory_core.domain.entities import (
    MemoryChunk,
    MemoryChunkKind,
    MemoryDocument,
    MemoryEpisode,
    MemoryFact,
    MemoryKind,
    MemoryProfile,
    MemorySpace,
    MemorySuggestion,
    ProfileId,
    SourceRef,
    SpaceId,
    SpeakerRole,
    ThreadId,
    TrustLevel,
)


@dataclass(frozen=True)
class CreateSpaceCommand:
    slug: str
    name: str


@dataclass(frozen=True)
class CreateProfileCommand:
    space_id: SpaceId
    external_ref: str
    name: str


@dataclass(frozen=True)
class SpaceResult:
    space: MemorySpace
    created: bool = True


@dataclass(frozen=True)
class ProfileResult:
    profile: MemoryProfile
    created: bool = True


@dataclass(frozen=True)
class RememberFactCommand:
    space_id: SpaceId
    profile_id: ProfileId
    text: str
    kind: MemoryKind
    source_refs: tuple[SourceRef, ...]
    thread_id: ThreadId | None = None
    idempotency_key: str | None = None
    classification: str = "internal"


@dataclass(frozen=True)
class UpdateFactCommand:
    fact_id: str
    expected_version: int
    text: str
    source_refs: tuple[SourceRef, ...]
    reason: str


@dataclass(frozen=True)
class ForgetFactCommand:
    fact_id: str


@dataclass(frozen=True)
class FactResult:
    fact: MemoryFact
    indexing_status: str


@dataclass(frozen=True)
class GetFactQuery:
    fact_id: str


@dataclass(frozen=True)
class FactVersionsQuery:
    fact_id: str


@dataclass(frozen=True)
class ListFactsQuery:
    space_id: SpaceId
    profile_id: ProfileId
    status: str | None
    limit: int
    cursor_updated_at: datetime | None = None
    cursor_id: str | None = None


@dataclass(frozen=True)
class FactQueryResult:
    fact: MemoryFact


@dataclass(frozen=True)
class FactsQueryResult:
    facts: tuple[MemoryFact, ...]


@dataclass(frozen=True)
class EnsureScopeCommand:
    space_slug: str
    profile_external_ref: str
    thread_external_ref: str | None = None


@dataclass(frozen=True)
class ScopeResult:
    space_id: SpaceId
    profile_id: ProfileId
    thread_id: ThreadId | None = None


@dataclass(frozen=True)
class IngestEpisodeCommand:
    space_id: SpaceId
    profile_id: ProfileId
    thread_id: ThreadId
    source_type: str
    source_external_id: str
    text: str
    occurred_at: object | None = None
    speaker: SpeakerRole = SpeakerRole.UNKNOWN
    trust_level: TrustLevel = TrustLevel.MEDIUM
    kind_hint: MemoryChunkKind | None = None
    language: str | None = None
    metadata: dict[str, object] | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class IngestEpisodeResult:
    episode: MemoryEpisode | None
    stored_chunks: int
    duplicate_chunks: int
    durability: str


@dataclass(frozen=True)
class IngestDocumentCommand:
    space_id: SpaceId
    profile_id: ProfileId
    title: str
    text: str
    source_type: str
    source_external_id: str
    thread_id: ThreadId | None = None
    idempotency_key: str | None = None
    classification: str = "unknown"


@dataclass(frozen=True)
class IngestDocumentResult:
    document: MemoryDocument
    chunks: tuple[MemoryChunk, ...]
    duplicate_chunks: int
    indexing_status: str


@dataclass(frozen=True)
class GetDocumentQuery:
    document_id: str


@dataclass(frozen=True)
class ListDocumentChunksQuery:
    document_id: str
    limit: int
    cursor_sequence: int | None = None
    cursor_id: str | None = None


@dataclass(frozen=True)
class DocumentQueryResult:
    document: MemoryDocument


@dataclass(frozen=True)
class DocumentChunksQueryResult:
    document: MemoryDocument
    chunks: tuple[MemoryChunk, ...]


@dataclass(frozen=True)
class DeleteDocumentCommand:
    document_id: str


@dataclass(frozen=True)
class ProcessDocumentCommand:
    document_id: str
    idempotency_key: str | None = None


@dataclass(frozen=True)
class DeleteDocumentResult:
    document: MemoryDocument
    deleted_chunks: int
    deleted_facts: int
    indexing_status: str


@dataclass(frozen=True)
class ProcessDocumentResult:
    document: MemoryDocument
    chunks: int
    indexing_status: str


@dataclass(frozen=True)
class ContextItem:
    item_id: str
    item_type: str
    text: str
    score: float
    source_refs: tuple[SourceRef, ...]
    is_instruction: bool = False
    diagnostics: dict[str, object] | None = None


@dataclass(frozen=True)
class ContextBundle:
    bundle_id: str
    rendered_text: str
    items: tuple[ContextItem, ...]
    token_estimate: int
    diagnostics: dict[str, object]


@dataclass(frozen=True)
class BuildContextQuery:
    space_id: SpaceId
    profile_ids: tuple[ProfileId, ...]
    query: str
    thread_id: ThreadId | None = None
    token_budget: int = 1800
    max_rendered_chars: int = 18000
    max_facts: int = 20
    max_chunks: int = 30
    include_graph: bool = True


@dataclass(frozen=True)
class DeleteThreadMemoryCommand:
    space_id: SpaceId
    profile_id: ProfileId
    thread_id: ThreadId


@dataclass(frozen=True)
class DeleteThreadMemoryResult:
    deleted_chunks: int
    deleted_facts: int
    deleted_jobs: int


@dataclass(frozen=True)
class GetSessionStatusQuery:
    space_id: SpaceId
    profile_id: ProfileId
    thread_id: ThreadId


@dataclass(frozen=True)
class SessionStatusResult:
    chunks: int
    facts: int
    jobs: int
    pending_jobs: int


@dataclass(frozen=True)
class CreateSuggestionCommand:
    space_id: SpaceId
    profile_id: ProfileId
    candidate_text: str
    kind: MemoryKind
    source_refs: tuple[SourceRef, ...]
    safe_reason: str
    confidence: str = "medium"
    trust_level: str = "medium"
    target_fact_id: str | None = None
    target_fact_version: int | None = None
    auto_approve: bool = False


@dataclass(frozen=True)
class SuggestionResult:
    suggestion: MemorySuggestion
    fact: MemoryFact | None = None
    indexing_status: str | None = None


@dataclass(frozen=True)
class ListSuggestionsQuery:
    space_id: SpaceId
    profile_id: ProfileId
    status: str | None = None
    limit: int = 100


@dataclass(frozen=True)
class ApproveSuggestionCommand:
    suggestion_id: str
    reason: str | None = None
    force: bool = False


@dataclass(frozen=True)
class RejectSuggestionCommand:
    suggestion_id: str
    reason: str | None = None


@dataclass(frozen=True)
class ExpireSuggestionCommand:
    suggestion_id: str
    reason: str | None = None
