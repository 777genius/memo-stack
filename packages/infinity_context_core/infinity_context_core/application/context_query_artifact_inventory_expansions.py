"""Artifact inventory query expansion rules."""

from __future__ import annotations

import re

_ENTITY_LABEL_RE = (
    r"[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё._-]{1,39}"
    r"(?:\s+[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё._-]{1,39}){0,4}"
)
_ARTIFACT_KIND_RE = (
    r"files?|documents?|docs?|screenshots?|images?|pictures?|photos?|"
    r"attachments?|assets?|artifacts?|uploads?|transcripts?"
)
_RU_ARTIFACT_KIND_RE = (
    r"файл(?:ы|ов|ам|ами|е)?|документ(?:ы|ов|ам|ами|е)?|"
    r"скриншот(?:ы|ов|ам|ами|е)?|скрин(?:ы|ов|ам|ами|е)?|"
    r"картинк(?:а|и|у|ой|е)?|изображени(?:е|я|й|ю|ем)?|"
    r"фото|вложени(?:е|я|й|ю|ем)?|артефакт(?:ы|ов|ам|ами|е)?|"
    r"загрузк(?:а|и|у|ой|е)?|транскрипт(?:ы|ов|ам|ами|е)?"
)

_ARTIFACT_INVENTORY_EXPANSION = (
    "files documents docs screenshots images pictures photos attachments assets artifacts "
    "uploads transcripts ocr vision audio video source refs evidence linked related "
    "associated project person event meeting call capture original file metadata"
)
_RU_ARTIFACT_INVENTORY_EXPANSION = (
    "файлы документы скриншоты картинки изображения фото вложения артефакты загрузки "
    "транскрипты ocr vision audio video источники evidence связаны относятся проект "
    "человек событие встреча созвон capture original file metadata"
)

_ARTIFACT_INVENTORY_QUERY_RE = re.compile(
    rf"\b(?:which|what|show|list|find|open)\s+(?:related\s+|linked\s+|attached\s+)?"
    rf"(?:{_ARTIFACT_KIND_RE})\s+(?:are\s+)?"
    rf"(?:related|linked|attached|connected|associated)?\s*"
    rf"(?:to|with|for|about|from|in|on)\s+{_ENTITY_LABEL_RE}\b|"
    rf"\b(?:{_ARTIFACT_KIND_RE})\s+(?:related|linked|attached|connected|associated)\s+"
    rf"(?:to|with|for|about|from|in|on)\s+{_ENTITY_LABEL_RE}\b|"
    rf"\b(?:show|list|find|open)\s+(?:the\s+)?(?:{_ARTIFACT_KIND_RE})\s+"
    rf"(?:for|about|from|in|on)\s+{_ENTITY_LABEL_RE}\b",
    re.IGNORECASE,
)
_RU_ARTIFACT_INVENTORY_QUERY_RE = re.compile(
    rf"\b(?:какие|покажи|показать|найди|открой|список)\s+"
    rf"(?:связанн\w+\s+|прикрепленн\w+\s+)?(?:{_RU_ARTIFACT_KIND_RE})\s+"
    rf"(?:связаны|относятся|прикреплены)?\s*"
    rf"(?:к|ко|с|со|по|про|для|из|в|во)\s+{_ENTITY_LABEL_RE}\b|"
    rf"\b(?:{_RU_ARTIFACT_KIND_RE})\s+"
    rf"(?:связаны|относятся|прикреплены|привязаны)\s+"
    rf"(?:к|ко|с|со|по|про|для|из|в|во)\s+{_ENTITY_LABEL_RE}\b",
    re.IGNORECASE,
)

ARTIFACT_INVENTORY_EXPANSION_RULES: tuple[tuple[frozenset[str], str, str], ...] = (
    (
        frozenset({"artifact_inventory_query"}),
        _ARTIFACT_INVENTORY_EXPANSION,
        "artifact_inventory_bridge",
    ),
    (
        frozenset({"ru_artifact_inventory_query"}),
        _RU_ARTIFACT_INVENTORY_EXPANSION,
        "artifact_inventory_bridge",
    ),
)


def artifact_inventory_query_variants(query: str) -> frozenset[str]:
    variants: set[str] = set()
    if _ARTIFACT_INVENTORY_QUERY_RE.search(query):
        variants.add("artifact_inventory_query")
    if _RU_ARTIFACT_INVENTORY_QUERY_RE.search(query):
        variants.add("ru_artifact_inventory_query")
    return frozenset(variants)
