"""Obsidian MCP response schemas."""

from __future__ import annotations

from pydantic import Field

from memo_stack_mcp.domain.models import McpDataModel, McpToolResponse


class MemoryObsidianCheckData(McpDataModel):
    name: str | None = None
    ok: bool | None = None
    required: bool | None = None
    message: str | None = None


class MemoryObsidianChangeData(McpDataModel):
    status: str | None = None
    path: str | None = None
    fact_id: str | None = None
    message: str | None = None
    version: int | None = None


class MemoryObsidianSyncPartData(McpDataModel):
    updated: int | None = None
    would_update: int | None = None
    suggested: int | None = None
    would_suggest: int | None = None
    exported: int | None = None
    skipped: int | None = None
    conflicts: int | None = None
    conflict_artifacts_written: int | None = None
    paths: list[str] = Field(default_factory=list)
    conflict_artifacts: list[str] = Field(default_factory=list)
    changes: list[MemoryObsidianChangeData] = Field(default_factory=list)


class MemoryObsidianData(McpDataModel):
    enabled: bool | None = None
    sync_enabled: bool | None = None
    configured: bool | None = None
    status: str | None = None
    dry_run: bool | None = None
    applied: bool | None = None
    vault_path: str | None = None
    obsidian_config_dir: str | None = None
    root_folder: str | None = None
    layout_version: str | None = None
    space_slug: str | None = None
    memory_scope_external_ref: str | None = None
    checks: list[MemoryObsidianCheckData] = Field(default_factory=list)
    written: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    would_write: list[str] = Field(default_factory=list)
    would_install_plugin: bool | None = None
    plugin_installed: bool | None = None
    plugin_enabled: bool | None = None
    settings_path: str | None = None
    import_result: MemoryObsidianSyncPartData | None = None
    export_result: MemoryObsidianSyncPartData | None = None
    export_skipped: bool | None = None
    export_skipped_reason: str | None = None


class MemoryObsidianResponse(McpToolResponse):
    data: MemoryObsidianData | None = None
