"""Cause-awareness rerank signals for event and campaign memory queries."""

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

_REASON = "cause_awareness_event_bridge"
_QUERY_RE = re.compile(
    r"\b(?:raise|raised|raising|spread|spreading|awareness|aware)\b"
    r"(?=.{0,120}\b(?:for|about|cause|issue|event|race|campaign|fundraiser|charity)\b)|"
    r"\b(?:what|which)\b(?=.{0,80}\b(?:cause|issue)\b)"
    r"(?=.{0,120}\b(?:race|event|campaign|fundraiser|charity|awareness)\b)",
    re.IGNORECASE | re.DOTALL,
)
_EVENT_EVIDENCE_RE = re.compile(
    r"\b(?:charity\s+(?:race|run|walk|event)|fundraiser|fundraising|campaign|"
    r"race|run|walk|event|drive|conference|workshop|talk|speech|parade|march)\b",
    re.IGNORECASE,
)
_CHARITY_RACE_QUERY_RE = re.compile(
    r"\bcharity\b(?=.{0,40}\b(?:race|run|walk|event)\b)|"
    r"\b(?:race|run|walk|event)\b(?=.{0,40}\bcharity\b)",
    re.IGNORECASE | re.DOTALL,
)
_CHARITY_RACE_EVIDENCE_RE = re.compile(
    r"\bcharity\b(?=.{0,60}\b(?:race|run|walk|event)\b)|"
    r"\b(?:race|run|walk|event)\b(?=.{0,60}\bcharity\b)",
    re.IGNORECASE | re.DOTALL,
)
_AWARENESS_EVIDENCE_RE = re.compile(
    r"\b(?:raise|raised|raising|spread|spreading|awareness|"
    r"bring(?:ing)?\s+attention|start(?:ing)?\s+conversations?|make\s+a\s+difference)\b",
    re.IGNORECASE,
)
_CAUSE_EVIDENCE_RE = re.compile(
    r"\b(?:mental\s+health|domestic\s+abuse|animal\s+welfare|veterans?|"
    r"education|infrastructure|lgbtq\+?|trans\s+rights?|gender\s+identity|"
    r"inclusion|public\s+health|health|rights?|victims?|cause|issue)\b",
    re.IGNORECASE,
)
_TECHNICAL_OR_PROMOTION_NOISE_RE = re.compile(
    r"\b(?:api|backend|brand\s+awareness|dashboard|frontend|marketing\s+strategy|"
    r"product|provider|sdk|seo|software|target\s+audience|technical|web)\b",
    re.IGNORECASE,
)


def awareness_cause_rerank_signal(
    *,
    query: str,
    query_reason: str,
    item: ContextItem,
    relevance: QueryRelevance,
) -> DomainRerankSignal:
    """Prefer evidence that binds an event to the issue it raised awareness for."""

    if not _is_candidate(query=query, query_reason=query_reason, item=item):
        return DomainRerankSignal()
    text = item.text
    if _exact_cause_awareness_evidence(query=query, text=text):
        return DomainRerankSignal(
            boost=0.034,
            reason="cause_awareness_exact_evidence",
            rank_signal_key="cause_awareness_answer_evidence",
            rank_signal=3.0,
        )
    if _TECHNICAL_OR_PROMOTION_NOISE_RE.search(text) is not None:
        return DomainRerankSignal(
            penalty=0.058,
            reason="cause_awareness_promotion_noise",
        )
    if relevance.distinctive_term_hits < 3:
        return DomainRerankSignal(
            penalty=0.034,
            reason="cause_awareness_weak_evidence",
        )
    return DomainRerankSignal()


def _is_candidate(*, query: str, query_reason: str, item: ContextItem) -> bool:
    if query_reason == _REASON:
        return True
    diagnostics = safe_diagnostic_mapping(item.diagnostics)
    signals = safe_score_signals(diagnostics.get("score_signals"))
    if signals.get("query_expansion_reason") == _REASON:
        return True
    return _QUERY_RE.search(query) is not None


def _exact_cause_awareness_evidence(*, query: str, text: str) -> bool:
    if (
        _CHARITY_RACE_QUERY_RE.search(query) is not None
        and _CHARITY_RACE_EVIDENCE_RE.search(text) is None
    ):
        return False
    has_event = _EVENT_EVIDENCE_RE.search(text) is not None
    has_awareness = _AWARENESS_EVIDENCE_RE.search(text) is not None
    has_cause = _CAUSE_EVIDENCE_RE.search(text) is not None
    return has_cause and has_awareness and has_event
