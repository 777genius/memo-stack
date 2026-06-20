"""Coordinate sanitation for provider-neutral extraction evidence."""

from __future__ import annotations

import math
from collections.abc import Sequence


def safe_time_range_ms(
    *,
    start_ms: int | None,
    end_ms: int | None,
) -> tuple[int | None, int | None]:
    """Return a bounded non-negative time range without fabricating invalid ends."""

    start = _non_negative_int(start_ms)
    end = _non_negative_int(end_ms)
    if start is not None and end is not None and end < start:
        end = None
    return start, end


def safe_page_number(value: int | None) -> int | None:
    page = _non_negative_int(value)
    return page if page is not None and page >= 1 else None


def safe_bbox(value: Sequence[float] | None) -> list[float] | None:
    """Return a finite non-negative [x1, y1, x2, y2] bbox or None."""

    if value is None or len(value) != 4:
        return None
    bbox: list[float] = []
    for raw in value:
        try:
            number = float(raw)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number):
            return None
        bbox.append(round(number, 4))
    if any(number < 0 for number in bbox):
        return None
    if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        return None
    return bbox


def _non_negative_int(value: int | None) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None
