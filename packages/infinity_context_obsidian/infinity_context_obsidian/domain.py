"""Domain values for the Obsidian connector.

The connector domain is intentionally small and independent from filesystem,
HTTP, sqlite and Obsidian plugin APIs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

NOTE_SCHEMA_VERSION = "infinity_context.obsidian.fact.v1"


class SyncMode(StrEnum):
    DIRECT = "direct"
    SUGGEST = "suggest"
    READONLY = "readonly"
    CONFLICT = "conflict"


class NoteKind(StrEnum):
    FACT = "fact"
    INBOX = "inbox"


class ImportStatus(StrEnum):
    UNCHANGED = "unchanged"
    REMOVED = "removed"
    WOULD_SUGGEST = "would_suggest"
    SUGGESTED = "suggested"
    WOULD_UPDATE = "would_update"
    UPDATED = "updated"
    CONFLICT = "conflict"
    SKIPPED = "skipped"


class ExportStatus(StrEnum):
    WOULD_EXPORT = "would_export"
    EXPORTED = "exported"
    CONFLICT = "conflict"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class ManagedFactNote:
    path: PurePosixPath
    fact_id: str
    version: int
    sync_mode: SyncMode
    text: str
    content_hash: str
    stored_hash: str | None
    frontmatter: dict[str, object]

    @property
    def changed_since_export(self) -> bool:
        return self.stored_hash != self.content_hash


@dataclass(frozen=True)
class SyncStateRecord:
    path: PurePosixPath
    infinity_context_id: str
    kind: NoteKind
    version: int
    content_hash: str


@dataclass(frozen=True)
class ImportChange:
    status: ImportStatus
    path: PurePosixPath
    fact_id: str | None = None
    message: str = ""
    version: int | None = None


@dataclass(frozen=True)
class ExportChange:
    status: ExportStatus
    path: PurePosixPath
    fact_id: str
    message: str = ""
    version: int | None = None


def content_hash(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
