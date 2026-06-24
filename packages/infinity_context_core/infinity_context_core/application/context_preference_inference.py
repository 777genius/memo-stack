"""Preference inference evidence signals."""

from __future__ import annotations

import re

from infinity_context_core.application.context_answer_evidence_types import (
    AnswerEvidenceSignal,
)
from infinity_context_core.application.context_lexical import query_terms

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

_INFERENCE_QUERY_TERMS = frozenset(
    {
        "could",
        "infer",
        "inference",
        "likely",
        "may",
        "might",
        "probably",
        "should",
        "would",
        "вероятно",
        "может",
        "похоже",
    }
)
_PREFERENCE_QUERY_TERMS = frozenset(
    {
        "enjoy",
        "enjoying",
        "like",
        "likes",
        "love",
        "loves",
        "prefer",
        "prefers",
    }
)
_POSITIVE_PREFERENCE_TERMS = frozenset(
    {
        "enjoy",
        "enjoyed",
        "enjoys",
        "fan",
        "favorite",
        "favourite",
        "interested",
        "like",
        "liked",
        "likes",
        "love",
        "loved",
        "loves",
        "prefer",
        "preferred",
        "prefers",
    }
)
_NEGATIVE_PREFERENCE_TERMS = frozenset(
    {
        "avoid",
        "avoided",
        "avoids",
        "dislike",
        "disliked",
        "dislikes",
        "hate",
        "hated",
        "hates",
        "instead",
    }
)
_STRONG_NEGATIVE_PREFERENCE_TERMS = _NEGATIVE_PREFERENCE_TERMS - frozenset({"instead"})
_NEGATIVE_PREFERENCE_FIT_RE = re.compile(
    r"\b(?:doesn'?t|does\s+not|didn'?t|did\s+not|wouldn'?t|would\s+not|not)\s+"
    r"(?:like|enjoy|prefer|want|care\s+for)\b|"
    r"\b(?:no\s+interest\s+in|not\s+a\s+fan\s+of)\b",
    re.IGNORECASE,
)
_MUSIC_QUERY_TERMS = frozenset(
    {
        "bach",
        "classical",
        "four",
        "music",
        "seasons",
        "song",
        "vivaldi",
    }
)
_CLASSICAL_MUSIC_TEXT_TERMS = frozenset(
    {
        "bach",
        "classical",
        "mozart",
        "music",
        "orchestra",
        "symphony",
        "vivaldi",
    }
)


def preference_inference_signal(*, query: str, text: str) -> AnswerEvidenceSignal:
    """Return preference answer-evidence signal, if the query asks for it."""

    query_tokens = _term_set(query)
    if not query_tokens & _PREFERENCE_QUERY_TERMS:
        return AnswerEvidenceSignal()
    text_tokens = _term_set(text)
    if query_tokens & _MUSIC_QUERY_TERMS:
        return _classical_music_preference_signal(text=text, text_tokens=text_tokens)
    positive_hits = text_tokens & _POSITIVE_PREFERENCE_TERMS
    negative_hits = text_tokens & _NEGATIVE_PREFERENCE_TERMS
    if positive_hits and _has_preference_domain_overlap(query_tokens, text_tokens):
        return AnswerEvidenceSignal(
            boost=0.028,
            reason="inference_preference_fit_evidence",
        )
    if (
        negative_hits
        and _has_negative_preference_evidence(text=text, text_tokens=text_tokens)
        and _has_preference_domain_overlap(query_tokens, text_tokens)
    ):
        return AnswerEvidenceSignal(
            boost=0.026,
            reason="inference_negative_preference_fit_evidence",
        )
    if negative_hits and not positive_hits:
        return AnswerEvidenceSignal(
            penalty=0.038,
            reason="inference_negative_preference_noise",
        )
    return AnswerEvidenceSignal()


def _classical_music_preference_signal(
    *,
    text: str,
    text_tokens: frozenset[str],
) -> AnswerEvidenceSignal:
    positive_hits = text_tokens & _POSITIVE_PREFERENCE_TERMS
    negative_hits = text_tokens & _NEGATIVE_PREFERENCE_TERMS
    classical_hits = text_tokens & _CLASSICAL_MUSIC_TEXT_TERMS
    if positive_hits and classical_hits:
        return AnswerEvidenceSignal(
            boost=0.028,
            reason="inference_preference_fit_evidence",
        )
    if (
        negative_hits
        and classical_hits
        and not positive_hits
        and _has_negative_preference_evidence(text=text, text_tokens=text_tokens)
    ):
        return AnswerEvidenceSignal(
            boost=0.026,
            reason="inference_negative_preference_fit_evidence",
        )
    if negative_hits and not positive_hits:
        return AnswerEvidenceSignal(
            penalty=0.038,
            reason="inference_negative_preference_noise",
        )
    if classical_hits and not positive_hits:
        return AnswerEvidenceSignal(
            penalty=0.032,
            reason="inference_classical_music_topic_only_noise",
        )
    return AnswerEvidenceSignal()


def _has_preference_domain_overlap(
    query_tokens: frozenset[str],
    text_tokens: frozenset[str],
) -> bool:
    return bool((query_tokens - _INFERENCE_QUERY_TERMS - _PREFERENCE_QUERY_TERMS) & text_tokens)


def _has_negative_preference_evidence(
    *,
    text: str,
    text_tokens: frozenset[str],
) -> bool:
    return bool(
        text_tokens & _STRONG_NEGATIVE_PREFERENCE_TERMS
        or _NEGATIVE_PREFERENCE_FIT_RE.search(text)
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
