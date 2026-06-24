"""Political leaning inference evidence signals."""

from __future__ import annotations

import re

from infinity_context_core.application.context_answer_evidence_types import (
    AnswerEvidenceSignal,
)
from infinity_context_core.application.context_lexical import query_terms

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

_POLITICAL_QUERY_TERMS = frozenset(
    {
        "leaning",
        "political",
        "politics",
    }
)
_POLITICAL_VALUES_TERMS = frozenset(
    {
        "acceptance",
        "accepting",
        "activism",
        "ally",
        "conservative",
        "conservatives",
        "equality",
        "inclusive",
        "inclusion",
        "lgbt",
        "lgbtq",
        "liberal",
        "progressive",
        "queer",
        "rights",
        "support",
        "supportive",
        "trans",
        "transgender",
        "transition",
        "unwelcoming",
    }
)
_POLITICAL_DIRECT_LEANING_TERMS = frozenset(
    {
        "conservative",
        "democrat",
        "democratic",
        "liberal",
        "progressive",
        "republican",
    }
)
_POLITICAL_TOPIC_TERMS = frozenset(
    {
        "campaign",
        "debate",
        "election",
        "news",
        "political",
        "politics",
    }
)
_POLITICAL_VALUES_PHRASE_RE = re.compile(
    r"\b(?:lgbtq?|trans(?:gender)?|transition|rights|equality|inclusion)\b"
    r".{0,100}\b(?:conservative|unwelcoming|support|supportive|acceptance|"
    r"progressive|liberal|rights)\b|"
    r"\b(?:conservative|unwelcoming|support|supportive|acceptance|progressive|"
    r"liberal|rights)\b.{0,100}\b(?:lgbtq?|trans(?:gender)?|transition|"
    r"rights|equality|inclusion)\b",
    re.IGNORECASE | re.DOTALL,
)


def political_inference_signal(*, query: str, text: str) -> AnswerEvidenceSignal:
    """Return evidence-fit signal for political leaning inference questions."""

    if not _requests_political_inference(query):
        return AnswerEvidenceSignal()
    text_tokens = _raw_term_set(text)
    values_hits = text_tokens & _POLITICAL_VALUES_TERMS
    direct_hits = text_tokens & _POLITICAL_DIRECT_LEANING_TERMS
    if _POLITICAL_VALUES_PHRASE_RE.search(text) and (
        len(values_hits) >= 2 or direct_hits
    ):
        return AnswerEvidenceSignal(
            boost=0.03,
            reason="inference_political_values_evidence",
        )
    if direct_hits and values_hits:
        return AnswerEvidenceSignal(
            boost=0.026,
            reason="inference_political_values_evidence",
        )
    if text_tokens & _POLITICAL_TOPIC_TERMS:
        return AnswerEvidenceSignal(
            penalty=0.032,
            reason="inference_political_topic_only_noise",
        )
    return AnswerEvidenceSignal()


def _requests_political_inference(query: str) -> bool:
    query_tokens = _term_set(query)
    return bool(query_tokens & _POLITICAL_QUERY_TERMS) and (
        "leaning" in query_tokens or "likely" in query_tokens or "would" in query_tokens
    )


def _term_set(text: str) -> frozenset[str]:
    terms: set[str] = set()
    for term in query_terms(text, min_chars=2, max_terms=40):
        terms.update(term.variants)
    for match in _TOKEN_RE.finditer(text):
        token = match.group(0).casefold().strip("_")
        if len(token) >= 2:
            terms.add(token)
    return frozenset(terms)


def _raw_term_set(text: str) -> frozenset[str]:
    return frozenset(
        match.group(0).casefold().strip("_")
        for match in _TOKEN_RE.finditer(text)
        if len(match.group(0).strip("_")) >= 2
    )
