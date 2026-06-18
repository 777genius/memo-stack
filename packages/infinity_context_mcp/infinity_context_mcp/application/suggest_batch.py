"""Batch suggestion normalization for MCP application services."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from infinity_context_mcp.application.normalization import (
    normalize_optional_label,
    normalize_tool_tags,
)
from infinity_context_mcp.domain.models import (
    MemoryGatewayError,
    MemoryScope,
    MemorySuggestBatchItemInput,
    SourceRef,
)

SourceRefFactory = Callable[[str | None, str | None, str | None, str], SourceRef]


def normalize_suggest_batch_items(
    *,
    items: list[MemorySuggestBatchItemInput | dict[str, Any]],
    scope: MemoryScope,
    source_type: str | None,
    source_id: str | None,
    quote_preview: str | None,
    source_ref_factory: SourceRefFactory,
) -> tuple[list[dict[str, Any]], str]:
    if not items or len(items) > 50:
        raise MemoryGatewayError(
            status_code=400,
            code="infinity_context_mcp.validation.input_too_large",
            message="Batch suggestion create requires 1 to 50 items",
            retryable=False,
        )

    payload_items: list[dict[str, Any]] = []
    total_chars = 0
    for index, raw_item in enumerate(items):
        item = MemorySuggestBatchItemInput.model_validate(raw_item)
        total_chars += len(item.candidate_text)
        if total_chars > 60_000:
            raise MemoryGatewayError(
                status_code=400,
                code="infinity_context_mcp.validation.input_too_large",
                message="Candidate text exceeds the 60000 character batch limit",
                retryable=False,
            )
        source = source_ref_factory(
            source_type,
            source_id,
            item.quote_preview or quote_preview,
            f"suggest-batch:{scope}:{index}:{item.candidate_text}",
        )
        payload_items.append(
            {
                "candidate_text": item.candidate_text,
                "kind": item.kind,
                "source_refs": [source],
                "confidence": item.confidence,
                "trust_level": item.trust_level,
                "safe_reason": item.safe_reason.strip()
                or "mcp_agent_suggestion_requires_review",
                "category": normalize_optional_label(item.category),
                "tags": normalize_tool_tags(item.tags),
                "ttl_policy": normalize_optional_label(item.ttl_policy),
            }
        )
    return payload_items, " ".join(item["candidate_text"] for item in payload_items)
