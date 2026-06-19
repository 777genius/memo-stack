"""Public source-ref serialization helpers."""

from __future__ import annotations

from typing import Any

from infinity_context_core.domain.entities import SourceRef
from pydantic import BaseModel, ConfigDict, Field

from infinity_context_server.api.public_payload import safe_public_text


class SourceRefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str = Field(min_length=1, max_length=80)
    source_id: str = Field(min_length=1, max_length=160)
    chunk_id: str | None = Field(default=None, max_length=160)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    quote_preview: str | None = Field(default=None, max_length=240)
    page_number: int | None = Field(default=None, ge=1)
    time_start_ms: int | None = Field(default=None, ge=0)
    time_end_ms: int | None = Field(default=None, ge=0)
    bbox: tuple[float, float, float, float] | None = None


def map_source_ref(request: SourceRefRequest) -> SourceRef:
    return SourceRef(
        source_type=request.source_type,
        source_id=request.source_id,
        chunk_id=request.chunk_id,
        char_start=request.char_start,
        char_end=request.char_end,
        quote_preview=request.quote_preview,
        page_number=request.page_number,
        time_start_ms=request.time_start_ms,
        time_end_ms=request.time_end_ms,
        bbox=request.bbox,
    )


def source_ref_to_response(ref: object) -> dict[str, Any]:
    quote_preview = getattr(ref, "quote_preview", None)
    return {
        "source_type": getattr(ref, "source_type", ""),
        "source_id": getattr(ref, "source_id", ""),
        "chunk_id": getattr(ref, "chunk_id", None),
        "char_start": getattr(ref, "char_start", None),
        "char_end": getattr(ref, "char_end", None),
        "quote_preview": safe_public_text(quote_preview) if quote_preview else None,
        "page_number": getattr(ref, "page_number", None),
        "time_start_ms": getattr(ref, "time_start_ms", None),
        "time_end_ms": getattr(ref, "time_end_ms", None),
        "bbox": _bbox_to_response(getattr(ref, "bbox", None)),
    }


def _bbox_to_response(value: object) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError):
        return None
