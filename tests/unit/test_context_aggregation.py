from datetime import UTC, datetime
from types import SimpleNamespace

from infinity_context_core.application import BuildContextQuery
from infinity_context_core.application.context_query_expansion import build_query_expansion_plan
from infinity_context_core.application.context_relevance import score_query_relevance
from infinity_context_core.application.use_cases.build_context import (
    _aggregation_evidence_text,
    _aggregation_source_kind_rank,
    _is_dialogue_visual_reference_source_sibling,
    _is_pottery_type_observation_companion,
    _keyword_aggregation_chunk_items,
    _keyword_aggregation_query_kind,
    _source_group_seed_turns,
    _source_sibling_companion_extra_slot,
    _source_sibling_rank,
    _source_sibling_relevance_allowed,
    _source_sibling_score,
    _SourceSiblingRank,
)
from infinity_context_core.domain.entities import (
    MemoryChunk,
    MemoryChunkId,
    MemoryChunkKind,
    MemoryDocumentId,
    MemoryScopeId,
    SpaceId,
)


def test_aggregation_evidence_text_prefers_dialogue_window_with_stronger_query_terms() -> None:
    text = "\n".join(
        [
            "D10:1 Caroline: Hey Melanie, anything new in 2023?",
            "D10:2 Melanie: Work has been busy.",
            "D10:3 Caroline: Glad to hear from you.",
            "D10:8 Melanie: We went to the beach recently and the kids had a blast.",
            "D10:9 Caroline: Sounds fun. What was the best part?",
            "D10:10 Melanie: We only go once or twice a year.",
            "D10:11 Caroline: Nice.",
        ]
    )

    snippet = _aggregation_evidence_text(
        query="How many times has Melanie gone to the beach in 2023?",
        text=text,
    )

    assert "D10:8 Melanie:" in snippet
    assert "beach recently" in snippet
    assert "D10:10 Melanie:" in snippet
    assert "D10:1 Caroline:" not in snippet


def test_keyword_aggregation_chunks_still_collect_count_queries() -> None:
    items, diagnostics = _keyword_aggregation_chunk_items(
        query=_build_query("How many hikes has Joanna been on?"),
        seed_chunks=(
            _chunk(
                "count_a",
                "D11:5 Joanna went on a hike near the waterfall. D11:6 Joanna loved the trail.",
            ),
        ),
    )

    assert diagnostics["keyword_aggregation_query_kind"] == "count"
    assert diagnostics["keyword_aggregation_chunks_used"] == 1
    assert items[0].diagnostics["retrieval_source"] == "keyword_aggregation_chunks"


def test_keyword_aggregation_chunks_collect_list_queries() -> None:
    items, diagnostics = _keyword_aggregation_chunk_items(
        query=_build_query("What items has Melanie bought?"),
        seed_chunks=(
            _chunk(
                "list_a",
                (
                    "D19:2 Melanie bought family figurines yesterday. "
                    "D19:3 Caroline asked whether she bought anything else. "
                    "D7:18 Melanie got some new shoes for work."
                ),
                source_external_id="locomo:conv-26:session_19:observation",
            ),
        ),
    )

    assert diagnostics["keyword_aggregation_query_kind"] == "list"
    assert diagnostics["keyword_aggregation_chunks_used"] == 1
    assert "family figurines" in items[0].text
    assert "new shoes" in items[0].text


def test_keyword_aggregation_query_kind_handles_band_list_queries() -> None:
    assert _keyword_aggregation_query_kind("What bands has Melanie seen?") == "list"
    assert (
        _keyword_aggregation_query_kind("What musical artists/bands has Melanie seen?")
        == "list"
    )


def test_keyword_aggregation_query_kind_handles_type_list_queries() -> None:
    assert _keyword_aggregation_query_kind("What types of pottery have Melanie made?") == "list"
    assert _keyword_aggregation_query_kind("Which kinds of documents did Alex save?") == "list"


def test_keyword_aggregation_source_kind_prefers_observation_over_raw_session() -> None:
    raw = _chunk("raw", "D1:1 raw", source_external_id="locomo:conv-26:session_12")
    observation = _chunk(
        "observation",
        "D12:14 related observation",
        source_external_id="locomo:conv-26:session_12:observation",
    )
    turn = _chunk(
        "turn",
        "D12:4 exact turn",
        source_external_id="locomo:conv-26:session_12:D12:4:turn",
    )

    assert _aggregation_source_kind_rank(observation) < _aggregation_source_kind_rank(turn)
    assert _aggregation_source_kind_rank(turn) < _aggregation_source_kind_rank(raw)


