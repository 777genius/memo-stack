"""Connector ports."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePosixPath
from typing import Any, Protocol

from memo_stack_obsidian.domain import SyncStateRecord


class MemoryGatewayPort(Protocol):
    def list_facts(
        self,
        *,
        space_slug: str,
        profile_external_ref: str,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Return the public `/v1/facts` response."""

    def get_fact(self, fact_id: str) -> dict[str, Any]:
        """Return one public fact payload."""

    def update_fact(
        self,
        fact_id: str,
        *,
        expected_version: int,
        text: str,
        reason: str,
        source_refs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Apply a direct canonical fact update."""

    def create_suggestion(
        self,
        *,
        space_slug: str,
        profile_external_ref: str,
        candidate_text: str,
        safe_reason: str,
        source_refs: list[dict[str, Any]],
        candidate_fingerprint: str | None = None,
    ) -> dict[str, Any]:
        """Create a pending memory suggestion."""


class VaultPort(Protocol):
    def exists(self, relative_path: PurePosixPath) -> bool:
        """Return whether a relative vault path exists."""

    def write_text(self, relative_path: PurePosixPath, text: str) -> None:
        """Write text atomically under the vault root."""

    def delete_text(self, relative_path: PurePosixPath) -> None:
        """Delete a text file under the vault root if it exists."""

    def read_text(self, relative_path: PurePosixPath) -> str:
        """Read text from a relative vault path."""

    def iter_markdown_files(self, relative_dir: PurePosixPath) -> Iterable[PurePosixPath]:
        """Yield relative markdown paths under a vault subdirectory."""


class SyncStateStorePort(Protocol):
    def get(self, path: PurePosixPath) -> SyncStateRecord | None:
        """Load the last connector state for a note."""

    def save(self, record: SyncStateRecord) -> None:
        """Persist the last connector state for a note."""
