"""Conversation participant/topic intent helpers for context ranking."""

from __future__ import annotations

import re

_CONVERSATION_COUNTERPARTY_QUERY_RE = re.compile(
    r"\b(?:who|whom)\b(?=.{0,100}\b(?:talk(?:ed)?|spoke|speak|meet|met|"
    r"message(?:d)?|text(?:ed)?|chat(?:ted)?|discuss(?:ed)?|call(?:ed)?)\b)|"
    r"\b(?:с\s+кем|кто|кого|кому)\b(?=.{0,100}\b(?:говорил\w*|"
    r"разговаривал\w*|общал\w*|переписывал\w*|созвон\w*|обсуждал\w*)\b)",
    re.IGNORECASE | re.DOTALL,
)
_CONVERSATION_NEGATIVE_TEXT_RE = re.compile(
    r"\b(?:no|not|never|without)\s+"
    r"(?:conversation|call|meeting|chat|dm|message|talk|discussion)\b|"
    r"\b(?:did\s+not|didn'?t|never)\s+"
    r"(?:talk|speak|meet|message|text|chat|discuss|call)\b|"
    r"\b(?:не\s+говорил\w*|не\s+разговаривал\w*|не\s+общал\w*|"
    r"не\s+переписывал\w*|не\s+созванивал\w*|не\s+обсуждал\w*|"
    r"без\s+(?:разговора|созвона|переписки|обсуждения))\b",
    re.IGNORECASE,
)
_CONVERSATION_COUNTERPARTY_EXACT_TEXT_RE = re.compile(
    r"\b(?:talk(?:ed)?|spoke|speak|met|meet|message(?:d)?|text(?:ed)?|"
    r"chat(?:ted)?|discuss(?:ed)?|call(?:ed)?)\s+(?:with|to|from)\s+"
    r"[A-Z][\w._-]{1,}\b|"
    r"\b[A-Z][\w._-]{1,}\s+and\s+[A-Z][\w._-]{1,}\s+"
    r"(?:talk(?:ed)?|spoke|met|message(?:d)?|text(?:ed)?|chat(?:ted)?|"
    r"discuss(?:ed)?|call(?:ed)?)\b|"
    r"\b(?:говорил\w*|разговаривал\w*|общал\w*|переписывал\w*|"
    r"созванивал\w*|обсуждал\w*)\s+с\s+[А-ЯЁA-Z][\wА-Яа-яЁё._-]{1,}\b",
    re.IGNORECASE,
)
_CONVERSATION_TOPIC_QUERY_RE = re.compile(
    r"\bwhat\s+did\s+[\w._-]+(?:\s+and\s+[\w._-]+)?\s+"
    r"(?:talk|speak|chat|discuss)\s+about\b|"
    r"\bwhat\s+did\s+[\w._-]+\s+(?:discuss|talk|speak|chat)\s+"
    r"(?:with|to)\s+[\w._-]+\b|"
    r"\bwhat\s+was\s+(?:[\w._-]+(?:'s|’s)\s+)?"
    r"(?:the\s+)?(?:conversation|call|chat|meeting|discussion)\s+"
    r"(?:between|with)\s+[\w._-]+(?:\s+and\s+[\w._-]+)?\s+about\b|"
    r"\bwhat\s+was\s+discussed\s+(?:in|during)\s+(?:the\s+)?"
    r"(?:[\w._-]+\s+){0,4}(?:conversation|call|chat|meeting|discussion)\b|"
    r"\bwhat\s+(?:topic|subject)\s+did\s+[\w._-]+\s+"
    r"(?:talk|speak|chat|discuss)\b|"
    r"\bчто\s+[\w._-]+(?:\s+и\s+[\w._-]+)?\s+"
    r"(?:обсуждал\w*|говорил\w*)\b|"
    r"\bчто\s+обсуждал\w*\s+(?:на|во\s+время)\s+"
    r"(?:созвон\w*|встреч\w*|разговор\w*)\b|"
    r"\bо\s+ч[её]м\s+[\w._-]+(?:\s+и\s+[\w._-]+)?\s+"
    r"(?:говорил\w*|разговаривал\w*|общал\w*|переписывал\w*|обсуждал\w*)\b",
    re.IGNORECASE | re.DOTALL,
)
_CONVERSATION_TOPIC_NEGATIVE_TEXT_RE = re.compile(
    r"\b(?:did\s+not|didn'?t|never)\s+"
    r"(?:talk|speak|chat|discuss)\s+about\b|"
    r"\b(?:did\s+not|didn'?t|never)\s+cover\b|"
    r"\b(?:no|not|never|without)\s+"
    r"(?:topic|subject|discussion)\s+about\b|"
    r"\b(?:не\s+говорил\w*|не\s+разговаривал\w*|не\s+общал\w*|"
    r"не\s+переписывал\w*|не\s+обсуждал\w*)\b.{0,60}\b"
    r"(?:о|об|про)\b",
    re.IGNORECASE | re.DOTALL,
)
_CONVERSATION_TOPIC_EXACT_TEXT_RE = re.compile(
    r"\b(?:talk(?:ed)?|spoke|speak|chat(?:ted)?|discuss(?:ed)?)\b"
    r"(?=.{0,90}\b(?:about|regarding|around|on)\b)|"
    r"\b(?:conversation|call|chat|meeting|discussion)\b"
    r"(?=.{0,90}\b(?:about|topic|subject|agenda|focused\s+on|"
    r"centered\s+on|covered|covers?)\b)|"
    r"\b(?:говорил\w*|разговаривал\w*|общал\w*|переписывал\w*|"
    r"обсуждал\w*)\b(?=.{0,90}\b(?:о|об|про)\b)|"
    r"\b(?:разговор|созвон|встреча|переписка|обсуждение)\b"
    r"(?=.{0,90}\b(?:о|об|про|тема)\b)",
    re.IGNORECASE | re.DOTALL,
)
_CONVERSATION_RECENCY_QUERY_RE = re.compile(
    r"\b(?:latest|last|newest|recent|most\s+recent)\s+"
    r"(?:conversation|call|meeting|chat|dm|message|text|discussion)\b|"
    r"\b(?:conversation|call|meeting|chat|dm|message|text|discussion)\b"
    r"(?=.{0,60}\b(?:latest|last|newest|recent|most\s+recent)\b)|"
    r"\b(?:conversation|call|meeting|chat|dm|message|text|discussion|"
    r"talk(?:ed)?|spoke|met|messag(?:ed|ing)|text(?:ed|ing)|"
    r"chat(?:ted|ting)?|discuss(?:ed)?|call(?:ed)?)\b"
    r"(?=.{0,90}\b(?:today|yesterday|earlier\s+today|"
    r"(?:one|two|three|\d+)\s+hours?\s+ago|hours?\s+ago|"
    r"(?:one|two|three|\d+)\s+days?\s+ago|days?\s+ago|last\s+week)\b)|"
    r"\blast\s+time\s+(?:i|we|[\w._-]+)\s+"
    r"(?:talked|spoke|met|messaged|texted|chatted|discussed|called)\b|"
    r"\b(?:последн\w*|недавн\w*|свеж\w*)\s+"
    r"(?:разговор\w*|созвон\w*|встреч\w*|переписк\w*|чат\w*|обсуждени\w*)\b|"
    r"\b(?:разговор\w*|созвон\w*|встреч\w*|переписк\w*|чат\w*|обсуждени\w*)\b"
    r"(?=.{0,60}\b(?:последн\w*|недавн\w*|свеж\w*)\b)|"
    r"\b(?:говорил\w*|разговаривал\w*|общал\w*|переписывал\w*|"
    r"созванивал\w*|обсуждал\w*|разговор\w*|созвон\w*|встреч\w*|"
    r"переписк\w*|чат\w*|обсуждени\w*)\b"
    r"(?=.{0,90}\b(?:сегодня|вчера|час\w*\s+назад|"
    r"д(?:ень|ня|ней)\s+назад|недел[юи]\s+назад|"
    r"на\s+прошл\w+\s+недел\w*)\b)",
    re.IGNORECASE | re.DOTALL,
)
_CONVERSATION_EVENT_TEXT_RE = re.compile(
    r"\b(?:conversation|call|meeting|chat|dm|message|text|discussion)\s+"
    r"(?:with|between|from|to)\s+[A-Z][\w._-]{1,}\b|"
    r"\b(?:talk(?:ed)?|spoke|met|messag(?:ed|ing)|text(?:ed|ing)|"
    r"chat(?:ted|ting)?|discuss(?:ed)?|call(?:ed)?)\b"
    r"(?=.{0,90}\b(?:with|to|from)\s+[A-Z][\w._-]{1,}\b)|"
    r"\b[A-Z][\w._-]{1,}(?:'s|’s)?\s+"
    r"(?:conversation|call|meeting|chat|dm|message|text|discussion)\b|"
    r"\b[A-Z][\w._-]{1,}\s+"
    r"(?:talk(?:ed)?|spoke|met|messag(?:ed|ing)|text(?:ed|ing)|"
    r"chat(?:ted|ting)?|discuss(?:ed)?|call(?:ed)?)\b|"
    r"\b(?:говорил\w*|разговаривал\w*|общал\w*|переписывал\w*|"
    r"созванивал\w*|обсуждал\w*)\s+с\s+[А-ЯЁA-Z][\wА-Яа-яЁё._-]{1,}\b|"
    r"\b(?:разговор|созвон|встреча|переписка|чат|обсуждение)\s+"
    r"(?:с|между)\s+[А-ЯЁA-Z][\wА-Яа-яЁё._-]{1,}\b",
    re.IGNORECASE | re.DOTALL,
)
_CONVERSATION_RECENCY_TEXT_RE = re.compile(
    r"\b(?:latest|last|newest|recent|most\s+recent|yesterday|today|"
    r"earlier\s+today|earlier\s+this\s+week|last\s+week|last\s+month|"
    r"previous\s+week|previous\s+month|this\s+week|this\s+month|"
    r"hour\s+ago|hours?\s+ago|days?\s+ago|weeks?\s+ago|months?\s+ago)\b|"
    r"\b(?:последн\w*|недавн\w*|свеж\w*|вчера|сегодня|час\w*\s+назад|"
    r"д(?:ень|ня|ней)\s+назад|недел[юи]\s+назад|месяц\w*\s+назад|"
    r"на\s+прошл\w+\s+недел\w*|в\s+прошл\w+\s+месяц\w*|"
    r"на\s+этой\s+недел\w*|в\s+этом\s+месяц\w*)\b",
    re.IGNORECASE,
)
_CONVERSATION_RECENT_TEMPORAL_HINTS = frozenset(
    {
        "earlier_today",
        "hour_ago",
        "hours_ago",
        "today",
        "today_afternoon",
        "today_evening",
        "today_morning",
        "yesterday",
    }
)
_CONVERSATION_FUTURE_TEMPORAL_HINT_PREFIXES = ("next_",)
_CONVERSATION_FUTURE_TEMPORAL_HINTS = frozenset(
    {
        "tomorrow",
    }
)


