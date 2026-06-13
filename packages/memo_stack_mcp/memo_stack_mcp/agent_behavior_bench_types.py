"""Shared types for the agent behavior benchmark."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from memo_stack_mcp.agent_behavior_bench_redaction import (
    _redact_payload,
    _truncate_text,
    _truncate_value,
)

DEFAULT_MAX_TOOL_ROUNDS = 8
DEFAULT_OUTPUT_LIMIT_CHARS = 12_000


@dataclass(frozen=True)
class AgentFunctionCall:
    call_id: str
    name: str
    arguments: dict[str, Any]
    raw_arguments: str = ""


@dataclass(frozen=True)
class AgentLlmResponse:
    response_id: str | None
    output_text: str
    function_calls: tuple[AgentFunctionCall, ...] = ()
    raw_output_items: tuple[dict[str, Any], ...] = ()


class AgentLlmClient(Protocol):
    async def create_response(
        self,
        *,
        model: str,
        instructions: str,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        previous_response_id: str | None,
    ) -> AgentLlmResponse: ...


@dataclass(frozen=True)
class AgentBenchConfig:
    base_url: str
    auth_token: str
    model: str
    run_id: str
    mcp_env: Mapping[str, str]
    space_slug_prefix: str = "agent-bench"
    memory_scope_external_ref: str = "default"
    max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS
    python_executable: str = sys.executable
    output_limit_chars: int = DEFAULT_OUTPUT_LIMIT_CHARS
    fail_on_projection_worker_error: bool = False


@dataclass
class ToolTrace:
    name: str
    arguments: dict[str, Any]
    is_error: bool
    output: str
    side_effects: list[str] = field(default_factory=list)
    raw_output_was_sensitive: bool = False

    def to_report(self, *, env: Mapping[str, str] | None) -> dict[str, Any]:
        return _redact_payload(
            {
                "name": self.name,
                "arguments": _truncate_value(self.arguments, max_chars=1200),
                "is_error": self.is_error,
                "side_effects": self.side_effects,
                "output_preview": _truncate_text(self.output, max_chars=1200),
                "raw_output_was_sensitive": self.raw_output_was_sensitive,
            },
            env=env,
        )


PREWRITE_GUARDRAIL_TOOL = "memory_guardrail_blocked_write"


@dataclass
class ScenarioRunResult:
    scenario_id: str
    category: str
    critical: bool
    final_answer: str
    tool_calls: list[ToolTrace]
    tags: tuple[str, ...] = ()
    exceeded_max_rounds: bool = False
    failures: list[dict[str, str]] = field(default_factory=list)
    memory_checks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            not self.exceeded_max_rounds
            and not self.failures
            and all(
                check.get("effective_passed", check.get("passed")) is True
                for check in self.memory_checks
            )
        )

    def to_report(self, *, env: Mapping[str, str] | None) -> dict[str, Any]:
        return _redact_payload(
            {
                "id": self.scenario_id,
                "category": self.category,
                "tags": list(self.tags),
                "critical": self.critical,
                "status": "passed" if self.passed else "failed",
                "tool_calls": [call.to_report(env=env) for call in self.tool_calls],
                "failures": self.failures,
                "memory_checks": self.memory_checks,
                "final_answer": _truncate_text(self.final_answer, max_chars=1200),
                "exceeded_max_rounds": self.exceeded_max_rounds,
            },
            env=env,
        )