def test_aggregation_evidence_text_preserves_omitted_source_markers() -> None:
    text = "\n".join(
        [
            "D12:2 D12:4 Melanie: Melanie finished another pottery project.",
            "D12:6 D12:8 Melanie: Art has been a source of comfort.",
            "D12:9 D12:10 Melanie: Life is tough but happy moments matter.",
            "D12:11 D12:12 Melanie: Caroline has been supportive.",
            "D12:13 Melanie: Caroline appreciates their friendship.",
            "D12:14 D12:16 Melanie: Melanie appreciates Caroline's friendship.",
        ]
    )

    snippet = _aggregation_evidence_text(
        query="What types of pottery have Melanie and her kids made?",
        text=text,
    )

    assert "D12:4 Melanie" in snippet
    assert "omitted source evidence markers:" in snippet
    assert "D12:14" in snippet


def test_keyword_aggregation_chunks_preserve_multiple_distinct_list_windows() -> None:
    items, diagnostics = _keyword_aggregation_chunk_items(
        query=_build_query("What activities has Melanie done with her family?"),
        seed_chunks=(
            _chunk(
                "list_multi_window",
                (
                    "D1:1 Caroline: How was your week? "
                    "D1:2 Melanie: We went camping with my family and roasted marshmallows. "
                    "D1:3 Caroline: That sounds relaxing. "
                    "D1:4 Melanie: Work has been busy. "
                    "D1:5 Caroline: Same here. "
                    "D1:6 Melanie: The kids had school events. "
                    "D1:7 Caroline: Any creative plans? "
                    "D1:8 Melanie: We painted nature scenes together as a family. "
                    "D1:9 Caroline: Nice. "
                    "D1:10 Melanie: We also went swimming with the kids."
                ),
                source_external_id="locomo:conv-26:session_1:observation",
            ),
        ),
    )

    assert diagnostics["keyword_aggregation_query_kind"] == "list"
    assert diagnostics["keyword_aggregation_chunks_used"] == 1
    assert "D1:2 Melanie" in items[0].text
    assert "roasted marshmallows" in items[0].text
    assert "D1:8 Melanie" in items[0].text
    assert "painted nature scenes" in items[0].text
    assert len(items[0].text) < len(
        "D1:1 Caroline: How was your week? "
        "D1:2 Melanie: We went camping with my family and roasted marshmallows. "
        "D1:3 Caroline: That sounds relaxing. "
        "D1:4 Melanie: Work has been busy. "
        "D1:5 Caroline: Same here. "
        "D1:6 Melanie: The kids had school events. "
        "D1:7 Caroline: Any creative plans? "
        "D1:8 Melanie: We painted nature scenes together as a family. "
        "D1:9 Caroline: Nice. "
        "D1:10 Melanie: We also went swimming with the kids."
    )


def test_keyword_aggregation_chunks_use_expansion_query_for_list_evidence_windows() -> None:
    query_text = "What activities has Melanie done with her family?"
    items, diagnostics = _keyword_aggregation_chunk_items(
        query=_build_query(query_text),
        query_plan=build_query_expansion_plan(query_text),
        seed_chunks=(
            _chunk(
                "list_expansion_window",
                (
                    "D8:1 Caroline: Hey Mel, what's up? "
                    "D8:2 Melanie: Last Fri I finally took my kids to a pottery workshop. "
                    "We all made our own pots, it was fun and therapeutic! "
                    "D8:3 Caroline: How'd they like it? "
                    "D8:4 Melanie: The kids loved it and made something with clay. "
                    "image caption: a photo of a cup with a dog face on it. "
                    "visual query: kids pottery finished pieces. "
                    "D8:5 Caroline: What other creative projects do you do with them? "
                    "D8:6 Melanie: We love painting together lately."
                ),
                source_external_id="locomo:conv-26:session_8:observation",
            ),
        ),
    )

    assert diagnostics["keyword_aggregation_query_kind"] == "list"
    assert diagnostics["keyword_aggregation_chunks_used"] == 1
    assert "D8:4 Melanie" in items[0].text
    assert "kids loved it" in items[0].text
    assert items[0].diagnostics["score_signals"]["query_expansion_reason"] in {
        "decomposition_activity_participation",
        "family_activity_bridge",
        "pottery_type_bridge",
    }


