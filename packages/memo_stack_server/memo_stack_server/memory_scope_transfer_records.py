"""Row serialization helpers for memory_scope snapshot transfer."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from memo_stack_adapters.postgres.models import (
    MemoryChunkRow,
    MemoryDocumentRow,
    MemoryEpisodeRow,
    MemoryFactRow,
    MemorySourceRefRow,
)


def contains_redacted_memory(
    payload: dict[str, Any],
    *,
    facts: list[dict[str, Any]],
    episodes: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> bool:
    if payload.get("redacted") is True:
        return True
    if any(fact.get("text") is None for fact in facts):
        return True
    if any(episode.get("text") is None for episode in episodes):
        return True
    return any(
        chunk.get("text") is None or chunk.get("normalized_text") is None for chunk in chunks
    )


def fact_to_json(row: MemoryFactRow, *, redacted: bool) -> dict[str, Any]:
    return {
        "id": row.id,
        "thread_id": row.thread_id,
        "kind": row.kind,
        "text": None if redacted else row.text,
        "status": row.status,
        "confidence": row.confidence,
        "trust_level": row.trust_level,
        "classification": row.classification,
        "category": row.category,
        "tags": list(row.tags_json or []),
        "ttl_policy": row.ttl_policy,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "version": row.version,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def document_to_json(row: MemoryDocumentRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "thread_id": row.thread_id,
        "title": row.title,
        "source_type": row.source_type,
        "source_external_id": row.source_external_id,
        "content_hash": row.content_hash,
        "classification": row.classification,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def episode_to_json(row: MemoryEpisodeRow, *, redacted: bool) -> dict[str, Any]:
    return {
        "id": row.id,
        "thread_id": row.thread_id,
        "source_type": row.source_type,
        "source_external_id": row.source_external_id,
        "text": None if redacted else row.text,
        "speaker": row.speaker,
        "trust_level": row.trust_level,
        "status": row.status,
        "occurred_at": row.occurred_at.isoformat(),
        "created_at": row.created_at.isoformat(),
        "metadata_json": row.metadata_json,
    }


def chunk_to_json(row: MemoryChunkRow, *, redacted: bool) -> dict[str, Any]:
    return {
        "id": row.id,
        "thread_id": row.thread_id,
        "document_id": row.document_id,
        "episode_id": row.episode_id,
        "source_type": row.source_type,
        "source_external_id": row.source_external_id,
        "source_hash": row.source_hash,
        "kind": row.kind,
        "text": None if redacted else row.text,
        "normalized_text": None if redacted else row.normalized_text,
        "status": row.status,
        "sequence": row.sequence,
        "char_start": row.char_start,
        "char_end": row.char_end,
        "token_estimate": row.token_estimate,
        "classification": row.classification,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "metadata_json": row.metadata_json,
    }


def source_ref_to_json(row: MemorySourceRefRow, *, redacted: bool) -> dict[str, Any]:
    return {
        "fact_id": row.fact_id,
        "fact_version": row.fact_version,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "chunk_id": row.chunk_id,
        "char_start": row.char_start,
        "char_end": row.char_end,
        "quote_preview": None if redacted else bounded_optional_text(row.quote_preview, 240),
    }


def fact_from_json(
    item: dict[str, Any],
    *,
    space_id: str,
    memory_scope_id: str,
    now: datetime,
) -> MemoryFactRow:
    return MemoryFactRow(
        id=str(item["id"]),
        space_id=space_id,
        memory_scope_id=memory_scope_id,
        thread_id=None,
        kind=str(item.get("kind", "note")),
        text=str(item.get("text") or "[redacted]"),
        status=str(item.get("status", "active")),
        confidence=str(item.get("confidence", "medium")),
        trust_level=str(item.get("trust_level", "medium")),
        classification=str(item.get("classification", "internal")),
        category=bounded_optional_text(item.get("category"), 80),
        tags_json=_bounded_tags(item.get("tags")),
        ttl_policy=bounded_optional_text(item.get("ttl_policy"), 80),
        expires_at=_parse_optional_dt(item.get("expires_at")),
        version=int(item.get("version", 1)),
        created_at=_parse_dt(item.get("created_at"), now),
        updated_at=_parse_dt(item.get("updated_at"), now),
    )


def document_from_json(
    item: dict[str, Any],
    *,
    space_id: str,
    memory_scope_id: str,
    now: datetime,
) -> MemoryDocumentRow:
    return MemoryDocumentRow(
        id=str(item["id"]),
        space_id=space_id,
        memory_scope_id=memory_scope_id,
        thread_id=None,
        title=str(item.get("title") or "Imported document"),
        source_type=str(item.get("source_type", "import")),
        source_external_id=str(item.get("source_external_id", item["id"])),
        content_hash=str(item.get("content_hash", item["id"])),
        classification=str(item.get("classification", "unknown")),
        status=str(item.get("status", "active")),
        created_at=_parse_dt(item.get("created_at"), now),
        updated_at=_parse_dt(item.get("updated_at"), now),
    )


def episode_from_json(
    item: dict[str, Any],
    *,
    space_id: str,
    memory_scope_id: str,
    now: datetime,
) -> MemoryEpisodeRow:
    return MemoryEpisodeRow(
        id=str(item["id"]),
        space_id=space_id,
        memory_scope_id=memory_scope_id,
        thread_id=str(item["thread_id"]),
        source_type=str(item.get("source_type", "import")),
        source_external_id=str(item.get("source_external_id", item["id"])),
        text=str(item.get("text") or "[redacted]"),
        speaker=str(item.get("speaker", "unknown")),
        trust_level=str(item.get("trust_level", "medium")),
        status=str(item.get("status", "active")),
        occurred_at=_parse_dt(item.get("occurred_at"), now),
        created_at=_parse_dt(item.get("created_at"), now),
        metadata_json=dict(item.get("metadata_json") or item.get("metadata") or {}),
    )


def chunk_from_json(
    item: dict[str, Any],
    *,
    space_id: str,
    memory_scope_id: str,
    now: datetime,
) -> MemoryChunkRow:
    text = str(item.get("text") or "[redacted]")
    return MemoryChunkRow(
        id=str(item["id"]),
        space_id=space_id,
        memory_scope_id=memory_scope_id,
        thread_id=item.get("thread_id"),
        document_id=item.get("document_id"),
        episode_id=item.get("episode_id"),
        source_type=str(item.get("source_type", "import")),
        source_external_id=str(item.get("source_external_id", item["id"])),
        source_hash=str(item.get("source_hash", item["id"])),
        kind=str(item.get("kind", "document_section")),
        text=text,
        normalized_text=str(item.get("normalized_text") or text),
        status=str(item.get("status", "active")),
        sequence=int(item.get("sequence", 0)),
        char_start=int(item.get("char_start", 0)),
        char_end=int(item.get("char_end", len(text))),
        token_estimate=int(item.get("token_estimate", max(1, len(text) // 4))),
        classification=str(item.get("classification", "unknown")),
        created_at=_parse_dt(item.get("created_at"), now),
        updated_at=_parse_dt(item.get("updated_at"), now),
        metadata_json=dict(item.get("metadata_json") or {}),
    )


def source_ref_from_json(item: dict[str, Any]) -> MemorySourceRefRow:
    return MemorySourceRefRow(
        fact_id=str(item["fact_id"]),
        fact_version=int(item.get("fact_version", 1)),
        source_type=str(item.get("source_type", "import")),
        source_id=str(item.get("source_id", "import")),
        chunk_id=item.get("chunk_id"),
        char_start=item.get("char_start"),
        char_end=item.get("char_end"),
        quote_preview=bounded_optional_text(item.get("quote_preview"), 240),
    )


def bounded_optional_text(value: object, limit: int) -> str | None:
    if value is None:
        return None
    return str(value)[:limit]


def _parse_dt(value: object, fallback: datetime) -> datetime:
    if not value:
        return fallback
    return datetime.fromisoformat(str(value))


def _parse_optional_dt(value: object) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value))


def _bounded_tags(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    for item in value:
        tag = str(item).strip().lower()[:48]
        if tag and tag not in tags:
            tags.append(tag)
        if len(tags) >= 10:
            break
    return tags
