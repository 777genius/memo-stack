from __future__ import annotations

from infinity_context_core.application.context_query_intent import build_query_anchor_intent
from infinity_context_core.application.context_requirement_coverage import (
    context_requirement_coverage,
)
from infinity_context_core.application.dto import ContextItem
from infinity_context_core.domain.entities import SourceRef


def test_context_requirement_coverage_tracks_what_day_temporal_shape() -> None:
    query = "What day did Caroline go to the LGBTQ support group?"
    intent = build_query_anchor_intent(query)
    item = ContextItem(
        item_id="support_group_turn",
        item_type="chunk",
        text=(
            "session_1 date: 7 May 2023\n"
            "D1:1 Caroline: I went to the LGBTQ support group today."
        ),
        score=0.9,
        source_refs=(SourceRef(source_type="locomo_turn", source_id="D1:1"),),
        diagnostics={"retrieval_source": "keyword_chunks"},
    )

    coverage = context_requirement_coverage(
        query=query,
        query_anchor_intent=intent,
        items=(item,),
    )

    assert "temporal" in coverage["requested_answer_shapes"]
    assert "temporal" in coverage["covered_answer_shapes"]
    assert coverage["missing_answer_shapes"] == []


def test_context_requirement_coverage_tracks_russian_which_day_temporal_shape() -> None:
    query = "В какой день был созвон с Алексом?"
    intent = build_query_anchor_intent(query)
    item = ContextItem(
        item_id="alex_call",
        item_type="chunk",
        text="Созвон с Алексом был на прошлой неделе, в пятницу.",
        score=0.9,
        source_refs=(SourceRef(source_type="document", source_id="call-note"),),
        diagnostics={"retrieval_source": "keyword_chunks"},
    )

    coverage = context_requirement_coverage(
        query=query,
        query_anchor_intent=intent,
        items=(item,),
    )

    assert "temporal" in coverage["requested_answer_shapes"]
    assert "temporal" in coverage["covered_answer_shapes"]
    assert coverage["missing_answer_shapes"] == []
