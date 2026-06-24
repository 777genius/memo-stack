"""Frequency and recurrence query helpers for deterministic retrieval."""

from __future__ import annotations

_FREQUENCY_PROMPT_TERMS = frozenset(
    {
        "cadence",
        "every",
        "frequent",
        "frequently",
        "frequency",
        "often",
        "recurring",
        "regular",
        "regularly",
        "routine",
        "schedule",
        "usually",
        "кажд",
        "регулярно",
        "часто",
        "частота",
        "обычно",
    }
)
_FREQUENCY_UNIT_TERMS = frozenset(
    {
        "annually",
        "daily",
        "day",
        "days",
        "monthly",
        "month",
        "months",
        "night",
        "nights",
        "per",
        "times",
        "week",
        "weekday",
        "weekdays",
        "weekend",
        "weekends",
        "weekly",
        "year",
        "yearly",
        "день",
        "дня",
        "дней",
        "ежедневно",
        "ежемесячно",
        "еженедельно",
        "год",
        "года",
        "лет",
        "месяц",
        "месяца",
        "недел",
        "недели",
        "неделю",
        "раз",
    }
)
_FREQUENCY_EVENT_TERMS = frozenset(
    {
        "attend",
        "attended",
        "call",
        "called",
        "chat",
        "chatted",
        "go",
        "goes",
        "meet",
        "meeting",
        "met",
        "message",
        "messaged",
        "participate",
        "participated",
        "practice",
        "practices",
        "run",
        "runs",
        "talk",
        "talked",
        "train",
        "trains",
        "visit",
        "visited",
        "volunteer",
        "volunteered",
        "volunteers",
        "work",
        "works",
        "бегает",
        "встречается",
        "волонтерит",
        "волонтерство",
        "говорит",
        "ходит",
        "работает",
        "созванивается",
        "тренируется",
        "участвует",
    }
)


def requests_frequency_recurrence_context(
    *,
    raw_tokens: frozenset[str],
    variants: frozenset[str],
) -> bool:
    """Return true for queries asking how often an event/activity recurs."""

    tokens = raw_tokens | variants
    has_frequency_prompt = bool(tokens & _FREQUENCY_PROMPT_TERMS) or (
        {"how", "often"}.issubset(tokens) or {"как", "часто"}.issubset(tokens)
    )
    has_rate_unit = bool(tokens & _FREQUENCY_UNIT_TERMS) and bool(
        {"per", "times", "раз"} & tokens
    )
    if not (has_frequency_prompt or has_rate_unit):
        return False
    return bool(tokens & _FREQUENCY_EVENT_TERMS) or has_frequency_prompt


def frequency_recurrence_tail(variants: frozenset[str]) -> str:
    """Build a compact retrieval tail for recurrence evidence."""

    activity_terms = " ".join(sorted((variants & _FREQUENCY_EVENT_TERMS)))[:120]
    return " ".join(
        part
        for part in (
            activity_terms,
            (
                "frequency recurrence cadence recurring repeated regular regularly "
                "usually often schedule routine every daily weekly monthly yearly "
                "weekend weekdays once twice three times per week per month"
            ),
        )
        if part
    )