def conversation_counterparty_negative_signal(*, query: str, text: str) -> tuple[float, str]:
    if not _CONVERSATION_COUNTERPARTY_QUERY_RE.search(query):
        return 0.0, ""
    if _CONVERSATION_NEGATIVE_TEXT_RE.search(text):
        return 0.07, "conversation_counterparty_negative_evidence"
    return 0.0, ""


def conversation_counterparty_evidence_signal(
    *,
    query: str,
    text: str,
) -> tuple[float, float, str]:
    if not _CONVERSATION_COUNTERPARTY_QUERY_RE.search(query):
        return 0.0, 0.0, ""
    if _CONVERSATION_NEGATIVE_TEXT_RE.search(text):
        return 0.0, 0.07, "conversation_counterparty_negative_evidence"
    if _CONVERSATION_COUNTERPARTY_EXACT_TEXT_RE.search(text):
        return 0.024, 0.0, "conversation_counterparty_exact_evidence"
    return 0.0, 0.0, ""


def requests_conversation_topic(query: str) -> bool:
    return _CONVERSATION_TOPIC_QUERY_RE.search(query) is not None


def requests_conversation_recency(query: str) -> bool:
    return _CONVERSATION_RECENCY_QUERY_RE.search(query) is not None


def conversation_topic_negative_signal(*, query: str, text: str) -> tuple[float, str]:
    if not requests_conversation_topic(query):
        return 0.0, ""
    if _CONVERSATION_TOPIC_NEGATIVE_TEXT_RE.search(text):
        return 0.07, "conversation_topic_negative_evidence"
    return 0.0, ""


