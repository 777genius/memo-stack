"""Admin projection repair and reindex commands."""

from __future__ import annotations

from datetime import datetime

from memo_stack_adapters.postgres.models import MemoryChunkRow, MemoryFactRow, MemoryOutboxRow
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from memo_stack_server.admin_invariants import ScopeFilters, _resolve_scope, _scope_filters
from memo_stack_server.composition import build_container
from memo_stack_server.config import Settings


async def repair_projections(
    *,
    space: str | None,
    memory_scope: str | None,
    dry_run: bool,
) -> dict[str, object]:
    if not space or not memory_scope:
        return {
            "status": "refused",
            "reason": "repair requires --space and --memory_scope",
            "dry_run": dry_run,
        }
    if not dry_run:
        return {
            "status": "refused",
            "reason": "repair requires --dry-run in Core Lite",
            "dry_run": dry_run,
        }
    container = build_container(Settings())
    try:
        async with AsyncSession(container.engine) as session:
            scope = await _resolve_scope(session, space=space, memory_scope=memory_scope)
            if scope is None:
                return {
                    "status": "not_found",
                    "space": space,
                    "memory_scope": memory_scope,
                    "dry_run": dry_run,
                }
            scope_filters = _scope_filters(scope)
            active_chunks = int(
                (
                    await session.scalar(
                        select(func.count())
                        .select_from(MemoryChunkRow)
                        .where(
                            MemoryChunkRow.status == "active",
                            *scope_filters.for_model(MemoryChunkRow),
                        )
                    )
                )
                or 0
            )
            active_facts = int(
                (
                    await session.scalar(
                        select(func.count())
                        .select_from(MemoryFactRow)
                        .where(
                            MemoryFactRow.status == "active",
                            *scope_filters.for_model(MemoryFactRow),
                        )
                    )
                )
                or 0
            )
        return {
            "status": "ok",
            "space": space,
            "memory_scope": memory_scope,
            "dry_run": dry_run,
            "qdrant": {
                "missing_chunks": active_chunks,
                "stale_chunks": 0,
                "would_upsert": active_chunks,
                "would_delete": 0,
                "enqueued": 0,
                "skipped_existing_jobs": 0,
            },
            "graphiti": {
                "missing_facts": active_facts,
                "stale_facts": 0,
                "would_upsert": active_facts,
                "would_delete": 0,
                "enqueued": 0,
                "skipped_existing_jobs": 0,
            },
        }
    finally:
        await container.engine.dispose()


async def reindex_qdrant(
    *,
    space: str | None,
    memory_scope: str | None,
    dry_run: bool,
    confirmed: bool = False,
) -> dict[str, object]:
    return await _reindex_projection(
        operation="reindex-qdrant",
        adapter_key="qdrant",
        aggregate_type="chunk",
        event_type="vector.upsert_chunk",
        space=space,
        memory_scope=memory_scope,
        dry_run=dry_run,
        confirmed=confirmed,
    )


async def reindex_graphiti(
    *,
    space: str | None,
    memory_scope: str | None,
    dry_run: bool,
    confirmed: bool = False,
) -> dict[str, object]:
    return await _reindex_projection(
        operation="reindex-graphiti",
        adapter_key="graphiti",
        aggregate_type="fact",
        event_type="graph.upsert_fact",
        space=space,
        memory_scope=memory_scope,
        dry_run=dry_run,
        confirmed=confirmed,
    )


async def _reindex_projection(
    *,
    operation: str,
    adapter_key: str,
    aggregate_type: str,
    event_type: str,
    space: str | None,
    memory_scope: str | None,
    dry_run: bool,
    confirmed: bool,
) -> dict[str, object]:
    if not space or not memory_scope:
        return {
            "status": "refused",
            "operation": operation,
            "reason": "reindex requires --space and --memory_scope",
            "dry_run": dry_run,
        }
    if not dry_run and not confirmed:
        return {
            "status": "refused",
            "operation": operation,
            "reason": "reindex requires --i-understand-this-enqueues-projection-jobs",
            "dry_run": dry_run,
        }

    container = build_container(Settings())
    try:
        async with AsyncSession(container.engine) as session:
            scope = await _resolve_scope(session, space=space, memory_scope=memory_scope)
            if scope is None:
                return {
                    "status": "not_found",
                    "operation": operation,
                    "space": space,
                    "memory_scope": memory_scope,
                    "dry_run": dry_run,
                }
            scope_filters = _scope_filters(scope)
            rows = await _active_projection_rows(
                session,
                aggregate_type=aggregate_type,
                scope_filters=scope_filters,
            )
            skipped_existing = 0
            enqueued = 0
            if not dry_run:
                now = container.clock.now()
                for row in rows:
                    aggregate_id = str(row.id)
                    aggregate_version = _projection_aggregate_version(row, aggregate_type)
                    exists_active_job = await _active_projection_job_exists(
                        session,
                        event_type=event_type,
                        aggregate_type=aggregate_type,
                        aggregate_id=aggregate_id,
                        aggregate_version=aggregate_version,
                    )
                    if exists_active_job:
                        skipped_existing += 1
                        continue
                    session.add(
                        _projection_outbox(
                            event_type=event_type,
                            aggregate_type=aggregate_type,
                            aggregate_id=aggregate_id,
                            aggregate_version=aggregate_version,
                            now=now,
                            payload=_projection_payload(
                                aggregate_type=aggregate_type,
                                aggregate_id=aggregate_id,
                                aggregate_version=aggregate_version,
                                space_id=str(row.space_id),
                                memory_scope_id=str(row.memory_scope_id),
                            ),
                        )
                    )
                    enqueued += 1
                await session.commit()
        would_upsert = len(rows)
        return {
            "status": "ok",
            "operation": operation,
            "space": space,
            "memory_scope": memory_scope,
            "dry_run": dry_run,
            adapter_key: _reindex_adapter_payload(
                aggregate_type=aggregate_type,
                would_upsert=would_upsert,
                enqueued=enqueued,
                skipped_existing_jobs=skipped_existing,
            ),
        }
    finally:
        await container.engine.dispose()


