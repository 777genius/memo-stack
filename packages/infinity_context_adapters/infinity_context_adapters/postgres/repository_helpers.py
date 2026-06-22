"""Shared helpers for Postgres repository implementations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from hashlib import sha256

from infinity_context_core.application.context_lexical import (
    query_terms,
    text_variant_counts,
)
from sqlalchemy import func, or_

from infinity_context_adapters.postgres.models import MemorySourceRefRow

_MAX_QUERY_TERMS = 24


def _terms(query: str) -> tuple[str, ...]:
    terms: list[str] = []
    seen: set[str] = set()
    for term in query_terms(query, max_terms=_MAX_QUERY_TERMS):
        for variant in term.variants:
            if len(variant) < 3 or variant in seen:
                continue
            terms.append(variant)
            seen.add(variant)
    return tuple(terms)


def _score(text: str, terms: tuple[str, ...]) -> int:
    unique_terms = tuple(dict.fromkeys(terms))
    counts = text_variant_counts(text)
    frequencies = tuple(
        counts.get(term, 0) or _approximate_term_frequency(term, counts)
        for term in unique_terms
    )
    unique_hits = sum(1 for frequency in frequencies if frequency > 0)
    if unique_hits == 0:
        return 0
    density_penalty = len(text) // 800
    return unique_hits * 1000 - density_penalty


def _approximate_term_frequency(term: str, counts: Mapping[str, int]) -> int:
    if len(term) < 6:
        return 0
    for candidate, frequency in counts.items():
        if len(candidate) < 6 or abs(len(candidate) - len(term)) > 1:
            continue
        if _edit_distance_at_most_one(term, candidate):
            return frequency
    return 0


def _edit_distance_at_most_one(left: str, right: str) -> bool:
    if left == right:
        return True
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) > len(right):
        left, right = right, left
    mismatch_count = 0
    left_index = 0
    right_index = 0
    while left_index < len(left) and right_index < len(right):
        if left[left_index] == right[right_index]:
            left_index += 1
            right_index += 1
            continue
        mismatch_count += 1
        if mismatch_count > 1:
            return False
        if len(left) == len(right):
            left_index += 1
        right_index += 1
    return True


def _retrieval_candidate_limit(limit: int) -> int:
    if limit <= 0:
        return 0
    return min(max(limit * 20, limit, 200), 2000)


def _escape_like(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def _not_expired(model: type, now: datetime | None):
    comparable_now = now if now is not None else func.now()
    return or_(model.expires_at.is_(None), model.expires_at > comparable_now)


def _tags_match(
    values: list[str],
    *,
    tags_any: tuple[str, ...],
    tags_all: tuple[str, ...],
    tags_none: tuple[str, ...],
) -> bool:
    tags = set(values)
    return (
        (not tags_any or bool(tags.intersection(tags_any)))
        and (not tags_all or set(tags_all).issubset(tags))
        and (not tags_none or not tags.intersection(tags_none))
    )


def _source_ref_points_to_deleted_document(
    ref: MemorySourceRefRow,
    *,
    document_id: str,
    chunk_ids: set[str],
) -> bool:
    if ref.chunk_id is not None:
        return ref.chunk_id in chunk_ids
    return ref.source_type == "document" and ref.source_id == document_id


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("\u241f".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"