def test_keyword_aggregation_chunks_collect_modified_list_queries() -> None:
    items, diagnostics = _keyword_aggregation_chunk_items(
        query=_build_query("What LGBTQ+ events has Caroline participated in?"),
        seed_chunks=(
            _chunk(
                "modified_list_a",
                "D5:1 Caroline went to an LGBTQ+ pride parade and felt like she belonged.",
            ),
        ),
    )

    assert diagnostics["keyword_aggregation_query_kind"] == "list"
    assert diagnostics["keyword_aggregation_chunks_used"] == 1
    assert "D5:1 Caroline" in items[0].text


def test_keyword_aggregation_chunks_skip_non_aggregation_queries() -> None:
    items, diagnostics = _keyword_aggregation_chunk_items(
        query=_build_query("Where does Alex live now?"),
        seed_chunks=(
            _chunk("plain_a", "D1:1 Alex lives in Berlin now."),
        ),
    )

    assert diagnostics["keyword_aggregation_query_kind"] == ""
    assert diagnostics["keyword_aggregation_chunks_considered"] == 0
    assert items == ()


def test_source_sibling_score_promotes_query_relevant_adjacent_turn() -> None:
    text = (
        "D4:3 Caroline: This necklace is from my home country, Sweden. "
        "It reminds me of my roots and family support."
    )
    relevance = score_query_relevance(
        query="Where did Caroline move from 4 years ago?",
        text=text,
    )

    score = _source_sibling_score(
        rank=_SourceSiblingRank(score=0.948, group_priority=1, turn_distance=2, turn_delta=-2),
        relevance=relevance,
        expansion_query="Where did Caroline move from 4 years ago?",
        expansion_reason="original_query",
        text=text,
    )

    assert score > 0.97


def test_source_sibling_relevance_rejects_single_hit_long_no_candidate_query() -> None:
    text = "Warranty renewal paperwork was archived for Project Atlas."
    query = "unrelated yakutsk cooking recipe quantum aquarium warranty"
    relevance = score_query_relevance(query=query, text=text)
    rank = _SourceSiblingRank(score=0.948, group_priority=1, turn_distance=1, turn_delta=1)

    assert (
        _source_sibling_relevance_allowed(
            rank=rank,
            relevance=relevance,
            expansion_query=query,
            expansion_reason="original_query",
            text=text,
        )
        is False
    )
    assert (
        _source_sibling_score(
            rank=rank,
            relevance=relevance,
            expansion_query=query,
            expansion_reason="original_query",
            text=text,
        )
        == rank.score
    )


def test_source_sibling_score_allows_nearby_visual_referent_turn() -> None:
    text = (
        "D5:6 Melanie: I'm a big fan of pottery - the creativity and skill is "
        "awesome. Plus, making it is so calming. Look at this!"
    )
    relevance = score_query_relevance(
        query="What types of pottery have Melanie and her kids made?",
        text=text,
    )
    rank = _SourceSiblingRank(score=0.948, group_priority=1, turn_distance=2, turn_delta=-2)

    assert _source_sibling_relevance_allowed(
        rank=rank,
        relevance=relevance,
        expansion_query="What types of pottery have Melanie and her kids made?",
        expansion_reason="decomposition_artifact_evidence",
        text=text,
    )
    assert (
        _source_sibling_score(
            rank=rank,
            relevance=relevance,
            expansion_query="What types of pottery have Melanie and her kids made?",
            expansion_reason="decomposition_artifact_evidence",
            text=text,
        )
        > 0.96
    )


def test_source_sibling_score_rejects_subject_only_visual_reference_noise() -> None:
    text = "D15:13 Caroline: Wow! Did you see that band?"
    query = "Caroline transgender conference supportive professionals advocacy"
    relevance = score_query_relevance(query=query, text=text)
    rank = _SourceSiblingRank(
        score=0.968,
        group_priority=7,
        turn_distance=0,
        turn_delta=0,
        group_level_seed=True,
    )

    assert _source_sibling_relevance_allowed(
        rank=rank,
        relevance=relevance,
        expansion_query=query,
        expansion_reason="symbol_importance_bridge",
        text=text,
    ) is False


