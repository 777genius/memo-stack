from __future__ import annotations

from infinity_context_core.application.context_query_expansion import (
    build_query_expansion_plan,
)
from infinity_context_core.application.context_ranking import (
    best_query_relevance,
    keyword_chunk_score,
)


def test_book_suggestion_bridge_matches_follow_up_reading_evidence() -> None:
    plan = build_query_expansion_plan("What book did Melanie read from Caroline's suggestion?")

    _, reason, relevance = best_query_relevance(
        plan,
        text=(
            "D17:10 Melanie: Thanks, Caroline. It was tough, but I'm doing ok. "
            "Been reading that book you recommended a while ago and painting to keep busy."
        ),
    )
    score = keyword_chunk_score(relevance, query_expansion_reason=reason)

    assert reason == "book_suggestion_bridge"
    assert relevance.distinctive_term_hits >= 6
    assert score >= 0.89
