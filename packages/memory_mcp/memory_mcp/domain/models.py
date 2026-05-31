"""Small domain model owned by the MCP adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MemoryScope:
    space_slug: str
    profile_external_ref: str
    thread_external_ref: str | None = None

    def to_read_scope(self) -> MemoryReadScope:
        return MemoryReadScope(
            space_slug=self.space_slug,
            profile_external_refs=(self.profile_external_ref,),
            thread_external_ref=self.thread_external_ref,
        )


@dataclass(frozen=True)
class MemoryReadScope:
    space_slug: str
    profile_external_refs: tuple[str, ...]
    thread_external_ref: str | None = None

    def __post_init__(self) -> None:
        normalized_space = self.space_slug.strip()
        normalized_profiles = tuple(ref.strip() for ref in self.profile_external_refs)
        if not normalized_space:
            raise ValueError("MemoryReadScope.space_slug is required")
        if not normalized_profiles:
            raise ValueError("MemoryReadScope.profile_external_refs is required")
        if any(not ref for ref in normalized_profiles):
            raise ValueError("MemoryReadScope.profile_external_refs cannot contain blanks")
        if len(set(normalized_profiles)) != len(normalized_profiles):
            raise ValueError("MemoryReadScope.profile_external_refs must be unique")
        normalized_thread = self.thread_external_ref.strip() if self.thread_external_ref else None
        if self.thread_external_ref is not None and not normalized_thread:
            raise ValueError("MemoryReadScope.thread_external_ref cannot be blank")
        if normalized_thread is not None and len(normalized_profiles) > 1:
            raise ValueError("MemoryReadScope thread scope supports one profile")
        object.__setattr__(self, "space_slug", normalized_space)
        object.__setattr__(self, "profile_external_refs", normalized_profiles)
        object.__setattr__(self, "thread_external_ref", normalized_thread)


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
