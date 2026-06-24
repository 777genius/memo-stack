"""Possession provenance signals for deterministic memory reranking."""

from __future__ import annotations

import re
from dataclasses import dataclass

from infinity_context_core.application.dto import ContextItem

_LABEL_RE = r"[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё._-]{1,39}"
_SPEAKER_RE = re.compile(
    rf"(?:^|\bD\d+:\d+\s+)(?P<speaker>{_LABEL_RE})\s*:",
    re.IGNORECASE | re.MULTILINE,
)
_WHO_GAVE_OWNER_OBJECT_QUERY_RE = re.compile(
    rf"\bwho\s+(?:gave|gifted)\s+(?P<owner>{_LABEL_RE})\s+"
    r"(?P<object>.{0,90}?)(?:\?|$|\b(?:during|after|before|at|in|on)\b)",
    re.IGNORECASE | re.DOTALL,
)
_WHO_WAS_OWNER_OBJECT_FROM_QUERY_RE = re.compile(
    rf"\bwho\s+was\s+(?P<owner>{_LABEL_RE})(?:'s|s')?\s+"
    r"(?P<object>.{0,80}?)\s+from\b",
    re.IGNORECASE | re.DOTALL,
)
_WHERE_OWNER_OBJECT_FROM_QUERY_RE = re.compile(
    rf"\bwhere\s+did\s+(?P<owner>{_LABEL_RE})(?:'s|s')?\s+"
    r"(?P<object>.{0,80}?)\s+(?:come\s+from|originate)\b",
    re.IGNORECASE | re.DOTALL,
)
_WHERE_OWNER_GOT_OBJECT_FROM_QUERY_RE = re.compile(
    rf"\bwhere\s+did\s+(?P<owner>{_LABEL_RE})\s+"
    r"(?:get|receive)\s+(?P<object>.{0,90}?)\s+from\b",
    re.IGNORECASE | re.DOTALL,
)
_SOURCE_EVIDENCE_RE = re.compile(
    r"\b(?:gift|present|keepsake)\b.{0,40}\bfrom\b.{0,90}\b"
    r"(?:grandma|grandmother|grandpa|grandfather|mother|father|mom|dad|"
    r"parent|friend|mentor|family|relative|home\s+country|native\s+country|"
    rf"{_LABEL_RE})\b|"
    r"\b(?:got|received)\b.{0,120}\bfrom\b.{0,90}\b"
    r"(?:grandma|grandmother|grandpa|grandfather|mother|father|mom|dad|"
    r"parent|friend|mentor|family|relative|home\s+country|native\s+country|"
    rf"{_LABEL_RE})\b|"
    r"\b(?:given|gifted)\b.{0,80}\bby\b.{0,90}\b"
    r"(?:grandma|grandmother|grandpa|grandfather|mother|father|mom|dad|"
    r"parent|friend|mentor|family|relative|home\s+country|native\s+country|"
    rf"{_LABEL_RE})\b",
    re.IGNORECASE | re.DOTALL,
)
_OBJECT_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "come",
        "did",
        "from",
        "gave",
        "get",
        "gifted",
        "originate",
        "receive",
        "the",
        "this",
        "that",
        "where",
        "who",
    }
)


@dataclass(frozen=True)
class _PossessionSourceQuery:
    owner_label: str
    object_terms: tuple[str, ...]


def possession_source_signal(*, query: str, item: ContextItem) -> tuple[float, float, str]:
    """Return bounded evidence signal for "who/where was this object from" queries."""

    source_query = _possession_source_query(query)
    if source_query is None:
        return 0.0, 0.0, ""
    if not _object_terms_match(item.text, source_query.object_terms):
        return 0.0, 0.0, ""
    if not _owner_matches_item(item.text, source_query.owner_label):
        return 0.0, 0.0, ""
    if _SOURCE_EVIDENCE_RE.search(item.text):
        return 0.024, 0.0, "possession_source_evidence"
    return 0.0, 0.014, "possession_source_missing"


def _possession_source_query(query: str) -> _PossessionSourceQuery | None:
    for pattern in (
        _WHO_GAVE_OWNER_OBJECT_QUERY_RE,
        _WHO_WAS_OWNER_OBJECT_FROM_QUERY_RE,
        _WHERE_OWNER_OBJECT_FROM_QUERY_RE,
        _WHERE_OWNER_GOT_OBJECT_FROM_QUERY_RE,
    ):
        match = pattern.search(query)
        if match is None:
            continue
        owner = _clean_label(match.group("owner"))
        object_terms = _object_terms(match.group("object") or "")
        if owner and object_terms:
            return _PossessionSourceQuery(
                owner_label=owner,
                object_terms=object_terms,
            )
    return None


def _owner_matches_item(text: str, owner: str) -> bool:
    owner_key = _normalized_label(owner)
    speakers = {
        _normalized_label(match.group("speaker"))
        for match in _SPEAKER_RE.finditer(text)
        if match.group("speaker")
    }
    if owner_key in speakers:
        return True
    owner_pattern = _label_pattern(owner)
    return bool(
        re.search(
            rf"{owner_pattern}(?:'s|s')?\b|"
            rf"{owner_pattern}.{{0,80}}\b(?:got|received|kept|shared|showed)\b",
            text,
            re.IGNORECASE | re.DOTALL,
        )
    )


def _object_terms_match(text: str, object_terms: tuple[str, ...]) -> bool:
    normalized = text.casefold()
    hits = sum(1 for term in object_terms if term in normalized)
    required = min(len(object_terms), 2)
    return hits >= required


def _object_terms(value: str) -> tuple[str, ...]:
    terms: list[str] = []
    for match in re.finditer(r"[A-Za-zА-Яа-яЁё0-9]{3,}", value.casefold()):
        token = match.group(0)
        if token in _OBJECT_STOP_WORDS:
            continue
        if token not in terms:
            terms.append(token)
        if len(terms) >= 5:
            break
    return tuple(terms)


def _clean_label(value: str) -> str:
    return (value or "").strip(" :,.!?;")


def _label_pattern(label: str) -> str:
    return rf"(?<!\w){re.escape(label)}(?!\w)"


def _normalized_label(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())
