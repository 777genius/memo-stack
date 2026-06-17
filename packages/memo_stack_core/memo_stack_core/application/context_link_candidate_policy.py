"""Candidate scoring and metadata policy for context-link suggestions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from math import log

from memo_stack_core.application.dto import ContextLinkCandidate, SuggestContextLinksCommand
from memo_stack_core.domain.entities import MemoryChunk

_TERM_PATTERN = re.compile(r"[\w.@:/#-]+", re.UNICODE)
_MAX_CANDIDATE_PREVIEW = 220
_LINK_STOP_TERMS = {
    "about",
    "after",
    "again",
    "ago",
    "and",
    "days",
    "from",
    "hour",
    "hours",
    "last",
    "note",
    "screenshot",
    "that",
    "the",
    "this",
    "today",
    "with",
    "week",
    "weeks",
    "what",
    "when",
    "where",
    "which",
    "yesterday",
    "вчера",
    "день",
    "дней",
    "дня",
    "когда",
    "назад",
    "неделю",
    "недели",
    "неделе",
    "прошлой",
    "прошлую",
    "про",
    "скриншот",
    "сегодня",
    "что",
    "час",
    "часа",
    "часов",
}
_NUMERIC_TEMPORAL_HINT_PATTERNS: tuple[tuple[str, re.Pattern[str], float, int], ...] = (
    (
        "hours",
        re.compile(
            r"\b(?:(?:about|around)\s+)?(?P<count>\d{1,3})\s+hours?\s+ago\b",
            re.IGNORECASE,
        ),
        1.0,
        24 * 14,
    ),
    (
        "hours",
        re.compile(
            r"\b(?:около\s+)?(?P<count>\d{1,3})\s+час(?:а|ов)?\s+назад\b",
            re.IGNORECASE,
        ),
        1.0,
        24 * 14,
    ),
    (
        "days",
        re.compile(
            r"\b(?:(?:about|around)\s+)?(?P<count>\d{1,3})\s+days?\s+ago\b",
            re.IGNORECASE,
        ),
        24.0,
        365,
    ),
    (
        "days",
        re.compile(
            r"\b(?:около\s+)?(?P<count>\d{1,3})\s+д(?:ень|ня|ней)\s+назад\b",
            re.IGNORECASE,
        ),
        24.0,
        365,
    ),
    (
        "weeks",
        re.compile(
            r"\b(?:(?:about|around)\s+)?(?P<count>\d{1,2})\s+weeks?\s+ago\b",
            re.IGNORECASE,
        ),
        24.0 * 7,
        52,
    ),
    (
        "weeks",
        re.compile(
            r"\b(?:около\s+)?(?P<count>\d{1,2})\s+недел[юи]\s+назад\b",
            re.IGNORECASE,
        ),
        24.0 * 7,
        52,
    ),
)
_TEMPORAL_HINT_PATTERNS: tuple[tuple[str, re.Pattern[str], float, float], ...] = (
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
    (
        "yesterday",
        re.compile(r"\b(?:yesterday|вчера)\b", re.IGNORECASE),
        18.0,
        54.0,
    ),
    (
        "last_week",
        re.compile(
            r"\b(?:last\s+week|(?:a\s+)?week\s+ago|1\s+week\s+ago|"
            r"на\s+прошлой\s+неделе|прошл(?:ой|ую)\s+недел[юе]|"
            r"недел[юи]\s+назад)\b",
            re.IGNORECASE,
        ),
        24.0,
        24.0 * 10,
    ),
)


@dataclass(frozen=True)
class TemporalHint:
    code: str
    min_hours: float
    max_hours: float


def terms(text: str) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for raw in _TERM_PATTERN.findall(text.lower()):
        term = raw.strip("._-:/#")
        if len(term) >= 3 and term not in _LINK_STOP_TERMS and term not in seen:
            seen[term] = None
    return tuple(seen)


def score_text_candidate(
    *,
    query_terms: tuple[str, ...],
    temporal_hints: tuple[TemporalHint, ...],
    target_text: str,
    updated_at: datetime,
    now: datetime,
    base: float,
) -> tuple[float, list[str], tuple[str, ...]]:
    score = base
    reasons: list[str] = []
    lowered = target_text.lower()
    hits = tuple(term for term in query_terms if term in lowered)
    if hits:
        score += min(48.0, 8.0 * len(hits))
        reasons.append("matching text")
    relative_age_hours = _relative_age_hours(updated_at, now)
    if _matches_temporal_hint(temporal_hints, relative_age_hours):
        score += 6 if hits else 22
        reasons.append("temporal intent match")
    age_hours = max(relative_age_hours, 0.0)
    if age_hours <= 1:
        score += 18
        reasons.append("recent activity")
    elif age_hours <= 24:
        score += 12
        reasons.append("recent activity")
    elif age_hours <= 24 * 7:
        score += max(2.0, 10.0 - log(age_hours + 1))
        reasons.append("near in time")
    if not reasons:
        reasons.append("recent context")
    return min(score, 99.0), reasons, hits


def has_link_signal(*, matched_terms: tuple[str, ...], reasons: list[str]) -> bool:
    if matched_terms:
        return True
    return any(
        reason
        in {
            "same thread",
            "explicit project reference",
            "known project/tool reference",
            "event phrase",
            "person name",
            "temporal intent match",
        }
        for reason in reasons
    )


def temporal_hints(text: str) -> tuple[TemporalHint, ...]:
    hints: list[TemporalHint] = []
    seen: set[str] = set()
    for hint in _numeric_temporal_hints(text):
        seen.add(hint.code)
        hints.append(hint)
    for code, pattern, min_hours, max_hours in _TEMPORAL_HINT_PATTERNS:
        if code in seen or not pattern.search(text):
            continue
        seen.add(code)
        hints.append(TemporalHint(code=code, min_hours=min_hours, max_hours=max_hours))
    return tuple(hints)


def candidate(
    *,
    target_type: str,
    target_id: str,
    label: str,
    preview: str,
    score: float,
    reasons: list[str],
    metadata: dict[str, object],
) -> ContextLinkCandidate:
    unique_reasons = tuple(dict.fromkeys(reasons))
    safe_metadata = dict(metadata)
    safe_metadata["reason_codes"] = _reason_codes(unique_reasons)
    return ContextLinkCandidate(
        target_type=target_type,
        target_id=target_id,
        label=label[:120],
        preview=preview[:_MAX_CANDIDATE_PREVIEW],
        score=round(score, 2),
        tier=_tier(score),
        reasons=unique_reasons,
        metadata=safe_metadata,
    )


def candidate_reason(candidate: ContextLinkCandidate) -> str:
    reason = "; ".join(candidate.reasons)
    return reason[:320] if reason else "related memory candidate"


def chunk_label(chunk: MemoryChunk) -> str:
    sequence = chunk.sequence
    kind = chunk.kind.value
    source = chunk.source_external_id.strip()
    suffix = f" - {source}" if source else ""
    if isinstance(sequence, int):
        return f"{kind} #{sequence}{suffix}"
    return f"{kind}{suffix}"


def episode_label(episode: object) -> str:
    source = str(getattr(episode, "source_external_id", "")).strip()
    source_type = str(getattr(episode, "source_type", "")).strip()
    return " - ".join(part for part in (source_type, source) if part) or "episode"


def confidence_for_candidate(candidate: ContextLinkCandidate) -> str:
    if candidate.tier == "likely":
        return "high"
    if candidate.tier == "possible":
        return "medium"
    return "low"


def candidate_metadata(
    candidate: ContextLinkCandidate,
    diagnostics: dict[str, object],
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "target_label": candidate.label,
        "target_preview": candidate.preview,
        "target_tier": candidate.tier,
        "resolver_version": str(diagnostics.get("resolver_version", "unknown")),
        "reason_codes": _reason_codes(candidate.reasons),
    }
    for key, value in (candidate.metadata or {}).items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            metadata[str(key)] = value
        elif isinstance(value, (list, tuple)):
            cleaned = [
                item for item in value if isinstance(item, (str, int, float, bool)) or item is None
            ]
            if cleaned:
                metadata[str(key)] = cleaned
    return metadata


def is_same_source(
    key: tuple[str, str],
    command: SuggestContextLinksCommand,
) -> bool:
    return key[0] == command.source_type and key[1] == command.source_id


def _numeric_temporal_hints(text: str) -> tuple[TemporalHint, ...]:
    hints: list[TemporalHint] = []
    seen: set[str] = set()
    for unit, pattern, unit_hours, max_count in _NUMERIC_TEMPORAL_HINT_PATTERNS:
        for match in pattern.finditer(text):
            count = int(match.group("count"))
            if count <= 0 or count > max_count:
                continue
            code = f"{count}_{unit}_ago"
            if code in seen:
                continue
            seen.add(code)
            min_hours, max_hours = _numeric_temporal_window(count * unit_hours)
            hints.append(TemporalHint(code=code, min_hours=min_hours, max_hours=max_hours))
    return tuple(hints)


def _numeric_temporal_window(target_hours: float) -> tuple[float, float]:
    if target_hours <= 24:
        tolerance = max(1.0, target_hours * 0.3)
    elif target_hours <= 24 * 7:
        tolerance = max(6.0, target_hours * 0.2)
    else:
        tolerance = max(24.0, target_hours * 0.15)
    return max(0.0, target_hours - tolerance), target_hours + tolerance


def _matches_temporal_hint(hints: tuple[TemporalHint, ...], age_hours: float) -> bool:
    return any(hint.min_hours <= age_hours <= hint.max_hours for hint in hints)


def _reason_codes(reasons: tuple[str, ...]) -> list[str]:
    codes: list[str] = []
    for reason in reasons:
        if reason == "matching text":
            codes.append("text_match")
        elif reason == "recent activity":
            codes.append("recent_activity")
        elif reason == "near in time":
            codes.append("temporal_proximity")
        elif reason == "temporal intent match":
            codes.append("temporal_intent_match")
        elif reason == "same thread":
            codes.append("same_thread")
        elif reason.startswith("category:"):
            codes.append("shared_category")
        elif reason == "recent context":
            codes.append("recent_context")
        else:
            codes.append("rule_signal")
    return list(dict.fromkeys(codes))


def _tier(score: float) -> str:
    if score >= 75:
        return "likely"
    if score >= 55:
        return "possible"
    return "weak"


def _relative_age_hours(value: datetime, now: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return (now - value).total_seconds() / 3600
