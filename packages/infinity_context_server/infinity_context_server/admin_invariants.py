"""Admin invariant checks for canonical memory storage."""

from __future__ import annotations

from infinity_context_adapters.postgres.models import (
    MemoryChunkRow,
    MemoryDocumentRow,
    MemoryEpisodeRow,
    MemoryFactRow,
    MemoryIdempotencyRecordRow,
    MemoryOutboxRow,
    MemoryScopeRow,
    MemorySourceRefRow,
    MemorySpaceRow,
    MemorySuggestionRow,
    MemoryThreadRow,
)
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from infinity_context_server.composition import build_container
from infinity_context_server.config import Settings


async def _count_outbox(session: AsyncSession, status: str) -> int:
    return int(
        (
            await session.scalar(
                select(func.count())
                .select_from(MemoryOutboxRow)
                .where(MemoryOutboxRow.status == status)
            )
        )
        or 0
    )


async def invariant_check(
    *,
    space: str | None = None,
    memory_scope: str | None = None,
    include_projections: bool = False,
) -> dict[str, object]:
    container = build_container(Settings())
    try:
        async with AsyncSession(container.engine) as session:
            scope = await _resolve_scope(session, space=space, memory_scope=memory_scope)
            if (space or memory_scope) and scope is None:
                return {
                    "status": "not_found",
                    "checks": [],
                    "space": space,
                    "memory_scope": memory_scope,
                }
            scope_filters = _scope_filters(scope)
            active_facts = await session.scalar(
                select(func.count())
                .select_from(MemoryFactRow)
                .where(MemoryFactRow.status == "active", *scope_filters.for_model(MemoryFactRow))
            )
            active_chunks = await session.scalar(
                select(func.count())
                .select_from(MemoryChunkRow)
                .where(MemoryChunkRow.status == "active", *scope_filters.for_model(MemoryChunkRow))
            )
            dead = await _count_outbox(session, "dead")
            checks = [
                await _check_active_fact_source_refs(session, scope_filters),
                await _check_active_chunk_parent_exists(session, scope_filters),
                await _check_memory_scope_rows_match_scope(session, scope_filters),
                await _check_deleted_document_has_no_active_chunks(session, scope_filters),
                await _check_idempotency_results_exist(session, scope_filters),
                _check_dead_outbox(dead),
            ]
            if include_projections:
                checks.append(
                    await _check_projection_outbox_aggregates_exist(session, scope_filters)
                )
        failed = [check for check in checks if check["status"] != "ok"]
        active_facts_without_source_refs = next(
            check["count"] for check in checks if check["name"] == "active_fact_source_refs"
        )
        return {
            "status": "ok" if not failed else "failed",
            "space": space,
            "memory_scope": memory_scope,
            "checks": checks,
            "active_facts": int(active_facts or 0),
            "active_facts_without_source_refs": int(active_facts_without_source_refs),
            "active_chunks": int(active_chunks or 0),
            "dead_outbox_jobs": dead,
            "include_projections": include_projections,
        }
    finally:
        await container.engine.dispose()


async def _check_active_fact_source_refs(
    session: AsyncSession,
    scope_filters: ScopeFilters,
) -> dict[str, object]:
    rows = list(
        (
            await session.execute(
                select(MemoryFactRow.id)
                .outerjoin(
                    MemorySourceRefRow,
                    (MemorySourceRefRow.fact_id == MemoryFactRow.id)
                    & (MemorySourceRefRow.fact_version == MemoryFactRow.version),
                )
                .where(
                    MemoryFactRow.status == "active",
                    MemorySourceRefRow.id.is_(None),
                    *scope_filters.for_model(MemoryFactRow),
                )
                .order_by(MemoryFactRow.id)
                .limit(50)
            )
        ).scalars()
    )
    return _check("active_fact_source_refs", rows)


