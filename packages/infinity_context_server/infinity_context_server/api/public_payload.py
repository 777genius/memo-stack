"""Public API payload sanitizers."""

from __future__ import annotations

from typing import Any

from infinity_context_core.application.safe_payload import safe_metadata, safe_metadata_text
from infinity_context_core.application.sensitive_text import contains_sensitive_text

_MAX_DICT_ITEMS = 120


def safe_public_text(value: str, *, limit: int = 500) -> str:
    return safe_metadata_text(value, limit=limit)


def safe_public_reason(value: str, *, limit: int = 500) -> str:
    if contains_sensitive_text(value):
        return "[redacted]"
    return safe_public_text(value, limit=limit)


def safe_public_metadata(metadata: Any, *, max_items: int = _MAX_DICT_ITEMS) -> dict[str, Any]:
    return safe_metadata(metadata, max_items=max_items)
