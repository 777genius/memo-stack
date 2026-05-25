"""Production-safe diagnostics for API routes and admin commands."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from memory_adapters.postgres.models import (
    MemoryChunkRow,
    MemoryDocumentRow,
    MemoryFactRow,
    MemoryOutboxRow,
    MemorySuggestionRow,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from memory_server.composition import Container
from memory_server.pagination import cursor_int, decode_cursor, encode_cursor


async def adapter_diagnostics(container: Container) -> dict[str, Any]:
    capabilities = await container.get_capabilities.execute()
    return {
        "adapters": {adapter.name: asdict(adapter) for adapter in capabilities.adapters},
        "enabled_adapters": [
            adapter.name for adapter in capabilities.adapters if adapter.enabled and adapter.healthy
        ],
        "policy_mode": capabilities.policy_mode,
        "deploy_profile": capabilities.deploy_profile,
    }


async def outbox_diagnostics(
    container: Container,
    *,
    limit: int,
    cursor: str | None,
) -> dict[str, Any]:
    decoded_cursor = decode_cursor(cursor, kind="diagnostics_outbox")
    last_id = cursor_int(decoded_cursor, "id")
    async with AsyncSession(container.engine) as session:
        counts = {
            str(status): int(count)
            for status, count in (
                await session.execute(
                    select(MemoryOutboxRow.status, func.count(MemoryOutboxRow.id)).group_by(
                        MemoryOutboxRow.status
                    )
                )
            ).all()
        }
        query = select(MemoryOutboxRow).order_by(MemoryOutboxRow.id).limit(limit + 1)
        if last_id is not None:
            query = query.where(MemoryOutboxRow.id > last_id)
        rows = list((await session.execute(query)).scalars())

    visible_rows = rows[:limit]
    next_cursor = (
        encode_cursor("diagnostics_outbox", id=visible_rows[-1].id)
        if len(rows) > limit and visible_rows
        else None
    )
    return {
        "counts": counts,
        "items": [_outbox_row_to_diagnostic(row) for row in visible_rows],
        "next_cursor": next_cursor,
    }


async def profile_diagnostics(container: Container, *, profile_id: str) -> dict[str, Any]:
    async with AsyncSession(container.engine) as session:
        active_facts = await _count_by_profile(session, MemoryFactRow, profile_id, "active")
        deleted_facts = await _count_by_profile(session, MemoryFactRow, profile_id, "deleted")
        active_documents = await _count_by_profile(
            session, MemoryDocumentRow, profile_id, "active"
        )
        deleted_documents = await _count_by_profile(
            session, MemoryDocumentRow, profile_id, "deleted"
        )
        active_chunks = await _count_by_profile(session, MemoryChunkRow, profile_id, "active")
        deleted_chunks = await _count_by_profile(session, MemoryChunkRow, profile_id, "deleted")
        pending_suggestions = await _count_by_profile(
            session, MemorySuggestionRow, profile_id, "pending"
        )
    return {
        "profile_id": profile_id,
        "facts": {"active": active_facts, "deleted": deleted_facts},
        "documents": {"active": active_documents, "deleted": deleted_documents},
        "chunks": {"active": active_chunks, "deleted": deleted_chunks},
        "suggestions": {"pending": pending_suggestions},
    }


async def _count_by_profile(
    session: AsyncSession,
    model: type[MemoryFactRow]
    | type[MemoryDocumentRow]
    | type[MemoryChunkRow]
    | type[MemorySuggestionRow],
    profile_id: str,
    status: str,
) -> int:
    return int(
        (
            await session.scalar(
                select(func.count())
                .select_from(model)
                .where(model.profile_id == profile_id, model.status == status)
            )
        )
        or 0
    )


def _outbox_row_to_diagnostic(row: MemoryOutboxRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "event_type": row.event_type,
        "aggregate_type": row.aggregate_type,
        "aggregate_id": row.aggregate_id,
        "aggregate_version": row.aggregate_version,
        "status": row.status,
        "attempt_count": row.attempt_count,
        "last_safe_error": row.last_safe_error,
        "next_attempt_at": row.next_attempt_at.isoformat(),
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }
