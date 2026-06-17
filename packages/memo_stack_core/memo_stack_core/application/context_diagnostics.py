"""Bounded context diagnostics policy."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from memo_stack_core.application.dto import ContextItem
from memo_stack_core.application.safe_payload import safe_metadata, safe_metadata_text

_MAX_RETRIEVAL_SOURCES = 8
_MAX_DIAGNOSTIC_MAPPING_ITEMS = 24
_MAX_DIAGNOSTIC_LIST_ITEMS = 8
_MAX_DIAGNOSTIC_KEY_CHARS = 80
_MAX_DIAGNOSTIC_STRING_CHARS = 240
_MAX_RANKING_REASON_CHARS = 240


def context_rank_key(item: ContextItem) -> tuple[float, str, str, str]:
    return (-round(item.score, 8), item.item_type, item.item_id, _updated_at(item))


def normalize_context_item_diagnostics(item: ContextItem) -> ContextItem:
    return replace(item, diagnostics=normalize_context_diagnostics(item.diagnostics))


def normalize_context_diagnostics(diagnostics: object) -> dict[str, object]:
    raw = _as_dict(diagnostics)
    retrieval_sources = diagnostic_retrieval_sources(raw)
    normalized = safe_diagnostic_mapping(raw)
    normalized["retrieval_sources"] = list(retrieval_sources)
    selected_source = _safe_retrieval_source(raw.get("retrieval_source")) or (
        retrieval_sources[0] if retrieval_sources else None
    )
    if selected_source:
        normalized["retrieval_source"] = selected_source
    else:
        normalized.pop("retrieval_source", None)
    ranking_reason = _safe_optional_text(raw.get("ranking_reason"), limit=_MAX_RANKING_REASON_CHARS)
    normalized["ranking_reason"] = ranking_reason or ranking_reason_for(retrieval_sources)
    normalized["score_signals"] = safe_score_signals(raw.get("score_signals"))
    provenance = safe_diagnostic_mapping(raw.get("provenance"))
    if retrieval_sources:
        provenance["retrieval_sources"] = list(retrieval_sources)
    normalized["provenance"] = provenance
    return normalized


def diagnostic_retrieval_sources(diagnostics: object) -> tuple[str, ...]:
    raw = _as_dict(diagnostics)
    values: list[str] = []
    raw_sources = raw.get("retrieval_sources")
    if isinstance(raw_sources, (list, tuple)):
        values.extend(_safe_retrieval_source(value) or "" for value in raw_sources)
    raw_source = _safe_retrieval_source(raw.get("retrieval_source"))
    if raw_source:
        values.append(raw_source)
    return _ordered_unique(tuple(value for value in values if value))


def merge_diagnostic_retrieval_sources(*diagnostics: object) -> tuple[str, ...]:
    return _ordered_unique(
        tuple(
            source
            for diagnostic in diagnostics
            for source in diagnostic_retrieval_sources(diagnostic)
        )
    )


def merge_context_diagnostics(
    *,
    primary: object,
    secondary: object,
    retrieval_sources: tuple[str, ...],
    source_ref_count: int,
    primary_score: float,
    secondary_score: float,
    hybrid_boost: float,
) -> dict[str, object]:
    primary_raw = _as_dict(primary)
    secondary_raw = _as_dict(secondary)
    merged = safe_diagnostic_mapping({**secondary_raw, **primary_raw})
    selected_source = _safe_retrieval_source(primary_raw.get("retrieval_source")) or (
        retrieval_sources[0] if retrieval_sources else None
    )
    if selected_source:
        merged["retrieval_source"] = selected_source
    merged["retrieval_sources"] = list(retrieval_sources)
    merged["merged_candidate_count"] = _candidate_count(primary_raw) + _candidate_count(
        secondary_raw
    )
    merged["ranking_reason"] = ranking_reason_for(retrieval_sources)
    merged["score_signals"] = {
        **safe_score_signals(secondary_raw.get("score_signals")),
        **safe_score_signals(primary_raw.get("score_signals")),
        "dedupe_primary_score": round(primary_score, 4),
        "dedupe_secondary_score": round(secondary_score, 4),
        "hybrid_source_count": len(retrieval_sources),
        "hybrid_boost": round(hybrid_boost, 4),
        "source_ref_count": source_ref_count,
    }
    merged["provenance"] = {
        **safe_diagnostic_mapping(secondary_raw.get("provenance")),
        **safe_diagnostic_mapping(primary_raw.get("provenance")),
        "retrieval_sources": list(retrieval_sources),
        "source_ref_count": source_ref_count,
        "selected_retrieval_source": selected_source or "unknown",
    }
    return normalize_context_diagnostics(merged)


def safe_score_signals(value: object) -> dict[str, object]:
    safe = safe_diagnostic_mapping(value)
    return {
        key: item
        for key, item in safe.items()
        if isinstance(item, (int, float, str, bool)) or item is None
    }


def safe_diagnostic_mapping(value: object) -> dict[str, object]:
    return _bounded_mapping(safe_metadata(value, max_items=_MAX_DIAGNOSTIC_MAPPING_ITEMS))


def ranking_reason_for(retrieval_sources: tuple[str, ...]) -> str:
    if len(retrieval_sources) > 1:
        reason = f"hybrid match via {', '.join(retrieval_sources)}"
    elif retrieval_sources:
        reason = f"matched via {retrieval_sources[0]}"
    else:
        reason = "matched without retrieval channel diagnostics"
    return safe_metadata_text(reason, limit=_MAX_RANKING_REASON_CHARS)


def _bounded_mapping(value: object, *, depth: int = 0) -> dict[str, object]:
    if not isinstance(value, dict) or depth > 2:
        return {}
    bounded: dict[str, object] = {}
    for raw_key, raw_value in list(value.items())[:_MAX_DIAGNOSTIC_MAPPING_ITEMS]:
        key = safe_metadata_text(str(raw_key), limit=_MAX_DIAGNOSTIC_KEY_CHARS).strip()
        if not key or "[redacted]" in key:
            continue
        item = _bounded_value(raw_value, depth=depth)
        if _is_safe_diagnostic_value(item):
            bounded[key] = item
    return bounded


def _bounded_value(value: object, *, depth: int) -> object:
    if isinstance(value, str):
        return safe_metadata_text(value, limit=_MAX_DIAGNOSTIC_STRING_CHARS)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return _bounded_mapping(value, depth=depth + 1)
    if isinstance(value, list):
        safe_items: list[object] = []
        for raw_item in value[:_MAX_DIAGNOSTIC_LIST_ITEMS]:
            item = _bounded_value(raw_item, depth=depth + 1)
            if _is_safe_diagnostic_value(item):
                safe_items.append(item)
        return safe_items
    return None


def _is_safe_diagnostic_value(value: object) -> bool:
    return isinstance(value, (str, int, float, bool, dict, list)) or value is None


def _safe_retrieval_source(value: object) -> str | None:
    if value is None:
        return None
    text = safe_metadata_text(str(value), limit=_MAX_DIAGNOSTIC_KEY_CHARS).strip()
    return text or None


def _safe_optional_text(value: object, *, limit: int) -> str | None:
    if value is None:
        return None
    text = safe_metadata_text(str(value), limit=limit).strip()
    return text or None


def _candidate_count(diagnostics: dict[str, Any]) -> int:
    value = diagnostics.get("merged_candidate_count")
    return value if isinstance(value, int) and value > 0 else 1


def _updated_at(item: ContextItem) -> str:
    diagnostics = item.diagnostics or {}
    if not isinstance(diagnostics, dict):
        return ""
    value = diagnostics.get("updated_at") or diagnostics.get("created_at") or ""
    return str(value)


def _as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _ordered_unique(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
        if len(result) >= _MAX_RETRIEVAL_SOURCES:
            break
    return tuple(result)
