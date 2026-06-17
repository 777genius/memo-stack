"""Scope helpers for MemoryScope snapshot transfer."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from memo_stack_adapters.postgres.models import MemoryScopeRow, MemorySpaceRow, MemoryThreadRow
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memo_stack_server.memory_scope_transfer_remap import episode_source_thread_id
from memo_stack_server.memory_scope_transfer_support import (
    bounded_external_ref,
    import_thread_external_ref,
    stable_id,
)


async def load_scope(
    session: AsyncSession,
    *,
    space_slug: str,
    memory_scope_external_ref: str,
) -> tuple[MemorySpaceRow, MemoryScopeRow] | None:
    space = (
        await session.execute(
            select(MemorySpaceRow).where(
                MemorySpaceRow.slug == space_slug,
                MemorySpaceRow.status == "active",
            )
        )
    ).scalar_one_or_none()
    if space is None:
        return None
    memory_scope = (
        await session.execute(
            select(MemoryScopeRow).where(
                MemoryScopeRow.space_id == space.id,
                MemoryScopeRow.external_ref == memory_scope_external_ref,
                MemoryScopeRow.status == "active",
            )
        )
    ).scalar_one_or_none()
    if memory_scope is None:
        return None
    return space, memory_scope


async def create_import_memory_scope(
    session: AsyncSession,
    *,
    space_id: str,
    base_memory_scope_id: str,
    now: datetime,
) -> MemoryScopeRow:
    base_memory_scope = await session.get(MemoryScopeRow, base_memory_scope_id)
    if base_memory_scope is None:
        msg = "Base memory_scope not found"
        raise ValueError(msg)
    external_ref = await _next_import_memory_scope_ref(
        session,
        space_id=space_id,
        base_external_ref=base_memory_scope.external_ref,
        now=now,
    )
    row = MemoryScopeRow(
        id=stable_id("memory_scope", space_id, external_ref),
        space_id=space_id,
        external_ref=external_ref,
        name=f"{base_memory_scope.name} import",
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    return row


async def ensure_import_threads(
    session: AsyncSession,
    *,
    episodes: list[dict[str, Any]],
    skipped_episode_ids: set[str],
    thread_id_map: dict[str, str],
    space_id: str,
    memory_scope_id: str,
    now: datetime,
) -> None:
    needed = {
        episode_source_thread_id(episode): thread_id_map.get(
            episode_source_thread_id(episode),
            episode_source_thread_id(episode),
        )
        for episode in episodes
        if str(episode.get("id")) not in skipped_episode_ids
    }
    if not needed:
        return
    existing = set(
        (
            await session.execute(
                select(MemoryThreadRow.id).where(MemoryThreadRow.id.in_(set(needed.values())))
            )
        ).scalars()
    )
    for source_thread_id, target_thread_id in needed.items():
        if target_thread_id in existing:
            continue
        session.add(
            MemoryThreadRow(
                id=target_thread_id,
                space_id=space_id,
                memory_scope_id=memory_scope_id,
                external_ref=import_thread_external_ref(source_thread_id, target_thread_id),
                status="active",
                created_at=now,
                updated_at=now,
            )
        )


async def _next_import_memory_scope_ref(
    session: AsyncSession,
    *,
    space_id: str,
    base_external_ref: str,
    now: datetime,
) -> str:
    base = bounded_external_ref(
        f"{base_external_ref}-import-{now.strftime('%Y%m%d%H%M%S')}",
        suffix="",
    )
    candidate = base
    suffix = 2
    while await _memory_scope_ref_exists(session, space_id=space_id, external_ref=candidate):
        candidate = bounded_external_ref(base, suffix=f"-{suffix}")
        suffix += 1
    return candidate


async def _memory_scope_ref_exists(
    session: AsyncSession,
    *,
    space_id: str,
    external_ref: str,
) -> bool:
    return (
        await session.scalar(
            select(MemoryScopeRow.id).where(
                MemoryScopeRow.space_id == space_id,
                MemoryScopeRow.external_ref == external_ref,
            )
        )
        is not None
    )
