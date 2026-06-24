"""Temporal query intent and scoring helpers for context assembly."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace

from infinity_context_core.application.context_diagnostics import (
    normalize_context_diagnostics,
    safe_diagnostic_mapping,
    safe_score_signals,
)
from infinity_context_core.application.context_lexical import date_tokens, query_terms
from infinity_context_core.application.context_query_state_transition import (
    state_transition_query_variants,
)
from infinity_context_core.application.context_temporal_hints import temporal_hint_codes
from infinity_context_core.application.dto import ContextItem

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_EXCLUDE_STALE_RE = re.compile(
    r"\b(?:not\s+(?:stale|old|outdated|obsolete|deprecated|expired)|"
    r"ignore\s+(?:stale|old|outdated|obsolete|deprecated|expired)|"
    r"do\s+not\s+(?:use|include)\s+"
    r"(?:stale|old|outdated|obsolete|deprecated|expired))\b|"
    r"(?:устаревш\w*\s+не\s+учитывать|не\s+учитывать\s+устаревш\w*)",
    re.IGNORECASE,
)
_AGE_QUERY_RE = re.compile(r"\bhow\s+old\b", re.IGNORECASE)
_OLD_SOCIAL_RELATION_RE = re.compile(
    r"\bold\s+(?:friend|friends|buddy|buddies|classmate|classmates|"
    r"roommate|roommates|colleague|colleagues|coworker|coworkers|"
    r"teammate|teammates)\b",
    re.IGNORECASE,
)
_CURRENT_PHRASE_RE = re.compile(
    r"\b(?:right\s+now|as\s+of\s+now|at\s+the\s+moment|for\s+now)\b|"
    r"\b(?:прямо\s+сейчас|на\s+данный\s+момент|в\s+данный\s+момент)\b",
    re.IGNORECASE,
)
_CURRENT_RECOMMENDATION_RE = re.compile(
    r"\bshould\s+(?:(?:i|we)\s+)?(?:use|choose|pick)\b|"
    r"\b(?:recommended|preferred|best)\s+"
    r"(?:provider|tool|model|option|engine|database|service)\b|"
    r"\b(?:provider|tool|model|option|engine|database|service)\b"
    r"(?=.{0,50}\b(?:recommended|preferred|best)\b)|"
    r"\b(?:какой|какую|какое|какие)\s+"
    r"(?:провайдер|инструмент|модель|вариант|движок|сервис)\b"
    r"(?=.{0,60}\b(?:использовать|выбрать|лучше|рекоменд))",
    re.IGNORECASE | re.DOTALL,
)
_CURRENT_DECISION_RE = re.compile(
    r"\b(?:provider|tool|model|option|engine|database|service)\b"
    r"(?=.{0,70}\b(?:decid(?:e|ed)|chose|chosen|choose|picked|selected|use)\b)|"
    r"\b(?:decid(?:e|ed)|chose|chosen|choose|picked|selected)\b"
    r"(?=.{0,70}\b(?:provider|tool|model|option|engine|database|service)\b)|"
    r"\b(?:final|canonical|source\s+of\s+truth|settled)\b"
    r"(?=.{0,90}\b(?:decision|provider|tool|model|option|plan|policy|source)\b)|"
    r"\b(?:decision|provider|tool|model|option|plan|policy|source)\b"
    r"(?=.{0,90}\b(?:final|canonical|source\s+of\s+truth|settled)\b)|"
    r"\b(?:провайдер|инструмент|модель|вариант|движок|сервис)\b"
    r"(?=.{0,70}\b(?:решил\w*|выбрал\w*|использовать)\b)|"
    r"\b(?:решил\w*|выбрал\w*)\b"
    r"(?=.{0,70}\b(?:провайдер|инструмент|модель|вариант|движок|сервис)\b)|"
    r"\b(?:финальн\w*|окончательн\w*|выбранн\w*)\b"
    r"(?=.{0,90}\b(?:решени\w*|провайдер|инструмент|модель|вариант|план)\b)|"
    r"\b(?:решени\w*|провайдер|инструмент|модель|вариант|план)\b"
    r"(?=.{0,90}\b(?:финальн\w*|окончательн\w*|выбранн\w*)\b)",
    re.IGNORECASE | re.DOTALL,
)
_CURRENT_DECISION_PROMPT_RE = re.compile(
    r"\b(?:what|which)\b"
    r"(?=.{0,90}\b(?:decid(?:e|ed)|chose|chosen|choose|picked|selected)\b)"
    r"(?=.{0,110}\b(?:use|choose|pick|select|selected|choice|option)\b)|"
    r"\b(?:что|какой|какую|какое|какие)\b"
    r"(?=.{0,90}\b(?:решил\w*|выбрал\w*)\b)"
    r"(?=.{0,110}\b(?:использовать|выбрать|вариант)\b)",
    re.IGNORECASE | re.DOTALL,
)
_STILL_CURRENT_STATE_RE = re.compile(
    r"\b(?:still|remain(?:s|ed)?|kept)\b"
    r"(?=.{0,80}\b(?:valid|active|current|recommended|preferred|use|using|"
    r"works?|available|chosen|selected|option|plan|provider|tool|model|policy)\b)|"
    r"\b(?:valid|active|current|recommended|preferred|available|chosen|selected)\b"
    r"(?=.{0,80}\b(?:still|remain(?:s|ed)?)\b)|"
    r"\b(?:все\s+еще|всё\s+ещ[её]|по-прежнему|остается|остался|осталась|остались)\b"
    r"(?=.{0,80}\b(?:актуал|действует|валидн|использовать|выбран|вариант|"
    r"план|провайдер|инструмент|модель|политик)\w*)",
    re.IGNORECASE | re.DOTALL,
)
_NO_LONGER_CURRENT_STATE_RE = re.compile(
    r"\b(?:no\s+longer|anymore|any\s+longer|stopped)\b"
    r"(?=.{0,80}\b(?:valid|active|current|recommended|preferred|use|using|"
    r"works?|available|chosen|selected|option|plan|provider|tool|model|policy)\b)|"
    r"\b(?:valid|active|current|recommended|preferred|available|chosen|selected)\b"
    r"(?=.{0,80}\b(?:no\s+longer|anymore|any\s+longer)\b)|"
    r"\b(?:больше\s+не|уже\s+не|перестал\w*)\b"
    r"(?=.{0,80}\b(?:актуал|действует|валидн|использовать|выбран|вариант|"
    r"план|провайдер|инструмент|модель|политик)\w*)",
    re.IGNORECASE | re.DOTALL,
)
_CURRENT_TERMS = frozenset(
    {
        "active",
        "actual",
        "актуальн",
        "актуально",
        "current",
        "currently",
        "действует",
        "latest",
        "newest",
        "now",
        "nowadays",
        "последн",
        "последнее",
        "recent",
        "сейчас",
        "текущ",
        "текущий",
        "valid",
    }
)
_PREVIOUS_TERMS = frozenset(
    {
        "before",
        "deprecated",
        "earlier",
        "expired",
        "initial",
        "obsolete",
        "old",
        "outdated",
        "previous",
        "prior",
        "stale",
        "superseded",
        "до",
        "перед",
        "предыдущ",
        "раньше",
        "устаревш",
    }
)
_CHANGE_TERMS = frozenset(
    {
        "change",
        "changed",
        "difference",
        "replaced",
        "superseded",
        "update",
        "updated",
        "измен",
        "изменилось",
        "обновлен",
        "обновление",
        "поменялось",
    }
)
_AFTER_TERMS = frozenset({"after", "following", "later", "после", "позже", "затем"})
_BEFORE_TERMS = frozenset({"before", "earlier", "prior", "до", "перед", "раньше"})
_EVENT_SEQUENCE_CONTEXT_TERMS = frozenset(
    {
        "call",
        "chat",
        "conversation",
        "demo",
        "dm",
        "interview",
        "interviews",
        "meeting",
        "message",
        "review",
        "sync",
        "встреча",
        "демо",
        "интервью",
        "переписка",
        "ревью",
        "созвон",
        "чат",
    }
)
_SINCE_EVENT_RE = re.compile(
    r"\b(?:since|right\s+after|immediately\s+after|shortly\s+after)\b|"
    r"\b(?:с\s+момента|сразу\s+после|прямо\s+после)\b",
    re.IGNORECASE,
)
_UNTIL_EVENT_RE = re.compile(
    r"\b(?:until|up\s+to|right\s+before|immediately\s+before|shortly\s+before)\b|"
    r"\b(?:вплоть\s+до|сразу\s+до|прямо\s+перед)\b",
    re.IGNORECASE,
)
_LAST_WEEK_CHILD_HINTS = frozenset(
    {
        "last_monday",
        "last_tuesday",
        "last_wednesday",
        "last_thursday",
        "last_friday",
        "last_saturday",
        "last_sunday",
        "last_weekend",
    }
)
_CURRENT_DAY_CHILD_HINTS = frozenset(
    {
        "earlier_today",
        "hour_ago",
        "hours_ago",
        "today_afternoon",
        "today_evening",
        "today_morning",
    }
)
_THIS_WEEK_CHILD_HINTS = frozenset(
    {
        *_CURRENT_DAY_CHILD_HINTS,
        "days_ago",
        "last_night",
        "this_weekend",
        "today",
        "yesterday",
    }
)
_THIS_MONTH_CHILD_HINTS = frozenset(
    {
        *_THIS_WEEK_CHILD_HINTS,
        "this_week",
    }
)
_THIS_QUARTER_CHILD_HINTS = frozenset(
    {
        *_THIS_MONTH_CHILD_HINTS,
        "this_month",
    }
)
_THIS_YEAR_CHILD_HINTS = frozenset(
    {
        *_THIS_QUARTER_CHILD_HINTS,
        *_LAST_WEEK_CHILD_HINTS,
        "last_month",
        "last_week",
        "months_ago",
        "this_quarter",
        "weekends_ago",
        "weeks_ago",
    }
)
_TEMPORAL_HINT_CHILDREN: Mapping[str, frozenset[str]] = {
    "this_month": _THIS_MONTH_CHILD_HINTS,
    "this_quarter": _THIS_QUARTER_CHILD_HINTS,
    "this_week": _THIS_WEEK_CHILD_HINTS,
    "this_year": _THIS_YEAR_CHILD_HINTS,
    "today": _CURRENT_DAY_CHILD_HINTS,
    "last_week": _LAST_WEEK_CHILD_HINTS,
    "weeks_ago": frozenset({"weekends_ago"}),
}
_TEMPORAL_HINT_PARENTS: Mapping[str, str] = {
    child: parent for parent, children in _TEMPORAL_HINT_CHILDREN.items() for child in children
}


@dataclass(frozen=True)
class TemporalQueryIntent:
    prefers_current: bool
    requests_previous: bool
    requests_change: bool
    after_event: bool
    before_event: bool
    excludes_stale: bool
    relative_time_hints: tuple[str, ...] = ()

    @property
    def include_superseded_review(self) -> bool:
        return (self.requests_previous or self.requests_change) and not self.excludes_stale

    @property
    def empty(self) -> bool:
        return not any(
            (
                self.prefers_current,
                self.requests_previous,
                self.requests_change,
                self.after_event,
                self.before_event,
                self.excludes_stale,
                self.relative_time_hints,
            )
        )

    def diagnostics(self) -> dict[str, object]:
        reasons: list[str] = []
        if self.prefers_current:
            reasons.append("prefers_current")
        if self.requests_previous:
            reasons.append("requests_previous")
        if self.requests_change:
            reasons.append("requests_change")
        if self.after_event:
            reasons.append("after_event")
        if self.before_event:
            reasons.append("before_event")
        if self.excludes_stale:
            reasons.append("excludes_stale")
        if self.relative_time_hints:
            reasons.append("relative_time_hint")
        return {
            "temporal_query_intent_status": "empty" if self.empty else "available",
            "temporal_query_prefers_current": self.prefers_current,
            "temporal_query_requests_previous": self.requests_previous,
            "temporal_query_requests_change": self.requests_change,
            "temporal_query_after_event": self.after_event,
            "temporal_query_before_event": self.before_event,
            "temporal_query_excludes_stale": self.excludes_stale,
            "temporal_query_include_superseded_review": (self.include_superseded_review),
            "temporal_query_relative_time_hints": list(self.relative_time_hints),
            "temporal_query_intent_reasons": reasons,
        }


@dataclass(frozen=True)
class TemporalQueryBoostSignal:
    boost: float = 0.0
    reason: str = ""
    code: str = ""

    @property
    def empty(self) -> bool:
        return self.boost == 0.0


def build_temporal_query_intent(query: str) -> TemporalQueryIntent:
    variants = _query_variant_set(query)
    variants = frozenset((*variants, *state_transition_query_variants(query)))
    relative_time_hints = _query_temporal_hint_codes(query)
    excludes_stale = bool(_EXCLUDE_STALE_RE.search(query))
    still_current_state = bool(_STILL_CURRENT_STATE_RE.search(query))
    no_longer_current_state = bool(_NO_LONGER_CURRENT_STATE_RE.search(query))
    requests_change = bool(
        variants.intersection(_CHANGE_TERMS) or "state_transition_request" in variants
    )
    previous_terms = variants.intersection(_PREVIOUS_TERMS)
    if _AGE_QUERY_RE.search(query) or _OLD_SOCIAL_RELATION_RE.search(query):
        previous_terms = previous_terms.difference({"old"})
    requests_previous = (bool(previous_terms) or no_longer_current_state) and not excludes_stale
    prefers_current = (
        excludes_stale
        or still_current_state
        or bool(variants.intersection(_CURRENT_TERMS))
        or bool(_CURRENT_PHRASE_RE.search(query))
        or bool(_CURRENT_RECOMMENDATION_RE.search(query))
        or (requests_change and not requests_previous)
    ) and not no_longer_current_state
    after_event = bool(variants.intersection(_AFTER_TERMS)) or _has_since_event_context(
        query,
        variants,
    )
    before_event = bool(variants.intersection(_BEFORE_TERMS)) or _has_until_event_context(
        query,
        variants,
    )
    current_decision = (
        bool(_CURRENT_DECISION_RE.search(query))
        or bool(_CURRENT_DECISION_PROMPT_RE.search(query))
    ) and not (
        after_event
        or before_event
        or bool(relative_time_hints)
        or requests_previous
    )
    prefers_current = prefers_current or current_decision
    return TemporalQueryIntent(
        prefers_current=prefers_current,
        requests_previous=requests_previous,
        requests_change=requests_change,
        after_event=after_event,
        before_event=before_event,
        excludes_stale=excludes_stale,
        relative_time_hints=relative_time_hints,
    )


def _query_temporal_hint_codes(query: str) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for code in (*temporal_hint_codes(query), *date_tokens(query)):
        if code not in seen:
            seen[code] = None
    return tuple(seen)


def apply_temporal_query_intent_boosts(
    items: tuple[ContextItem, ...],
    *,
    intent: TemporalQueryIntent,
) -> tuple[ContextItem, ...]:
    if intent.empty:
        return items
    return tuple(_apply_temporal_query_intent(item, intent=intent) for item in items)


def temporal_query_boost_signal(
    item: ContextItem,
    *,
    intent: TemporalQueryIntent,
) -> TemporalQueryBoostSignal:
    if intent.empty:
        return TemporalQueryBoostSignal()
    diagnostics = normalize_context_diagnostics(item.diagnostics)
    retrieval_source = str(diagnostics.get("retrieval_source") or "")
    provenance = safe_diagnostic_mapping(diagnostics.get("provenance"))
    fact_status = str(provenance.get("fact_status") or diagnostics.get("fact_status") or "")
    is_review_only = diagnostics.get("review_only") is True
    is_superseded = retrieval_source == "superseded_review" or fact_status == "superseded"
    has_temporal_relation = bool(diagnostics.get("temporal_relations"))
    temporal_hint_code = _temporal_hint_code(diagnostics, provenance)
    if intent.excludes_stale and (is_review_only or is_superseded):
        return TemporalQueryBoostSignal(
            boost=-0.12,
            reason="query excludes stale memory",
            code="excludes_stale",
        )
    if _temporal_hint_matches(intent=intent, temporal_hint_code=temporal_hint_code):
        return TemporalQueryBoostSignal(
            boost=0.032,
            reason="query relative time matches item event window",
            code="relative_time_match",
        )
    if _temporal_hint_is_contained_by_query(
        intent=intent,
        temporal_hint_code=temporal_hint_code,
    ):
        return TemporalQueryBoostSignal(
            boost=0.018,
            reason="query relative time contains item event window",
            code="relative_time_contains",
        )
    if _temporal_hint_conflicts(intent=intent, temporal_hint_code=temporal_hint_code):
        return TemporalQueryBoostSignal(
            boost=-0.026,
            reason="query relative time conflicts with item event window",
            code="relative_time_conflict",
        )
    if intent.requests_change and retrieval_source == "temporal_supersedes_relation":
        return TemporalQueryBoostSignal(
            boost=0.05,
            reason="query asks what changed and item is active replacement",
            code="change_active_replacement",
        )
    if intent.requests_change and has_temporal_relation:
        return TemporalQueryBoostSignal(
            boost=0.035,
            reason="query asks what changed and item has temporal relation",
            code="change_temporal_relation",
        )
    if intent.requests_change and is_superseded:
        return TemporalQueryBoostSignal(
            boost=0.035,
            reason="query asks what changed and item is previous state evidence",
            code="change_previous_state",
        )
    if direction_boost := _event_sequence_direction_boost(
        intent=intent,
        text=item.text,
    ):
        return TemporalQueryBoostSignal(
            boost=direction_boost,
            reason=_event_sequence_direction_reason(intent=intent, boost=direction_boost),
            code=_event_sequence_direction_code(intent=intent, boost=direction_boost),
        )
    if intent.requests_previous and is_superseded:
        return TemporalQueryBoostSignal(
            boost=0.045,
            reason="query asks for previous state evidence",
            code="previous_state_evidence",
        )
    if intent.prefers_current and (is_review_only or is_superseded):
        return TemporalQueryBoostSignal(
            boost=-0.024,
            reason="query prefers current active memory and item is superseded",
            code="current_superseded_conflict",
        )
    if intent.prefers_current and not is_review_only and not is_superseded:
        return TemporalQueryBoostSignal(
            boost=0.018,
            reason="query prefers current active memory",
            code="current_active_match",
        )
    return TemporalQueryBoostSignal()


def _apply_temporal_query_intent(
    item: ContextItem,
    *,
    intent: TemporalQueryIntent,
) -> ContextItem:
    signal = temporal_query_boost_signal(item, intent=intent)
    if signal.empty:
        return item
    return _with_temporal_query_boost(
        item,
        boost=signal.boost,
        reason=signal.reason,
        intent=intent,
    )


def _with_temporal_query_boost(
    item: ContextItem,
    *,
    boost: float,
    reason: str,
    intent: TemporalQueryIntent,
) -> ContextItem:
    diagnostics = normalize_context_diagnostics(item.diagnostics)
    diagnostics["temporal_query_intent_reason"] = reason
    diagnostics["score_signals"] = {
        **safe_score_signals(diagnostics.get("score_signals")),
        "temporal_query_intent_boost": round(boost, 4),
    }
    diagnostics["provenance"] = {
        **safe_diagnostic_mapping(diagnostics.get("provenance")),
        "temporal_query_intent_applied": True,
        "temporal_query_intent_reasons": intent.diagnostics()["temporal_query_intent_reasons"],
    }
    return replace(
        item,
        score=min(0.99, max(0.0, round(item.score + boost, 4))),
        diagnostics=normalize_context_diagnostics(diagnostics),
    )


def _event_sequence_direction_boost(*, intent: TemporalQueryIntent, text: str) -> float:
    if intent.after_event == intent.before_event:
        return 0.0
    variants = _query_variant_set(text)
    has_after = bool(variants.intersection(_AFTER_TERMS)) or _has_since_event_context(
        text,
        variants,
    )
    has_before = bool(variants.intersection(_BEFORE_TERMS)) or _has_until_event_context(
        text,
        variants,
    )
    if intent.after_event:
        if has_after:
            return 0.026
        if has_before and not intent.requests_change:
            return -0.024
    if intent.before_event:
        if has_before:
            return 0.026
        if has_after and not intent.requests_change:
            return -0.024
    return 0.0


def _event_sequence_direction_reason(*, intent: TemporalQueryIntent, boost: float) -> str:
    direction = "after" if intent.after_event else "before"
    if boost > 0:
        return f"query asks for {direction}-event sequence and item matches direction"
    return f"query asks for {direction}-event sequence and item conflicts with direction"


def _event_sequence_direction_code(*, intent: TemporalQueryIntent, boost: float) -> str:
    direction = "after" if intent.after_event else "before"
    suffix = "match" if boost > 0 else "conflict"
    return f"{direction}_event_sequence_{suffix}"


def _query_variant_set(query: str) -> frozenset[str]:
    variants: set[str] = set()
    for term in query_terms(query, min_chars=2, max_terms=32):
        variants.update(term.variants)
    for match in _TOKEN_RE.finditer(query):
        token = match.group(0).casefold().strip("_")
        if len(token) >= 2:
            variants.add(token)
    return frozenset(variants)


def _has_since_event_context(text: str, variants: frozenset[str]) -> bool:
    return bool(_SINCE_EVENT_RE.search(text)) and bool(
        variants.intersection(_EVENT_SEQUENCE_CONTEXT_TERMS)
    )


def _has_until_event_context(text: str, variants: frozenset[str]) -> bool:
    return bool(_UNTIL_EVENT_RE.search(text)) and bool(
        variants.intersection(_EVENT_SEQUENCE_CONTEXT_TERMS)
    )


def _temporal_hint_conflicts(
    *,
    intent: TemporalQueryIntent,
    temporal_hint_code: str,
) -> bool:
    if not temporal_hint_code or not intent.relative_time_hints:
        return False
    query_exact_dates = {
        hint for hint in intent.relative_time_hints if _is_exact_date_temporal_hint(hint)
    }
    if query_exact_dates:
        return _is_exact_date_temporal_hint(temporal_hint_code) and (
            temporal_hint_code not in query_exact_dates
        )
    if _is_exact_date_temporal_hint(temporal_hint_code):
        return False
    return not _temporal_hint_overlaps(intent=intent, temporal_hint_code=temporal_hint_code)


def _temporal_hint_matches(
    *,
    intent: TemporalQueryIntent,
    temporal_hint_code: str,
) -> bool:
    return bool(temporal_hint_code and temporal_hint_code in set(intent.relative_time_hints))


def _temporal_hint_is_contained_by_query(
    *,
    intent: TemporalQueryIntent,
    temporal_hint_code: str,
) -> bool:
    if not temporal_hint_code:
        return False
    query_hints = set(intent.relative_time_hints)
    return any(temporal_hint_code in _TEMPORAL_HINT_CHILDREN.get(hint, ()) for hint in query_hints)


def _temporal_hint_overlaps(
    *,
    intent: TemporalQueryIntent,
    temporal_hint_code: str,
) -> bool:
    if _temporal_hint_matches(intent=intent, temporal_hint_code=temporal_hint_code):
        return True
    if _temporal_hint_is_contained_by_query(
        intent=intent,
        temporal_hint_code=temporal_hint_code,
    ):
        return True
    parent = _TEMPORAL_HINT_PARENTS.get(temporal_hint_code)
    if parent is not None and parent in set(intent.relative_time_hints):
        return True
    return any(
        _TEMPORAL_HINT_PARENTS.get(hint) == temporal_hint_code
        for hint in intent.relative_time_hints
    )


def _is_exact_date_temporal_hint(code: str) -> bool:
    return code.startswith("date_")


def _temporal_hint_code(
    diagnostics: Mapping[str, object],
    provenance: Mapping[str, object],
) -> str:
    for source in (diagnostics, provenance):
        value = source.get("event_temporal_hint_code")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
