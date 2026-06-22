"""Context dedupe, rank fusion and deterministic ranking helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace

from infinity_context_core.application.context_diagnostics import (
    context_duplicate_primary_key,
    context_rank_key,
    diagnostic_retrieval_sources,
    merge_context_diagnostics,
    merge_diagnostic_retrieval_sources,
    normalize_context_diagnostics,
    normalize_context_item_diagnostics,
    safe_diagnostic_mapping,
    safe_score_signals,
)
from infinity_context_core.application.context_query_expansion import QueryExpansionPlan
from infinity_context_core.application.context_relevance import (
    QueryRelevance,
    is_query_relevance_sufficient,
    score_query_relevance,
)
from infinity_context_core.application.dto import ContextItem
from infinity_context_core.domain.entities import MAX_SOURCE_REFS_PER_ITEM, SourceRef

_RRF_RANK_CONSTANT = 60.0
_RRF_MAX_RANK_PER_SOURCE = 50
_RRF_MAX_BOOST = 0.045
_KEYWORD_EXPANSION_SCORE_CAPS = {
    "career_intent_bridge": 0.91,
    "support_career_motivation_bridge": 0.96,
    "support_counterfactual_bridge": 0.94,
    "support_origin_bridge": 0.94,
    "outdoor_preference_bridge": 0.94,
    "outdoor_nature_memory_bridge": 0.94,
    "personality_trait_bridge": 0.94,
    "personality_authenticity_bridge": 0.94,
    "personality_drive_bridge": 0.94,
    "personality_thoughtfulness_bridge": 0.94,
    "adverse_trip_bridge": 0.94,
}
_KEYWORD_EXPANSION_REASON_BOOSTS = {
    "adverse_trip_bridge": 0.012,
    "outdoor_nature_memory_bridge": 0.018,
    "personality_authenticity_bridge": 0.014,
    "personality_drive_bridge": 0.014,
    "personality_thoughtfulness_bridge": 0.014,
    "personality_trait_bridge": 0.012,
    "support_career_motivation_bridge": 0.022,
    "support_origin_bridge": 0.01,
}


def dedupe_rank_items(items: tuple[ContextItem, ...]) -> tuple[ContextItem, ...]:
    by_key: dict[tuple[str, str], ContextItem] = {}
    for raw_item in items:
        item = normalize_context_item_diagnostics(raw_item)
        key = (item.item_type, item.item_id)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = item
        elif _should_replace_context_item(candidate=item, existing=existing):
            by_key[key] = _merge_context_items(primary=item, secondary=existing)
        else:
            by_key[key] = _merge_context_items(primary=existing, secondary=item)
    return tuple(sorted(by_key.values(), key=context_rank_key))


def apply_rank_fusion_boosts(
    items: tuple[ContextItem, ...],
    *,
    rank_constant: float = _RRF_RANK_CONSTANT,
    max_rank_per_source: int = _RRF_MAX_RANK_PER_SOURCE,
    max_boost: float = _RRF_MAX_BOOST,
) -> tuple[ContextItem, ...]:
    if (
        len(items) <= 1
        or rank_constant <= 0
        or max_rank_per_source <= 0
        or max_boost <= 0
    ):
        return items
    rankings = _ranked_items_by_retrieval_source(items)
    if len(rankings) <= 1:
        return items
    fusion_scores = reciprocal_rank_fusion_scores(
        rankings,
        rank_constant=rank_constant,
        max_rank_per_source=max_rank_per_source,
    )
    max_fusion_score = max(fusion_scores.values(), default=0.0)
    if max_fusion_score <= 0:
        return items
    return tuple(
        _with_rank_fusion_boost(
            item,
            fusion_score=fusion_scores.get((item.item_type, item.item_id), 0.0),
            max_fusion_score=max_fusion_score,
            max_boost=max_boost,
            source_count=len(rankings),
        )
        for item in items
    )


def reciprocal_rank_fusion_scores(
    rankings: Mapping[str, Sequence[ContextItem]],
    *,
    rank_constant: float = _RRF_RANK_CONSTANT,
    max_rank_per_source: int = _RRF_MAX_RANK_PER_SOURCE,
    source_weights: Mapping[str, float] | None = None,
) -> dict[tuple[str, str], float]:
    if rank_constant <= 0:
        raise ValueError("rank_constant must be positive")
    if max_rank_per_source <= 0:
        raise ValueError("max_rank_per_source must be positive")
    scores: dict[tuple[str, str], float] = {}
    for source, ranked_items in rankings.items():
        weight = _bounded_source_weight(
            source_weights.get(source, 1.0) if source_weights else 1.0
        )
        if weight <= 0:
            continue
        seen: set[tuple[str, str]] = set()
        for rank, item in enumerate(ranked_items, start=1):
            if rank > max_rank_per_source:
                break
            key = (item.item_type, item.item_id)
            if key in seen:
                continue
            seen.add(key)
            scores[key] = round(
                scores.get(key, 0.0) + weight / (rank_constant + rank),
                8,
            )
    return scores


def best_query_relevance(
    plan: QueryExpansionPlan,
    *,
    text: str,
) -> tuple[str, str, QueryRelevance]:
    scored = tuple(
        (
            expansion.query,
            expansion.reason,
            score_query_relevance(query=expansion.query, text=text),
        )
        for expansion in plan.retrieval_queries
    )
    return max(scored, key=query_relevance_rank_key)


def query_relevance_rank_key(
    item: tuple[str, str, QueryRelevance],
) -> tuple[bool, int, int, float, bool]:
    _, reason, relevance = item
    return (
        is_query_relevance_sufficient(relevance),
        relevance.distinctive_term_hits,
        relevance.unique_term_hits,
        relevance.score_boost,
        reason == "original_query",
    )


def keyword_chunk_score(
    relevance: QueryRelevance,
    *,
    query_expansion_reason: str,
) -> float:
    distinctive_boost = min(0.028, relevance.distinctive_term_hits * 0.007)
    phrase_boost = min(0.018, relevance.phrase_bigram_hits * 0.006)
    frequency_boost = min(0.014, relevance.capped_frequency_hits * 0.0015)
    expansion_boost = 0.004 if query_expansion_reason != "original_query" else 0.0
    reason_boost = _KEYWORD_EXPANSION_REASON_BOOSTS.get(query_expansion_reason, 0.0)
    score_cap = _KEYWORD_EXPANSION_SCORE_CAPS.get(query_expansion_reason, 0.93)
    return min(
        score_cap,
        round(
            0.75
            + relevance.score_boost
            + distinctive_boost
            + phrase_boost
            + frequency_boost
            + expansion_boost
            + reason_boost,
            4,
        ),
    )


def _should_replace_context_item(*, candidate: ContextItem, existing: ContextItem) -> bool:
    if candidate.score > existing.score:
        return True
    if candidate.score < existing.score:
        return False
    return context_duplicate_primary_key(candidate) < context_duplicate_primary_key(existing)


def _merge_context_items(*, primary: ContextItem, secondary: ContextItem) -> ContextItem:
    source_refs = _merge_source_refs(primary.source_refs, secondary.source_refs)
    retrieval_sources = merge_diagnostic_retrieval_sources(
        primary.diagnostics,
        secondary.diagnostics,
    )
    hybrid_boost = _hybrid_boost(
        retrieval_source_count=len(retrieval_sources),
        source_ref_count=len(source_refs),
    )
    score = min(0.99, round(max(primary.score, secondary.score) + hybrid_boost, 4))
    return replace(
        primary,
        score=score,
        source_refs=source_refs,
        diagnostics=merge_context_diagnostics(
            primary=primary.diagnostics,
            secondary=secondary.diagnostics,
            retrieval_sources=retrieval_sources,
            source_ref_count=len(source_refs),
            primary_score=primary.score,
            secondary_score=secondary.score,
            hybrid_boost=hybrid_boost,
        ),
    )


def _merge_source_refs(
    primary: tuple[SourceRef, ...],
    secondary: tuple[SourceRef, ...],
) -> tuple[SourceRef, ...]:
    refs: list[SourceRef] = []
    seen: set[tuple[object, ...]] = set()
    for ref in (*primary, *secondary):
        key = (
            ref.source_type,
            ref.source_id,
            ref.chunk_id,
            ref.char_start,
            ref.char_end,
            ref.quote_preview,
            ref.page_number,
            ref.time_start_ms,
            ref.time_end_ms,
            ref.bbox,
        )
        if key in seen:
            continue
        seen.add(key)
        refs.append(ref)
        if len(refs) >= MAX_SOURCE_REFS_PER_ITEM:
            break
    return tuple(refs)


def _hybrid_boost(*, retrieval_source_count: int, source_ref_count: int) -> float:
    if retrieval_source_count <= 1:
        return 0.0
    source_boost = 0.035 * (retrieval_source_count - 1)
    provenance_boost = 0.01 * min(3, max(0, source_ref_count - 1))
    return min(0.08, source_boost + provenance_boost)


def _ranked_items_by_retrieval_source(
    items: tuple[ContextItem, ...],
) -> dict[str, tuple[ContextItem, ...]]:
    by_source: dict[str, list[ContextItem]] = {}
    for item in items:
        sources = diagnostic_retrieval_sources(item.diagnostics)
        if not sources:
            continue
        by_source.setdefault(sources[0], []).append(item)
    return {
        source: tuple(sorted(source_items, key=context_rank_key))
        for source, source_items in by_source.items()
    }


def _bounded_source_weight(value: float) -> float:
    if value <= 0:
        return 0.0
    return min(5.0, float(value))


def _with_rank_fusion_boost(
    item: ContextItem,
    *,
    fusion_score: float,
    max_fusion_score: float,
    max_boost: float,
    source_count: int,
) -> ContextItem:
    if _rank_fusion_already_applied(item):
        return item
    if fusion_score <= 0 or max_fusion_score <= 0:
        return item
    normalized_score = min(1.0, fusion_score / max_fusion_score)
    boost = round(max_boost * normalized_score, 4)
    if boost <= 0:
        return item
    diagnostics = normalize_context_diagnostics(item.diagnostics)
    diagnostics["ranking_reason"] = diagnostics.get(
        "ranking_reason",
        "ranked by retrieval score",
    )
    diagnostics["rank_fusion_reason"] = (
        f"RRF over {source_count} retrieval sources"
    )
    diagnostics["score_signals"] = {
        **safe_score_signals(diagnostics.get("score_signals")),
        "rank_fusion_score": round(fusion_score, 6),
        "rank_fusion_normalized_score": round(normalized_score, 4),
        "rank_fusion_boost": boost,
        "rank_fusion_source_count": source_count,
    }
    diagnostics["provenance"] = {
        **safe_diagnostic_mapping(diagnostics.get("provenance")),
        "rank_fusion_applied": True,
        "rank_fusion_source_count": source_count,
    }
    return replace(
        item,
        score=min(0.99, round(item.score + boost, 4)),
        diagnostics=normalize_context_diagnostics(diagnostics),
    )


def _rank_fusion_already_applied(item: ContextItem) -> bool:
    diagnostics = normalize_context_diagnostics(item.diagnostics)
    provenance = safe_diagnostic_mapping(diagnostics.get("provenance"))
    return provenance.get("rank_fusion_applied") is True
