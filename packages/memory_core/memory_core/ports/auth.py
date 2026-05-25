"""Authentication ports and principal DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MemoryPrincipal:
    id: str
    type: str
    permissions: tuple[str, ...]
    space_ids: tuple[str, ...]
    profile_ids: tuple[str, ...] = ()


class AuthPort(Protocol):
    async def authenticate(self, token: str | None) -> MemoryPrincipal:
        """Authenticate a request token."""
