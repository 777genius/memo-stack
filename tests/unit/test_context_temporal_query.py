from infinity_context_core.application.context_temporal_query import (
    apply_temporal_query_intent_boosts,
    build_temporal_query_intent,
)
from infinity_context_core.application.dto import ContextItem
from infinity_context_core.domain.entities import SourceRef


def test_temporal_query_intent_detects_current_and_stale_exclusion() -> None:
    intent = build_temporal_query_intent(
        "Устаревшее не учитывать, что сейчас актуально по проекту Атлас?"
    )

    assert intent.prefers_current is True
    assert intent.excludes_stale is True
    assert intent.include_superseded_review is False
    assert intent.diagnostics()["temporal_query_intent_reasons"] == [
        "prefers_current",
        "excludes_stale",
    ]


def test_temporal_query_intent_detects_change_and_previous_state() -> None:
    changed = build_temporal_query_intent("What changed after the meeting with Alex?")
    previous = build_temporal_query_intent("What was the previous Atlas plan before the call?")

    assert changed.requests_change is True
    assert changed.after_event is True
    assert changed.include_superseded_review is True
    assert previous.requests_previous is True
    assert previous.before_event is True
    assert previous.include_superseded_review is True


def test_temporal_query_boosts_active_replacement_for_change_query() -> None:
    intent = build_temporal_query_intent("What changed after the meeting?")
    active_replacement = _item(
        "active",
        score=0.8,
        retrieval_source="temporal_supersedes_relation",
        fact_status="active",
    )
    previous = _item(
        "previous",
        score=0.62,
        retrieval_source="superseded_review",
        fact_status="superseded",
        review_only=True,
    )

    boosted = apply_temporal_query_intent_boosts(
        (active_replacement, previous),
        intent=intent,
    )

    assert boosted[0].score == 0.85
    assert boosted[0].diagnostics["score_signals"]["temporal_query_intent_boost"] == 0.05
    assert boosted[1].score == 0.655
    assert boosted[1].diagnostics["temporal_query_intent_reason"] == (
        "query asks what changed and item is previous state evidence"
    )


def test_temporal_query_demotes_stale_when_query_excludes_stale() -> None:
    intent = build_temporal_query_intent("ignore stale notes, what is current?")
    current = _item(
        "current",
        score=0.8,
        retrieval_source="postgres_facts",
        fact_status="active",
    )
    stale = _item(
        "stale",
        score=0.62,
        retrieval_source="superseded_review",
        fact_status="superseded",
        review_only=True,
    )

    boosted = apply_temporal_query_intent_boosts((current, stale), intent=intent)

    assert boosted[0].score == 0.818
    assert boosted[1].score == 0.5
    assert boosted[1].diagnostics["temporal_query_intent_reason"] == (
        "query excludes stale memory"
    )


def _item(
    item_id: str,
    *,
    score: float,
    retrieval_source: str,
    fact_status: str,
    review_only: bool = False,
) -> ContextItem:
    return ContextItem(
        item_id=item_id,
        item_type="fact",
        text=item_id,
        score=score,
        source_refs=(SourceRef(source_type="fact", source_id=item_id),),
        diagnostics={
            "retrieval_source": retrieval_source,
            "retrieval_sources": [retrieval_source],
            "review_only": review_only,
            "score_signals": {"base_score": score},
            "provenance": {"fact_status": fact_status},
        },
    )
