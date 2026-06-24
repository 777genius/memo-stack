"""Frequency and recurrence rerank signals."""

from __future__ import annotations

import re

from infinity_context_core.application.context_diagnostics import (
    safe_diagnostic_mapping,
    safe_score_signals,
)
from infinity_context_core.application.context_domain_rerank_signals import (
    DomainRerankSignal,
)
from infinity_context_core.application.context_relevance import QueryRelevance
from infinity_context_core.application.dto import ContextItem

_FREQUENCY_REASON = "decomposition_frequency_recurrence"
_RECURRENCE_EXACT_RE = re.compile(
    r"\b(?:every\s+(?:day|night|morning|afternoon|evening|weekday|weekend|week|"
    r"month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"daily|weekly|monthly|yearly|annually|regularly|usually|often|"
    r"(?:once|twice|three|four|five|six|\d{1,2})\s+times?\s+(?:a|per)\s+"
    r"(?:day|week|month|year)|"
    r"(?:once|twice)\s+(?:a|per)\s+(?:day|week|month|year)|"
    r"couple\s+times?\s+(?:a|per)\s+(?:day|week|month|year)|"
    r"several\s+times?\s+(?:a|per)\s+(?:day|week|month|year))\b|"
    r"\b(?:кажд\w+\s+(?:день|недел\w*|месяц|год|утро|вечер|выходн\w*)|"
    r"ежедневно|еженедельно|ежемесячно|ежегодно|регулярно|обычно|часто|"
    r"(?:один|два|три|четыре|пять|шесть|\d{1,2})\s+раз(?:а)?\s+в\s+"
    r"(?:день|недел\w*|месяц|год))\b",
    re.IGNORECASE,
)
_ONE_TIME_EVENT_RE = re.compile(
    r"\b(?:once|one\s+time|one-time|single\s+time)\b(?!\s+(?:a|per)\b)|"
    r"\b(?:for\s+orientation|only\s+once|just\s+once|single\s+visit)\b|"
    r"\b(?:один\s+раз|только\s+раз|единожды)\b",
    re.IGNORECASE,
)
_GENERIC_TOPIC_RE = re.compile(
    r"\b(?:schedule|calendar|activity|event|meeting|volunteer|practice|training)\b"
    r"(?![^.]{0,80}\b(?:every|daily|weekly|monthly|regularly|usually|often|"
    r"times?\s+(?:a|per))\b)",
    re.IGNORECASE,
)


def frequency_recurrence_rerank_signal(
    *,
    query_reason: str,
    item: ContextItem,
    relevance: QueryRelevance,
) -> DomainRerankSignal:
    """Prefer evidence that answers recurrence, and demote one-off mentions."""

    if not _is_frequency_candidate(query_reason=query_reason, item=item):
        return DomainRerankSignal()
    if _RECURRENCE_EXACT_RE.search(item.text) is not None:
        return DomainRerankSignal(
            boost=0.03,
            reason="frequency_recurrence_exact_evidence",
        )
    if _ONE_TIME_EVENT_RE.search(item.text) is not None:
        return DomainRerankSignal(
            penalty=0.052,
            reason="frequency_recurrence_one_time_noise",
        )
    if _GENERIC_TOPIC_RE.search(item.text) is not None or relevance.distinctive_term_hits < 4:
        return DomainRerankSignal(
            penalty=0.036,
            reason="frequency_recurrence_weak_evidence",
        )
    return DomainRerankSignal()


def _is_frequency_candidate(*, query_reason: str, item: ContextItem) -> bool:
    if query_reason == _FREQUENCY_REASON:
        return True
    diagnostics = safe_diagnostic_mapping(item.diagnostics)
    signals = safe_score_signals(diagnostics.get("score_signals"))
    reason = signals.get("query_expansion_reason")
    return isinstance(reason, str) and reason == _FREQUENCY_REASON
