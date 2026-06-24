"""State residence inference evidence signals."""

from __future__ import annotations

import re

from infinity_context_core.application.context_answer_evidence_types import (
    AnswerEvidenceSignal,
)
from infinity_context_core.application.context_lexical import query_terms

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

_STATE_RESIDENCE_QUERY_TERMS = frozenset(
    {
        "live",
        "lives",
        "living",
        "reside",
        "residence",
        "state",
    }
)
_STATE_RESIDENCE_GEO_TEXT_TERMS = frozenset(
    {
        "caption",
        "city",
        "county",
        "forest",
        "hiking",
        "image",
        "lake",
        "map",
        "minnesota",
        "national",
        "park",
        "photo",
        "route",
        "state",
        "trail",
        "trails",
        "trees",
        "voyageurs",
    }
)
_STATE_RESIDENCE_STRONG_GEO_TERMS = frozenset(
    {
        "forest",
        "hiking",
        "lake",
        "map",
        "national",
        "park",
        "route",
        "state",
        "trail",
        "trails",
        "trees",
        "voyageurs",
    }
)
_STATE_RESIDENCE_LOCATION_TERMS = frozenset(
    {
        "city",
        "county",
        "minnesota",
        "state",
        "voyageurs",
    }
)
_STATE_RESIDENCE_TECHNICAL_NOISE_RE = re.compile(
    r"\b(?:state\s+machine|state\s+management|app\s+state|"
    r"frontend|backend|database|code|repository|repo|workflow|config)\b|"
    r"\b(?:map|mapping)\b.{0,80}\b(?:code|app|schema|database|object)\b",
    re.IGNORECASE | re.DOTALL,
)


def state_residence_inference_signal(*, query: str, text: str) -> AnswerEvidenceSignal:
    """Return evidence-fit signal for inferred US state residence questions."""

    if not _requests_state_residence_inference(query):
        return AnswerEvidenceSignal()
    text_tokens = _term_set(text)
    strong_geo_hits = text_tokens & _STATE_RESIDENCE_STRONG_GEO_TERMS
    location_hits = text_tokens & _STATE_RESIDENCE_LOCATION_TERMS
    if _STATE_RESIDENCE_TECHNICAL_NOISE_RE.search(text) and len(strong_geo_hits) < 3:
        return AnswerEvidenceSignal(
            penalty=0.034,
            reason="inference_state_residence_technical_noise",
        )
    if len(strong_geo_hits) >= 3 and (
        location_hits or {"map", "trail"} <= text_tokens or {"map", "trails"} <= text_tokens
    ):
        return AnswerEvidenceSignal(
            boost=0.03,
            reason="inference_state_residence_geo_evidence",
        )
    if text_tokens & _STATE_RESIDENCE_GEO_TEXT_TERMS and len(strong_geo_hits) <= 1:
        return AnswerEvidenceSignal(
            penalty=0.026,
            reason="inference_state_residence_topic_only_noise",
        )
    return AnswerEvidenceSignal()


def _requests_state_residence_inference(query: str) -> bool:
    query_tokens = _term_set(query)
    return "state" in query_tokens and bool(
        query_tokens & _STATE_RESIDENCE_QUERY_TERMS
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
