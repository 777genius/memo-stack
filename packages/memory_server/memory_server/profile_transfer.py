"""Profile export/import lite.

This is a local portability tool, not a sync protocol. It reads and writes
canonical Postgres rows only and never serializes derived Qdrant/Graphiti state.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from memory_adapters.postgres.models import (
    MemoryChunkRow,
    MemoryDocumentRow,
    MemoryFactRow,
    MemoryOutboxRow,
    MemoryProfileRow,
    MemorySourceRefRow,
    MemorySpaceRow,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

SCHEMA_VERSION = 1


async def export_profile(
    *,
    engine: AsyncEngine,
    space_slug: str,
    profile_external_ref: str,
    out_path: Path,
    redacted: bool,
) -> dict[str, object]:
    async with AsyncSession(engine) as session:
        scope = await _load_scope(
            session,
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
        )
        if scope is None:
            return {"status": "not_found", "out": str(out_path)}
        space, profile = scope
        facts = list(
            (
                await session.execute(
                    select(MemoryFactRow)
                    .where(
                        MemoryFactRow.space_id == space.id,
                        MemoryFactRow.profile_id == profile.id,
                    )
                    .order_by(MemoryFactRow.created_at, MemoryFactRow.id)
                )
            ).scalars()
        )
        documents = list(
            (
                await session.execute(
                    select(MemoryDocumentRow)
                    .where(
                        MemoryDocumentRow.space_id == space.id,
                        MemoryDocumentRow.profile_id == profile.id,
                    )
                    .order_by(MemoryDocumentRow.created_at, MemoryDocumentRow.id)
                )
            ).scalars()
        )
        chunks = list(
            (
                await session.execute(
                    select(MemoryChunkRow)
                    .where(
                        MemoryChunkRow.space_id == space.id,
                        MemoryChunkRow.profile_id == profile.id,
                    )
                    .order_by(MemoryChunkRow.created_at, MemoryChunkRow.id)
                )
            ).scalars()
        )
        fact_ids = [fact.id for fact in facts]
        source_refs = []
        if fact_ids:
            source_refs = list(
                (
                    await session.execute(
                        select(MemorySourceRefRow)
                        .where(MemorySourceRefRow.fact_id.in_(fact_ids))
                        .order_by(MemorySourceRefRow.fact_id, MemorySourceRefRow.id)
                    )
                ).scalars()
            )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "space": {"slug": space.slug, "id": space.id},
        "profile": {"external_ref": profile.external_ref, "id": profile.id},
        "facts": [_fact_to_json(fact, redacted=redacted) for fact in facts],
        "documents": [_document_to_json(document) for document in documents],
        "chunks": [_chunk_to_json(chunk, redacted=redacted) for chunk in chunks],
        "source_refs": [_source_ref_to_json(ref, redacted=redacted) for ref in source_refs],
        "exported_at": datetime.now(UTC).isoformat(),
        "redacted": redacted,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": "ok",
        "out": str(out_path),
        "facts": len(facts),
        "documents": len(documents),
        "chunks": len(chunks),
        "redacted": redacted,
    }


async def import_profile(
    *,
    engine: AsyncEngine,
    now: datetime,
    space_id: str,
    profile_id: str,
    in_path: Path,
    dry_run: bool,
    merge_strategy: str,
) -> dict[str, object]:
    payload = json.loads(in_path.read_text(encoding="utf-8"))
    if int(payload.get("schema_version", 0)) != SCHEMA_VERSION:
        return {"status": "failed", "reason": "unsupported_schema_version"}
    if merge_strategy not in {"fail_on_conflict", "skip_existing"}:
        return {"status": "failed", "reason": "unsupported_merge_strategy"}

    facts = list(payload.get("facts", []))
    documents = list(payload.get("documents", []))
    chunks = list(payload.get("chunks", []))
    source_refs = list(payload.get("source_refs", []))

    async with AsyncSession(engine) as session:
        conflict_ids = await _conflicts(
            session,
            fact_ids=[str(item["id"]) for item in facts],
            document_ids=[str(item["id"]) for item in documents],
            chunk_ids=[str(item["id"]) for item in chunks],
        )
        if conflict_ids and merge_strategy == "fail_on_conflict":
            return {
                "status": "conflict",
                "conflict_count": len(conflict_ids),
                "conflict_ids": conflict_ids[:20],
                "dry_run": dry_run,
            }
        if dry_run:
            return {
                "status": "ok",
                "dry_run": True,
                "would_import": {
                    "facts": len(facts) - _count_conflicts(facts, conflict_ids),
                    "documents": len(documents) - _count_conflicts(documents, conflict_ids),
                    "chunks": len(chunks) - _count_conflicts(chunks, conflict_ids),
                    "source_refs": len(source_refs),
                },
                "conflict_count": len(conflict_ids),
            }

        skipped = set(conflict_ids) if merge_strategy == "skip_existing" else set()
        for fact in facts:
            if str(fact["id"]) in skipped:
                continue
            session.add(_fact_from_json(fact, space_id=space_id, profile_id=profile_id, now=now))
        for document in documents:
            if str(document["id"]) in skipped:
                continue
            session.add(
                _document_from_json(document, space_id=space_id, profile_id=profile_id, now=now)
            )
        for chunk in chunks:
            if str(chunk["id"]) in skipped:
                continue
            session.add(_chunk_from_json(chunk, space_id=space_id, profile_id=profile_id, now=now))
            session.add(
                _outbox(
                    event_type="vector.upsert_chunk",
                    aggregate_type="chunk",
                    aggregate_id=str(chunk["id"]),
                    now=now,
                    payload={"chunk_id": str(chunk["id"])},
                )
            )
        for ref in source_refs:
            if str(ref["fact_id"]) in skipped:
                continue
            session.add(_source_ref_from_json(ref))
        for fact in facts:
            if str(fact["id"]) in skipped or str(fact.get("status", "active")) != "active":
                continue
            session.add(
                _outbox(
                    event_type="graph.upsert_fact",
                    aggregate_type="fact",
                    aggregate_id=str(fact["id"]),
                    aggregate_version=int(fact.get("version", 1)),
                    now=now,
                    payload={"fact_id": str(fact["id"])},
                )
            )
        await session.commit()

    return {
        "status": "ok",
        "dry_run": False,
        "imported": {
            "facts": len(facts) - _count_conflicts(facts, skipped),
            "documents": len(documents) - _count_conflicts(documents, skipped),
            "chunks": len(chunks) - _count_conflicts(chunks, skipped),
            "source_refs": len(source_refs),
        },
    }


async def _load_scope(
    session: AsyncSession,
    *,
    space_slug: str,
    profile_external_ref: str,
) -> tuple[MemorySpaceRow, MemoryProfileRow] | None:
    space = (
        await session.execute(select(MemorySpaceRow).where(MemorySpaceRow.slug == space_slug))
    ).scalar_one_or_none()
    if space is None:
        return None
    profile = (
        await session.execute(
            select(MemoryProfileRow).where(
                MemoryProfileRow.space_id == space.id,
                MemoryProfileRow.external_ref == profile_external_ref,
            )
        )
    ).scalar_one_or_none()
    if profile is None:
        return None
    return space, profile


async def _conflicts(
    session: AsyncSession,
    *,
    fact_ids: list[str],
    document_ids: list[str],
    chunk_ids: list[str],
) -> list[str]:
    conflicts: list[str] = []
    for model, ids in (
        (MemoryFactRow, fact_ids),
        (MemoryDocumentRow, document_ids),
        (MemoryChunkRow, chunk_ids),
    ):
        if not ids:
            continue
        result = await session.execute(select(model.id).where(model.id.in_(ids)))
        conflicts.extend(str(row_id) for row_id in result.scalars())
    return conflicts


def _count_conflicts(items: list[dict[str, Any]], conflicts: set[str] | list[str]) -> int:
    conflict_set = set(conflicts)
    return sum(1 for item in items if str(item["id"]) in conflict_set)


def _fact_to_json(row: MemoryFactRow, *, redacted: bool) -> dict[str, Any]:
    return {
        "id": row.id,
        "thread_id": row.thread_id,
        "kind": row.kind,
        "text": None if redacted else row.text,
        "status": row.status,
        "confidence": row.confidence,
        "trust_level": row.trust_level,
        "classification": row.classification,
        "version": row.version,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _document_to_json(row: MemoryDocumentRow) -> dict[str, Any]:
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


def _chunk_to_json(row: MemoryChunkRow, *, redacted: bool) -> dict[str, Any]:
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


def _source_ref_to_json(row: MemorySourceRefRow, *, redacted: bool) -> dict[str, Any]:
    return {
        "fact_id": row.fact_id,
        "fact_version": row.fact_version,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "chunk_id": row.chunk_id,
        "char_start": row.char_start,
        "char_end": row.char_end,
        "quote_preview": None if redacted else _bounded_optional_text(row.quote_preview, 240),
    }


def _fact_from_json(
    item: dict[str, Any],
    *,
    space_id: str,
    profile_id: str,
    now: datetime,
) -> MemoryFactRow:
    return MemoryFactRow(
        id=str(item["id"]),
        space_id=space_id,
        profile_id=profile_id,
        thread_id=item.get("thread_id"),
        kind=str(item.get("kind", "note")),
        text=str(item.get("text") or "[redacted]"),
        status=str(item.get("status", "active")),
        confidence=str(item.get("confidence", "medium")),
        trust_level=str(item.get("trust_level", "medium")),
        classification=str(item.get("classification", "internal")),
        version=int(item.get("version", 1)),
        created_at=_parse_dt(item.get("created_at"), now),
        updated_at=_parse_dt(item.get("updated_at"), now),
    )


def _document_from_json(
    item: dict[str, Any],
    *,
    space_id: str,
    profile_id: str,
    now: datetime,
) -> MemoryDocumentRow:
    return MemoryDocumentRow(
        id=str(item["id"]),
        space_id=space_id,
        profile_id=profile_id,
        thread_id=item.get("thread_id"),
        title=str(item.get("title") or "Imported document"),
        source_type=str(item.get("source_type", "import")),
        source_external_id=str(item.get("source_external_id", item["id"])),
        content_hash=str(item.get("content_hash", item["id"])),
        classification=str(item.get("classification", "unknown")),
        status=str(item.get("status", "active")),
        created_at=_parse_dt(item.get("created_at"), now),
        updated_at=_parse_dt(item.get("updated_at"), now),
    )


def _chunk_from_json(
    item: dict[str, Any],
    *,
    space_id: str,
    profile_id: str,
    now: datetime,
) -> MemoryChunkRow:
    text = str(item.get("text") or "[redacted]")
    return MemoryChunkRow(
        id=str(item["id"]),
        space_id=space_id,
        profile_id=profile_id,
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


def _source_ref_from_json(item: dict[str, Any]) -> MemorySourceRefRow:
    return MemorySourceRefRow(
        fact_id=str(item["fact_id"]),
        fact_version=int(item.get("fact_version", 1)),
        source_type=str(item.get("source_type", "import")),
        source_id=str(item.get("source_id", "import")),
        chunk_id=item.get("chunk_id"),
        char_start=item.get("char_start"),
        char_end=item.get("char_end"),
        quote_preview=_bounded_optional_text(item.get("quote_preview"), 240),
    )


def _outbox(
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    now: datetime,
    payload: dict[str, object],
    aggregate_version: int | None = None,
) -> MemoryOutboxRow:
    return MemoryOutboxRow(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        aggregate_version=aggregate_version,
        payload_json=payload,
        status="pending",
        attempt_count=0,
        next_attempt_at=now,
        last_safe_error=None,
        created_at=now,
        updated_at=now,
    )


def _parse_dt(value: object, fallback: datetime) -> datetime:
    if not value:
        return fallback
    return datetime.fromisoformat(str(value))


def _bounded_optional_text(value: object, limit: int) -> str | None:
    if value is None:
        return None
    return str(value)[:limit]
