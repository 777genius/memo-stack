"""Event summary query expansion rules for evidence-oriented retrieval."""

from __future__ import annotations

import re

_EVENT_LABEL_RE = (
    r"[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё._-]{1,39}"
    r"(?:\s+[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё._-]{1,39}){0,4}"
)
_EVENT_TERM_RE = (
    r"meeting|call|chat|conversation|sync|review|demo|standup|workshop|session"
)
_EVENT_DESCRIPTOR_RE = r"(?:[A-Za-zА-Яа-яЁё._-]{2,40}\s+){0,4}"
_RU_EVENT_TERM_RE = (
    r"встреч(?:а|у|и|е|ей)?|созвон(?:а|у|ом|е)?|разговор(?:а|у|ом|е)?|"
    r"переписк(?:а|у|и|е|ой)?|чат(?:а|у|ом|е)?|демо|ревью|стендап(?:а|у|ом|е)?"
)

_EVENT_SUMMARY_EXPANSION = (
    "event meeting call conversation recap summary notes transcript discussion discussed "
    "review sync demo standup workshop session decisions action items follow up "
    "participants timeline outcome context evidence source of truth"
)
_RU_EVENT_SUMMARY_EXPANSION = (
    "событие встреча созвон разговор переписка чат саммари кратко итоги заметки "
    "конспект транскрипт обсуждали обсудили решения поручения follow up участники "
    "таймлайн исход evidence source of truth"
)

_EVENT_SUMMARY_QUERY_RE = re.compile(
    rf"\b(?:summari[sz]e|recap)\s+(?:the\s+|our\s+|my\s+)?"
    rf"(?:last\s+|recent\s+|latest\s+|previous\s+)?"
    rf"{_EVENT_DESCRIPTOR_RE}(?:{_EVENT_TERM_RE})"
    rf"(?:\s+(?:with|about|for|on)\s+{_EVENT_LABEL_RE})?\b|"
    rf"\bwhat\s+(?:happened|came\s+up|was\s+discussed)\s+"
    rf"(?:in|during|on|at)\s+(?:the\s+|our\s+|my\s+)?"
    rf"(?:last\s+|recent\s+|latest\s+|previous\s+)?"
    rf"{_EVENT_DESCRIPTOR_RE}(?:{_EVENT_TERM_RE})\b|"
    rf"\bwhat\s+did\s+.+?\s+(?:discuss|talk\s+about|decide|agree)\s+"
    rf"(?:in|during|on|at|after)\s+(?:the\s+|our\s+|my\s+)?"
    rf"(?:last\s+|recent\s+|latest\s+|previous\s+)?"
    rf"{_EVENT_DESCRIPTOR_RE}(?:{_EVENT_TERM_RE})\b|"
    rf"\b(?:notes|decisions|action\s+items|follow\s+ups?)\s+"
    rf"(?:from|for|after)\s+(?:the\s+|our\s+|my\s+)?"
    rf"(?:last\s+|recent\s+|latest\s+|previous\s+)?"
    rf"{_EVENT_DESCRIPTOR_RE}(?:{_EVENT_TERM_RE})\b",
    re.IGNORECASE,
)
_RU_EVENT_SUMMARY_QUERY_RE = re.compile(
    rf"\b(?:кратко|саммари|резюме|итоги|конспект|заметки)\s+"
    rf"(?:по|про|после|с|со)?\s*(?:{_RU_EVENT_TERM_RE})\b|"
    rf"\bчто\s+(?:было|произошло|обсуждали|обсудили|решили)\s+"
    rf"(?:на|в|во|после)\s+(?:{_RU_EVENT_TERM_RE})\b|"
    rf"\b(?:какие\s+)?(?:решения|поручения|задачи|follow\s*up)\s+"
    rf"(?:после|по|с|со)\s+(?:{_RU_EVENT_TERM_RE})\b",
    re.IGNORECASE,
)

EVENT_SUMMARY_EXPANSION_RULES: tuple[tuple[frozenset[str], str, str], ...] = (
    (
        frozenset({"event_summary_query"}),
        _EVENT_SUMMARY_EXPANSION,
        "event_summary_bridge",
    ),
    (
        frozenset({"ru_event_summary_query"}),
        _RU_EVENT_SUMMARY_EXPANSION,
        "event_summary_bridge",
    ),
)


def event_summary_query_variants(query: str) -> frozenset[str]:
    variants: set[str] = set()
    if _EVENT_SUMMARY_QUERY_RE.search(query):
        variants.add("event_summary_query")
    if _RU_EVENT_SUMMARY_QUERY_RE.search(query):
        variants.add("ru_event_summary_query")
    return frozenset(variants)
