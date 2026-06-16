"""Context-link review normalization for MCP tools."""

from __future__ import annotations

from typing import Any

from memo_stack_mcp.domain.models import MemoryGatewayError

CONTEXT_LINK_STATUSES = {"active", "deleted"}
CONTEXT_LINK_SUGGESTION_STATUSES = {"pending", "approved", "rejected", "expired"}
CONTEXT_LINK_REVIEW_ACTIONS = {"approve", "reject", "expire"}


def normalize_context_link_review_batch_items(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items:
        raise _invalid("items must be a non-empty list")
    if len(items) > 50:
        raise MemoryGatewayError(
            status_code=400,
            code="memo_stack_mcp.validation.input_too_large",
            message="items supports at most 50 entries",
            retryable=False,
        )
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in items:
        normalized_item = normalize_context_link_review_item(item)
        suggestion_id = normalized_item["suggestion_id"]
        if suggestion_id in seen_ids:
            raise MemoryGatewayError(
                status_code=409,
                code="memo_stack_mcp.conflict.duplicate_batch_item",
                message="duplicate suggestion_id in context-link review batch",
                retryable=False,
            )
        seen_ids.add(suggestion_id)
        normalized.append(normalized_item)
    return normalized


def normalize_context_link_review_item(item: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise _invalid("item must be an object")
    suggestion_id = _bounded_text(item.get("suggestion_id"), "suggestion_id", 160, required=True)
    action = _bounded_text(item.get("action"), "action", 16, required=True)
    if action not in CONTEXT_LINK_REVIEW_ACTIONS:
        raise _invalid(f"Invalid action: {action}")
    return {
        "suggestion_id": suggestion_id,
        "action": action,
        "reason": _bounded_text(item.get("reason"), "reason", 320),
        "target_type": _bounded_text(item.get("target_type"), "target_type", 80),
        "target_id": _bounded_text(item.get("target_id"), "target_id", 160),
        "relation_type": _bounded_text(item.get("relation_type"), "relation_type", 80),
        "confidence": _bounded_text(item.get("confidence"), "confidence", 40),
        "link_reason": _bounded_text(item.get("link_reason"), "link_reason", 320),
    }


def status_filter_payload(
    *,
    status: str | None,
    statuses: list[str] | None,
    allowed: set[str],
) -> tuple[str | None, str | None]:
    if statuses:
        normalized_statuses: list[str] = []
        for item in statuses:
            value = _bounded_text(item, "statuses", 40, required=True)
            if value not in allowed:
                raise _invalid(f"Invalid statuses: {value}")
            normalized_statuses.append(value)
        return None, ",".join(dict.fromkeys(normalized_statuses))
    if status is None:
        return None, None
    value = _bounded_text(status, "status", 40, required=True)
    if value not in allowed:
        raise _invalid(f"Invalid status: {value}")
    return value, None


def _bounded_text(
    value: Any,
    field_name: str,
    max_length: int,
    *,
    required: bool = False,
) -> str | None:
    if value is None:
        if required:
            raise _invalid(f"{field_name} is required")
        return None
    text = str(value).strip()
    if not text and required:
        raise _invalid(f"{field_name} is required")
    if len(text) > max_length:
        raise _invalid(f"{field_name} must be <={max_length} chars")
    return text or None


def _invalid(message: str) -> MemoryGatewayError:
    return MemoryGatewayError(
        status_code=400,
        code="memo_stack_mcp.validation.invalid_input",
        message=message,
        retryable=False,
    )
