"""Temporal validation helpers for memory_scope snapshot transfer."""

from __future__ import annotations

from datetime import datetime

from infinity_context_core.domain.errors import MemoryValidationError


def validate_temporal_window(
    *,
    valid_from: datetime | None,
    valid_to: datetime | None,
) -> None:
    if valid_from is None or valid_to is None:
        return
    comparable_from = valid_from
    comparable_to = valid_to
    if comparable_from.tzinfo is None and comparable_to.tzinfo is not None:
        comparable_from = comparable_from.replace(tzinfo=comparable_to.tzinfo)
    elif comparable_from.tzinfo is not None and comparable_to.tzinfo is None:
        comparable_to = comparable_to.replace(tzinfo=comparable_from.tzinfo)
    if comparable_to <= comparable_from:
        raise MemoryValidationError("Temporal valid_to must be after valid_from")