async def _check_active_chunk_parent_exists(
    session: AsyncSession,
    scope_filters: ScopeFilters,
) -> dict[str, object]:
    document_exists = exists(
        select(MemoryDocumentRow.id).where(MemoryDocumentRow.id == MemoryChunkRow.document_id)
    )
    episode_exists = exists(
        select(MemoryEpisodeRow.id).where(MemoryEpisodeRow.id == MemoryChunkRow.episode_id)
    )
    rows = list(
        (
            await session.execute(
                select(MemoryChunkRow.id)
                .where(
                    MemoryChunkRow.status == "active",
                    or_(
                        and_(
                            MemoryChunkRow.document_id.is_(None),
                            MemoryChunkRow.episode_id.is_(None),
                        ),
                        and_(
                            MemoryChunkRow.document_id.is_not(None),
                            ~document_exists,
                        ),
                        and_(
                            MemoryChunkRow.episode_id.is_not(None),
                            ~episode_exists,
                        ),
                    ),
                    *scope_filters.for_model(MemoryChunkRow),
                )
                .order_by(MemoryChunkRow.id)
                .limit(50)
            )
        ).scalars()
    )
    return _check("active_chunk_parent_exists", rows)


async def _check_memory_scope_rows_match_scope(
    session: AsyncSession,
    scope_filters: ScopeFilters,
) -> dict[str, object]:
    ids: list[str] = []
    for model, prefix in (
        (MemoryFactRow, "fact"),
        (MemoryDocumentRow, "doc"),
        (MemoryChunkRow, "chunk"),
        (MemorySuggestionRow, "suggestion"),
    ):
        ids.extend(
            f"{prefix}:{row_id}"
            for row_id in (
                await session.execute(
                    select(model.id)
                    .outerjoin(
                        MemoryScopeRow,
                        (MemoryScopeRow.id == model.memory_scope_id)
                        & (MemoryScopeRow.space_id == model.space_id),
                    )
                    .where(
                        MemoryScopeRow.id.is_(None),
                        *scope_filters.for_model(model),
                    )
                    .order_by(model.id)
                    .limit(50)
                )
            ).scalars()
        )
    return _check("memory_scope_scoped_rows_match_memory_scope", ids[:50])


async def _check_deleted_document_has_no_active_chunks(
    session: AsyncSession,
    scope_filters: ScopeFilters,
) -> dict[str, object]:
    rows = list(
        (
            await session.execute(
                select(MemoryChunkRow.id)
                .join(MemoryDocumentRow, MemoryDocumentRow.id == MemoryChunkRow.document_id)
                .where(
                    MemoryChunkRow.status == "active",
                    MemoryDocumentRow.status == "deleted",
                    *scope_filters.for_model(MemoryChunkRow),
                )
                .order_by(MemoryChunkRow.id)
                .limit(50)
            )
        ).scalars()
    )
    return _check("deleted_document_active_chunks", rows)


async def _check_idempotency_results_exist(
    session: AsyncSession,
    scope_filters: ScopeFilters,
) -> dict[str, object]:
    rows = list(
        (
            await session.execute(
                select(MemoryIdempotencyRecordRow).where(*scope_filters.for_idempotency())
            )
        ).scalars()
    )
    broken: list[str] = []
    for row in rows:
        model = {
            "fact": MemoryFactRow,
            "document": MemoryDocumentRow,
            "episode": MemoryEpisodeRow,
        }.get(row.result_type)
        if model is None:
            broken.append(str(row.id))
            continue
        exists_result = await session.scalar(
            select(func.count()).select_from(model).where(model.id == row.result_id)
        )
        if int(exists_result or 0) == 0:
            broken.append(str(row.id))
    return _check("idempotency_results_exist", broken[:50])


def _check_dead_outbox(dead: int) -> dict[str, object]:
    return {
        "name": "dead_outbox_jobs",
        "status": "ok" if dead == 0 else "failed",
        "count": dead,
        "ids": [],
    }