def conversation_topic_evidence_signal(
    *,
    query: str,
    text: str,
) -> tuple[float, float, str]:
    if not requests_conversation_topic(query):
        return 0.0, 0.0, ""
    if _CONVERSATION_TOPIC_NEGATIVE_TEXT_RE.search(text):
        return 0.0, 0.07, "conversation_topic_negative_evidence"
    if _CONVERSATION_TOPIC_EXACT_TEXT_RE.search(text):
        return 0.032, 0.0, "conversation_topic_exact_evidence"
    if _CONVERSATION_COUNTERPARTY_EXACT_TEXT_RE.search(text):
        return 0.0, 0.028, "conversation_topic_missing_topic_evidence"
    return 0.0, 0.0, ""


def conversation_recency_evidence_signal(
    *,
    query: str,
    text: str,
) -> tuple[float, float, str]:
    if not _CONVERSATION_RECENCY_QUERY_RE.search(query):
        return 0.0, 0.0, ""
    if _CONVERSATION_NEGATIVE_TEXT_RE.search(text):
        return 0.0, 0.07, "conversation_recency_negative_evidence"
    if _CONVERSATION_EVENT_TEXT_RE.search(text):
        if _CONVERSATION_RECENCY_TEXT_RE.search(text):
            return 0.034, 0.0, "conversation_recency_temporal_evidence"
        return 0.022, 0.0, "conversation_recency_event_evidence"
    return 0.0, 0.024, "conversation_recency_missing_event_evidence"


