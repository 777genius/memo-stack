"""Response helpers for FastMCP tools."""

from __future__ import annotations

from typing import Any, TypeVar

from mcp.types import CallToolResult, TextContent

from memo_stack_mcp.domain.models import McpToolResponse

TResponse = TypeVar("TResponse", bound=McpToolResponse)


def tool_response(payload: dict[str, Any], response_type: type[TResponse]) -> CallToolResult:
    response = response_type.model_validate(payload)
    structured = response.model_dump(mode="json", exclude_none=True)
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=response.model_dump_json(exclude_none=True, indent=2),
            )
        ],
        structuredContent=structured,
        isError=not response.ok,
    )
