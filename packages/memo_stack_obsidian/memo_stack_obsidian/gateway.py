"""Memo Stack SDK gateway adapter."""

from __future__ import annotations

from typing import Any

from memo_stack_sdk import MemoStackClient


class SdkMemoryGateway:
    def __init__(self, client: MemoStackClient) -> None:
        self._client = client

    def list_facts(
        self,
        *,
        space_slug: str,
        memory_scope_external_ref: str,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return self._client.list_facts(
            space_slug=space_slug,
            memory_scope_external_ref=memory_scope_external_ref,
            limit=limit,
            cursor=cursor,
        )

    def get_fact(self, fact_id: str) -> dict[str, Any]:
        return self._client.get_fact(fact_id)

    def update_fact(
        self,
        fact_id: str,
        *,
        expected_version: int,
        text: str,
        reason: str,
        source_refs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self._client.update_fact(
            fact_id,
            expected_version=expected_version,
            text=text,
            reason=reason,
            source_refs=source_refs,
        )

    def create_suggestion(
        self,
        *,
        space_slug: str,
        memory_scope_external_ref: str,
        candidate_text: str,
        safe_reason: str,
        source_refs: list[dict[str, Any]],
        candidate_fingerprint: str | None = None,
    ) -> dict[str, Any]:
        return self._client.create_suggestion(
            space_slug=space_slug,
            memory_scope_external_ref=memory_scope_external_ref,
            candidate_text=candidate_text,
            safe_reason=safe_reason,
            source_refs=source_refs,
            candidate_fingerprint=candidate_fingerprint,
        )
