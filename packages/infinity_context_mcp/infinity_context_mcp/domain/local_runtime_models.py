"""Local runtime MCP response schemas."""

from __future__ import annotations

from pydantic import Field

from infinity_context_mcp.domain.models import McpDataModel, McpToolResponse


class MemoryLocalRuntimeCheckDetailData(McpDataModel):
    key: str | None = None
    value: str | int | bool | None = None


class MemoryLocalRuntimeCheckData(McpDataModel):
    name: str | None = None
    ok: bool | None = None
    message: str | None = None
    details: list[MemoryLocalRuntimeCheckDetailData] = Field(default_factory=list)


class MemoryLocalRuntimeResultData(McpDataModel):
    ok: bool | None = None
    command: list[str] = Field(default_factory=list)
    returncode: int | None = None
    stdout: str | None = None
    stderr: str | None = None


class MemoryLocalRuntimeData(McpDataModel):
    enabled: bool | None = None
    start_enabled: bool | None = None
    status: str | None = None
    dry_run: bool | None = None
    applied: bool | None = None
    home: str | None = None
    repo_dir: str | None = None
    api_url: str | None = None
    config_path: str | None = None
    env_path: str | None = None
    config_exists: bool | None = None
    env_exists: bool | None = None
    token_configured: bool | None = None
    default_local_token: bool | None = None
    runtime_compose_profile: str | None = None
    compose_project_name: str | None = None
    start_compose_profile: str | None = None
    checks: list[MemoryLocalRuntimeCheckData] = Field(default_factory=list)
    written: list[str] = Field(default_factory=list)
    would_write: list[str] = Field(default_factory=list)
    command: list[str] = Field(default_factory=list)
    runtime_result: MemoryLocalRuntimeResultData | None = None


class MemoryLocalRuntimeResponse(McpToolResponse):
    data: MemoryLocalRuntimeData | None = None
