"""Stateless helpers for the agent-facing MCP service."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from memo_stack_core.application.semantic_dedupe import (
    meaningful_memory_terms,
    normalize_memory_text,
)

from memo_stack_mcp.domain.models import (
    MemoryGatewayError,
    MemoryScope,
    MemoryUpdateCandidateInput,
    has_control_characters,
    has_zero_width_characters,
    safe_message,
)


def stable_key(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest[:32]}"


def normalize_candidate(text: str) -> str:
    return normalize_memory_text(text)


def meaningful_terms(text: str) -> set[str]:
    return meaningful_memory_terms(text)


def payload_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data", payload)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def candidate_fingerprint(
    *,
    scope: MemoryScope,
    candidate: MemoryUpdateCandidateInput,
    source_id: str | None,
) -> str:
    return stable_key(
        "mcp-candidate",
        scope.space_slug,
        scope.profile_external_ref,
        scope.thread_external_ref,
        candidate.operation.value,
        candidate.target_fact_id,
        candidate.expected_version,
        normalize_candidate(candidate.text),
        source_id or "",
    )


def candidate_result(
    candidate_index: int,
    status: str,
    decision_code: str,
    *,
    text: str,
    fact_id: str | None = None,
    suggestion_id: str | None = None,
    duplicate_id: str | None = None,
    target_fact_id: str | None = None,
    retryable: bool = False,
    message: str | None = None,
) -> dict[str, Any]:
    resource_uri = f"memory://fact/{fact_id}" if fact_id else None
    return {
        "candidate_index": candidate_index,
        "status": status,
        "decision_code": decision_code,
        "text": text,
        "fact_id": fact_id,
        "suggestion_id": suggestion_id,
        "duplicate_id": duplicate_id,
        "target_fact_id": target_fact_id,
        "resource_uri": resource_uri,
        "retryable": retryable,
        "message": message,
    }


def resource_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def bounded_resource_value(value: Any, *, max_string_chars: int) -> tuple[Any, bool]:
    if isinstance(value, str):
        if len(value) <= max_string_chars:
            return value, False
        return value[:max_string_chars] + "\n[truncated]", True
    if isinstance(value, list):
        bounded_items: list[Any] = []
        truncated = False
        for item in value:
            bounded_item, item_truncated = bounded_resource_value(
                item,
                max_string_chars=max_string_chars,
            )
            bounded_items.append(bounded_item)
            truncated = truncated or item_truncated
        return bounded_items, truncated
    if isinstance(value, dict):
        bounded_dict: dict[str, Any] = {}
        truncated = False
        for key, item in value.items():
            bounded_item, item_truncated = bounded_resource_value(
                item,
                max_string_chars=max_string_chars,
            )
            bounded_dict[str(key)] = bounded_item
            truncated = truncated or item_truncated
        return bounded_dict, truncated
    return value, False


def generated_at() -> str:
    return datetime.now(UTC).isoformat()


def ensure_choice(field_name: str, value: str, allowed: set[str]) -> None:
    if value not in allowed:
        raise MemoryGatewayError(
            status_code=400,
            code="memo_stack_mcp.validation.invalid_input",
            message=f"Invalid {field_name}: {safe_message(value)}",
            retryable=False,
        )


def ensure_bool(field_name: str, value: object) -> None:
    if not isinstance(value, bool):
        raise MemoryGatewayError(
            status_code=400,
            code="memo_stack_mcp.validation.invalid_input",
            message=f"{field_name} must be a boolean",
            retryable=False,
        )


def clamp_int(
    *,
    name: str,
    value: int,
    minimum: int,
    maximum: int,
) -> tuple[int, list[str]]:
    if value < minimum:
        return minimum, [f"{name}_clamped_to_min"]
    if value > maximum:
        return maximum, [f"{name}_clamped_to_max"]
    return value, []


def sanitize_source_path(value: str) -> str:
    if has_control_characters(value) or has_zero_width_characters(value):
        raise MemoryGatewayError(
            status_code=400,
            code="memo_stack_mcp.validation.invalid_source_ref",
            message="Source id contains unsafe formatting characters",
            retryable=False,
        )
    if value.startswith(("/Users/", "/home/")) or "\\Users\\" in value:
        return stable_key("mcp-source-path", value)
    return value
