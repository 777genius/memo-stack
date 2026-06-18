"""Local policy helpers for MemoryToolService."""

from __future__ import annotations

from typing import Any

from infinity_context_mcp.domain.models import MemoryGatewayError
from infinity_context_mcp.domain.policy import (
    MemoryPolicyInput,
    MemoryPolicyOperation,
    MemoryPolicyResult,
)


class MemoryToolPolicyMixin:
    def _decide_policy(
        self,
        *,
        operation: MemoryPolicyOperation,
        text: str,
        source_type: str | None,
        user_confirmed: bool = False,
        text_length: int | None = None,
    ) -> MemoryPolicyResult:
        result = self._policy.decide(
            MemoryPolicyInput(
                operation=operation,
                text=text,
                source_type=source_type,
                write_mode=self._settings.write_mode,
                delete_mode=self._settings.delete_mode,
                ingest_mode=self._settings.ingest_mode,
                writes_enabled=self._settings.writes_enabled,
                deletes_enabled=self._settings.deletes_enabled,
                user_confirmed=user_confirmed,
                text_length=len(text) if text_length is None else text_length,
                small_doc_max_chars=self._settings.small_doc_max_chars,
            )
        )
        if not result.allowed:
            raise MemoryGatewayError(
                status_code=403,
                code=result.code,
                message=result.safe_message,
                retryable=False,
            )
        return result

    @staticmethod
    def _policy_payload(result: MemoryPolicyResult) -> dict[str, Any]:
        return {
            "decision": result.decision.value,
            "code": result.code,
            "direct_allowed": result.direct_allowed,
            "allowed": result.allowed,
        }

    def _ensure_writes_allowed(self) -> None:
        if not self._settings.writes_enabled:
            raise MemoryGatewayError(
                status_code=403,
                code="infinity_context_mcp.policy.write_mode_off",
                message="Infinity Context MCP writes are disabled by local policy",
                retryable=False,
            )

    def _ensure_deletes_allowed(self) -> None:
        if not self._settings.deletes_enabled:
            raise MemoryGatewayError(
                status_code=403,
                code="infinity_context_mcp.policy.delete_mode_off",
                message="Infinity Context MCP deletes are disabled by local policy",
                retryable=False,
            )
