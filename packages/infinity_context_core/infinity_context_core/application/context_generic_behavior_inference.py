"""Generic behavior evidence signals for inference reranking."""

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
_QUERY_STOP_TERMS = frozenset(
    {
        "about",
        "and",
        "are",
        "based",
        "be",
        "been",
        "being",
        "consider",
        "considered",
        "could",
        "does",
        "from",
        "have",
        "her",
        "him",
        "his",
        "likely",
        "might",
        "probably",
        "should",
        "the",
        "their",
        "them",
        "this",
        "what",
        "would",
    }
) | _INFERENCE_QUERY_TERMS
_IDENTITY_STOP_TERMS = frozenset(
    {
        "Could",
        "Does",
        "May",
        "Might",
        "Should",
        "What",
        "Would",
    }
)
_BEHAVIOR_EVIDENCE_TERMS = frozenset(
    {
        "always",
        "cared",
        "checked",
        "chose",
        "chosen",
        "completed",
        "comforted",
        "consistently",
        "decided",
        "encouraged",
        "enjoyed",
        "finished",
        "followed",
        "helped",
        "interested",
        "joined",
        "keeps",
        "kept",
        "listened",
        "often",
        "offered",
        "organized",
        "planned",
        "practiced",
        "prepared",
        "regularly",
        "repeatedly",
        "reassured",
        "reviewed",
        "showed",
        "shows",
        "started",
        "stayed",
        "supported",
        "tends",
        "trained",
        "tried",
        "usually",
        "verified",
        "volunteered",
        "wanted",
        "wants",
        "worked",
    }
)
_DIRECT_TRAIT_ASSERTION_RE = re.compile(
    r"\b("
    r"is|was|seems?|seemed|looks?|looked|sounds?|sounded|"
    r"became|becomes|known\s+as|considered|called|described\s+as|"
    r"very|really|quite|so"
    r")\b",
    re.IGNORECASE,
)
_RELIABILITY_TRAIT_QUERY_TERMS = frozenset(
    {"dependable", "reliable", "reliability", "responsible", "trustworthy"}
)
_RELIABILITY_TRAIT_TEXT_TERMS = frozenset(
    {
        "dependable",
        "followed",
        "kept",
        "promise",
        "promises",
        "reliable",
        "responsible",
        "through",
        "trustworthy",
    }
)
_RELIABILITY_DIRECT_TRAIT_TEXT_TERMS = frozenset(
    {
        "dependable",
        "reliability",
        "reliable",
        "responsibility",
        "responsible",
        "trustworthy",
    }
)
_ORGANIZED_TRAIT_QUERY_TERMS = frozenset({"organized", "organised", "planner"})
_ORGANIZED_TRAIT_TEXT_TERMS = frozenset(
    {"coordinated", "managed", "organized", "organised", "planned", "prepared", "scheduled"}
)
_CREATIVE_TRAIT_QUERY_TERMS = frozenset({"creative", "artistic", "imaginative"})
_CREATIVE_TRAIT_TEXT_TERMS = frozenset(
    {"art", "created", "designed", "drew", "made", "painted", "wrote"}
)
_HELPFUL_TRAIT_QUERY_TERMS = frozenset(
    {"caring", "considerate", "helpful", "patient", "supportive", "thoughtful"}
)
_HELPFUL_TRAIT_TEXT_TERMS = frozenset(
    {
        "cared",
        "caring",
        "comforted",
        "considerate",
        "encouraged",
        "helped",
        "helpful",
        "listened",
        "offered",
        "patient",
        "reassured",
        "supported",
        "supportive",
        "thoughtful",
    }
)
_DISCIPLINED_TRAIT_QUERY_TERMS = frozenset(
    {"dedicated", "disciplined", "hardworking", "persistent"}
)
_DISCIPLINED_TRAIT_TEXT_TERMS = frozenset(
    {
        "completed",
        "consistently",
        "dedicated",
        "disciplined",
        "finished",
        "focused",
        "hardworking",
        "persistent",
        "practiced",
        "prepared",
        "regularly",
        "trained",
        "worked",
    }
)
_CAREFUL_TRAIT_QUERY_TERMS = frozenset(
    {"careful", "cautious", "meticulous", "thorough"}
)
_CAREFUL_TRAIT_TEXT_TERMS = frozenset(
    {
        "careful",
        "carefully",
        "cautious",
        "checked",
        "detail",
        "meticulous",
        "prepared",
        "reviewed",
        "thorough",
        "verified",
    }
)


