"""Context visibility policy helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from memo_stack_core.application.dto import BuildContextQuery
from memo_stack_core.domain.entities import MemoryFact


def thread_is_visible(item_thread_id: object | None, query_thread_id: object | None) -> bool:
    if query_thread_id is None:
        return True
    return item_thread_id is None or str(item_thread_id) == str(query_thread_id)


def is_graph_fact_visible(
    fact: MemoryFact,
    *,
    query: BuildContextQuery,
    profile_ids: tuple[str, ...],
    now: datetime | None = None,
) -> bool:
    return (
        str(fact.space_id) == str(query.space_id)
        and str(fact.profile_id) in profile_ids
        and fact.status.value == "active"
        and thread_is_visible(fact.thread_id, query.thread_id)
        and not fact_is_expired(fact, now=now)
    )


def is_context_fact_visible(
    fact: MemoryFact,
    *,
    query: BuildContextQuery,
    profile_ids: tuple[str, ...],
    now: datetime | None = None,
) -> bool:
    return is_graph_fact_visible(
        fact,
        query=query,
        profile_ids=profile_ids,
        now=now,
    ) and (fact.classification != "restricted")


def fact_is_expired(fact: MemoryFact, *, now: datetime | None = None) -> bool:
    if fact.expires_at is None:
        return False
    comparable_now = now or datetime.now(tz=UTC)
    comparable_expires_at = fact.expires_at
    if comparable_expires_at.tzinfo is None and comparable_now.tzinfo is not None:
        comparable_expires_at = comparable_expires_at.replace(tzinfo=comparable_now.tzinfo)
    elif comparable_expires_at.tzinfo is not None and comparable_now.tzinfo is None:
        comparable_now = comparable_now.replace(tzinfo=comparable_expires_at.tzinfo)
    return comparable_expires_at <= comparable_now
