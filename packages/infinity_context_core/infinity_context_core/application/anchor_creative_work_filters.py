"""False-positive guards for creative-work titles in person anchor extraction."""

from __future__ import annotations

import re

_CREATIVE_WORK_TITLE_REMAINDER_AUTHOR_SUFFIX_PATTERN = re.compile(
    r"^(?:\s+[A-Z][a-z][A-Za-z]{1,40}){0,5}[\"']?\s+by\s+"
    r"[A-Z][a-z][A-Za-z]{1,40}(?:\s+[A-Z][a-z][A-Za-z]{1,40}){0,4}\b"
)
_CREATIVE_WORK_ACTION_PREFIX_PATTERN = re.compile(
    r"\b(?:enjoy(?:ed|ing|s)?|lik(?:e|ed|es|ing)|listen(?:ed|ing)?|"
    r"recommend(?:ed|ing|s)?|read|reading|suggest(?:ed|ing|s)?)\s+$",
    re.IGNORECASE,
)
_CREATIVE_WORK_NOUN_PREFIX_PATTERN = re.compile(
    r"\b(?:article|book|film|memoir|movie|novel|poem|song|story|track)\s+[\"']?$",
    re.IGNORECASE,
)
_CREATIVE_WORK_VIEW_ACTION_PREFIX_PATTERN = re.compile(
    r"\b(?:saw|watch(?:ed|es|ing)?)\s+$",
    re.IGNORECASE,
)
_CREATIVE_WORK_ARTICLED_TITLE_PATTERN = re.compile(
    r"^(?:A|An|The)\s+[A-Z][a-z][A-Za-z]{1,40}"
    r"(?:\s+[A-Z][a-z][A-Za-z]{1,40}){0,4}$"
)
_CREATIVE_WORK_VIEW_TITLE_SUFFIX_PATTERN = re.compile(
    r"^(?:[\"']?\s+(?:with|for)\s+[A-Z][a-z][A-Za-z]{1,40}\b|[\"']?[.!?]?$)"
)
_CREATIVE_WORK_TITLE_PREFIX_PATTERN = re.compile(
    r"\b(?:enjoy(?:ed|ing|s)?|lik(?:e|ed|es|ing)|listen(?:ed|ing)?|"
    r"recommend(?:ed|ing|s)?|read|reading|suggest(?:ed|ing|s)?)\s+"
    r"(?:[A-Z][a-z][A-Za-z]{1,40}\s*){1,5}$"
)
_CREATIVE_WORK_CONTEXT_TITLE_PREFIX_PATTERN = re.compile(
    r"\b(?i:article|book|film|memoir|movie|novel|poem|song|story|track)\s+[\"']?"
    r"(?:(?i:the)\s+)?(?:[A-Z][a-z][A-Za-z]{1,40}\s*){1,6}[\"']?$",
)
_CREATIVE_WORK_TITLED_PREFIX_PATTERN = re.compile(
    r"\b(?:book|novel|memoir|story|article|poem|song|album|movie|film)\s+"
    r"(?:called|titled|named)\s+"
    r"(?:[A-Z][a-z][A-Za-z]{1,40}\s*){1,5}$",
    re.IGNORECASE,
)
_CREATIVE_WORK_AUTHOR_FRAGMENT_PATTERN = re.compile(r"\bby\s+(?:[A-Z][a-z][A-Za-z]{1,40}\s+){0,4}$")
_MUSIC_CREATOR_SUFFIX_PATTERN = re.compile(
    r"^\s+(?:composition|compositions|concerto|concertos|music|piece|pieces|"
    r"sonata|sonatas|symphonies|symphony)\b",
    re.IGNORECASE,
)
_MUSIC_CONTEXT_PATTERN = re.compile(
    r"\b(?:classical|composer|concert|enjoy(?:ed|ing|s)?|fan|lik(?:e|ed|es|ing)|"
    r"listen(?:ed|ing)?|music|song|track)\b",
    re.IGNORECASE,
)
_BOOK_AUTHOR_TITLE_PREFIX_PATTERN = re.compile(r"\bDr\.\s*$")
_BOOK_AUTHOR_CONTEXT_SUFFIX_PATTERN = re.compile(
    r"^\s+(?:book|books|bookshelf|classic|classics|stories|story)\b",
    re.IGNORECASE,
)


def is_creative_work_person_false_positive(text: str, start: int, end: int) -> bool:
    return (
        _is_creative_work_title_person_false_positive(
            text,
            start,
            end,
        )
        or _is_creative_work_author_person_false_positive(
            text,
            start,
        )
        or _is_viewed_creative_work_title_person_false_positive(
            text,
            start,
            end,
        )
        or _is_titled_book_author_person_false_positive(text, start, end)
        or _is_music_creator_person_false_positive(text, start, end)
    )


def _is_creative_work_title_person_false_positive(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 96) : start]
    suffix = text[end : end + 96]
    return bool(
        (
            _CREATIVE_WORK_ACTION_PREFIX_PATTERN.search(prefix)
            or _CREATIVE_WORK_NOUN_PREFIX_PATTERN.search(prefix)
            or _CREATIVE_WORK_TITLE_PREFIX_PATTERN.search(prefix)
            or _CREATIVE_WORK_CONTEXT_TITLE_PREFIX_PATTERN.search(prefix)
        )
        and _CREATIVE_WORK_TITLE_REMAINDER_AUTHOR_SUFFIX_PATTERN.match(suffix)
    )


def _is_creative_work_author_person_false_positive(text: str, start: int) -> bool:
    prefix = text[max(0, start - 160) : start]
    if not _CREATIVE_WORK_AUTHOR_FRAGMENT_PATTERN.search(prefix):
        return False

    by_match = re.search(
        r"\bby\s+(?:[A-Z][a-z][A-Za-z]{1,40}\s+){0,4}$",
        prefix,
    )
    if not by_match:
        return False

    before_by = prefix[: by_match.start()].rstrip()
    return bool(
        _CREATIVE_WORK_TITLE_PREFIX_PATTERN.search(before_by)
        or _CREATIVE_WORK_CONTEXT_TITLE_PREFIX_PATTERN.search(before_by)
        or _CREATIVE_WORK_TITLED_PREFIX_PATTERN.search(before_by)
    )


def _is_music_creator_person_false_positive(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 96) : start]
    suffix = text[end : end + 48]
    return bool(
        _MUSIC_CONTEXT_PATTERN.search(prefix) and _MUSIC_CREATOR_SUFFIX_PATTERN.match(suffix)
    )


def _is_titled_book_author_person_false_positive(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 16) : start]
    suffix = text[end : end + 48]
    return bool(
        _BOOK_AUTHOR_TITLE_PREFIX_PATTERN.search(prefix)
        and _BOOK_AUTHOR_CONTEXT_SUFFIX_PATTERN.match(suffix)
    )


def _is_viewed_creative_work_title_person_false_positive(
    text: str,
    start: int,
    end: int,
) -> bool:
    label = text[start:end].strip()
    prefix = text[max(0, start - 48) : start]
    suffix = text[end : end + 48]
    return bool(
        _CREATIVE_WORK_ARTICLED_TITLE_PATTERN.match(label)
        and _CREATIVE_WORK_VIEW_ACTION_PREFIX_PATTERN.search(prefix)
        and _CREATIVE_WORK_VIEW_TITLE_SUFFIX_PATTERN.match(suffix)
    )
