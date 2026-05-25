"""Configuration for the Memory Platform MCP adapter."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class McpTransport(StrEnum):
    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable-http"


@dataclass(frozen=True)
class MemoryMcpSettings:
    api_url: str = "http://127.0.0.1:7788"
    auth_token: str | None = None
    default_space_slug: str = "hackinterview"
    default_profile_external_ref: str = "default"
    default_thread_external_ref: str | None = None
    agent_name: str = "mcp-agent"
    source_type: str = "ai_response"
    request_timeout_seconds: float = 10.0
    max_tool_text_chars: int = 20_000
    allow_writes: bool = True
    allow_deletes: bool = True
    transport: McpTransport = McpTransport.STDIO

    @property
    def sanitized_api_url(self) -> str:
        return self.api_url.rstrip("/")


def load_settings(env: Mapping[str, str] | None = None) -> MemoryMcpSettings:
    values = env or os.environ
    token = _get(values, "MEMORY_MCP_AUTH_TOKEN") or _get(values, "MEMORY_SERVICE_TOKEN")
    return MemoryMcpSettings(
        api_url=_get(values, "MEMORY_MCP_API_URL", "http://127.0.0.1:7788").rstrip("/"),
        auth_token=token,
        default_space_slug=_get(values, "MEMORY_MCP_DEFAULT_SPACE_SLUG", "hackinterview"),
        default_profile_external_ref=_get(
            values, "MEMORY_MCP_DEFAULT_PROFILE_EXTERNAL_REF", "default"
        ),
        default_thread_external_ref=_empty_to_none(
            _get(values, "MEMORY_MCP_DEFAULT_THREAD_EXTERNAL_REF")
        ),
        agent_name=_get(values, "MEMORY_MCP_AGENT_NAME", "mcp-agent"),
        source_type=_get(values, "MEMORY_MCP_SOURCE_TYPE", "ai_response"),
        request_timeout_seconds=_positive_float(
            _get(values, "MEMORY_MCP_REQUEST_TIMEOUT_SECONDS", "10"),
            "MEMORY_MCP_REQUEST_TIMEOUT_SECONDS",
        ),
        max_tool_text_chars=_positive_int(
            _get(values, "MEMORY_MCP_MAX_TOOL_TEXT_CHARS", "20000"),
            "MEMORY_MCP_MAX_TOOL_TEXT_CHARS",
        ),
        allow_writes=_bool(_get(values, "MEMORY_MCP_ALLOW_WRITES", "true")),
        allow_deletes=_bool(_get(values, "MEMORY_MCP_ALLOW_DELETES", "true")),
        transport=McpTransport(_get(values, "MEMORY_MCP_TRANSPORT", McpTransport.STDIO.value)),
    )


def _get(values: Mapping[str, str], key: str, default: str | None = None) -> str:
    value = values.get(key)
    if value is None:
        return "" if default is None else default
    return value.strip()


def _empty_to_none(value: str) -> str | None:
    return value or None


def _positive_float(value: str, name: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive number") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _bool(value: str) -> bool:
    return value.lower() not in {"0", "false", "no", "off"}
