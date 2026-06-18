"""Shared helpers for Postgres repository implementations."""

from __future__ import annotations

import re
from datetime import datetime
from hashlib import sha256

from sqlalchemy import func, or_

from infinity_context_adapters.postgres.models import MemorySourceRefRow


def _terms(query: str) -> tuple[str, ...]:
    return tuple(term for term in re.findall(r"\w+", query.lower()) if len(term) >= 3)


def _score(text: str, terms: tuple[str, ...]) -> int:
    lowered = text.lower()
    unique_terms = tuple(dict.fromkeys(terms))
    unique_hits = sum(1 for term in unique_terms if term in lowered)
    if unique_hits == 0:
        return 0
    capped_frequency = sum(min(lowered.count(term), 3) for term in unique_terms)
    density_penalty = len(lowered) // 800
    return unique_hits * 1000 + capped_frequency * 10 - density_penalty


def _retrieval_candidate_limit(limit: int) -> int:
    if limit <= 0:
        return 0
    return min(max(limit * 20, limit), 2000)


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
