"""Public API payload sanitizers."""

from __future__ import annotations

from typing import Any

from memo_stack_core.application.safe_payload import safe_metadata, safe_metadata_text

_MAX_DICT_ITEMS = 120


def safe_public_text(value: str, *, limit: int = 500) -> str:
    return safe_metadata_text(value, limit=limit)


def safe_public_metadata(metadata: Any, *, max_items: int = _MAX_DICT_ITEMS) -> dict[str, Any]:
    return safe_metadata(metadata, max_items=max_items)
