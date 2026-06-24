"""Support-role intent helpers for counterfactual memory retrieval."""

from __future__ import annotations

import re
from collections.abc import Iterable

from infinity_context_core.application.context_lexical import query_terms

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

_SUPPORT_ROLE_FIT_VARIANT = "support_role_fit"

_COUNTERFACTUAL_MODAL_TERMS = frozenset(
    {
        "can",
        "could",
        "likely",
        "might",
        "probably",
        "should",
        "would",
        "может",
        "мог",
        "могла",
        "подойдет",
        "смог",
        "смогла",
    }
)
_FIT_TERMS = frozenset(
    {
        "appropriate",
        "best",
        "candidate",
        "effective",
        "fit",
        "good",
        "right",
        "role",
        "suitable",
        "useful",
        "подойдет",
        "подходит",
    }
)
_ROLE_TERMS = frozenset(
    {
        "advisor",
        "advise",
        "caregiver",
        "caretaker",
        "coach",
        "counsel",
        "counseling",
        "counselor",
        "guide",
        "guidance",
        "mentor",
        "mentoring",
        "mentorship",
        "therapist",
        "therapy",
        "volunteer",
        "volunteering",
        "наставник",
        "наставником",
        "волонтер",
        "волонтером",
    }
)
_HELP_ACTION_TERMS = frozenset(
    {
        "confide",
        "confided",
        "confides",
        "confiding",
        "help",
        "helping",
        "open",
        "opened",
        "opening",
        "support",
        "supporting",
        "comfort",
        "comforting",
        "trust",
        "trusted",
        "trusting",
    }
)
_HELP_SCENARIO_TERMS = frozenset(
    {
        "anxiety",
        "community",
        "health",
        "issue",
        "issues",
        "kids",
        "mental",
        "personal",
        "private",
        "problem",
        "problems",
        "secret",
        "sensitive",
        "people",
        "shelter",
        "similar",
        "struggle",
        "struggles",
        "youth",
    }
)


def support_role_query_variants(query: str) -> frozenset[str]:
    """Return normalized support-role variants for expansion selection."""

    variants = _query_variant_set(query)
    raw_tokens = frozenset(_raw_query_tokens(query))
    if not requests_support_role_fit(raw_tokens=raw_tokens, variants=variants):
        return frozenset()
    return frozenset({_SUPPORT_ROLE_FIT_VARIANT})


def requests_support_role_fit(
    *,
    raw_tokens: frozenset[str],
    variants: frozenset[str],
) -> bool:
    """Detect questions asking whether someone fits a help/mentor/support role."""

    if "pursue" in raw_tokens and raw_tokens.intersection(
        {"career", "education", "field", "fields", "option", "path"}
    ):
        return False
    has_modal_or_fit = bool(
        raw_tokens.intersection(_COUNTERFACTUAL_MODAL_TERMS)
        or variants.intersection(_COUNTERFACTUAL_MODAL_TERMS)
        or raw_tokens.intersection(_FIT_TERMS)
        or variants.intersection(_FIT_TERMS)
    )
    if not has_modal_or_fit:
        return False
    if raw_tokens.intersection(_ROLE_TERMS):
        return True
    has_help_action = bool(raw_tokens.intersection(_HELP_ACTION_TERMS))
    has_support_scenario = bool(raw_tokens.intersection(_HELP_SCENARIO_TERMS))
    return has_help_action and has_support_scenario


def _query_variant_set(query: str) -> frozenset[str]:
    variants: set[str] = set()
    for term in query_terms(query, min_chars=2, max_terms=24):
        variants.update(term.variants)
    variants.update(_raw_query_tokens(query))
    return frozenset(variants)


def _raw_query_tokens(query: str) -> Iterable[str]:
    for match in _TOKEN_RE.finditer(query):
        token = match.group(0).casefold().strip("_")
        if len(token) >= 2:
            yield token
