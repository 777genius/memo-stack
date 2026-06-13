"""Authentication and authorization scope ports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from memo_stack_core.domain.errors import MemoryValidationError


@dataclass(frozen=True)
class MemoryUser:
    id: str
    type: str
    permissions: tuple[str, ...]
    space_ids: tuple[str, ...]
    memory_scope_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemoryWriteScope:
    space_id: str
    memory_scope_id: str
    thread_id: str | None = None
    tenant_id: str | None = None
    workspace_id: str | None = None

    def __post_init__(self) -> None:
        if not self.space_id.strip():
            raise MemoryValidationError("MemoryWriteScope.space_id is required")
        if not self.memory_scope_id.strip():
            raise MemoryValidationError("MemoryWriteScope.memory_scope_id is required")
        if self.thread_id is not None and not self.thread_id.strip():
            raise MemoryValidationError("MemoryWriteScope.thread_id cannot be blank")
        if self.tenant_id is not None and not self.tenant_id.strip():
            raise MemoryValidationError("MemoryWriteScope.tenant_id cannot be blank")
        if self.workspace_id is not None and not self.workspace_id.strip():
            raise MemoryValidationError("MemoryWriteScope.workspace_id cannot be blank")


@dataclass(frozen=True)
class ReadScope:
    space_id: str
    memory_scope_ids: tuple[str, ...]
    thread_id: str | None = None
    tenant_id: str | None = None
    workspace_id: str | None = None

    def __post_init__(self) -> None:
        if not self.space_id.strip():
            raise MemoryValidationError("ReadScope.space_id is required")
        if not self.memory_scope_ids:
            raise MemoryValidationError("ReadScope.memory_scope_ids is required")
        if any(not memory_scope_id.strip() for memory_scope_id in self.memory_scope_ids):
            raise MemoryValidationError("ReadScope.memory_scope_ids cannot contain blanks")
        if len(set(self.memory_scope_ids)) != len(self.memory_scope_ids):
            raise MemoryValidationError("ReadScope.memory_scope_ids cannot contain duplicates")
        if self.thread_id is not None and not self.thread_id.strip():
            raise MemoryValidationError("ReadScope.thread_id cannot be blank")
        if self.tenant_id is not None and not self.tenant_id.strip():
            raise MemoryValidationError("ReadScope.tenant_id cannot be blank")
        if self.workspace_id is not None and not self.workspace_id.strip():
            raise MemoryValidationError("ReadScope.workspace_id cannot be blank")


class AuthPort(Protocol):
    async def authenticate(self, token: str | None) -> MemoryUser:
        """Authenticate a request token."""
