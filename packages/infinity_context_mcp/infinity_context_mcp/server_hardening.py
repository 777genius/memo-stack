"""FastMCP schema and host-argument hardening."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import ConfigDict

_IGNORED_HOST_TOOL_ARGUMENTS = frozenset({"wait_for_previous"})


def install_host_argument_sanitizers(mcp: FastMCP) -> None:
    tool_manager = getattr(mcp, "_tool_manager", None)
    if tool_manager is None:
        return
    for tool in tool_manager.list_tools():
        original_run = tool.run

        async def run(
            arguments: dict[str, Any],
            context: Any | None = None,
            convert_result: bool = False,
            *,
            original_run: Any = original_run,
        ) -> Any:
            return await original_run(
                _sanitize_host_tool_arguments(arguments),
                context=context,
                convert_result=convert_result,
            )

        object.__setattr__(tool, "run", run)


def harden_tool_input_schemas(mcp: FastMCP) -> None:
    tool_manager = getattr(mcp, "_tool_manager", None)
    if tool_manager is None:
        return
    for tool in tool_manager.list_tools():
        tool.parameters.setdefault("additionalProperties", False)
        tool.fn_metadata.arg_model.model_config = ConfigDict(
            arbitrary_types_allowed=True,
            extra="forbid",
        )
        tool.fn_metadata.arg_model.model_rebuild(force=True)


def _sanitize_host_tool_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    if not _IGNORED_HOST_TOOL_ARGUMENTS.intersection(arguments):
        return arguments
    return {
        key: value for key, value in arguments.items() if key not in _IGNORED_HOST_TOOL_ARGUMENTS
    }
