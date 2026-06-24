from infinity_context_core.application.context_conversation_counterparty import (
    conversation_counterparty_evidence_signal,
    conversation_recency_evidence_signal,
    conversation_recency_missing_temporal_signal,
    conversation_recency_temporal_hint_signal,
    conversation_topic_evidence_signal,
    requests_conversation_recency,
)


def test_conversation_counterparty_evidence_signal_prefers_explicit_participant() -> None:
    boost, penalty, reason = conversation_counterparty_evidence_signal(
        query="Who did Alex talk to about Project Atlas?",
        text="Alex talked with Sam about Project Atlas rollout.",
    )

    assert boost > 0
    assert penalty == 0
    assert reason == "conversation_counterparty_exact_evidence"


def test_conversation_counterparty_evidence_signal_keeps_negative_reason() -> None:
    boost, penalty, reason = conversation_counterparty_evidence_signal(
        query="Who did Alex talk to about Project Atlas?",
        text="Sam said Project Atlas is delayed, but there was no conversation with Alex.",
    )

    assert boost == 0
    assert penalty > 0
    assert reason == "conversation_counterparty_negative_evidence"


def test_conversation_topic_evidence_signal_prefers_explicit_topic() -> None:
    boost, penalty, reason = conversation_topic_evidence_signal(
        query="What did Alex and Maria talk about?",
        text="Alex talked with Maria about Project Atlas and invoice approval.",
    )

    assert boost > 0
    assert penalty == 0
    assert reason == "conversation_topic_exact_evidence"


def test_conversation_topic_evidence_signal_handles_covered_call_wording() -> None:
    boost, penalty, reason = conversation_topic_evidence_signal(
        query="What was Alex's call with Maria about?",
        text="Alex's call with Maria covered Project Atlas migration risks.",
    )

    assert boost > 0
    assert penalty == 0
    assert reason == "conversation_topic_exact_evidence"


def test_conversation_topic_evidence_signal_penalizes_negative_covered_wording() -> None:
    boost, penalty, reason = conversation_topic_evidence_signal(
        query="What was Alex's call with Maria about?",
        text="Alex's call with Maria did not cover Project Atlas migration risks.",
    )

    assert boost == 0
    assert penalty > 0
    assert reason == "conversation_topic_negative_evidence"


def test_conversation_topic_evidence_signal_penalizes_participant_only_text() -> None:
    boost, penalty, reason = conversation_topic_evidence_signal(
        query="What was Alex's call with Maria about?",
        text="Alex had a call with Maria after lunch.",
    )

    assert boost == 0
    assert penalty > 0
    assert reason == "conversation_topic_missing_topic_evidence"


def test_conversation_recency_evidence_signal_prefers_temporal_event_text() -> None:
    boost, penalty, reason = conversation_recency_evidence_signal(
        query="What was my latest call with Alex about?",
        text="Yesterday's call with Alex covered Project Atlas migration risks.",
    )

    assert boost > 0
    assert penalty == 0
    assert reason == "conversation_recency_temporal_evidence"


def test_conversation_recency_evidence_signal_uses_textual_temporal_evidence() -> None:
    english_boost, english_penalty, english_reason = conversation_recency_evidence_signal(
        query="What was the latest conversation with Alex?",
        text="Last week Alex had a call with Maria about Atlas.",
    )
    russian_boost, russian_penalty, russian_reason = conversation_recency_evidence_signal(
        query="Что было на последнем созвоне с Алексом?",
        text="На прошлой неделе был созвон с Алексом про Atlas.",
    )

    assert english_boost > 0
    assert english_penalty == 0
    assert english_reason == "conversation_recency_temporal_evidence"
    assert russian_boost > 0
    assert russian_penalty == 0
    assert russian_reason == "conversation_recency_temporal_evidence"


def test_conversation_recency_evidence_signal_supports_relative_time_queries() -> None:
    english_boost, english_penalty, english_reason = conversation_recency_evidence_signal(
        query="What did I discuss with Alex two hours ago?",
        text="Two hours ago I discussed Project Atlas migration risks with Alex.",
    )
    russian_boost, russian_penalty, russian_reason = conversation_recency_evidence_signal(
        query="Что я обсуждал с Алексом час назад?",
        text="Час назад был созвон с Алексом про Atlas.",
    )

    assert english_boost > 0
    assert english_penalty == 0
    assert english_reason == "conversation_recency_temporal_evidence"
    assert russian_boost > 0
    assert russian_penalty == 0
    assert russian_reason == "conversation_recency_temporal_evidence"


def test_requests_conversation_recency_detects_latest_conversation_queries() -> None:
    assert requests_conversation_recency("What was my latest call with Alex about?")
    assert requests_conversation_recency("Что было на последнем созвоне с Алексом?")
    assert requests_conversation_recency("What did I discuss with Alex two hours ago?")
    assert requests_conversation_recency("Что я обсуждал с Алексом час назад?")
    assert not requests_conversation_recency("What did Alex and Maria talk about?")


def test_conversation_recency_evidence_signal_penalizes_generic_person_fact() -> None:
    boost, penalty, reason = conversation_recency_evidence_signal(
        query="What was the last conversation with Alex?",
        text="Alex owns the Project Atlas renewal follow-up.",
    )

    assert boost == 0
    assert penalty > 0
    assert reason == "conversation_recency_missing_event_evidence"


def test_conversation_recency_temporal_hint_signal_uses_recent_event_hint() -> None:
    boost, reason = conversation_recency_temporal_hint_signal(
        query="What was the latest conversation with Alex?",
        temporal_hint_code="today",
    )

    assert boost > 0
    assert reason == "conversation_recency_temporal_hint_evidence"


def test_conversation_recency_temporal_hint_signal_prefers_dated_event_hint() -> None:
    boost, reason = conversation_recency_temporal_hint_signal(
        query="What was the latest conversation with Alex?",
        temporal_hint_code="last_week",
    )
    future_boost, future_reason = conversation_recency_temporal_hint_signal(
        query="What was the latest conversation with Alex?",
        temporal_hint_code="next_week",
    )

    assert boost > 0
    assert reason == "conversation_recency_dated_temporal_hint_evidence"
    assert future_boost == 0
    assert future_reason == ""


def test_conversation_recency_missing_temporal_signal_penalizes_undated_event() -> None:
    penalty, reason = conversation_recency_missing_temporal_signal(
        query="What was the latest conversation with Alex?",
        text="Call with Alex covered Project Atlas migration risks.",
        temporal_hint_code="",
    )

    assert penalty > 0
    assert reason == "conversation_recency_missing_temporal_evidence"
