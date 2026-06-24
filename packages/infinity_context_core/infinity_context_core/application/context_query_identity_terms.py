"""Identity term helpers for deterministic query expansion."""

from __future__ import annotations

import re
from collections.abc import Iterable

from infinity_context_core.application.context_query_personal_fact_expansions import (
    PERSONAL_FACT_QUESTION_STOPWORDS,
)

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_CAPITALIZED_IDENTITY_STOPWORDS = frozenset(
    {
        "Are",
        "Can",
        "Could",
        "Did",
        "Does",
        "How",
        "Is",
        "May",
        "Might",
        "Should",
        "The",
        "Was",
        "Were",
        "What",
        "When",
        "Where",
        "Which",
        "Who",
        "Whom",
        "Why",
        "Will",
        "Would",
        "Где",
        "Зачем",
        "Как",
        "Какая",
        "Какие",
        "Какой",
        "Когда",
        "Кто",
        "Почему",
        "Что",
        *PERSONAL_FACT_QUESTION_STOPWORDS,
    }
)


def raw_query_tokens(query: str) -> Iterable[str]:
    for match in _TOKEN_RE.finditer(query):
        token = match.group(0).casefold().strip("_")
        if len(token) >= 2:
            yield token


def capitalized_identity_terms(query: str) -> tuple[str, ...]:
    terms: list[str] = []
    seen: set[str] = set()
    for match in _TOKEN_RE.finditer(query):
        token = match.group(0).strip("_")
        if len(token) < 2 or token in _CAPITALIZED_IDENTITY_STOPWORDS:
            continue
        if not token[:1].isupper():
            continue
        normalized = token.casefold()
        if normalized in seen:
            continue
        terms.append(token)
        seen.add(normalized)
        if len(terms) >= 3:
            break
    return tuple(terms)


def with_identity_terms(identity_terms: tuple[str, ...], expansion: str) -> str:
    if not identity_terms:
        return expansion
    return " ".join((*identity_terms, expansion))
