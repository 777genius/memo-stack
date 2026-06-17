"""Export helpers for the public Memo Stack SDK."""

from __future__ import annotations

from typing import Any, Protocol

import memo_stack_sdk._payloads as _payloads
from memo_stack_sdk.scopes import MemoryScope


class _RequestClient(Protocol):
    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]: ...


class MemoStackExportMixin:
    def export_memory_scope_snapshot(
        self: _RequestClient,
        *,
        space_slug: str,
        memory_scope_external_ref: str,
        redacted: bool = False,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/v1/export/memory_scope-snapshot",
            params={
                "space_slug": space_slug,
                "memory_scope_external_ref": memory_scope_external_ref,
                "redacted": redacted,
            },
        )

    def export_graph(
        self: _RequestClient,
        *,
        scope: MemoryScope | None = None,
        space_id: str | None = None,
        memory_scope_id: str | None = None,
        thread_id: str | None = None,
        space_slug: str | None = None,
        memory_scope_external_ref: str | None = None,
        thread_external_ref: str | None = None,
        include_deleted: bool = False,
        include_restricted: bool = False,
        max_facts: int = 250,
        max_documents: int = 100,
        max_episodes: int = 100,
        max_chunks: int = 500,
    ) -> dict[str, Any]:
        scope_payload = (
            scope.to_payload()
            if scope is not None
            else _payloads.single_scope_body(
                space_id=space_id,
                memory_scope_id=memory_scope_id,
                thread_id=thread_id,
                space_slug=space_slug,
                memory_scope_external_ref=memory_scope_external_ref,
                thread_external_ref=thread_external_ref,
            )
        )
        _payloads.validate_single_scope_payload(scope_payload)
        return self._request(
            "GET",
            "/v1/export/graph.json",
            params={
                **scope_payload,
                "include_deleted": include_deleted,
                "include_restricted": include_restricted,
                "max_facts": max_facts,
                "max_documents": max_documents,
                "max_episodes": max_episodes,
                "max_chunks": max_chunks,
            },
        )

    def import_memory_scope_snapshot(
        self: _RequestClient,
        *,
        space_slug: str,
        memory_scope_external_ref: str,
        snapshot: dict[str, Any],
        manifest: dict[str, Any] | None = None,
        dry_run: bool = True,
        merge_strategy: str = "fail_on_conflict",
        confirmed: bool = False,
        source_name: str = "sdk-memory_scope-snapshot",
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/export/memory_scope-snapshot/import",
            json={
                "space_slug": space_slug,
                "memory_scope_external_ref": memory_scope_external_ref,
                "snapshot": snapshot,
                "manifest": manifest,
                "dry_run": dry_run,
                "merge_strategy": merge_strategy,
                "confirmed": confirmed,
                "source_name": source_name,
            },
        )

    def preview_memory_scope_snapshot_import(
        self: _RequestClient,
        *,
        space_slug: str,
        memory_scope_external_ref: str,
        snapshot: dict[str, Any],
        manifest: dict[str, Any] | None = None,
        merge_strategy: str = "fail_on_conflict",
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/export/memory_scope-snapshot/preview",
            json={
                "space_slug": space_slug,
                "memory_scope_external_ref": memory_scope_external_ref,
                "snapshot": snapshot,
                "manifest": manifest,
                "merge_strategy": merge_strategy,
            },
        )