def test_source_sibling_score_allows_event_visual_reference_followup() -> None:
    text = "D15:13 Caroline: Wow! Did you see that band?"
    query = "Caroline transgender conference supportive professionals advocacy"
    relevance = score_query_relevance(query=query, text=text)
    rank = _SourceSiblingRank(
        score=0.968,
        group_priority=7,
        turn_distance=0,
        turn_delta=0,
        group_level_seed=True,
    )

    assert _source_sibling_relevance_allowed(
        rank=rank,
        relevance=relevance,
        expansion_query=query,
        expansion_reason="transgender_conference_event_bridge",
        text=text,
    )
    assert _source_sibling_score(
        rank=rank,
        relevance=relevance,
        expansion_query=query,
        expansion_reason="transgender_conference_event_bridge",
        text=text,
    ) > rank.score


def test_source_sibling_score_allows_explicit_visual_reference_question() -> None:
    text = "D15:13 Caroline: Wow! Did you see that band?"
    query = "What band did Caroline see in the picture?"
    relevance = score_query_relevance(query=query, text=text)
    rank = _SourceSiblingRank(
        score=0.968,
        group_priority=7,
        turn_distance=0,
        turn_delta=0,
        group_level_seed=True,
    )

    assert _source_sibling_relevance_allowed(
        rank=rank,
        relevance=relevance,
        expansion_query=query,
        expansion_reason="original_query",
        text=text,
    )
    assert (
        _source_sibling_score(
            rank=rank,
            relevance=relevance,
            expansion_query=query,
            expansion_reason="original_query",
            text=text,
        )
        > rank.score
    )


def test_source_sibling_score_caps_low_signal_precise_bridge_noise() -> None:
    weak_text = (
        "D14:11 Caroline: Wow, Mel, you're amazing. "
        "image caption: a crowd walking with a rainbow flag."
    )
    strong_text = (
        "D14:15 Caroline: The rainbow flag mural is important to me. "
        "The eagle symbolizes freedom and pride."
    )
    query = "symbols important Caroline rainbow flag mural eagle symbolizes freedom pride"
    rank = _SourceSiblingRank(
        score=0.968,
        group_priority=1,
        turn_distance=0,
        turn_delta=0,
        group_level_seed=True,
    )
    weak_relevance = score_query_relevance(query=query, text=weak_text)
    strong_relevance = score_query_relevance(query=query, text=strong_text)

    weak_score = _source_sibling_score(
        rank=rank,
        relevance=weak_relevance,
        expansion_query=query,
        expansion_reason="symbol_importance_bridge",
        text=weak_text,
    )
    strong_score = _source_sibling_score(
        rank=rank,
        relevance=strong_relevance,
        expansion_query=query,
        expansion_reason="symbol_importance_bridge",
        text=strong_text,
    )

    assert weak_score < strong_score
    assert strong_score == 0.99


def test_source_sibling_score_caps_low_signal_pottery_type_noise() -> None:
    weak_text = (
        "D8:28 Melanie: I'm getting there, Caroline. Creativity and family keep me "
        "at peace. image caption: a photo of a frisbee basket."
    )
    strong_text = (
        "D8:4 Melanie: The kids loved the pottery workshop, made something with "
        "clay, and the image shows a cup with a dog face."
    )
    query = "Melanie pottery types pieces made clay finished ceramic bowl bowls cup mug kids"
    rank = _SourceSiblingRank(
        score=0.968,
        group_priority=1,
        turn_distance=0,
        turn_delta=0,
        group_level_seed=True,
    )
    weak_relevance = score_query_relevance(query=query, text=weak_text)
    strong_relevance = score_query_relevance(query=query, text=strong_text)

    weak_score = _source_sibling_score(
        rank=rank,
        relevance=weak_relevance,
        expansion_query=query,
        expansion_reason="pottery_type_bridge",
        text=weak_text,
    )
    strong_score = _source_sibling_score(
        rank=rank,
        relevance=strong_relevance,
        expansion_query=query,
        expansion_reason="pottery_type_bridge",
        text=strong_text,
    )

    assert (
        _source_sibling_relevance_allowed(
            rank=rank,
            relevance=weak_relevance,
            expansion_query=query,
            expansion_reason="pottery_type_bridge",
            text=weak_text,
        )
        is False
    )
    assert weak_score <= 0.965
    assert weak_score < strong_score


