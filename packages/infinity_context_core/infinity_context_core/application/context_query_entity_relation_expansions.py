"""Entity relation inventory query expansion rules."""

from __future__ import annotations

import re

_ENTITY_LABEL_RE = (
    r"[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё._-]{1,39}"
    r"(?:\s+[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё._-]{1,39}){0,4}"
)
_ENTITY_KIND_RE = (
    r"project|company|organization|organisation|org|team|client|customer|vendor|"
    r"partner|event|meeting|call"
)
_RU_ENTITY_KIND_RE = (
    r"проект(?:а|у|ом)?|компан(?:ия|ию|ии)|организац(?:ия|ию|ии)|"
    r"команд(?:а|у|ы)|клиент(?:а|у|ом)?|заказчик(?:а|у|ом)?|"
    r"вендор(?:а|у|ом)?|партн[её]р(?:а|у|ом)?|событи(?:е|я|ю|ем)|"
    r"встреч(?:а|у|и|е)|созвон(?:а|у|ом)?"
)

_ENTITY_RELATION_INVENTORY_EXPANSION = (
    "people persons stakeholders contacts owners participants collaborators involved "
    "connected related linked associated relationship relation anchor graph project "
    "organization event meeting call decision owner assignee evidence source of truth"
)
_RU_ENTITY_RELATION_INVENTORY_EXPANSION = (
    "люди участники контакты стейкхолдеры заинтересованные ответственные владельцы "
    "связаны относится отношение связь граф проект организация событие встреча созвон "
    "решение владелец исполнитель evidence source of truth"
)

_ENTITY_RELATION_INVENTORY_QUERY_RE = re.compile(
    rf"\bwho\s+(?:is|are|was|were)\s+(?:connected|related|linked|associated)\s+"
    rf"(?:to|with)\s+(?:(?:{_ENTITY_KIND_RE})\s+)?{_ENTITY_LABEL_RE}\b|"
    rf"\b(?:which|what)\s+(?:people|persons|stakeholders|contacts|owners|"
    rf"participants|collaborators)\s+(?:are|were)?\s*"
    rf"(?:connected|related|linked|associated|involved)?\s*"
    rf"(?:to|with|in|on|for)\s+(?:(?:{_ENTITY_KIND_RE})\s+)?{_ENTITY_LABEL_RE}\b|"
    rf"\bwho\s+(?:is|are|was|were)\s+(?:involved|participating|working)\s+"
    rf"(?:in|on|with)\s+(?:(?:{_ENTITY_KIND_RE})\s+)?{_ENTITY_LABEL_RE}\b|"
    rf"\bwho\s+(?:are|were)\s+(?:the\s+)?(?:stakeholders|contacts|owners|"
    rf"participants|collaborators)\s+(?:for|on|in)\s+"
    rf"(?:(?:{_ENTITY_KIND_RE})\s+)?{_ENTITY_LABEL_RE}\b",
    re.IGNORECASE,
)
_RU_ENTITY_RELATION_INVENTORY_QUERY_RE = re.compile(
    rf"\bкто\s+(?:связан|связана|связаны|относится|участвует|вовлеч[её]н\w*)\s+"
    rf"(?:с|со|в|во|к|ко|по)\s+(?:(?:{_RU_ENTITY_KIND_RE})\s+)?{_ENTITY_LABEL_RE}\b|"
    rf"\b(?:какие|кто)\s+(?:люди|участники|контакты|стейкхолдеры|"
    rf"заинтересованные|ответственные)\s+"
    rf"(?:связаны|участвуют|вовлечены|относятся)?\s*"
    rf"(?:с|со|в|во|к|ко|по)\s+(?:(?:{_RU_ENTITY_KIND_RE})\s+)?{_ENTITY_LABEL_RE}\b|"
    rf"\b(?:контакты|участники|стейкхолдеры|ответственные)\s+"
    rf"(?:по|для|в)\s+(?:(?:{_RU_ENTITY_KIND_RE})\s+)?{_ENTITY_LABEL_RE}\b",
    re.IGNORECASE,
)

ENTITY_RELATION_EXPANSION_RULES: tuple[tuple[frozenset[str], str, str], ...] = (
    (
        frozenset({"entity_relation_inventory_query"}),
        _ENTITY_RELATION_INVENTORY_EXPANSION,
        "entity_relation_inventory_bridge",
    ),
    (
        frozenset({"ru_entity_relation_inventory_query"}),
        _RU_ENTITY_RELATION_INVENTORY_EXPANSION,
        "entity_relation_inventory_bridge",
    ),
)


def entity_relation_query_variants(query: str) -> frozenset[str]:
    variants: set[str] = set()
    if _ENTITY_RELATION_INVENTORY_QUERY_RE.search(query):
        variants.add("entity_relation_inventory_query")
    if _RU_ENTITY_RELATION_INVENTORY_QUERY_RE.search(query):
        variants.add("ru_entity_relation_inventory_query")
    return frozenset(variants)
