from infinity_context_core.application.context_domain_rerank_apply import (
    apply_domain_rerank_signals,
)
from infinity_context_core.application.context_relevance import QueryRelevance
from infinity_context_core.application.dto import ContextItem
from infinity_context_core.domain.entities import SourceRef


def test_apply_domain_rerank_signals_collects_adjustments_and_reasons() -> None:
    item = ContextItem(
        item_id="audrey_roasted_chicken",
        item_type="chunk",
        text="Audrey says roasted chicken is one of her favorite comfort meals.",
        score=0.7,
        source_refs=(SourceRef(source_type="document", source_id="doc"),),
        diagnostics={
            "retrieval_source": "keyword_chunks",
            "retrieval_sources": ["keyword_chunks"],
            "score_signals": {"query_expansion_reason": "food_preference_bridge"},
        },
    )

    adjustment = apply_domain_rerank_signals(
        query="Which meat does Audrey prefer eating more than others?",
        query_reason="food_preference_bridge",
        item=item,
        relevance=QueryRelevance(
            score_boost=0.0,
            query_term_count=5,
            unique_term_hits=5,
            capped_frequency_hits=5,
            hit_ratio=1.0,
            distinctive_term_count=5,
            distinctive_term_hits=5,
        ),
    )

    assert adjustment.boost > 0
    assert adjustment.penalty == 0
    assert "preference_exact_evidence" in adjustment.reasons


def test_apply_domain_rerank_signals_includes_outdoor_preference_evidence() -> None:
    item = ContextItem(
        item_id="melanie_perseid_trip",
        item_type="chunk",
        text=(
            "Melanie remembered the camping trip where her family watched the Perseid "
            "meteor shower and felt at one with the universe."
        ),
        score=0.7,
        source_refs=(SourceRef(source_type="document", source_id="doc"),),
        diagnostics={
            "retrieval_source": "keyword_chunks",
            "retrieval_sources": ["keyword_chunks"],
            "score_signals": {"query_expansion_reason": "outdoor_preference_bridge"},
        },
    )

    adjustment = apply_domain_rerank_signals(
        query="Would Melanie be more interested in a national park or a theme park?",
        query_reason="outdoor_preference_bridge",
        item=item,
        relevance=QueryRelevance(
            score_boost=0.0,
            query_term_count=6,
            unique_term_hits=6,
            capped_frequency_hits=6,
            hit_ratio=1.0,
            distinctive_term_count=6,
            distinctive_term_hits=5,
        ),
    )

    assert adjustment.boost > 0
    assert adjustment.penalty == 0
    assert "outdoor_preference_exact_evidence" in adjustment.reasons


def test_apply_domain_rerank_signals_includes_causal_reason_evidence() -> None:
    item = ContextItem(
        item_id="gina_job_loss",
        item_type="chunk",
        text=(
            "Gina lost her Door Dash job, so she started thinking seriously "
            "about opening her own clothing store."
        ),
        score=0.7,
        source_refs=(SourceRef(source_type="document", source_id="doc"),),
        diagnostics={
            "retrieval_source": "keyword_chunks",
            "retrieval_sources": ["keyword_chunks"],
            "score_signals": {"query_expansion_reason": "business_start_reason_bridge"},
        },
    )

    adjustment = apply_domain_rerank_signals(
        query="Why did Gina start her own clothing store?",
        query_reason="business_start_reason_bridge",
        item=item,
        relevance=QueryRelevance(
            score_boost=0.0,
            query_term_count=5,
            unique_term_hits=5,
            capped_frequency_hits=5,
            hit_ratio=1.0,
            distinctive_term_count=5,
            distinctive_term_hits=5,
        ),
    )

    assert adjustment.boost > 0
    assert "causal_reason_exact_evidence" in adjustment.reasons