def test_source_sibling_promotes_pottery_observation_companion() -> None:
    chunk = SimpleNamespace(
        source_external_id="locomo:conv-26:session_12:observation",
    )
    text = (
        "D12:8 Melanie: Melanie's pottery project was a source of happiness. "
        "Related turns: D12:2 D12:4 D12:10. "
        "D12:14 Melanie: Melanie values friendship with Caroline."
    )
    query = "Melanie pottery types pieces made clay finished ceramic bowl bowls cup mug kids"
    relevance = score_query_relevance(query=query, text=text)
    rank = _SourceSiblingRank(
        score=0.955,
        group_priority=10,
        turn_distance=0,
        turn_delta=0,
        group_level_seed=False,
    )

    assert _is_pottery_type_observation_companion(
        chunk=chunk,
        expansion_reason="pottery_type_bridge",
        text=text,
    )
    assert not _is_pottery_type_observation_companion(
        chunk=chunk,
        expansion_reason="original_query",
        text=text,
    )
    assert (
        _source_sibling_score(
            rank=rank,
            relevance=relevance,
            expansion_query=query,
            expansion_reason="pottery_type_bridge",
            text=text,
        )
        >= 0.99
    )


def test_source_sibling_companion_extra_slot_distinguishes_observation_windows() -> None:
    chunk = _chunk(
        "pottery_observation_split",
        (
            "D12:8 Melanie: Melanie's pottery project was a source of happiness. "
            "Related turns: D12:2 D12:4 D12:10. "
            "D12:14 Melanie: Melanie values friendship with Caroline. "
            "Related turns: D12:6 D12:16."
        ),
        source_external_id="locomo:conv-26:session_12:observation",
    )

    assert _source_sibling_companion_extra_slot(
        chunk=chunk,
        text=chunk.text,
    ) == "locomo:conv-26:session_12:observation:D12:8:D12:16"


def test_source_sibling_caps_generic_volunteer_career_noise() -> None:
    weak_text = (
        "D25:9 John: Keep up the awesome work. "
        "visual query: volunteer orientation shelter"
    )
    strong_text = (
        "D32:14 Maria: I spent time at the shelter volunteering at the front desk. "
        "Seeing people get food or a bed made me feel good."
    )
    query = (
        "Maria future job career started volunteering volunteer shelter homeless "
        "front desk talks residents bed fulfilling counselor coordinator compliments"
    )
    rank = _SourceSiblingRank(
        score=0.968,
        group_priority=1,
        turn_distance=0,
        turn_delta=0,
        group_level_seed=True,
    )
    weak_relevance = score_query_relevance(query=query, text=weak_text)
    strong_relevance = score_query_relevance(query=query, text=strong_text)

    weak_score = _source_sibling_score(
        rank=rank,
        relevance=weak_relevance,
        expansion_query=query,
        expansion_reason="volunteer_career_inference_bridge",
        text=weak_text,
    )
    strong_score = _source_sibling_score(
        rank=rank,
        relevance=strong_relevance,
        expansion_query=query,
        expansion_reason="volunteer_career_inference_bridge",
        text=strong_text,
    )

    assert weak_score <= 0.976
    assert strong_score > weak_score


def test_source_sibling_filters_post_event_activity_timing_noise() -> None:
    weak_text = (
        "D2:5 Melanie: I carve out me-time each day with running, reading, "
        "and violin after work."
    )
    strong_text = (
        "D18:17 Melanie: Yup, we just did it yesterday! The kids loved it "
        "and it was a nice way to relax after the road trip."
    )
    visual_companion = (
        "D18:15 Melanie: Having my family around helps a lot. "
        "image caption: a woman and child walking on a trail. "
        "visual query: family hiking mountains."
    )
    query = (
        "Melanie roadtrip road trip after hike hiking family mountains trail "
        "picture pic recent yesterday just did it kids loved nice way relax"
    )
    rank = _SourceSiblingRank(
        score=0.968,
        group_priority=1,
        turn_distance=1,
        turn_delta=1,
        group_level_seed=True,
    )
    weak_relevance = score_query_relevance(query=query, text=weak_text)
    strong_relevance = score_query_relevance(query=query, text=strong_text)
    visual_relevance = score_query_relevance(query=query, text=visual_companion)

    assert (
        _source_sibling_relevance_allowed(
            rank=rank,
            relevance=weak_relevance,
            expansion_query=query,
            expansion_reason="post_event_activity_timing_bridge",
            text=weak_text,
        )
        is False
    )
    assert _source_sibling_relevance_allowed(
        rank=rank,
        relevance=strong_relevance,
        expansion_query=query,
        expansion_reason="post_event_activity_timing_bridge",
        text=strong_text,
    )
    assert _source_sibling_relevance_allowed(
        rank=rank,
        relevance=visual_relevance,
        expansion_query=query,
        expansion_reason="post_event_activity_timing_bridge",
        text=visual_companion,
    )
    assert (
        _source_sibling_score(
            rank=rank,
            relevance=weak_relevance,
            expansion_query=query,
            expansion_reason="post_event_activity_timing_bridge",
            text=weak_text,
        )
        <= 0.976
    )
    assert _source_sibling_score(
        rank=rank,
        relevance=strong_relevance,
        expansion_query=query,
        expansion_reason="post_event_activity_timing_bridge",
        text=strong_text,
    ) > _source_sibling_score(
        rank=rank,
        relevance=weak_relevance,
        expansion_query=query,
        expansion_reason="post_event_activity_timing_bridge",
        text=weak_text,
    )


