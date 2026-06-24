"""Safe temporal metadata extraction helpers."""

from __future__ import annotations

import re
from collections.abc import Mapping

_TEMPORAL_HINT_CODE_KEYS = (
    "event_temporal_hint_code",
    "temporal_hint_code",
    "event_time_hint_code",
    "event_temporal_hint",
    "temporal_hint",
)
_TEMPORAL_HINT_CODE_RE = re.compile(r"^(?:[a-z][a-z0-9_]{0,63}|date_\d{4}_\d{2}_\d{2})$")


def temporal_hint_code_from_metadata(*sources: Mapping[str, object]) -> str:
    """Return the first bounded normalized temporal hint code from safe metadata."""

    for source in sources:
        for key in _TEMPORAL_HINT_CODE_KEYS:
            value = source.get(key)
            if not isinstance(value, str):
                continue
            code = value.strip().casefold()
            if _TEMPORAL_HINT_CODE_RE.fullmatch(code):
                return code
    return ""