async def _check_projection_outbox_aggregates_exist(
    session: AsyncSession,
    scope_filters: ScopeFilters,
) -> dict[str, object]:
    rows = list(
        (
            await session.execute(
                select(MemoryOutboxRow)
                .where(MemoryOutboxRow.workload_class == "projection")
                .order_by(MemoryOutboxRow.id)
                .limit(500)
            )
        ).scalars()
    )
    broken: list[str] = []
    for row in rows:
        model = _projection_aggregate_model(row.aggregate_type)
        if model is None:
            continue
        exists_any = await session.scalar(
            select(func.count()).select_from(model).where(model.id == row.aggregate_id)
        )
        if int(exists_any or 0) == 0:
            if scope_filters.is_scoped and not scope_filters.matches_payload(row.payload_json):
                continue
            broken.append(f"{row.aggregate_type}:{row.aggregate_id}")
            continue
        if scope_filters.is_scoped:
            exists_scoped = await session.scalar(
                select(func.count())
                .select_from(model)
                .where(model.id == row.aggregate_id, *scope_filters.for_model(model))
            )
            if int(exists_scoped or 0) == 0:
                continue
    return _check("projection_outbox_aggregate_exists", broken[:50])


def _projection_aggregate_model(
    aggregate_type: str,
) -> (
    type[MemoryFactRow]
    | type[MemoryDocumentRow]
    | type[MemoryChunkRow]
    | type[MemoryEpisodeRow]
    | type[MemoryThreadRow]
    | None
):
    return {
        "fact": MemoryFactRow,
        "document": MemoryDocumentRow,
        "chunk": MemoryChunkRow,
        "episode": MemoryEpisodeRow,
        "thread": MemoryThreadRow,
    }.get(aggregate_type)


def _check(name: str, ids: list[str]) -> dict[str, object]:
    return {
        "name": name,
        "status": "ok" if not ids else "failed",
        "count": len(ids),
        "ids": ids[:20],
    }


class ScopeFilters:
    def __init__(self, *, space_id: str | None, memory_scope_id: str | None) -> None:
        self.space_id = space_id
        self.memory_scope_id = memory_scope_id

    def for_model(self, model) -> list[object]:
        filters = []
        if self.space_id is not None:
            filters.append(model.space_id == self.space_id)
        if self.memory_scope_id is not None:
            filters.append(model.memory_scope_id == self.memory_scope_id)
        return filters

    def for_idempotency(self) -> list[object]:
        if self.space_id is None:
            return []
        return [MemoryIdempotencyRecordRow.space_id == self.space_id]

    @property
    def is_scoped(self) -> bool:
        return self.space_id is not None or self.memory_scope_id is not None

    def matches_payload(self, payload: object) -> bool:
        if not isinstance(payload, dict):
            return False
        if self.space_id is not None and str(payload.get("space_id")) != self.space_id:
            return False
        if (
            self.memory_scope_id is not None
            and str(payload.get("memory_scope_id")) != self.memory_scope_id
        ):
            return False
        return self.is_scoped


async def _resolve_scope(
    session: AsyncSession,
    *,
    space: str | None,
    memory_scope: str | None,
) -> tuple[str | None, str | None] | None:
    if space is None and memory_scope is None:
        return (None, None)
    if space is None or memory_scope is None:
        return None
    space_row = (
        await session.execute(select(MemorySpaceRow).where(MemorySpaceRow.slug == space))
    ).scalar_one_or_none()
    if space_row is None:
        return None
    memory_scope_row = (
        await session.execute(
            select(MemoryScopeRow).where(
                MemoryScopeRow.space_id == space_row.id,
                MemoryScopeRow.external_ref == memory_scope,
            )
        )
    ).scalar_one_or_none()
    if memory_scope_row is None:
        return None
    return (space_row.id, memory_scope_row.id)


def _scope_filters(scope: tuple[str | None, str | None] | None) -> ScopeFilters:
    space_id, memory_scope_id = scope or (None, None)
    return ScopeFilters(space_id=space_id, memory_scope_id=memory_scope_id)