def test_source_sibling_allows_shoe_usage_question_turn() -> None:
    question_text = "D7:19 Caroline: Love that purple color! For walking or running?"
    weak_text = "D16:6 Melanie: The yellow leaves in that photo are cozy and pretty."
    query = "Melanie new shoes purple walking running used for walk run love color sneakers"
    rank = _SourceSiblingRank(
        score=0.968,
        group_priority=1,
        turn_distance=1,
        turn_delta=1,
        group_level_seed=True,
    )
    question_relevance = score_query_relevance(query=query, text=question_text)
    weak_relevance = score_query_relevance(query=query, text=weak_text)

    assert _source_sibling_relevance_allowed(
        rank=rank,
        relevance=question_relevance,
        expansion_query=query,
        expansion_reason="shoe_usage_bridge",
        text=question_text,
    )
    assert (
        _source_sibling_score(
            rank=rank,
            relevance=weak_relevance,
            expansion_query=query,
            expansion_reason="shoe_usage_bridge",
            text=weak_text,
        )
        <= 0.976
    )
    assert _source_sibling_score(
        rank=rank,
        relevance=question_relevance,
        expansion_query=query,
        expansion_reason="shoe_usage_bridge",
        text=question_text,
    ) > _source_sibling_score(
        rank=rank,
        relevance=weak_relevance,
        expansion_query=query,
        expansion_reason="shoe_usage_bridge",
        text=weak_text,
    )


def test_source_sibling_allows_running_reason_question_turn() -> None:
    question_text = "D7:21 Caroline: Wow! What got you into running?"
    answer_text = (
        "D7:22 Melanie: I've been running farther to de-stress, "
        "which has been great for my headspace."
    )
    weak_text = (
        "D17:12 Melanie: The sunset painting was calming and helped "
        "Caroline talk about feelings."
    )
    query = (
        "Melanie running run farther longer de-stress destress clear mind "
        "headspace mood boost shoes purple walking or running what got into running"
    )
    rank = _SourceSiblingRank(
        score=0.968,
        group_priority=1,
        turn_distance=1,
        turn_delta=1,
        group_level_seed=True,
    )
    question_relevance = score_query_relevance(query=query, text=question_text)
    answer_relevance = score_query_relevance(query=query, text=answer_text)
    weak_relevance = score_query_relevance(query=query, text=weak_text)

    assert _source_sibling_relevance_allowed(
        rank=rank,
        relevance=question_relevance,
        expansion_query=query,
        expansion_reason="running_reason_bridge",
        text=question_text,
    )
    assert _source_sibling_relevance_allowed(
        rank=rank,
        relevance=answer_relevance,
        expansion_query=query,
        expansion_reason="running_reason_bridge",
        text=answer_text,
    )
    assert not _source_sibling_relevance_allowed(
        rank=rank,
        relevance=weak_relevance,
        expansion_query=query,
        expansion_reason="running_reason_bridge",
        text=weak_text,
    )
    assert _source_sibling_score(
        rank=rank,
        relevance=question_relevance,
        expansion_query=query,
        expansion_reason="running_reason_bridge",
        text=question_text,
    ) > 0.96
    assert _source_sibling_score(
        rank=rank,
        relevance=answer_relevance,
        expansion_query=query,
        expansion_reason="running_reason_bridge",
        text=answer_text,
    ) > 0.96


