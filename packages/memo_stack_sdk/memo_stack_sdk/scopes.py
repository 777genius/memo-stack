"""Scope value objects for the Memo Stack SDK."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from memo_stack_sdk._payloads import (
    context_scope_payload as _context_scope_payload,
)
from memo_stack_sdk._payloads import (
    single_scope_body as _single_scope_body,
)
from memo_stack_sdk._payloads import (
    validate_read_scope_payload as _validate_read_scope_payload,
)
from memo_stack_sdk._payloads import (
    validate_single_scope_payload as _validate_single_scope_payload,
)


@dataclass(frozen=True)
class MemoryScope:
    space_id: str | None = None
    memory_scope_id: str | None = None
    thread_id: str | None = None
    space_slug: str | None = None
    memory_scope_external_ref: str | None = None
    thread_external_ref: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload = _single_scope_body(
            space_id=self.space_id,
            memory_scope_id=self.memory_scope_id,
            thread_id=self.thread_id,
            space_slug=self.space_slug,
            memory_scope_external_ref=self.memory_scope_external_ref,
            thread_external_ref=self.thread_external_ref,
        )
        _validate_single_scope_payload(payload)
        return payload


@dataclass(frozen=True)
class ReadScope:
    space_id: str | None = None
    memory_scope_ids: tuple[str, ...] | None = None
    thread_id: str | None = None
    space_slug: str | None = None
    memory_scope_external_ref: str | None = None
    memory_scope_external_refs: tuple[str, ...] | None = None
    thread_external_ref: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload = _context_scope_payload(
            space_id=self.space_id,
            memory_scope_ids=list(self.memory_scope_ids)
            if self.memory_scope_ids is not None
            else None,
            thread_id=self.thread_id,
            space_slug=self.space_slug,
            memory_scope_external_ref=self.memory_scope_external_ref,
            memory_scope_external_refs=(
                list(self.memory_scope_external_refs)
                if self.memory_scope_external_refs is not None
                else None
            ),
            thread_external_ref=self.thread_external_ref,
        )
        _validate_read_scope_payload(payload)
        return payload


__all__ = ["MemoryScope", "ReadScope"]
