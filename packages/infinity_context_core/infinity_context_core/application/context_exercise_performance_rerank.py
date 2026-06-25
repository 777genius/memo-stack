"""Exercise performance transfer rerank signals."""

from __future__ import annotations

import re

from infinity_context_core.application.context_domain_rerank_signals import (
    DomainRerankSignal,
)
from infinity_context_core.application.context_relevance import QueryRelevance
from infinity_context_core.application.dto import ContextItem

_EXERCISE_PERFORMANCE_QUERY_RE = re.compile(
    r"\bexercises?\b(?=.{0,120}\b(?:help|improve|performance|basketball|"
    r"athletic|game|court)\b)|"
    r"\b(?:help|improve|performance|basketball|athletic|game|court)\b"
    r"(?=.{0,120}\bexercises?\b)",
    re.IGNORECASE | re.DOTALL,
)
_EXERCISE_ACTIVITY_RE = re.compile(
    r"\b(?:yoga|boxing|sprinting|running|run|workout|workouts?|exercise|"
    r"exercises?|fitness|kickboxing|taekwondo|tae\s+kwon\s+do|karate|"
    r"strength\s+training|weight\s+training|weights?|circuit\s+training)\b",
    re.IGNORECASE,
)
_PERFORMANCE_TRANSFER_RE = re.compile(
    r"\b(?:strength|flexibility|agility|speed|shooting|accuracy|stamina|"
    r"endurance|balance|coordination|upper\s+hand|up\s+my\s+game|confidence|"
    r"performance)\b",
    re.IGNORECASE,
)
_SOCIAL_STRENGTH_NOISE_RE = re.compile(
    r"\b(?:friends?|family|parents?|mentors?|support\s+system|people\s+around)\b"
    r".{0,100}\b(?:support|strength|motivat(?:e|es|ed|ing)|there\s+for)\b|"
    r"\b(?:support|strength|motivat(?:e|es|ed|ing)|there\s+for)\b"
    r".{0,100}\b(?:friends?|family|parents?|mentors?|support\s+system|people\s+around)\b",
    re.IGNORECASE | re.DOTALL,
)


def exercise_performance_rerank_signal(
    *,
    query: str,
    query_reason: str,
    item: ContextItem,
    relevance: QueryRelevance,
) -> DomainRerankSignal:
    """Prefer activities that explain athletic performance transfer."""

    if query_reason != "exercise_activity_inventory_bridge":
        return DomainRerankSignal()
    if not _EXERCISE_PERFORMANCE_QUERY_RE.search(query):
        return DomainRerankSignal()
    text = item.text
    has_activity = _EXERCISE_ACTIVITY_RE.search(text) is not None
    has_transfer = _PERFORMANCE_TRANSFER_RE.search(text) is not None
    if has_activity and has_transfer:
        return DomainRerankSignal(
            boost=0.058,
            reason="exercise_performance_transfer_evidence",
            rank_signal_key="exercise_performance_transfer_evidence",
            rank_signal=max(3.0, float(relevance.distinctive_term_hits)),
        )
    if _SOCIAL_STRENGTH_NOISE_RE.search(text) and not has_activity:
        return DomainRerankSignal(
            penalty=0.075,
            reason="exercise_performance_social_strength_noise",
            rank_signal_key="exercise_performance_social_strength_noise",
            rank_signal=1.0,
        )
    return DomainRerankSignal()
