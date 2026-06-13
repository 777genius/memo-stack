"""Thread-memory helpers for the public Memo Stack SDK."""

from __future__ import annotations

from typing import Any

import memo_stack_sdk._payloads as _payloads


class MemoStackThreadMemoryMixin:
    def thread_memory_status(
        self,
        *,
        space_id: str | None = None,
        memory_scope_id: str | None = None,
        thread_id: str | None = None,
        space_slug: str | None = None,
        memory_scope_external_ref: str | None = None,
        thread_external_ref: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/thread-memory/status",
            json=_payloads.single_scope_body(
                space_id=space_id,
                memory_scope_id=memory_scope_id,
                thread_id=thread_id,
                space_slug=space_slug,
                memory_scope_external_ref=memory_scope_external_ref,
                thread_external_ref=thread_external_ref,
            ),
        )

    def delete_thread_memory(
        self,
        *,
        space_id: str | None = None,
        memory_scope_id: str | None = None,
        thread_id: str | None = None,
        space_slug: str | None = None,
        memory_scope_external_ref: str | None = None,
        thread_external_ref: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "DELETE",
            "/v1/thread-memory",
            json=_payloads.single_scope_body(
                space_id=space_id,
                memory_scope_id=memory_scope_id,
                thread_id=thread_id,
                space_slug=space_slug,
                memory_scope_external_ref=memory_scope_external_ref,
                thread_external_ref=thread_external_ref,
            ),
        )
