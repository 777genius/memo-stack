"""Rule selection helpers for deterministic query expansion."""

from __future__ import annotations

import re

from infinity_context_core.application.context_lexical import query_terms
from infinity_context_core.application.context_query_identity_terms import (
    raw_query_tokens as _raw_query_tokens,
)
from infinity_context_core.application.context_temporal_query import build_temporal_query_intent

_NEGATIVE_EATING_QUERY_RE = re.compile(
    r"\b(?:can\W*t|cannot|can\s+not|unable\s+to)\b(?=.{0,80}\beat(?:s|ing)?\b)|"
    r"\beat(?:s|ing)?\b(?=.{0,80}\b(?:can\W*t|cannot|can\s+not|unable\s+to)\b)",
    re.IGNORECASE | re.DOTALL,
)
_WHO_ELSE_COMMONALITY_QUERY_RE = re.compile(
    r"\bwho\s+else\b(?=.{0,120}\b(?:like|likes|enjoy|enjoys|love|loves|"
    r"prefer|prefers|interest|hobby|activity|share|shares)\b)|"
    r"\bwho\s+shares?\b(?=.{0,120}\b(?:interest|hobby|activity|like|love|"
    r"preference)\b)|"
    r"\bкто\s+(?:ещ[её])\b(?=.{0,120}\b(?:любит|нравит|интерес|хобби|"
    r"увлечен|увлечён|предпочитает)\b)",
    re.IGNORECASE | re.DOTALL,
)
_SOCIAL_SUPPORT_NETWORK_QUERY_RE = re.compile(
    r"\bwho\b(?=.{0,90}\b(?:support|supports|supported|supporting|help|helps|"
    r"helped|comfort|encourage|encourages|there\s+for|rocks?|family|friends?|"
    r"mentors?)\b)|"
    r"\b(?:who\s+is|who\s+was|who\s+has\s+been)\b(?=.{0,90}\bthere\s+for\b)|"
    r"\bкто\b(?=.{0,90}\b(?:поддерживает|поддерживал|поддерживала|"
    r"поддержал|поддержала|поддержали|помогает|помогал|помогала|"
    r"помог|помогла|помогли|рядом|семья|друзья|наставники)\b)",
    re.IGNORECASE | re.DOTALL,
)
_TECHNICAL_SUPPORT_CONTEXT_TERMS = frozenset(
    {
        "api",
        "backend",
        "browser",
        "client",
        "cloud",
        "customer",
        "database",
        "frontend",
        "infra",
        "infrastructure",
        "integration",
        "library",
        "model",
        "platform",
        "provider",
        "runtime",
        "sdk",
        "service",
        "software",
        "technical",
        "tool",
        "tools",
        "web",
    }
)


def query_expansion_variant_set(query: str) -> frozenset[str]:
    variants: set[str] = set()
    for term in query_terms(query, min_chars=2, max_terms=24):
        variants.update(term.variants)
    variants.update(_raw_query_tokens(query))
    if _NEGATIVE_EATING_QUERY_RE.search(query):
        variants.update(("not", "cannot", "eat"))
    if any(token.startswith("познаком") for token in variants):
        variants.update(("познакомились", "meet", "met"))
    if any(token.startswith("встрет") for token in variants):
        variants.update(("встретились", "meet", "met"))
    return frozenset(variants)


def should_skip_expansion_rule(
    reason: str,
    *,
    query: str,
    raw_tokens: set[str],
) -> bool:
    if reason in {
        "current_recommendation_bridge",
        "current_state_temporal_bridge",
    } and _requests_stale_state_update(query=query, raw_tokens=raw_tokens):
        return True
    if reason == "career_intent_bridge" and "alternative" in raw_tokens:
        return True
    if reason == "career_intent_bridge" and {"future", "job"}.issubset(raw_tokens):
        return True
    if reason == "children_count_sibling_bridge" and not raw_tokens.intersection(
        {"child", "children", "kid", "kids", "sibling", "siblings", "brother", "sister"}
    ):
        return True
    if reason == "allergy_inventory_bridge" and raw_tokens.intersection(
        {"condition", "underlying"}
    ):
        return True
    if reason in {
        "friend_place_inventory_bridge",
        "friend_place_shelter_inventory_bridge",
        "friend_place_gym_inventory_bridge",
        "friend_place_church_inventory_bridge",
    }:
        return not (
            "where" in raw_tokens
            and raw_tokens.intersection({"friend", "friends"})
            and raw_tokens.intersection({"made", "met", "meet", "joined", "join"})
        )
    if reason == "travel_country_inventory_bridge":
        return not (
            raw_tokens.intersection({"country", "countries"})
            and raw_tokens.intersection(
                {
                    "been",
                    "travel",
                    "traveled",
                    "travelled",
                    "trip",
                    "visited",
                    "visit",
                    "went",
                }
            )
        )
    if reason in {
        "cause_education_infrastructure_inventory_bridge",
        "cause_veterans_inventory_bridge",
    }:
        return not (
            raw_tokens.intersection({"cause", "causes"})
            and raw_tokens.intersection(
                {"support", "supporting", "passionate", "interested", "interest"}
            )
        )
    if reason == "support_network_bridge":
        return (
            not _SOCIAL_SUPPORT_NETWORK_QUERY_RE.search(query)
            or bool(raw_tokens.intersection(_TECHNICAL_SUPPORT_CONTEXT_TERMS))
        )
    if reason == "relationship_origin_bridge":
        return not _requests_relationship_origin(raw_tokens)
    if reason == "after_event_temporal_bridge":
        return not build_temporal_query_intent(query).after_event
    if reason == "before_event_temporal_bridge":
        return not build_temporal_query_intent(query).before_event
    return reason == "camping_detail_bridge" and not any(
        token.startswith("camp") for token in raw_tokens
    )


def _requests_relationship_origin(raw_tokens: set[str]) -> bool:
    if raw_tokens.intersection(
        {
            "introduced",
            "introduce",
            "known",
            "meet",
            "met",
        }
    ):
        return True
    return any(
        token.startswith(("познаком", "встрет"))
        for token in raw_tokens
    )


def identity_terms_for_expansion(
    *,
    reason: str,
    query: str,
    identity_terms: tuple[str, ...],
) -> tuple[str, ...]:
    if reason == "commonality_interest_bridge" and _WHO_ELSE_COMMONALITY_QUERY_RE.search(query):
        return ()
    if reason == "travel_country_inventory_bridge":
        return tuple(
            term
            for term in identity_terms
            if term.casefold() not in {"europe", "european", "европа", "европейские"}
        )
    return identity_terms


def _requests_stale_state_update(*, query: str, raw_tokens: set[str]) -> bool:
    normalized = query.casefold()
    if any(
        phrase in normalized
        for phrase in (
            "not stale",
            "not outdated",
            "not obsolete",
            "not deprecated",
            "not expired",
        )
    ):
        return False
    return bool(
        "no longer" in normalized
        or "not current" in normalized
        or raw_tokens.intersection({"anymore", "stopped", "больше"})
        or {"longer", "use"}.issubset(raw_tokens)
        or {"больше", "использовать"}.issubset(raw_tokens)
    )
