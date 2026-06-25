"""Organization summary query expansion rules for evidence-oriented retrieval."""

from __future__ import annotations

import re

_ORGANIZATION_LABEL_RE = (
    r"[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё._-]{1,39}"
    r"(?:\s+[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё._-]{1,39}){0,3}"
)
_ORGANIZATION_KIND_RE = (
    r"company|organization|organisation|org|team|client|customer|vendor|partner"
)
_RU_ORGANIZATION_KIND_RE = (
    r"компан(?:ия|ию|ии)|организац(?:ия|ию|ии)|команд(?:а|у|ы)|"
    r"клиент(?:а|у|ом)?|заказчик(?:а|у|ом)?|вендор(?:а|у|ом)?|партнер(?:а|у|ом)?|"
    r"партн[её]р(?:а|у|ом)?"
)

_ORGANIZATION_SUMMARY_EXPANSION = (
    "organization company team profile summary overview facts background role "
    "stakeholders contacts owners people relationship vendor client customer partner "
    "projects decisions requirements meetings calls documents services products risks "
    "contracts agreements evidence source of truth"
)
_RU_ORGANIZATION_SUMMARY_EXPANSION = (
    "организация компания команда профиль обзор кратко факты роль контакты люди "
    "ответственные отношения клиент заказчик вендор партнер проекты решения требования "
    "встречи созвоны документы сервисы продукты риски договоренности evidence source of truth"
)

_ORGANIZATION_SUMMARY_QUERY_RE = re.compile(
    rf"(?i:\bwhat\s+(?:is|was)\s+(?:{_ORGANIZATION_KIND_RE})\s+)"
    rf"{_ORGANIZATION_LABEL_RE}\s*(?:\?|$)|"
    rf"(?i:\bwhat\s+(?:do|did)\s+(?:we|you)\s+know\s+about\s+)"
    rf"(?:(?:{_ORGANIZATION_KIND_RE})\s+)?{_ORGANIZATION_LABEL_RE}\b|"
    rf"(?i:\btell\s+me\s+about\s+(?:(?:{_ORGANIZATION_KIND_RE})\s+)?)"
    rf"{_ORGANIZATION_LABEL_RE}\b|"
    rf"(?i:\bsummari[sz]e\s+(?:(?:{_ORGANIZATION_KIND_RE})\s+)?)"
    rf"{_ORGANIZATION_LABEL_RE}\b|"
    rf"(?i:\b(?:{_ORGANIZATION_KIND_RE})\s+)"
    rf"{_ORGANIZATION_LABEL_RE}(?i:\s+(?:summary|overview|profile))\b",
)
_RU_ORGANIZATION_SUMMARY_QUERY_RE = re.compile(
    rf"(?i:\bчто\s+это\s+за\s+(?:{_RU_ORGANIZATION_KIND_RE})\s+)"
    rf"{_ORGANIZATION_LABEL_RE}\s*(?:\?|$)|"
    rf"(?i:\bчто\s+(?:мы|ты)\s+зна(?:ем|ешь)\s+(?:об|о|про)\s+)"
    rf"(?:(?:{_RU_ORGANIZATION_KIND_RE})\s+)?{_ORGANIZATION_LABEL_RE}\b|"
    rf"(?i:\bрасскажи\s+(?:об|о|про)\s+(?:(?:{_RU_ORGANIZATION_KIND_RE})\s+)?)"
    rf"{_ORGANIZATION_LABEL_RE}\b|"
    rf"(?i:\b(?:профиль|обзор|сводка)\s+(?:{_RU_ORGANIZATION_KIND_RE})\s+)"
    rf"{_ORGANIZATION_LABEL_RE}\b",
)

ORGANIZATION_SUMMARY_EXPANSION_RULES: tuple[tuple[frozenset[str], str, str], ...] = (
    (
        frozenset({"organization_summary_query"}),
        _ORGANIZATION_SUMMARY_EXPANSION,
        "organization_summary_bridge",
    ),
    (
        frozenset({"ru_organization_summary_query"}),
        _RU_ORGANIZATION_SUMMARY_EXPANSION,
        "organization_summary_bridge",
    ),
)


def organization_summary_query_variants(query: str) -> frozenset[str]:
    variants: set[str] = set()
    if _ORGANIZATION_SUMMARY_QUERY_RE.search(query):
        variants.add("organization_summary_query")
    if _RU_ORGANIZATION_SUMMARY_QUERY_RE.search(query):
        variants.add("ru_organization_summary_query")
    return frozenset(variants)
