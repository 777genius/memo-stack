"""Allergy condition inference evidence signals."""

from __future__ import annotations

import re

from infinity_context_core.application.context_answer_evidence_types import (
    AnswerEvidenceSignal,
)
from infinity_context_core.application.context_lexical import query_terms

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

_ALLERGY_QUERY_TERMS = frozenset(
    {
        "allergic",
        "allergies",
        "allergy",
        "аллергией",
        "аллергии",
        "аллергия",
    }
)
_CONDITION_QUERY_TERMS = frozenset(
    {
        "condition",
        "health",
        "medical",
        "underlying",
        "заболевание",
        "состояние",
    }
)
_ALLERGY_EVIDENCE_TERMS = frozenset(
    {
        "allergic",
        "allergies",
        "allergy",
        "аллергией",
        "аллергии",
        "аллергия",
    }
)
_BROAD_ANIMAL_ALLERGY_TERMS = frozenset(
    {
        "animal",
        "animals",
        "cockroach",
        "cockroaches",
        "fur",
        "pet",
        "pets",
        "reptile",
        "reptiles",
        "шерсть",
        "животное",
        "животные",
        "питомец",
        "питомцы",
        "рептилия",
        "рептилии",
    }
)
_ALLERGY_SYMPTOM_TERMS = frozenset(
    {
        "itchy",
        "puffy",
        "rash",
        "swollen",
        "swelling",
        "зуд",
        "отек",
        "отекла",
        "отёк",
        "отёкла",
    }
)
_ALLERGY_MARKER_RE = re.compile(
    r"\b(?:allerg(?:y|ies|ic)|allergic\s+to)\b|"
    r"\b(?:face|eyes?|skin)\b.{0,60}\b(?:puffy|itchy|swollen|rash)\b|"
    r"\b(?:puffy|itchy|swollen|rash)\b.{0,60}\b(?:face|eyes?|skin)\b|"
    r"\b(?:аллерги\w*|зуд|от[её]к\w*)\b",
    re.IGNORECASE | re.DOTALL,
)
_ANIMAL_TOPIC_ONLY_RE = re.compile(
    r"\b(?:animals?|pets?|reptiles?|cockroaches?|fur)\b"
    r"(?=.{0,120}\b(?:cute|stuffed|photo|picture|toy|store|shelter|zoo|"
    r"reminder|drawing|game|story)\b)|"
    r"\b(?:cute|stuffed|photo|picture|toy|store|shelter|zoo|reminder|"
    r"drawing|game|story)\b"
    r"(?=.{0,120}\b(?:animals?|pets?|reptiles?|cockroaches?|fur)\b)",
    re.IGNORECASE | re.DOTALL,
)


def allergy_condition_inference_signal(
    *,
    query: str,
    text: str,
) -> AnswerEvidenceSignal:
    """Return evidence-fit signal for inferred allergy condition questions."""

    if not _requests_allergy_condition_inference(query):
        return AnswerEvidenceSignal()
    text_tokens = _term_set(text)
    has_allergy_marker = bool(
        text_tokens & _ALLERGY_EVIDENCE_TERMS or _ALLERGY_MARKER_RE.search(text)
    )
    animal_hits = text_tokens & _BROAD_ANIMAL_ALLERGY_TERMS
    symptom_hits = text_tokens & _ALLERGY_SYMPTOM_TERMS
    if has_allergy_marker and (len(animal_hits) >= 2 or (animal_hits and symptom_hits)):
        return AnswerEvidenceSignal(
            boost=0.034,
            reason="inference_allergy_condition_evidence",
        )
    if has_allergy_marker and symptom_hits:
        return AnswerEvidenceSignal(
            boost=0.024,
            reason="inference_allergy_symptom_evidence",
        )
    if (
        len(animal_hits) >= 2 or _ANIMAL_TOPIC_ONLY_RE.search(text)
    ) and not has_allergy_marker:
        return AnswerEvidenceSignal(
            penalty=0.04,
            reason="inference_allergy_condition_topic_only_noise",
        )
    return AnswerEvidenceSignal()


def _requests_allergy_condition_inference(query: str) -> bool:
    query_tokens = _term_set(query)
    return bool(query_tokens & _ALLERGY_QUERY_TERMS) and bool(
        query_tokens & _CONDITION_QUERY_TERMS
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
