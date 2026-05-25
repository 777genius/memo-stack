"""Ports used by the Memory MCP application service."""

from __future__ import annotations

from typing import Any, Protocol

from memory_mcp.domain.models import MemoryScope, SourceRef


class MemoryGatewayPort(Protocol):
    async def health(self) -> dict[str, Any]: ...

    async def capabilities(self) -> dict[str, Any]: ...

    async def build_context(
        self,
        *,
        scope: MemoryScope,
        query: str,
        token_budget: int,
        max_facts: int,
        max_chunks: int,
    ) -> dict[str, Any]: ...

    async def remember_fact(
        self,
        *,
        scope: MemoryScope,
        text: str,
        kind: str,
        source_refs: list[SourceRef],
        classification: str,
        idempotency_key: str,
    ) -> dict[str, Any]: ...

    async def list_facts(
        self,
        *,
        scope: MemoryScope,
        status: str | None,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]: ...

    async def get_fact(self, *, fact_id: str) -> dict[str, Any]: ...

    async def list_fact_versions(self, *, fact_id: str) -> dict[str, Any]: ...

    async def update_fact(
        self,
        *,
        fact_id: str,
        expected_version: int,
        text: str,
        reason: str,
        source_refs: list[SourceRef],
    ) -> dict[str, Any]: ...

    async def forget_fact(self, *, fact_id: str) -> dict[str, Any]: ...

    async def ingest_document(
        self,
        *,
        scope: MemoryScope,
        title: str,
        text: str,
        source_type: str,
        source_external_id: str,
        classification: str,
        idempotency_key: str,
    ) -> dict[str, Any]: ...