def generic_behavior_inference_signal(*, query: str, text: str) -> AnswerEvidenceSignal:
    query_tokens = _term_set(query)
    text_tokens = _term_set(text)
    behavior_hits = text_tokens & _BEHAVIOR_EVIDENCE_TERMS
    if not behavior_hits:
        if _direct_trait_evidence_matches(
            query=query,
            query_tokens=query_tokens,
            text=text,
            text_tokens=text_tokens,
        ):
            return AnswerEvidenceSignal(
                boost=0.04,
                reason="inference_behavior_evidence",
            )
        if _trait_direct_or_topic_matches(
            query_tokens=query_tokens,
            text_tokens=text_tokens,
        ):
            return AnswerEvidenceSignal(
                penalty=0.03,
                reason="inference_behavior_topic_only_noise",
            )
        return AnswerEvidenceSignal()
    if _trait_evidence_matches(query_tokens=query_tokens, text_tokens=text_tokens):
        return AnswerEvidenceSignal(
            boost=0.022,
            reason="inference_behavior_evidence",
        )
    salient_overlap = _salient_query_terms(query=query, query_tokens=query_tokens) & text_tokens
    if len(behavior_hits) >= 2 and salient_overlap:
        return AnswerEvidenceSignal(
            boost=0.018,
            reason="inference_behavior_evidence",
        )
    return AnswerEvidenceSignal()


def _trait_evidence_matches(
    *,
    query_tokens: frozenset[str],
    text_tokens: frozenset[str],
) -> bool:
    if query_tokens & _RELIABILITY_TRAIT_QUERY_TERMS:
        return len(text_tokens & _RELIABILITY_TRAIT_TEXT_TERMS) >= 2
    if query_tokens & _ORGANIZED_TRAIT_QUERY_TERMS:
        return bool(text_tokens & _ORGANIZED_TRAIT_TEXT_TERMS)
    if query_tokens & _CREATIVE_TRAIT_QUERY_TERMS:
        return bool(text_tokens & _CREATIVE_TRAIT_TEXT_TERMS)
    if query_tokens & _HELPFUL_TRAIT_QUERY_TERMS:
        return bool(text_tokens & _HELPFUL_TRAIT_TEXT_TERMS)
    if query_tokens & _DISCIPLINED_TRAIT_QUERY_TERMS:
        return bool(text_tokens & _DISCIPLINED_TRAIT_TEXT_TERMS)
    if query_tokens & _CAREFUL_TRAIT_QUERY_TERMS:
        return bool(text_tokens & _CAREFUL_TRAIT_TEXT_TERMS)
    return False


def _direct_trait_evidence_matches(
    *,
    query: str,
    query_tokens: frozenset[str],
    text: str,
    text_tokens: frozenset[str],
) -> bool:
    if not _trait_direct_or_topic_matches(
        query_tokens=query_tokens,
        text_tokens=text_tokens,
    ):
        return False
    identity_tokens = _capitalized_identity_terms(query)
    if identity_tokens and not identity_tokens & text_tokens:
        return False
    return _DIRECT_TRAIT_ASSERTION_RE.search(text) is not None


def _trait_direct_or_topic_matches(
    *,
    query_tokens: frozenset[str],
    text_tokens: frozenset[str],
) -> bool:
    if query_tokens & _RELIABILITY_TRAIT_QUERY_TERMS:
        return bool(text_tokens & _RELIABILITY_DIRECT_TRAIT_TEXT_TERMS)
    if query_tokens & _ORGANIZED_TRAIT_QUERY_TERMS:
        return bool(text_tokens & _ORGANIZED_TRAIT_TEXT_TERMS)
    if query_tokens & _CREATIVE_TRAIT_QUERY_TERMS:
        return bool(text_tokens & _CREATIVE_TRAIT_TEXT_TERMS)
    if query_tokens & _HELPFUL_TRAIT_QUERY_TERMS:
        return bool(text_tokens & _HELPFUL_TRAIT_TEXT_TERMS)
    if query_tokens & _DISCIPLINED_TRAIT_QUERY_TERMS:
        return bool(text_tokens & _DISCIPLINED_TRAIT_TEXT_TERMS)
    if query_tokens & _CAREFUL_TRAIT_QUERY_TERMS:
        return bool(text_tokens & _CAREFUL_TRAIT_TEXT_TERMS)
    return False


def _salient_query_terms(
    *,
    query: str,
    query_tokens: frozenset[str],
) -> frozenset[str]:
    identity_tokens = _capitalized_identity_terms(query)
    return frozenset(
        token
        for token in query_tokens
        if len(token) >= 4 and token not in _QUERY_STOP_TERMS and token not in identity_tokens
    )


def _capitalized_identity_terms(query: str) -> frozenset[str]:
    terms: set[str] = set()
    for match in re.finditer(r"\b[A-Z][A-Za-z._-]{1,39}\b", query):
        raw = match.group(0)
        if raw in _IDENTITY_STOP_TERMS:
            continue
        terms.add(raw.casefold())
        for term in query_terms(raw, min_chars=2, max_terms=4):
            terms.update(term.variants)
    return frozenset(terms)


def _term_set(text: str) -> frozenset[str]:
    terms: set[str] = set()
    for term in query_terms(text, min_chars=2, max_terms=40):
        terms.update(term.variants)
    for match in _TOKEN_RE.finditer(text):
        token = match.group(0).casefold().strip("_")
        if len(token) >= 2:
            terms.add(token)
    return frozenset(terms)