def conversation_recency_temporal_hint_signal(
    *,
    query: str,
    temporal_hint_code: str,
) -> tuple[float, str]:
    if not temporal_hint_code or not _CONVERSATION_RECENCY_QUERY_RE.search(query):
        return 0.0, ""
    if temporal_hint_code in _CONVERSATION_RECENT_TEMPORAL_HINTS:
        return 0.018, "conversation_recency_temporal_hint_evidence"
    if _is_non_future_temporal_hint(temporal_hint_code):
        return 0.01, "conversation_recency_dated_temporal_hint_evidence"
    return 0.0, ""


def conversation_recency_missing_temporal_signal(
    *,
    query: str,
    text: str,
    temporal_hint_code: str,
) -> tuple[float, str]:
    if (
        temporal_hint_code
        or not _CONVERSATION_RECENCY_QUERY_RE.search(query)
        or not _CONVERSATION_EVENT_TEXT_RE.search(text)
        or _CONVERSATION_RECENCY_TEXT_RE.search(text)
    ):
        return 0.0, ""
    return 0.022, "conversation_recency_missing_temporal_evidence"


def _is_non_future_temporal_hint(code: str) -> bool:
    if code in _CONVERSATION_FUTURE_TEMPORAL_HINTS:
        return False
    return not code.startswith(_CONVERSATION_FUTURE_TEMPORAL_HINT_PREFIXES)
