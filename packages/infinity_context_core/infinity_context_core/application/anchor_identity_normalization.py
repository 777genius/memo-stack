"""Canonical key normalization helpers for memory anchors."""

from __future__ import annotations

import re

_CYRILLIC_TO_LATIN = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "i",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
)
_CYRILLIC_PERSON_CASE_OVERRIDES = {
    "алекса": "алекс",
    "атласе": "атлас",
}
_CYRILLIC_PROJECT_CASE_OVERRIDES = {
    "атласе": "атлас",
}


def canonical_token(value: str) -> str:
    return value.translate(_CYRILLIC_TO_LATIN).replace("x", "ks")


def normalize_cyrillic_person_case(part: str) -> str:
    if not re.search(r"[а-яё]", part, re.IGNORECASE):
        return part
    if part in _CYRILLIC_PERSON_CASE_OVERRIDES:
        return _CYRILLIC_PERSON_CASE_OVERRIDES[part]
    if len(part) <= 4:
        return part
    if part.endswith("ией"):
        return f"{part[:-3]}ия"
    if part.endswith("ии"):
        return f"{part[:-2]}ия"
    if part.endswith("еем"):
        return f"{part[:-3]}ей"
    if part.endswith("ея"):
        return f"{part[:-2]}ей"
    if part.endswith("ием"):
        return f"{part[:-3]}ий"
    if part.endswith("ой"):
        return f"{part[:-2]}а"
    if part.endswith(("ом", "ем")):
        return part[:-2]
    return part


def normalize_cyrillic_project_case(part: str) -> str:
    if not re.search(r"[а-яё]", part, re.IGNORECASE):
        return part
    if part in _CYRILLIC_PROJECT_CASE_OVERRIDES:
        return _CYRILLIC_PROJECT_CASE_OVERRIDES[part]
    if len(part) >= 5 and part.endswith("е"):
        return part[:-1]
    return part
