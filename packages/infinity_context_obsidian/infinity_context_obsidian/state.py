"""SQLite sync state adapter."""

from __future__ import annotations

import sqlite3
from pathlib import Path, PurePosixPath

from infinity_context_obsidian.domain import NoteKind, SyncStateRecord


class SqliteSyncStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path.expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def get(self, path: PurePosixPath) -> SyncStateRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT path, infinity_context_id, kind, version, content_hash
                FROM obsidian_sync_notes
                WHERE path = ?
                """,
                (path.as_posix(),),
            ).fetchone()
        if row is None:
            return None
        return SyncStateRecord(
            path=PurePosixPath(str(row["path"])),
            infinity_context_id=str(row["infinity_context_id"]),
            kind=NoteKind(str(row["kind"])),
            version=int(row["version"]),
            content_hash=str(row["content_hash"]),
        )

    def save(self, record: SyncStateRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO obsidian_sync_notes (
                    path, infinity_context_id, kind, version, content_hash, updated_at
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(path) DO UPDATE SET
                    infinity_context_id = excluded.infinity_context_id,
                    kind = excluded.kind,
                    version = excluded.version,
                    content_hash = excluded.content_hash,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    record.path.as_posix(),
                    record.infinity_context_id,
                    record.kind.value,
                    record.version,
                    record.content_hash,
                ),
            )

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS obsidian_sync_notes (
                    path TEXT PRIMARY KEY,
                    infinity_context_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_obsidian_sync_notes_infinity_context_id
                ON obsidian_sync_notes (infinity_context_id)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn
