"""Shared bounded relative temporal hint parsing for memory retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TemporalHint:
    code: str
    min_hours: float
    max_hours: float
    canonical_code: str = ""


_NUMBER_WORDS = {
    "один": 1,
    "одна": 1,
    "one": 1,
    "два": 2,
    "две": 2,
    "two": 2,
    "три": 3,
    "three": 3,
    "четыре": 4,
    "four": 4,
    "пять": 5,
    "five": 5,
    "шесть": 6,
    "six": 6,
}
_EN_NUMBER_WORD_PATTERN = "one|two|three|four|five|six"
_RU_NUMBER_WORD_PATTERN = "один|одна|два|две|три|четыре|пять|шесть"
_EN_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
_NUMERIC_TEMPORAL_HINT_PATTERNS: tuple[tuple[str, re.Pattern[str], float, int], ...] = (
    (
        "hours",
        re.compile(
            r"\b(?:(?:about|around)\s+)?"
            rf"(?P<count>\d{{1,3}}|{_EN_NUMBER_WORD_PATTERN})\s+hours?\s+ago\b",
            re.IGNORECASE,
        ),
        1.0,
        24 * 14,
    ),
    (
        "hours",
        re.compile(
            rf"\b(?:около\s+)?(?P<count>\d{{1,3}}|{_RU_NUMBER_WORD_PATTERN})\s+"
            r"час(?:а|ов)?\s+назад\b",
            re.IGNORECASE,
        ),
        1.0,
        24 * 14,
    ),
    (
        "days",
        re.compile(
            rf"\b(?:(?:about|around)\s+)?(?P<count>\d{{1,3}}|{_EN_NUMBER_WORD_PATTERN})"
            r"\s+days?\s+ago\b",
            re.IGNORECASE,
        ),
        24.0,
        365,
    ),
    (
        "days",
        re.compile(
            rf"\b(?:около\s+)?(?P<count>\d{{1,3}}|{_RU_NUMBER_WORD_PATTERN})\s+"
            r"д(?:ень|ня|ней)\s+назад\b",
            re.IGNORECASE,
        ),
        24.0,
        365,
    ),
    (
        "weeks",
        re.compile(
            rf"\b(?:(?:about|around)\s+)?(?P<count>\d{{1,2}}|{_EN_NUMBER_WORD_PATTERN})"
            r"\s+weeks?\s+ago\b",
            re.IGNORECASE,
        ),
        24.0 * 7,
        52,
    ),
    (
        "weeks",
        re.compile(
            rf"\b(?:около\s+)?(?P<count>\d{{1,2}}|{_RU_NUMBER_WORD_PATTERN})\s+"
            r"недел[юи]\s+назад\b",
            re.IGNORECASE,
        ),
        24.0 * 7,
        52,
    ),
    (
        "weekends",
        re.compile(
            rf"\b(?:(?:about|around)\s+)?(?P<count>\d{{1,2}}|{_EN_NUMBER_WORD_PATTERN})"
            r"\s+weekends?\s+ago\b",
            re.IGNORECASE,
        ),
        24.0 * 7,
        52,
    ),
    (
        "months",
        re.compile(
            rf"\b(?:(?:about|around)\s+)?(?P<count>\d{{1,2}}|{_EN_NUMBER_WORD_PATTERN})"
            r"\s+months?\s+ago\b",
            re.IGNORECASE,
        ),
        24.0 * 30,
        120,
    ),
    (
        "months",
        re.compile(
            rf"\b(?:около\s+)?(?P<count>\d{{1,2}}|{_RU_NUMBER_WORD_PATTERN})\s+"
            r"месяц(?:а|ев)?\s+назад\b",
            re.IGNORECASE,
        ),
        24.0 * 30,
        120,
    ),
    (
        "years",
        re.compile(
            rf"\b(?:(?:about|around)\s+)?(?P<count>\d{{1,2}}|{_EN_NUMBER_WORD_PATTERN})"
            r"\s+years?\s+ago\b",
            re.IGNORECASE,
        ),
        24.0 * 365,
        20,
    ),
    (
        "years",
        re.compile(
            rf"\b(?:около\s+)?(?P<count>\d{{1,2}}|{_RU_NUMBER_WORD_PATTERN})\s+"
            r"(?:год(?:а)?|лет)\s+назад\b",
            re.IGNORECASE,
        ),
        24.0 * 365,
        20,
    ),
)
_TEMPORAL_HINT_PATTERNS: tuple[tuple[str, re.Pattern[str], float, float], ...] = (
    *(
        (
            f"last_{weekday}",
            re.compile(rf"\b(?:last|previous|prior)\s+{weekday}\b", re.IGNORECASE),
            24.0,
            24.0 * 8,
        )
        for weekday in _EN_WEEKDAYS
    ),
    (
        "earlier_today",
        re.compile(r"\b(?:earlier\s+today|ранее\s+сегодня)\b", re.IGNORECASE),
        0.0,
        30.0,
    ),
    (
        "today_morning",
        re.compile(
            r"\b(?:this\s+morning|сегодня\s+утром|утром\s+сегодня)\b",
            re.IGNORECASE,
        ),
        0.0,
        18.0,
    ),
    (
        "today_afternoon",
        re.compile(
            r"\b(?:this\s+afternoon|сегодня\s+д[нн]ём|д[нн]ём\s+сегодня|"
            r"сегодня\s+днем|днем\s+сегодня)\b",
            re.IGNORECASE,
        ),
        0.0,
        12.0,
    ),
    (
        "today_evening",
        re.compile(
            r"\b(?:this\s+evening|сегодня\s+вечером|вечером\s+сегодня)\b",
            re.IGNORECASE,
        ),
        0.0,
        8.0,
    ),
    (
        "hour_ago",
        re.compile(
            r"\b(?:an?\s+hour\s+ago|1\s+hour\s+ago|last\s+hour|"
            r"(?<!\d\s)(?:около\s+)?час(?:а|ов)?\s+назад)\b",
            re.IGNORECASE,
        ),
        0.0,
        2.5,
    ),
    (
        "today",
        re.compile(r"\b(?:today|сегодня)\b", re.IGNORECASE),
        0.0,
        30.0,
    ),
    # Future windows use negative offsets so age-based link matching does not
    # treat freshly updated memories as future events.
    (
        "tomorrow",
        re.compile(r"\b(?:tomorrow|завтра)\b", re.IGNORECASE),
        -48.0,
        -0.01,
    ),
    (
        "this_week",
        re.compile(
            r"\b(?:this\s+week|current\s+week|earlier\s+this\s+week|"
            r"на\s+этой\s+неделе|в\s+эту\s+неделю|эта\s+неделя)\b",
            re.IGNORECASE,
        ),
        0.0,
        24.0 * 8,
    ),
    (
        "next_week",
        re.compile(
            r"\b(?:next\s+week|upcoming\s+week|following\s+week|"
            r"на\s+следующей\s+неделе|в\s+следующую\s+неделю|"
            r"следующая\s+неделя)\b",
            re.IGNORECASE,
        ),
        -24.0 * 14,
        -24.0,
    ),
    (
        "this_month",
        re.compile(
            r"\b(?:this\s+month|current\s+month|в\s+этом\s+месяце|этот\s+месяц)\b",
            re.IGNORECASE,
        ),
        0.0,
        24.0 * 31,
    ),
    (
        "next_month",
        re.compile(
            r"\b(?:next\s+month|upcoming\s+month|following\s+month|"
            r"в\s+следующем\s+месяце|на\s+следующий\s+месяц|"
            r"следующий\s+месяц)\b",
            re.IGNORECASE,
        ),
        -24.0 * 45,
        -24.0 * 20,
    ),
    (
        "this_quarter",
        re.compile(
            r"\b(?:this\s+quarter|current\s+quarter|"
            r"в\s+этом\s+квартале|этот\s+квартал)\b",
            re.IGNORECASE,
        ),
        0.0,
        24.0 * 93,
    ),
    (
        "next_quarter",
        re.compile(
            r"\b(?:next\s+quarter|upcoming\s+quarter|following\s+quarter|"
            r"в\s+следующем\s+квартале|на\s+следующий\s+квартал|"
            r"следующий\s+квартал)\b",
            re.IGNORECASE,
        ),
        -24.0 * 190,
        -24.0 * 60,
    ),
    (
        "this_year",
        re.compile(
            r"\b(?:this\s+year|current\s+year|в\s+этом\s+году|этот\s+год)\b",
            re.IGNORECASE,
        ),
        0.0,
        24.0 * 366,
    ),
    (
        "next_year",
        re.compile(
            r"\b(?:next\s+year|upcoming\s+year|following\s+year|"
            r"в\s+следующем\s+году|на\s+следующий\s+год|следующий\s+год)\b",
            re.IGNORECASE,
        ),
        -24.0 * 430,
        -24.0 * 300,
    ),
    (
        "yesterday",
        re.compile(r"\b(?:yesterday|вчера)\b", re.IGNORECASE),
        18.0,
        54.0,
    ),
    (
        "last_night",
        re.compile(
            r"\b(?:last\s+night|прошл(?:ой|ую)\s+ноч(?:ью)?|вчера\s+ночью)\b",
            re.IGNORECASE,
        ),
        6.0,
        30.0,
    ),
    (
        "last_week",
        re.compile(
            r"\b(?:(?:last|previous|prior)\s+week|(?:a\s+)?week\s+ago|1\s+week\s+ago|"
            r"на\s+прошлой\s+неделе|прошл(?:ой|ую)\s+недел[юе]|"
            r"недел[юи]\s+назад)\b",
            re.IGNORECASE,
        ),
        24.0,
        24.0 * 10,
    ),
    (
        "this_weekend",
        re.compile(
            r"\b(?:this\s+weekend|current\s+weekend|"
            r"в\s+эти\s+выходные|на\s+этих\s+выходных)\b",
            re.IGNORECASE,
        ),
        0.0,
        24.0 * 4,
    ),
    (
        "last_weekend",
        re.compile(
            r"\b(?:(?:last|previous|prior)\s+weekend|(?:a\s+)?weekend\s+ago|"
            r"1\s+weekend\s+ago|на\s+прошлых\s+выходных|"
            r"прошл(?:ые|ых)\s+выходн(?:ые|ых))\b",
            re.IGNORECASE,
        ),
        24.0,
        24.0 * 10,
    ),
    (
        "last_month",
        re.compile(
            r"\b(?:(?:last|previous|prior)\s+month|(?:a\s+)?month\s+ago|1\s+month\s+ago|"
            r"в\s+прошлом\s+месяце|прошл(?:ый|ом)\s+месяц(?:е)?|"
            r"месяц\s+назад)\b",
            re.IGNORECASE,
        ),
        24.0 * 20,
        24.0 * 45,
    ),
    (
        "last_quarter",
        re.compile(
            r"\b(?:(?:last|previous|prior)\s+quarter|"
            r"в\s+прошлом\s+квартале|прошл(?:ый|ом)\s+квартал(?:е)?)\b",
            re.IGNORECASE,
        ),
        24.0 * 60,
        24.0 * 190,
    ),
    (
        "last_year",
        re.compile(
            r"\b(?:(?:last|previous|prior)\s+year|(?:a\s+)?year\s+ago|1\s+year\s+ago|"
            r"в\s+прошлом\s+году|прошл(?:ый|ом)\s+год(?:у)?|год\s+назад)\b",
            re.IGNORECASE,
        ),
        24.0 * 300,
        24.0 * 430,
    ),
)


def temporal_hint_windows(text: str) -> tuple[TemporalHint, ...]:
    hints: list[TemporalHint] = []
    seen: set[str] = set()
    for hint in _numeric_temporal_hints(text):
        seen.add(hint.code)
        hints.append(hint)
    for code, pattern, min_hours, max_hours in _TEMPORAL_HINT_PATTERNS:
        if code == "last_week" and any(
            hint.canonical_code in {"last_week", "weeks_ago"} for hint in hints
        ):
            continue
        if code == "last_weekend" and any(
            hint.canonical_code in {"last_weekend", "weekends_ago"} for hint in hints
        ):
            continue
        if code == "last_month" and any(hint.canonical_code == "months_ago" for hint in hints):
            continue
        if code == "last_year" and any(hint.canonical_code == "years_ago" for hint in hints):
            continue
        if code in seen or not pattern.search(text):
            continue
        seen.add(code)
        hints.append(
            TemporalHint(
                code=code,
                min_hours=min_hours,
                max_hours=max_hours,
                canonical_code=code,
            )
        )
    return tuple(hints)


def temporal_hint_codes(text: str) -> tuple[str, ...]:
    codes: list[str] = []
    seen: set[str] = set()
    for hint in temporal_hint_windows(text):
        code = hint.canonical_code or hint.code
        if code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return tuple(codes)


def _numeric_temporal_hints(text: str) -> tuple[TemporalHint, ...]:
    hints: list[TemporalHint] = []
    seen: set[str] = set()
    for unit, pattern, unit_hours, max_count in _NUMERIC_TEMPORAL_HINT_PATTERNS:
        for match in pattern.finditer(text):
            count = _parse_count(match.group("count"))
            if count <= 0 or count > max_count:
                continue
            code = f"{count}_{unit}_ago"
            if code in seen:
                continue
            seen.add(code)
            min_hours, max_hours = _numeric_temporal_window(count * unit_hours)
            hints.append(
                TemporalHint(
                    code=code,
                    min_hours=min_hours,
                    max_hours=max_hours,
                    canonical_code=_canonical_numeric_code(unit=unit, count=count),
                )
            )
    return tuple(hints)


def _numeric_temporal_window(target_hours: float) -> tuple[float, float]:
    if target_hours <= 24:
        tolerance = max(1.0, target_hours * 0.3)
    elif target_hours <= 24 * 7:
        tolerance = max(6.0, target_hours * 0.2)
    else:
        tolerance = max(24.0, target_hours * 0.15)
    return max(0.0, target_hours - tolerance), target_hours + tolerance


def _canonical_numeric_code(*, unit: str, count: int) -> str:
    if unit == "hours":
        return "hours_ago"
    if unit == "days":
        return "days_ago"
    if unit == "weeks":
        return "last_week" if count == 1 else "weeks_ago"
    if unit == "weekends":
        return "last_weekend" if count == 1 else "weekends_ago"
    if unit == "months":
        return "last_month" if count == 1 else "months_ago"
    if unit == "years":
        return "last_year" if count == 1 else "years_ago"
    return f"{unit}_ago"


def _parse_count(value: str) -> int:
    normalized = value.casefold()
    if normalized.isdigit():
        return int(normalized)
    return _NUMBER_WORDS.get(normalized, 0)
