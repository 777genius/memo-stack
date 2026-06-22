"""Context dedupe, rank fusion and deterministic ranking helpers."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

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
from infinity_context_core.application.context_lexical import (
    LexicalQueryTerm,
    query_term_frequency,
    query_terms,
    text_variant_counts,
    text_variant_sequence,
)
from infinity_context_core.application.context_query_expansion import QueryExpansionPlan
from infinity_context_core.application.context_query_intent import (
    QueryAnchorIntent,
    match_query_anchor_intent_to_text,
    query_anchor_intent_text_conflicts,
)
from infinity_context_core.application.context_relevance import (
    QueryRelevance,
    has_project_identity_mismatch,
    is_query_relevance_sufficient,
    score_query_relevance,
)
from infinity_context_core.application.context_requirement_coverage import (
    context_requirement_coverage,
)
from infinity_context_core.application.dto import ContextItem
from infinity_context_core.domain.entities import MAX_SOURCE_REFS_PER_ITEM, SourceRef

_RRF_RANK_CONSTANT = 60.0
_RRF_MAX_RANK_PER_SOURCE = 50
_RRF_MAX_BOOST = 0.045
_DEFAULT_RRF_SOURCE_WEIGHTS = {
    "approved_context_linked_anchors": 1.18,
    "approved_context_linked_asset_manifest_evidence": 1.14,
    "approved_context_linked_assets": 1.08,
    "approved_context_linked_chunks": 1.12,
    "approved_context_linked_extraction_artifacts": 1.2,
    "approved_context_linked_facts": 1.14,
    "artifact_evidence": 1.2,
    "canonical_anchor_relations": 1.12,
    "canonical_anchors": 1.15,
    "graph_hydrated": 1.08,
    "keyword_aggregation_chunks": 1.12,
    "keyword_chunks": 1.04,
    "keyword_neighbor_chunks": 1.04,
    "keyword_source_sibling_chunks": 1.08,
    "postgres_facts": 1.06,
    "rag_recall": 1.06,
    "temporal_supersedes_relation": 1.12,
    "vector_chunks": 1.08,
}
_BM25_K1 = 1.2
_BM25_B = 0.75
_BM25_MAX_BOOST = 0.035
_QUERY_ANCHOR_INTENT_MAX_BOOST = 0.035
_CONTEXT_REQUIREMENT_MAX_BOOST = 0.04
_CONTEXT_REQUIREMENT_ANCHOR_BOOST = 0.008
_CONTEXT_REQUIREMENT_MODALITY_BOOST = 0.022
_CONTEXT_REQUIREMENT_FEATURE_BOOST = 0.014
_DETERMINISTIC_RERANK_MAX_BOOST = 0.055
_DETERMINISTIC_RERANK_MAX_PENALTY = 0.085
_DUPLICATE_SOURCE_SCORE_TOLERANCE = 0.015
_STRONG_EVIDENCE_RERANK_SOURCES = frozenset(
    {
        "approved_context_linked_anchors",
        "approved_context_linked_asset_manifest_evidence",
        "approved_context_linked_assets",
        "approved_context_linked_chunks",
        "approved_context_linked_extraction_artifacts",
        "approved_context_linked_facts",
        "artifact_evidence",
        "canonical_anchor_relations",
        "canonical_anchors",
        "temporal_supersedes_relation",
    }
)
_KEYWORD_EXPANSION_SCORE_CAPS = {
    "career_intent_bridge": 0.91,
    "education_career_field_bridge": 0.96,
    "identity_bridge": 0.96,
    "relationship_status_bridge": 0.96,
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
    "allergy_condition_inference_bridge": 0.018,
    "attribute_description_bridge": 0.018,
    "beach_or_mountains_inference_bridge": 0.018,
    "book_suggestion_bridge": 0.018,
    "children_count_sibling_bridge": 0.016,
    "console_game_cover_bridge": 0.018,
    "counseling_workshop_bridge": 0.018,
    "degree_policy_inference_bridge": 0.018,
    "education_career_field_bridge": 0.022,
    "decomposition_attribute_aggregation": 0.018,
    "decomposition_current_preference_or_goal": 0.018,
    "decomposition_event_sequence": 0.018,
    "decomposition_identity_attribute": 0.02,
    "decomposition_relationship_status": 0.02,
    "event_participation_bridge": 0.018,
    "family_activity_bridge": 0.024,
    "family_motivation_context_bridge": 0.02,
    "family_painting_activity_bridge": 0.02,
    "family_swimming_activity_bridge": 0.02,
    "event_participation_help_bridge": 0.02,
    "friends_team_inference_bridge": 0.018,
    "identity_bridge": 0.022,
    "lgbtq_community_participation_bridge": 0.02,
    "lgbtq_pride_event_bridge": 0.02,
    "lgbtq_school_event_bridge": 0.02,
    "lgbtq_support_group_event_bridge": 0.02,
    "meteor_shower_feeling_bridge": 0.018,
    "music_artist_band_bridge": 0.018,
    "outdoor_nature_memory_bridge": 0.018,
    "personality_authenticity_bridge": 0.014,
    "personality_drive_bridge": 0.014,
    "personality_thoughtfulness_bridge": 0.014,
    "personality_trait_bridge": 0.012,
    "pet_allergy_discomfort_bridge": 0.018,
    "pottery_color_reason_bridge": 0.018,
    "relationship_status_bridge": 0.022,
    "shoe_usage_bridge": 0.018,
    "support_career_motivation_bridge": 0.022,
    "support_origin_bridge": 0.01,
    "symbol_importance_bridge": 0.018,
    "transgender_poetry_event_bridge": 0.02,
    "volunteer_career_inference_bridge": 0.018,
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
    source_weights: Mapping[str, float] | None = None,
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
        source_weights=(
            _DEFAULT_RRF_SOURCE_WEIGHTS if source_weights is None else source_weights
        ),
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
            source_weighted=bool(
                _DEFAULT_RRF_SOURCE_WEIGHTS if source_weights is None else source_weights
            ),
        )
        for item in items
    )


def apply_bm25_lexical_boosts(
    items: tuple[ContextItem, ...],
    *,
    query: str,
    k1: float = _BM25_K1,
    b: float = _BM25_B,
    max_boost: float = _BM25_MAX_BOOST,
) -> tuple[ContextItem, ...]:
    if len(items) <= 1 or k1 <= 0 or not 0 <= b <= 1 or max_boost <= 0:
        return items
    terms = query_terms(query)
    if not terms:
        return items
    documents, raw_scores = _bm25_raw_scores(items=items, terms=terms, k1=k1, b=b)
    max_raw_score = max(raw_scores, default=0.0)
    if max_raw_score <= 0:
        return items
    return tuple(
        _with_bm25_lexical_boost(
            document.item,
            raw_score=raw_score,
            max_raw_score=max_raw_score,
            max_boost=max_boost,
            query_term_count=len(terms),
            matched_term_count=sum(
                1 for frequency in document.term_frequencies if frequency > 0
            ),
        )
        for document, raw_score in zip(documents, raw_scores, strict=True)
    )


def apply_query_plan_bm25_lexical_boosts(
    items: tuple[ContextItem, ...],
    *,
    plan: QueryExpansionPlan,
    k1: float = _BM25_K1,
    b: float = _BM25_B,
    max_boost: float = _BM25_MAX_BOOST,
) -> tuple[ContextItem, ...]:
    if len(items) <= 1 or k1 <= 0 or not 0 <= b <= 1 or max_boost <= 0:
        return items
    matches = _best_bm25_query_matches(items=items, plan=plan, k1=k1, b=b)
    if not any(match.normalized_score > 0 for match in matches):
        return items
    return tuple(
        _with_bm25_lexical_boost(
            item,
            raw_score=match.normalized_score,
            max_raw_score=1.0,
            max_boost=max_boost,
            query_term_count=match.query_term_count,
            matched_term_count=match.matched_term_count,
            query_reason=match.query_reason,
            query_coverage=match.query_coverage,
        )
        for item, match in zip(items, matches, strict=True)
    )


def apply_query_anchor_intent_boosts(
    items: tuple[ContextItem, ...],
    *,
    intent: QueryAnchorIntent,
    max_boost: float = _QUERY_ANCHOR_INTENT_MAX_BOOST,
) -> tuple[ContextItem, ...]:
    if not items or intent.empty or max_boost <= 0:
        return items
    return tuple(
        _with_query_anchor_intent_boost(
            item,
            match=match_query_anchor_intent_to_text(intent, item.text),
            max_boost=max_boost,
        )
        for item in items
    )


def apply_context_requirement_boosts(
    items: tuple[ContextItem, ...],
    *,
    query: str,
    query_anchor_intent: QueryAnchorIntent,
    max_boost: float = _CONTEXT_REQUIREMENT_MAX_BOOST,
) -> tuple[ContextItem, ...]:
    if not items or max_boost <= 0:
        return items
    requested = context_requirement_coverage(
        query=query,
        query_anchor_intent=query_anchor_intent,
        items=(),
    )
    requested_anchor_kinds = _coverage_value_set(requested.get("requested_anchor_kinds"))
    requested_modalities = _coverage_value_set(requested.get("requested_modalities"))
    requested_features = _coverage_value_set(requested.get("requested_evidence_features"))
    if not requested_anchor_kinds and not requested_modalities and not requested_features:
        return items
    return tuple(
        _with_context_requirement_boost(
            item,
            query=query,
            query_anchor_intent=query_anchor_intent,
            requested_anchor_kinds=requested_anchor_kinds,
            requested_modalities=requested_modalities,
            requested_features=requested_features,
            max_boost=max_boost,
        )
        for item in items
    )


def apply_deterministic_rerank_adjustments(
    items: tuple[ContextItem, ...],
    *,
    query: str,
    plan: QueryExpansionPlan,
    query_anchor_intent: QueryAnchorIntent,
    max_boost: float = _DETERMINISTIC_RERANK_MAX_BOOST,
    max_penalty: float = _DETERMINISTIC_RERANK_MAX_PENALTY,
) -> tuple[ContextItem, ...]:
    if not items or (max_boost <= 0 and max_penalty <= 0):
        return items
    requested_coverage = context_requirement_coverage(
        query=query,
        query_anchor_intent=query_anchor_intent,
        items=(),
    )
    requested_total = _coverage_int(requested_coverage.get("requested_total"))
    return tuple(
        _with_deterministic_rerank_adjustment(
            item,
            query=query,
            plan=plan,
            query_anchor_intent=query_anchor_intent,
            requested_total=requested_total,
            max_boost=max_boost,
            max_penalty=max_penalty,
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
        if existing.score - candidate.score <= _DUPLICATE_SOURCE_SCORE_TOLERANCE:
            return context_duplicate_primary_key(candidate) < context_duplicate_primary_key(
                existing
            )
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
    body_item = _preferred_merge_body_item(primary=primary, secondary=secondary)
    return replace(
        body_item,
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


def _preferred_merge_body_item(*, primary: ContextItem, secondary: ContextItem) -> ContextItem:
    if (primary.item_type, primary.item_id) != (secondary.item_type, secondary.item_id):
        return primary
    primary_sources = set(diagnostic_retrieval_sources(primary.diagnostics))
    secondary_sources = set(diagnostic_retrieval_sources(secondary.diagnostics))
    if (
        "keyword_aggregation_chunks" in secondary_sources
        and "keyword_aggregation_chunks" not in primary_sources
    ):
        return secondary
    if (
        "keyword_aggregation_chunks" in primary_sources
        and "keyword_aggregation_chunks" not in secondary_sources
    ):
        return primary
    return primary


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
        for source in sources:
            by_source.setdefault(source, []).append(item)
    return {
        source: tuple(sorted(source_items, key=context_rank_key))
        for source, source_items in by_source.items()
    }


def _bounded_source_weight(value: float) -> float:
    if value <= 0:
        return 0.0
    return min(5.0, float(value))


@dataclass(frozen=True)
class _Bm25Document:
    item: ContextItem
    term_frequencies: tuple[int, ...]
    length: int


@dataclass(frozen=True)
class _Bm25QueryMatch:
    normalized_score: float
    query_term_count: int
    matched_term_count: int
    query_reason: str
    query_coverage: float = 0.0


@dataclass(frozen=True)
class _DeterministicRerankSignals:
    boost: float
    penalty: float
    reasons: tuple[str, ...]
    source_count: int
    strong_source_count: int
    coverage_ratio: float
    anchor_conflict: bool
    query_reason: str

    @property
    def net_adjustment(self) -> float:
        return round(self.boost - self.penalty, 4)


def _best_bm25_query_matches(
    *,
    items: tuple[ContextItem, ...],
    plan: QueryExpansionPlan,
    k1: float,
    b: float,
) -> tuple[_Bm25QueryMatch, ...]:
    best_matches = tuple(
        _Bm25QueryMatch(
            normalized_score=0.0,
            query_term_count=0,
            matched_term_count=0,
            query_reason="",
            query_coverage=0.0,
        )
        for _ in items
    )
    for expansion in plan.retrieval_queries:
        terms = query_terms(expansion.query)
        if not terms:
            continue
        documents, raw_scores = _bm25_raw_scores(
            items=items,
            terms=terms,
            k1=k1,
            b=b,
        )
        max_raw_score = max(raw_scores, default=0.0)
        if max_raw_score <= 0:
            continue
        query_matches: list[_Bm25QueryMatch] = []
        for document, raw_score in zip(documents, raw_scores, strict=True):
            matched_term_count = sum(
                1 for frequency in document.term_frequencies if frequency > 0
            )
            coverage = _bm25_query_coverage(
                matched_term_count=matched_term_count,
                query_term_count=len(terms),
            )
            query_matches.append(
                _Bm25QueryMatch(
                    normalized_score=round(
                        min(1.0, raw_score / max_raw_score) * coverage,
                        6,
                    ),
                    query_term_count=len(terms),
                    matched_term_count=matched_term_count,
                    query_reason=expansion.reason,
                    query_coverage=coverage,
                )
            )
        best_matches = tuple(
            _select_bm25_query_match(best, candidate)
            for best, candidate in zip(best_matches, tuple(query_matches), strict=True)
        )
    return best_matches


def _select_bm25_query_match(
    best: _Bm25QueryMatch,
    candidate: _Bm25QueryMatch,
) -> _Bm25QueryMatch:
    if candidate.matched_term_count <= 0:
        return best
    if candidate.normalized_score > best.normalized_score:
        return candidate
    if candidate.normalized_score < best.normalized_score:
        return best
    if candidate.matched_term_count > best.matched_term_count:
        return candidate
    if candidate.matched_term_count < best.matched_term_count:
        return best
    if candidate.query_reason == "original_query" and best.query_reason != "original_query":
        return candidate
    return best


def _bm25_raw_scores(
    *,
    items: tuple[ContextItem, ...],
    terms: tuple[LexicalQueryTerm, ...],
    k1: float,
    b: float,
) -> tuple[tuple[_Bm25Document, ...], tuple[float, ...]]:
    documents = tuple(_bm25_document(item=item, terms=terms) for item in items)
    average_length = sum(document.length for document in documents) / len(documents)
    document_frequencies = tuple(
        sum(1 for document in documents if document.term_frequencies[index] > 0)
        for index, _ in enumerate(terms)
    )
    raw_scores = tuple(
        _bm25_score(
            term_frequencies=document.term_frequencies,
            document_frequencies=document_frequencies,
            document_count=len(documents),
            document_length=document.length,
            average_document_length=max(1.0, average_length),
            k1=k1,
            b=b,
        )
        for document in documents
    )
    return documents, raw_scores


def _bm25_query_coverage(*, matched_term_count: int, query_term_count: int) -> float:
    if matched_term_count <= 0 or query_term_count <= 0:
        return 0.0
    denominator = min(8, max(3, query_term_count))
    return round(min(1.0, matched_term_count / denominator), 4)


def _bm25_document(
    *,
    item: ContextItem,
    terms: tuple[LexicalQueryTerm, ...],
) -> _Bm25Document:
    counts = text_variant_counts(item.text)
    return _Bm25Document(
        item=item,
        term_frequencies=tuple(query_term_frequency(term, counts) for term in terms),
        length=max(1, len(text_variant_sequence(item.text))),
    )


def _bm25_score(
    *,
    term_frequencies: tuple[int, ...],
    document_frequencies: tuple[int, ...],
    document_count: int,
    document_length: int,
    average_document_length: float,
    k1: float,
    b: float,
) -> float:
    score = 0.0
    length_ratio = document_length / average_document_length
    normalizer = k1 * (1 - b + b * length_ratio)
    for frequency, document_frequency in zip(
        term_frequencies,
        document_frequencies,
        strict=True,
    ):
        if frequency <= 0 or document_frequency <= 0:
            continue
        idf = math.log(
            1
            + (document_count - document_frequency + 0.5)
            / (document_frequency + 0.5)
        )
        score += idf * (frequency * (k1 + 1)) / (frequency + normalizer)
    return round(score, 8)


def _with_bm25_lexical_boost(
    item: ContextItem,
    *,
    raw_score: float,
    max_raw_score: float,
    max_boost: float,
    query_term_count: int,
    matched_term_count: int,
    query_reason: str = "original_query",
    query_coverage: float | None = None,
) -> ContextItem:
    if _bm25_lexical_already_applied(item):
        return item
    if raw_score <= 0 or max_raw_score <= 0 or matched_term_count <= 0:
        return item
    normalized_score = min(1.0, raw_score / max_raw_score)
    boost = round(max_boost * normalized_score, 4)
    if boost <= 0:
        return item
    diagnostics = normalize_context_diagnostics(item.diagnostics)
    diagnostics["bm25_lexical_reason"] = "BM25 lexical rerank over candidate pool"
    diagnostics["score_signals"] = {
        **safe_score_signals(diagnostics.get("score_signals")),
        "bm25_lexical_raw_score": round(raw_score, 6),
        "bm25_lexical_normalized_score": round(normalized_score, 4),
        "bm25_lexical_boost": boost,
        "bm25_lexical_query_term_count": query_term_count,
        "bm25_lexical_matched_term_count": matched_term_count,
        "bm25_lexical_query_reason": query_reason,
    }
    if query_coverage is not None:
        diagnostics["score_signals"]["bm25_lexical_query_coverage"] = round(
            query_coverage,
            4,
        )
    diagnostics["provenance"] = {
        **safe_diagnostic_mapping(diagnostics.get("provenance")),
        "bm25_lexical_applied": True,
        "bm25_lexical_query_reason": query_reason,
    }
    return replace(
        item,
        score=min(0.99, round(item.score + boost, 4)),
        diagnostics=normalize_context_diagnostics(diagnostics),
    )


def _bm25_lexical_already_applied(item: ContextItem) -> bool:
    diagnostics = normalize_context_diagnostics(item.diagnostics)
    provenance = safe_diagnostic_mapping(diagnostics.get("provenance"))
    return provenance.get("bm25_lexical_applied") is True


def _with_query_anchor_intent_boost(
    item: ContextItem,
    *,
    match: object,
    max_boost: float,
) -> ContextItem:
    if match is None or _query_anchor_intent_already_applied(item):
        return item
    try:
        raw_boost = float(getattr(match, "score_boost", 0.0))
    except (TypeError, ValueError):
        return item
    boost = min(max_boost, max(0.0, round(raw_boost, 4)))
    if boost <= 0:
        return item
    diagnostics = normalize_context_diagnostics(item.diagnostics)
    reasons = tuple(getattr(match, "reasons", ()) or ())
    matched_keys = tuple(getattr(match, "matched_keys", ()) or ())
    diagnostics["query_anchor_intent_reason"] = (
        "query anchor identity matched context item text"
    )
    diagnostics["score_signals"] = {
        **safe_score_signals(diagnostics.get("score_signals")),
        "query_anchor_intent_boost": boost,
        "query_anchor_intent_reason_count": len(reasons),
        "query_anchor_intent_matched_key_count": len(matched_keys),
    }
    diagnostics["provenance"] = {
        **safe_diagnostic_mapping(diagnostics.get("provenance")),
        "query_anchor_intent_applied": True,
        "query_anchor_intent_reasons": list(reasons[:8]),
        "query_anchor_intent_matched_keys": list(matched_keys[:8]),
    }
    return replace(
        item,
        score=min(0.99, round(item.score + boost, 4)),
        diagnostics=normalize_context_diagnostics(diagnostics),
    )


def _query_anchor_intent_already_applied(item: ContextItem) -> bool:
    diagnostics = normalize_context_diagnostics(item.diagnostics)
    provenance = safe_diagnostic_mapping(diagnostics.get("provenance"))
    return provenance.get("query_anchor_intent_applied") is True


def _with_context_requirement_boost(
    item: ContextItem,
    *,
    query: str,
    query_anchor_intent: QueryAnchorIntent,
    requested_anchor_kinds: frozenset[str],
    requested_modalities: frozenset[str],
    requested_features: frozenset[str],
    max_boost: float,
) -> ContextItem:
    if _context_requirement_boost_already_applied(item):
        return item
    normalized_item = normalize_context_item_diagnostics(item)
    coverage = context_requirement_coverage(
        query=query,
        query_anchor_intent=query_anchor_intent,
        items=(normalized_item,),
    )
    matched_anchor_kinds = _sorted_coverage_matches(
        requested_anchor_kinds,
        coverage.get("covered_anchor_kinds"),
    )
    matched_modalities = _sorted_coverage_matches(
        requested_modalities,
        coverage.get("covered_modalities"),
    )
    matched_features = _sorted_coverage_matches(
        requested_features,
        coverage.get("covered_evidence_features"),
    )
    raw_boost = (
        len(matched_anchor_kinds) * _CONTEXT_REQUIREMENT_ANCHOR_BOOST
        + len(matched_modalities) * _CONTEXT_REQUIREMENT_MODALITY_BOOST
        + len(matched_features) * _CONTEXT_REQUIREMENT_FEATURE_BOOST
    )
    boost = min(max_boost, round(raw_boost, 4))
    if boost <= 0:
        return item
    diagnostics = normalize_context_diagnostics(normalized_item.diagnostics)
    diagnostics["context_requirement_reason"] = "explicit query requirement matched item evidence"
    diagnostics["score_signals"] = {
        **safe_score_signals(diagnostics.get("score_signals")),
        "context_requirement_boost": boost,
        "context_requirement_matched_anchor_kind_count": len(matched_anchor_kinds),
        "context_requirement_matched_modality_count": len(matched_modalities),
        "context_requirement_matched_feature_count": len(matched_features),
    }
    diagnostics["provenance"] = {
        **safe_diagnostic_mapping(diagnostics.get("provenance")),
        "context_requirement_boost_applied": True,
        "context_requirement_matched_anchor_kinds": list(matched_anchor_kinds),
        "context_requirement_matched_modalities": list(matched_modalities),
        "context_requirement_matched_evidence_features": list(matched_features),
    }
    return replace(
        normalized_item,
        score=min(0.99, round(normalized_item.score + boost, 4)),
        diagnostics=normalize_context_diagnostics(diagnostics),
    )


def _context_requirement_boost_already_applied(item: ContextItem) -> bool:
    diagnostics = normalize_context_diagnostics(item.diagnostics)
    provenance = safe_diagnostic_mapping(diagnostics.get("provenance"))
    return provenance.get("context_requirement_boost_applied") is True


def _with_deterministic_rerank_adjustment(
    item: ContextItem,
    *,
    query: str,
    plan: QueryExpansionPlan,
    query_anchor_intent: QueryAnchorIntent,
    requested_total: int,
    max_boost: float,
    max_penalty: float,
) -> ContextItem:
    if _deterministic_rerank_already_applied(item):
        return item
    normalized_item = normalize_context_item_diagnostics(item)
    signals = _deterministic_rerank_signals(
        normalized_item,
        query=query,
        plan=plan,
        query_anchor_intent=query_anchor_intent,
        requested_total=requested_total,
        max_boost=max_boost,
        max_penalty=max_penalty,
    )
    if signals.net_adjustment == 0:
        return item
    diagnostics = normalize_context_diagnostics(normalized_item.diagnostics)
    diagnostics["deterministic_rerank_reason"] = (
        "query-aware deterministic rerank over fused candidates"
    )
    diagnostics["score_signals"] = {
        **safe_score_signals(diagnostics.get("score_signals")),
        "deterministic_rerank_boost": signals.boost,
        "deterministic_rerank_penalty": signals.penalty,
        "deterministic_rerank_net_adjustment": signals.net_adjustment,
        "deterministic_rerank_source_count": signals.source_count,
        "deterministic_rerank_strong_source_count": signals.strong_source_count,
        "deterministic_rerank_requirement_coverage": signals.coverage_ratio,
        "deterministic_rerank_query_reason": signals.query_reason,
    }
    diagnostics["provenance"] = {
        **safe_diagnostic_mapping(diagnostics.get("provenance")),
        "deterministic_rerank_applied": True,
        "deterministic_rerank_reasons": list(signals.reasons[:8]),
        "deterministic_rerank_anchor_conflict": signals.anchor_conflict,
    }
    return replace(
        normalized_item,
        score=min(0.99, max(0.0, round(normalized_item.score + signals.net_adjustment, 4))),
        diagnostics=normalize_context_diagnostics(diagnostics),
    )


def _deterministic_rerank_signals(
    item: ContextItem,
    *,
    query: str,
    plan: QueryExpansionPlan,
    query_anchor_intent: QueryAnchorIntent,
    requested_total: int,
    max_boost: float,
    max_penalty: float,
) -> _DeterministicRerankSignals:
    sources = diagnostic_retrieval_sources(item.diagnostics)
    strong_source_count = len(set(sources).intersection(_STRONG_EVIDENCE_RERANK_SOURCES))
    query_text, query_reason, relevance = best_query_relevance(plan, text=item.text)
    del query_text
    coverage_ratio = _item_requirement_coverage_ratio(
        item,
        query=query,
        query_anchor_intent=query_anchor_intent,
        requested_total=requested_total,
    )
    anchor_match = match_query_anchor_intent_to_text(query_anchor_intent, item.text)
    anchor_conflict = query_anchor_intent_text_conflicts(
        query_anchor_intent,
        item.text,
    ) or has_project_identity_mismatch(query=query, text=item.text)
    boost = 0.0
    penalty = 0.0
    reasons: list[str] = []
    if len(sources) >= 2:
        boost += min(0.018, 0.006 * len(sources))
        reasons.append("hybrid_source_diversity")
    if strong_source_count:
        boost += min(0.018, 0.008 * strong_source_count)
        reasons.append("strong_evidence_source")
    if anchor_match is not None:
        boost += min(0.018, max(0.0, anchor_match.score_boost) * 0.35)
        reasons.append("query_anchor_match")
    if requested_total > 0 and coverage_ratio > 0:
        boost += 0.014 * coverage_ratio
        reasons.append("explicit_requirement_covered")
    if is_query_relevance_sufficient(relevance):
        relevance_boost = min(
            0.012,
            relevance.score_boost * 0.1 + relevance.distinctive_term_hits * 0.003,
        )
        if relevance_boost > 0:
            boost += relevance_boost
            reasons.append("query_relevance_supported")
    if anchor_conflict:
        penalty += 0.07
        reasons.append("query_anchor_conflict")
    if requested_total > 0:
        if coverage_ratio <= 0:
            penalty += 0.025
            reasons.append("explicit_requirement_missing")
        elif coverage_ratio < 0.5:
            penalty += 0.012
            reasons.append("explicit_requirement_partial")
    if (
        not is_query_relevance_sufficient(relevance)
        and anchor_match is None
        and coverage_ratio <= 0
    ):
        penalty += 0.018
        reasons.append("weak_query_relevance")
    return _DeterministicRerankSignals(
        boost=round(min(max_boost, boost), 4),
        penalty=round(min(max_penalty, penalty), 4),
        reasons=tuple(dict.fromkeys(reasons)),
        source_count=len(sources),
        strong_source_count=strong_source_count,
        coverage_ratio=round(coverage_ratio, 4),
        anchor_conflict=anchor_conflict,
        query_reason=query_reason,
    )


def _item_requirement_coverage_ratio(
    item: ContextItem,
    *,
    query: str,
    query_anchor_intent: QueryAnchorIntent,
    requested_total: int,
) -> float:
    if requested_total <= 0:
        return 0.0
    coverage = context_requirement_coverage(
        query=query,
        query_anchor_intent=query_anchor_intent,
        items=(item,),
    )
    return _coverage_ratio(coverage.get("coverage_ratio"))


def _coverage_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value))
    return 0


def _coverage_ratio(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, int | float):
        return min(1.0, max(0.0, float(value)))
    return 0.0


def _deterministic_rerank_already_applied(item: ContextItem) -> bool:
    diagnostics = normalize_context_diagnostics(item.diagnostics)
    provenance = safe_diagnostic_mapping(diagnostics.get("provenance"))
    return provenance.get("deterministic_rerank_applied") is True


def _coverage_value_set(value: object) -> frozenset[str]:
    if not isinstance(value, list | tuple):
        return frozenset()
    return frozenset(
        text
        for item in value
        if isinstance(item, str) and (text := item.strip().casefold())
    )


def _sorted_coverage_matches(
    requested: frozenset[str],
    covered: object,
) -> tuple[str, ...]:
    return tuple(sorted(requested & _coverage_value_set(covered)))


def _with_rank_fusion_boost(
    item: ContextItem,
    *,
    fusion_score: float,
    max_fusion_score: float,
    max_boost: float,
    source_count: int,
    source_weighted: bool = False,
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
        "rank_fusion_source_weighted": source_weighted,
    }
    diagnostics["provenance"] = {
        **safe_diagnostic_mapping(diagnostics.get("provenance")),
        "rank_fusion_applied": True,
        "rank_fusion_source_count": source_count,
        "rank_fusion_source_weighted": source_weighted,
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