async def _active_projection_rows(
    session: AsyncSession,
    *,
    aggregate_type: str,
    scope_filters: ScopeFilters,
) -> list[MemoryChunkRow] | list[MemoryFactRow]:
    if aggregate_type == "chunk":
        return list(
            (
                await session.execute(
                    select(MemoryChunkRow)
                    .where(
                        MemoryChunkRow.status == "active",
                        *scope_filters.for_model(MemoryChunkRow),
                    )
                    .order_by(MemoryChunkRow.id)
                )
            ).scalars()
        )
    if aggregate_type == "fact":
        return list(
            (
                await session.execute(
                    select(MemoryFactRow)
                    .where(
                        MemoryFactRow.status == "active",
                        *scope_filters.for_model(MemoryFactRow),
                    )
                    .order_by(MemoryFactRow.id)
                )
            ).scalars()
        )
    raise ValueError(f"Unsupported projection aggregate type: {aggregate_type}")


async def _active_projection_job_exists(
    session: AsyncSession,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    aggregate_version: int | None,
) -> bool:
    version_filter = (
        MemoryOutboxRow.aggregate_version.is_(None)
        if aggregate_version is None
        else MemoryOutboxRow.aggregate_version == aggregate_version
    )
    count = await session.scalar(
        select(func.count())
        .select_from(MemoryOutboxRow)
        .where(
            MemoryOutboxRow.event_type == event_type,
            MemoryOutboxRow.aggregate_type == aggregate_type,
            MemoryOutboxRow.aggregate_id == aggregate_id,
            version_filter,
            MemoryOutboxRow.status.in_(("pending", "retry_pending", "running")),
        )
    )
    return int(count or 0) > 0


def _projection_aggregate_version(
    row: MemoryChunkRow | MemoryFactRow,
    aggregate_type: str,
) -> int | None:
    if aggregate_type == "fact":
        return int(row.version)
    return None


def _projection_payload(
    *,
    aggregate_type: str,
    aggregate_id: str,
    aggregate_version: int | None,
    space_id: str,
    memory_scope_id: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "space_id": space_id,
        "memory_scope_id": memory_scope_id,
    }
    if aggregate_type == "chunk":
        payload["chunk_id"] = aggregate_id
    elif aggregate_type == "fact":
        payload["fact_id"] = aggregate_id
        payload["fact_version"] = aggregate_version
    return payload


def _reindex_adapter_payload(
    *,
    aggregate_type: str,
    would_upsert: int,
    enqueued: int,
    skipped_existing_jobs: int,
) -> dict[str, object]:
    if aggregate_type == "chunk":
        return {
            "missing_chunks": would_upsert,
            "stale_chunks": 0,
            "would_upsert": would_upsert,
            "would_delete": 0,
            "enqueued": enqueued,
            "skipped_existing_jobs": skipped_existing_jobs,
        }
    return {
        "missing_facts": would_upsert,
        "stale_facts": 0,
        "would_upsert": would_upsert,
        "would_delete": 0,
        "enqueued": enqueued,
        "skipped_existing_jobs": skipped_existing_jobs,
    }


def _projection_outbox(
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
        workload_class="projection",
        fairness_key=f"{aggregate_type}:{aggregate_id}",
        payload_json=payload,
        status="pending",
        attempt_count=0,
        next_attempt_at=now,
        last_safe_error=None,
        last_safe_diagnostic_code=None,
        created_at=now,
        updated_at=now,
    )