def test_dialogue_visual_reference_priority_requires_dialogue_reference() -> None:
    rank = _SourceSiblingRank(
        score=0.968,
        group_priority=7,
        turn_distance=0,
        turn_delta=0,
        group_level_seed=True,
    )
    dialogue_relevance = score_query_relevance(
        query="Caroline transgender conference",
        text="D15:13 Caroline: Wow! Did you see that band?",
    )
    caption_relevance = score_query_relevance(
        query="Caroline transgender conference",
        text="D15:13 Caroline image caption: a photo of a band playing on stage",
    )

    assert _is_dialogue_visual_reference_source_sibling(
        rank=rank,
        relevance=dialogue_relevance,
        expansion_query="What band did Caroline see in the picture?",
        expansion_reason="original_query",
        text="D15:13 Caroline: Wow! Did you see that band?",
    )
    assert not _is_dialogue_visual_reference_source_sibling(
        rank=rank,
        relevance=caption_relevance,
        expansion_query="What band did Caroline see in the picture?",
        expansion_reason="original_query",
        text="D15:13 Caroline image caption: a photo of a band playing on stage",
    )


def test_source_sibling_rank_keeps_primary_seed_turn_available_for_hybrid_boost() -> None:
    seed = SimpleNamespace(source_external_id="locomo:conv-26:session_7:D7:4:turn")
    source_groups = _source_group_seed_turns((seed,))

    rank = _source_sibling_rank(seed, source_groups=source_groups)

    assert rank is not None
    assert rank.turn_distance == 0
    assert rank.turn_delta == 0
    assert rank.score > 0.96


def test_source_sibling_rank_uses_session_events_as_group_level_seed() -> None:
    seed = SimpleNamespace(source_external_id="locomo:conv-41:session_24:events")
    candidate = SimpleNamespace(source_external_id="locomo:conv-41:session_24:D24:3:turn")
    source_groups = _source_group_seed_turns((seed,))

    rank = _source_sibling_rank(candidate, source_groups=source_groups)

    assert tuple(source_groups) == ("locomo:conv-41:session_24",)
    assert rank is not None
    assert rank.group_level_seed is True
    assert rank.turn_distance == 0
    assert rank.turn_delta == 0
    assert rank.score > 0.96


def test_source_sibling_rank_allows_session_observation_pages_as_group_siblings() -> None:
    seed = SimpleNamespace(source_external_id="locomo:conv-26:session_12:D12:4:turn")
    candidate = SimpleNamespace(source_external_id="locomo:conv-26:session_12:observation")
    source_groups = _source_group_seed_turns((seed,))

    rank = _source_sibling_rank(candidate, source_groups=source_groups)

    assert tuple(source_groups) == ("locomo:conv-26:session_12",)
    assert rank is not None
    assert rank.group_level_seed is False
    assert rank.turn_distance == 0
    assert rank.turn_delta == 0
    assert rank.score >= 0.955


def test_source_sibling_rank_does_not_treat_plain_summary_as_source_group_seed() -> None:
    seed = SimpleNamespace(source_external_id="notes:release:summary")

    assert _source_group_seed_turns((seed,)) == {}


def _build_query(query: str) -> BuildContextQuery:
    return BuildContextQuery(
        space_id=SpaceId("space_test"),
        memory_scope_ids=(MemoryScopeId("scope_test"),),
        query=query,
        max_chunks=10,
    )


def _chunk(
    chunk_id: str,
    text: str,
    *,
    source_external_id: str | None = None,
) -> MemoryChunk:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return MemoryChunk.create(
        chunk_id=MemoryChunkId(chunk_id),
        space_id=SpaceId("space_test"),
        memory_scope_id=MemoryScopeId("scope_test"),
        document_id=MemoryDocumentId(f"{chunk_id}_document"),
        source_type="document",
        source_external_id=source_external_id or f"locomo:conv-26:session_1:{chunk_id}:turn",
        source_hash=f"{chunk_id}_hash",
        kind=MemoryChunkKind.DOCUMENT_SECTION,
        text=text,
        normalized_text=text.casefold(),
        sequence=1,
        char_start=0,
        char_end=len(text),
        token_estimate=max(1, len(text.split())),
        now=now,
    )
