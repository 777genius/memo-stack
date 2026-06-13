"""Ports for usage governance persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from memo_stack_core.domain.usage import UsageRecord


class UsageRepositoryPort(Protocol):
    async def create(self, record: UsageRecord) -> UsageRecord:
        """Persist an append-only usage record."""

    async def find_by_idempotency_key(self, idempotency_key: str) -> UsageRecord | None:
        """Load an existing usage record for an idempotent operation."""

    async def list_for_source(
        self,
        *,
        source_type: str,
        source_id: str,
        resource: str,
    ) -> list[UsageRecord]:
        """Load usage records for one source/resource."""

    async def sum_quantity(
        self,
        *,
        subject_type: str,
        subject_id: str,
        resource: str,
        window_start: datetime,
        window_end: datetime,
    ) -> int:
        """Return committed usage quantity inside one billing window."""
