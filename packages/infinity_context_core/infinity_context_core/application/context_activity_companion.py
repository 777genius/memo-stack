"""Activity companion evidence signals for deterministic memory reranking."""

from __future__ import annotations

import re

from infinity_context_core.application.context_query_intent import QueryAnchorIntent
from infinity_context_core.application.dto import ContextItem
from infinity_context_core.domain.entities import MemoryAnchorKind

_SPEAKER_LABEL_RE = r"[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё._-]{1,39}"
_DIALOGUE_SPEAKER_RE = re.compile(
    rf"(?:^|\bD\d+:\d+\s+)(?P<speaker>{_SPEAKER_LABEL_RE})\s*:",
    re.IGNORECASE | re.MULTILINE,
)
_ACTIVITY_COMPANION_QUERY_RE = re.compile(
    r"\bwho\b(?=.{0,140}\b(?:with|alongside|together)\b)"
    r"(?=.{0,180}\b(?:go|went|attend(?:ed|ing)?|join(?:ed|ing)?|"
    r"camp(?:ed|ing)?|hik(?:e|ed|ing)|travel(?:ed|led|ing)?|trip|visit(?:ed|ing)?)\b)|"
    r"\bс\s+кем\b(?=.{0,180}\b(?:ходил|ходила|ездил|ездила|пошел|пошла|"
    r"ходили|ездили|поехал|поехала|кемпинг|поход|встреч\w+|конференц\w+)\b)",
    re.IGNORECASE | re.DOTALL,
)
_ACTIVITY_COMPANION_TEXT_RE = re.compile(
    r"\b(?:went|go|attended|joined|camp(?:ed|ing)?|hik(?:ed|ing)?|"
    r"travel(?:ed|led)?|visited|trip|conference|parade|event)\b",
    re.IGNORECASE,
)
_COMPANION_WITH_TEXT_RE = re.compile(
    r"\b(?:with|alongside|together\s+with|joined\s+by|accompanied\s+by)\b"
    r".{0,90}\b(?:my|his|her|their|our)?\s*"
    r"(?:family|kids?|children|friends?|parents?|partner|spouse|team|group|"
    r"[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё._-]{1,39})\b|"
    r"\b(?:family|kids?|children|friends?|parents?|partner|team|group)\b"
    r".{0,90}\b(?:came|joined|went|attended|camp(?:ed|ing)?|hik(?:ed|ing)?)\b|"
    r"\b(?:с|вместе\s+с|рядом\s+с)\b.{0,90}\b"
    r"(?:семь[её]й|детьми|друзьями|родителями|партнер\w+|командой|группой|"
    r"[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё._-]{1,39})\b",
    re.IGNORECASE | re.DOTALL,
)
_COMPANION_NEGATIVE_TEXT_RE = re.compile(
    r"\b(?:alone|solo|by\s+myself|by\s+herself|by\s+himself|by\s+themselves|"
    r"without\s+(?:anyone|anybody|friends?|family|kids?|children|parents?|"
    r"my\s+family|his\s+family|her\s+family|their\s+family|our\s+family))\b|"
    r"\b(?:один|одна|сам|сама|без\s+(?:кого-либо|друзей|семьи|детей|родителей))\b",
    re.IGNORECASE,
)


def activity_companion_signal(
    *,
    query: str,
    item: ContextItem,
    query_anchor_intent: QueryAnchorIntent,
) -> tuple[float, float, str]:
    """Return bounded companion evidence signal for "who went with X" queries."""

    if not _ACTIVITY_COMPANION_QUERY_RE.search(query):
        return 0.0, 0.0, ""
    if not _ACTIVITY_COMPANION_TEXT_RE.search(item.text):
        return 0.0, 0.0, ""
    owner_labels = _query_person_labels(query_anchor_intent)
    if owner_labels and not _activity_companion_owner_matches(
        text=item.text,
        owner_labels=owner_labels,
    ):
        return 0.0, 0.0, ""
    if _COMPANION_NEGATIVE_TEXT_RE.search(item.text):
        return 0.0, 0.062, "activity_companion_negated_evidence"
    if _COMPANION_WITH_TEXT_RE.search(item.text):
        return 0.026, 0.0, "activity_companion_positive_match"
    return 0.0, 0.018, "activity_companion_missing_evidence"


def _activity_companion_owner_matches(
    *,
    text: str,
    owner_labels: frozenset[str],
) -> bool:
    speakers = _dialogue_speaker_labels(text)
    if speakers.intersection(owner_labels):
        return True
    normalized_text = _normalized_dialogue_label(text)
    return any(label and label in normalized_text for label in owner_labels)


def _query_person_labels(query_anchor_intent: QueryAnchorIntent) -> frozenset[str]:
    labels: set[str] = set()
    for hint in query_anchor_intent.hints:
        if hint.kind != MemoryAnchorKind.PERSON:
            continue
        label = _normalized_dialogue_label(hint.label)
        if label:
            labels.add(label)
        canonical = _normalized_dialogue_label(hint.canonical_key)
        if canonical:
            labels.add(canonical)
    return frozenset(labels)


def _dialogue_speaker_labels(text: str) -> frozenset[str]:
    return frozenset(
        label
        for label in (
            _normalized_dialogue_label(match.group("speaker"))
            for match in _DIALOGUE_SPEAKER_RE.finditer(text)
        )
        if label
    )


def _normalized_dialogue_label(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())
