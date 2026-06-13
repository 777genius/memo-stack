"""Response helpers for MemoryToolService."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from memo_stack_mcp.application.normalization import drop_none_values as _drop_none_values
from memo_stack_mcp.domain.models import (
    McpDiagnostics,
    McpToolError,
    McpToolResponse,
    MemoryGatewayError,
    public_error_code,
    safe_message,
)


class MemoryToolResponseMixin:
    def _truncate(self, value: str) -> str:
        if len(value) <= self._settings.max_tool_text_chars:
            return value
        return value[: self._settings.max_tool_text_chars] + "\n[truncated]"

    async def _guard(self, action) -> dict[str, Any]:
        try:
            return await action()
        except MemoryGatewayError as exc:
            code = public_error_code(exc.code, status_code=exc.status_code)
            message = safe_message(exc.message)
            response = McpToolResponse(
                ok=False,
                message=message,
                error=McpToolError(
                    status_code=exc.status_code,
                    code=code,
                    message=message,
                    safe_message=message,
                    retryable=exc.retryable,
                    unknown_commit_state=exc.unknown_commit_state,
                ),
                diagnostics=McpDiagnostics(
                    trace_id=self._trace_id(),
                    backend={"code": safe_message(exc.code), "status_code": exc.status_code},
                    degraded=code.startswith(
                        ("memo_stack_mcp.gateway.", "memo_stack_mcp.degraded.")
                    ),
                ),
            )
            return response.model_dump(exclude_none=True)

    def _ok(
        self,
        message: str,
        *,
        data: dict[str, Any] | list[Any],
        scope: dict[str, Any] | None = None,
        policy: dict[str, Any] | None = None,
        side_effects: list[str] | None = None,
        warnings: list[str] | None = None,
        degraded: bool = False,
        backend: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        diagnostics = McpDiagnostics(
            trace_id=self._trace_id(),
            scope=scope,
            policy=policy or {},
            side_effects=side_effects or [],
            warnings=warnings or [],
            degraded=degraded,
            backend=backend or {},
        )
        clean_data = _drop_none_values(data)
        response_data: dict[str, Any] | list[Any]
        response_data = {"items": clean_data} if isinstance(clean_data, list) else clean_data
        return {
            "ok": True,
            "message": message,
            "data": response_data,
            "diagnostics": diagnostics.model_dump(exclude_none=True),
        }

    async def _capture_gateway(
        self,
        call: Callable[[], Awaitable[dict[str, Any]]],
    ) -> tuple[dict[str, Any] | None, MemoryGatewayError | None]:
        try:
            return await call(), None
        except MemoryGatewayError as exc:
            return None, exc

    @staticmethod
    def _trace_id() -> str:
        return f"mcp_{uuid.uuid4().hex[:16]}"
