"""Query relevance helpers for context assembly."""

from __future__ import annotations

from dataclasses import dataclass

from infinity_context_core.application.context_lexical import (
    query_term_frequency,
    query_terms,
    text_variant_counts,
)


@dataclass(frozen=True)
class QueryRelevance:
    score_boost: float
    query_term_count: int
    unique_term_hits: int
    capped_frequency_hits: int
    hit_ratio: float


def score_query_relevance(*, query: str, text: str, max_boost: float = 0.12) -> QueryRelevance:
    terms = query_terms(query)
    if not terms:
        return QueryRelevance(
            score_boost=0.0,
            query_term_count=0,
            unique_term_hits=0,
            capped_frequency_hits=0,
            hit_ratio=0.0,
        )
    counts = text_variant_counts(text)
    frequencies = tuple(query_term_frequency(term, counts) for term in terms)
    unique_hits = sum(1 for frequency in frequencies if frequency > 0)
    capped_frequency_hits = sum(min(frequency, 3) for frequency in frequencies)
    hit_ratio = unique_hits / len(terms)
    frequency_boost = min(0.025, capped_frequency_hits * 0.002)
    score_boost = min(max_boost, round(hit_ratio * max_boost + frequency_boost, 4))
    return QueryRelevance(
        score_boost=score_boost,
        query_term_count=len(terms),
        unique_term_hits=unique_hits,
        capped_frequency_hits=capped_frequency_hits,
        hit_ratio=round(hit_ratio, 4),
    )
