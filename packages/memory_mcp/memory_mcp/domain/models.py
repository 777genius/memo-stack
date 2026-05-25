"""Small domain model owned by the MCP adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MemoryScope:
    space_slug: str
    profile_external_ref: str
    thread_external_ref: str | None = None


@dataclass(frozen=True)
class SourceRef:
    source_type: str
    source_id: str
    chunk_id: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    quote_preview: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return _without_none(
            {
                "source_type": self.source_type,
                "source_id": self.source_id,
                "chunk_id": self.chunk_id,
                "char_start": self.char_start,
                "char_end": self.char_end,
                "quote_preview": self.quote_preview,
            }
        )


@dataclass(frozen=True)
class MemoryGatewayError(RuntimeError):
    status_code: int
    code: str
    message: str
    retryable: bool

    def __str__(self) -> str:
        return self.message


def _without_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}
