from infinity_context_core.application.context_query_expansion import (
    build_query_expansion_plan,
)
from infinity_context_core.application.context_query_intent import build_query_anchor_intent
from infinity_context_core.application.context_ranking import (
    apply_deterministic_rerank_adjustments,
)
from infinity_context_core.application.dto import ContextItem
from infinity_context_core.domain.entities import SourceRef


def test_deterministic_rerank_uses_after_recommendation_roles() -> None:
    query = "What book did Melanie read after Caroline recommended it?"
    plan = build_query_expansion_plan(query)
    intent = build_query_anchor_intent(query)
    correct = _item(
        "caroline_to_melanie",
        score=0.7,
        text="Caroline recommended Becoming Nicole by Amy Ellis Nutt to Melanie.",
    )
    reversed_roles = _item(
        "melanie_to_caroline",
        score=0.72,
        text="Melanie recommended Becoming Nicole to Caroline.",
    )

    reranked = apply_deterministic_rerank_adjustments(
        (reversed_roles, correct),
        query=query,
        plan=plan,
        query_anchor_intent=intent,
    )
    by_id = {item.item_id: item for item in reranked}

    assert by_id["caroline_to_melanie"].score > by_id["melanie_to_caroline"].score
    assert (
        "action_role_actor_recipient_match"
        in by_id["caroline_to_melanie"].diagnostics["provenance"][
            "deterministic_rerank_reasons"
        ]
    )
    assert (
        "action_role_actor_recipient_reversed"
        in by_id["melanie_to_caroline"].diagnostics["provenance"][
            "deterministic_rerank_reasons"
        ]
    )


def test_deterministic_rerank_prefers_requested_recipient_evidence() -> None:
    query = "Who did Caroline recommend Becoming Nicole to?"
    plan = build_query_expansion_plan(query)
    intent = build_query_anchor_intent(query)
    correct = _item(
        "caroline_to_melanie",
        score=0.7,
        text="Caroline recommended Becoming Nicole by Amy Ellis Nutt to Melanie.",
    )
    actor_only = _item(
        "caroline_actor_only",
        score=0.72,
        text="Caroline recommended Becoming Nicole by Amy Ellis Nutt.",
    )
    wrong_actor = _item(
        "melanie_to_caroline",
        score=0.73,
        text="Melanie recommended Becoming Nicole to Caroline.",
    )

    reranked = apply_deterministic_rerank_adjustments(
        (actor_only, wrong_actor, correct),
        query=query,
        plan=plan,
        query_anchor_intent=intent,
    )
    by_id = {item.item_id: item for item in reranked}

    assert by_id["caroline_to_melanie"].score > by_id["caroline_actor_only"].score
    assert by_id["caroline_to_melanie"].score > by_id["melanie_to_caroline"].score
    assert (
        "action_role_actor_to_recipient_evidence"
        in by_id["caroline_to_melanie"].diagnostics["provenance"][
            "deterministic_rerank_reasons"
        ]
    )
    assert (
        "action_role_requested_recipient_missing"
        in by_id["caroline_actor_only"].diagnostics["provenance"][
            "deterministic_rerank_reasons"
        ]
    )
    assert (
        "action_role_actor_mismatch"
        in by_id["melanie_to_caroline"].diagnostics["provenance"][
            "deterministic_rerank_reasons"
        ]
    )


def _item(item_id: str, *, score: float, text: str) -> ContextItem:
    return ContextItem(
        item_id=item_id,
        item_type="chunk",
        text=text,
        score=score,
        source_refs=(SourceRef(source_type="document", source_id="doc"),),
        diagnostics={
            "retrieval_source": "keyword_chunks",
            "retrieval_sources": ["keyword_chunks"],
            "score_signals": {"base_score": score},
            "provenance": {"retrieval_sources": ["keyword_chunks"]},
        },
    )
