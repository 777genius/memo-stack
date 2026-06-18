"""Postgres usage governance repositories."""

from __future__ import annotations

from datetime import datetime

from infinity_context_core.domain.entities import MemoryScopeId, SpaceId
from infinity_context_core.domain.errors import MemoryConflictError
from infinity_context_core.domain.usage import (
    UsageRecord,
    UsageRecordId,
    UsageRecordStatus,
    UsageResource,
    UsageSubjectType,
)
from infinity_context_core.ports.usage import UsageRepositoryPort
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from infinity_context_adapters.postgres.models import MemoryUsageRecordRow


class PostgresUsageRepository(UsageRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, record: UsageRecord) -> UsageRecord:
        self._session.add(_usage_record_to_row(record))
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise MemoryConflictError("Usage record conflicted with existing data") from exc
        return record

    async def find_by_idempotency_key(self, idempotency_key: str) -> UsageRecord | None:
        row = (
            await self._session.execute(
                select(MemoryUsageRecordRow)
                .where(MemoryUsageRecordRow.idempotency_key == idempotency_key)
                .limit(1)
            )
        ).scalar_one_or_none()
        return _usage_record_row_to_domain(row) if row is not None else None

    async def list_for_source(
        self,
        *,
        source_type: str,
        source_id: str,
        resource: str,
    ) -> list[UsageRecord]:
        rows = (
            await self._session.execute(
                select(MemoryUsageRecordRow)
                .where(
                    MemoryUsageRecordRow.source_type == source_type,
                    MemoryUsageRecordRow.source_id == source_id,
                    MemoryUsageRecordRow.resource == resource,
                )
                .order_by(MemoryUsageRecordRow.created_at.asc(), MemoryUsageRecordRow.id.asc())
            )
        ).scalars()
        return [_usage_record_row_to_domain(row) for row in rows]

    async def sum_quantity(
        self,
        *,
        subject_type: str,
        subject_id: str,
        resource: str,
        window_start: datetime,
        window_end: datetime,
    ) -> int:
        total = (
            await self._session.execute(
                select(func.coalesce(func.sum(MemoryUsageRecordRow.quantity), 0)).where(
                    MemoryUsageRecordRow.subject_type == subject_type,
                    MemoryUsageRecordRow.subject_id == subject_id,
                    MemoryUsageRecordRow.resource == resource,
                    MemoryUsageRecordRow.status == UsageRecordStatus.COMMITTED.value,
                    MemoryUsageRecordRow.window_start == window_start,
                    MemoryUsageRecordRow.window_end == window_end,
                )
            )
        ).scalar_one()
        return int(total or 0)


def _usage_record_to_row(record: UsageRecord) -> MemoryUsageRecordRow:
    return MemoryUsageRecordRow(
        id=str(record.id),
        subject_type=record.subject_type.value,
        subject_id=record.subject_id,
        space_id=str(record.space_id),
        memory_scope_id=str(record.memory_scope_id) if record.memory_scope_id else None,
        resource=record.resource.value,
        quantity=record.quantity,
        status=record.status.value,
        source_type=record.source_type,
        source_id=record.source_id,
        idempotency_key=record.idempotency_key,
        window_start=record.window_start,
        window_end=record.window_end,
        metadata_json=dict(record.metadata),
        created_at=record.created_at,
    )


def _usage_record_row_to_domain(row: MemoryUsageRecordRow) -> UsageRecord:
    return UsageRecord(
        id=UsageRecordId(row.id),
        subject_type=UsageSubjectType(row.subject_type),
        subject_id=row.subject_id,
        space_id=SpaceId(row.space_id),
        memory_scope_id=MemoryScopeId(row.memory_scope_id) if row.memory_scope_id else None,
        resource=UsageResource(row.resource),
        quantity=row.quantity,
        status=UsageRecordStatus(row.status),
        source_type=row.source_type,
        source_id=row.source_id,
        idempotency_key=row.idempotency_key,
        window_start=row.window_start,
        window_end=row.window_end,
        metadata=dict(row.metadata_json or {}),
        created_at=row.created_at,
    )
