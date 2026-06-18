"""Conflict artifact rendering for Obsidian-visible sync failures."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from infinity_context_obsidian.domain import ExportChange, ExportStatus, ImportChange, ImportStatus
from infinity_context_obsidian.frontmatter import dump_frontmatter
from infinity_context_obsidian.layout import DEFAULT_ROOT_FOLDER, ObsidianVaultLayout, safe_filename
from infinity_context_obsidian.ports import VaultPort

CONFLICTS_DIR = PurePosixPath(f"{DEFAULT_ROOT_FOLDER}/conflicts")


@dataclass(frozen=True)
class ConflictArtifactResult:
    written: int
    paths: tuple[str, ...]


@dataclass
class WriteConflictArtifactsUseCase:
    vault: VaultPort
    layout: ObsidianVaultLayout = field(default_factory=ObsidianVaultLayout)

    def execute(
        self,
        *,
        direction: str,
        changes: Iterable[ExportChange | ImportChange],
        space_slug: str = "default",
        memory_scope_external_ref: str = "default",
    ) -> ConflictArtifactResult:
        paths: list[str] = []
        for change in changes:
            if not _is_conflict(change):
                continue
            path = conflict_artifact_path(
                direction=direction,
                change=change,
                layout=self.layout,
                space_slug=space_slug,
                memory_scope_external_ref=memory_scope_external_ref,
            )
            self.vault.write_text(
                path,
                render_conflict_artifact(direction=direction, change=change),
            )
            paths.append(path.as_posix())
        return ConflictArtifactResult(written=len(paths), paths=tuple(paths))


def conflict_artifact_path(
    *,
    direction: str,
    change: ExportChange | ImportChange,
    layout: ObsidianVaultLayout | None = None,
    space_slug: str = "default",
    memory_scope_external_ref: str = "default",
) -> PurePosixPath:
    identity = change.fact_id or change.path.as_posix()
    conflicts_dir = (
        layout.conflicts_dir(
            space_slug=space_slug,
            memory_scope_external_ref=memory_scope_external_ref,
        )
        if layout is not None
        else CONFLICTS_DIR
    )
    return conflicts_dir / f"{safe_filename(direction)}-{safe_filename(identity)}.md"


def render_conflict_artifact(
    *,
    direction: str,
    change: ExportChange | ImportChange,
) -> str:
    metadata = {
        "infinity_context_conflict": True,
        "infinity_context_conflict_direction": direction,
        "infinity_context_source_path": change.path.as_posix(),
        "infinity_context_fact_id": change.fact_id or "",
        "infinity_context_version": change.version or "",
    }
    return (
        dump_frontmatter(metadata)
        + "\n".join(
            [
                "# Infinity Context Sync Conflict",
                "",
                f"- Direction: `{direction}`",
                f"- Source path: `{change.path.as_posix()}`",
                f"- Fact id: `{change.fact_id or ''}`",
                f"- Version: `{change.version or ''}`",
                f"- Reason: {change.message or 'Conflict requires review.'}",
                "",
                "## What to do",
                "",
                "Review the source note and Infinity Context fact before applying changes.",
                "Do not delete this conflict note until the source note syncs cleanly.",
                "",
            ]
        )
    )


def _is_conflict(change: ExportChange | ImportChange) -> bool:
    return change.status in {ExportStatus.CONFLICT, ImportStatus.CONFLICT}
