"""High-level MCP setup response schemas."""

from __future__ import annotations

from pydantic import Field

from memo_stack_mcp.domain.local_runtime_models import MemoryLocalRuntimeData
from memo_stack_mcp.domain.models import McpDataModel, McpToolResponse
from memo_stack_mcp.domain.obsidian_models import MemoryObsidianData


class MemoryObsidianPrepareData(McpDataModel):
    status: str | None = None
    dry_run: bool | None = None
    applied: bool | None = None
    local_runtime: MemoryLocalRuntimeData | None = None
    obsidian_setup: MemoryObsidianData | None = None
    local_status: MemoryLocalRuntimeData | None = None
    obsidian_preview: MemoryObsidianData | None = None
    next_actions: list[str] = Field(default_factory=list)


class MemoryObsidianPrepareResponse(McpToolResponse):
    data: MemoryObsidianPrepareData | None = None
