"""Build read-only memory management insights for a scope."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

from memo_stack_core.application.dto import (
    BuildMemoryInsightsQuery,
    MemoryInsightActionItem,
    MemoryInsightsResult,
)
from memo_stack_core.application.sensitive_text import redact_sensitive_text
from memo_stack_core.domain.capture import ConsolidationStatus
from memo_stack_core.domain.entities import (
    FactStatus,
    MemoryDocument,
    MemoryFact,
    MemorySuggestion,
    ProfileId,
)
from memo_stack_core.ports.clock import ClockPort
from memo_stack_core.ports.ids import IdGeneratorPort
from memo_stack_core.ports.unit_of_work import UnitOfWorkFactoryPort

_FACT_STATUSES = ("active", "superseded", "disputed", "deleted")
_SUGGESTION_STATUSES = ("pending", "approved", "rejected", "expired")
_CAPTURE_CONSOLIDATION_STATUSES = (
    "pending",
    "running",
    "retry_pending",
    "dead",
    "skipped",
    "consolidated",
    "not_required",
)
_CAPTURE_ATTENTION_STATUSES = {
    ConsolidationStatus.PENDING.value,
    ConsolidationStatus.RETRY_PENDING.value,
    ConsolidationStatus.DEAD.value,
}


@dataclass(frozen=True)
class _ProfileSample:
    profile_id: str
    facts: tuple[MemoryFact, ...]
    documents: tuple[MemoryDocument, ...]
    document_chunk_counts: dict[str, int]
    suggestions: tuple[MemorySuggestion, ...]
    capture_status_counts: dict[str, int]


class BuildMemoryInsightsUseCase:
    """Summarize memory quality and maintenance needs without mutating state."""

    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactoryPort,
        clock: ClockPort,
        ids: IdGeneratorPort,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._ids = ids

    async def execute(self, query: BuildMemoryInsightsQuery) -> MemoryInsightsResult:
        now = self._clock.now()
        samples = await self._load_samples(query)
        metrics = _metrics(samples=samples, now=now)
        taxonomy = _taxonomy(samples)
        action_items = _action_items(samples=samples, now=now)
        return MemoryInsightsResult(
            insights_id=self._ids.new_id("ins"),
            generated_at=now,
            scope={
                "space_id": str(query.space_id),
                "profile_ids": [str(profile_id) for profile_id in query.profile_ids],
                "thread_id": str(query.thread_id) if query.thread_id else None,
            },
            health_score=_health_score(metrics),
            metrics=metrics,
            taxonomy=taxonomy,
            action_items=tuple(action_items[:50]),
            diagnostics={
                "evidence_only": True,
                "read_only": True,
                "sample_limited": True,
                "max_facts_per_profile": query.max_facts,
                "max_documents_per_profile": query.max_documents,
                "max_suggestions_per_profile": query.max_suggestions,
                "max_captures_per_profile": query.max_captures,
                "profiles_sampled": len(samples),
            },
        )

    async def _load_samples(
        self,
        query: BuildMemoryInsightsQuery,
    ) -> tuple[_ProfileSample, ...]:
        samples: list[_ProfileSample] = []
        async with self._uow_factory() as uow:
            for profile_id in query.profile_ids:
                facts = await self._load_facts(query, profile_id=profile_id, uow=uow)
                documents = tuple(
                    await uow.documents.list_for_scope(
                        space_id=str(query.space_id),
                        profile_id=str(profile_id),
                        thread_id=str(query.thread_id) if query.thread_id else None,
                        status=None,
                        limit=query.max_documents,
                    )
                )
                chunk_counts: dict[str, int] = {}
                for document in documents:
                    chunks = await uow.documents.list_chunks(str(document.id), limit=501)
                    chunk_counts[str(document.id)] = min(len(chunks), 500)
                suggestions = await self._load_suggestions(query, profile_id=profile_id, uow=uow)
                capture_counts = await self._load_capture_counts(
                    query,
                    profile_id=profile_id,
                    uow=uow,
                )
                samples.append(
                    _ProfileSample(
                        profile_id=str(profile_id),
                        facts=tuple(facts),
                        documents=documents,
                        document_chunk_counts=chunk_counts,
                        suggestions=tuple(suggestions),
                        capture_status_counts=capture_counts,
                    )
                )
        return tuple(samples)

    async def _load_facts(
        self,
        query: BuildMemoryInsightsQuery,
        *,
        profile_id: ProfileId,
        uow: object,
    ) -> tuple[MemoryFact, ...]:
        facts: list[MemoryFact] = []
        for status in _FACT_STATUSES:
            facts.extend(
                await uow.facts.list_for_scope(
                    space_id=str(query.space_id),
                    profile_id=str(profile_id),
                    thread_id=str(query.thread_id) if query.thread_id else None,
                    status=status,
                    limit=query.max_facts,
                )
            )
        status_none_facts = await uow.facts.list_for_scope(
            space_id=str(query.space_id),
            profile_id=str(profile_id),
            thread_id=str(query.thread_id) if query.thread_id else None,
            status=None,
            limit=query.max_facts,
        )
        return _dedupe_facts((*facts, *status_none_facts))

    async def _load_suggestions(
        self,
        query: BuildMemoryInsightsQuery,
        *,
        profile_id: ProfileId,
        uow: object,
    ) -> tuple[MemorySuggestion, ...]:
        suggestions: list[MemorySuggestion] = []
        for status in _SUGGESTION_STATUSES:
            suggestions.extend(
                await uow.suggestions.list_for_scope(
                    space_id=str(query.space_id),
                    profile_id=str(profile_id),
                    status=status,
                    operation=None,
                    category=None,
                    tag=None,
                    limit=query.max_suggestions,
                )
            )
        return _dedupe_suggestions(tuple(suggestions))

    async def _load_capture_counts(
        self,
        query: BuildMemoryInsightsQuery,
        *,
        profile_id: ProfileId,
        uow: object,
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for consolidation_status in _CAPTURE_CONSOLIDATION_STATUSES:
            captures = await uow.captures.list_for_scope(
                space_id=str(query.space_id),
                profile_id=str(profile_id),
                status=None,
                consolidation_status=consolidation_status,
                limit=query.max_captures,
            )
            counts[consolidation_status] = len(captures)
        return counts


def _metrics(*, samples: tuple[_ProfileSample, ...], now: datetime) -> dict[str, object]:
    fact_status_counts: Counter[str] = Counter()
    suggestion_status_counts: Counter[str] = Counter()
    suggestion_operation_counts: Counter[str] = Counter()
    capture_status_counts: Counter[str] = Counter()
    active_facts = 0
    expired_active_facts = 0
    uncategorized_active_facts = 0
    untagged_active_facts = 0
    active_documents = 0
    documents_without_chunks = 0
    total_document_chunks = 0

    for sample in samples:
        for fact in sample.facts:
            fact_status_counts[fact.status.value] += 1
            if fact.status == FactStatus.ACTIVE:
                active_facts += 1
                if _is_expired(fact.expires_at, now):
                    expired_active_facts += 1
                if not fact.category:
                    uncategorized_active_facts += 1
                if not fact.tags:
                    untagged_active_facts += 1
        for document in sample.documents:
            if document.status.value == "active":
                active_documents += 1
                chunk_count = sample.document_chunk_counts.get(str(document.id), 0)
                total_document_chunks += chunk_count
                if chunk_count == 0:
                    documents_without_chunks += 1
        for suggestion in sample.suggestions:
            suggestion_status_counts[suggestion.status.value] += 1
            suggestion_operation_counts[suggestion.operation.value] += 1
        capture_status_counts.update(sample.capture_status_counts)

    attention_captures = sum(
        count
        for status, count in capture_status_counts.items()
        if status in _CAPTURE_ATTENTION_STATUSES
    )
    return {
        "profiles": len(samples),
        "facts": {
            "total_sampled": sum(fact_status_counts.values()),
            "active": active_facts,
            "expired_active": expired_active_facts,
            "uncategorized_active": uncategorized_active_facts,
            "untagged_active": untagged_active_facts,
            "by_status": dict(sorted(fact_status_counts.items())),
        },
        "documents": {
            "active": active_documents,
            "chunks_sampled": total_document_chunks,
            "without_chunks": documents_without_chunks,
        },
        "suggestions": {
            "total_sampled": sum(suggestion_status_counts.values()),
            "pending": suggestion_status_counts.get("pending", 0),
            "by_status": dict(sorted(suggestion_status_counts.items())),
            "by_operation": dict(sorted(suggestion_operation_counts.items())),
        },
        "captures": {
            "attention_needed": attention_captures,
            "by_consolidation_status": dict(sorted(capture_status_counts.items())),
        },
    }


def _taxonomy(samples: tuple[_ProfileSample, ...]) -> dict[str, object]:
    categories: Counter[str] = Counter()
    tags: Counter[str] = Counter()
    ttl_policies: Counter[str] = Counter()
    for sample in samples:
        for fact in sample.facts:
            if fact.status != FactStatus.ACTIVE:
                continue
            categories[fact.category or "uncategorized"] += 1
            tags.update(fact.tags)
            if fact.ttl_policy:
                ttl_policies[fact.ttl_policy] += 1
    return {
        "top_categories": _top_counts(categories),
        "top_tags": _top_counts(tags),
        "ttl_policies": _top_counts(ttl_policies),
    }


def _action_items(
    *,
    samples: tuple[_ProfileSample, ...],
    now: datetime,
) -> list[MemoryInsightActionItem]:
    items: list[MemoryInsightActionItem] = []
    for sample in samples:
        pending_suggestions = [
            suggestion for suggestion in sample.suggestions if suggestion.status.value == "pending"
        ]
        if pending_suggestions:
            items.append(
                _item(
                    severity="warning",
                    action="review_pending_suggestions",
                    target_type="suggestion_queue",
                    target_id=None,
                    profile_id=sample.profile_id,
                    reason=f"{len(pending_suggestions)} pending suggestions need review.",
                    metadata={"pending_count": len(pending_suggestions)},
                )
            )
        for suggestion in pending_suggestions[:10]:
            items.append(
                _item(
                    severity="info",
                    action="review_suggestion",
                    target_type="suggestion",
                    target_id=str(suggestion.id),
                    profile_id=sample.profile_id,
                    reason=f"Pending {suggestion.operation.value} suggestion.",
                    preview=_preview(suggestion.candidate_text),
                    metadata={
                        "operation": suggestion.operation.value,
                        "category": suggestion.category,
                        "tags": list(suggestion.tags),
                    },
                )
            )
        expired = [
            fact
            for fact in sample.facts
            if fact.status == FactStatus.ACTIVE
            and _is_expired(fact.expires_at, now)
        ]
        for fact in expired[:10]:
            items.append(
                _item(
                    severity="warning",
                    action="review_expired_fact",
                    target_type="fact",
                    target_id=str(fact.id),
                    profile_id=sample.profile_id,
                    reason="Active fact has expired and is hidden from active recall.",
                    preview=_preview(fact.text),
                    metadata={
                        "ttl_policy": fact.ttl_policy,
                        "expires_at": fact.expires_at.isoformat()
                        if fact.expires_at
                        else None,
                    },
                )
            )
        uncategorized = [
            fact
            for fact in sample.facts
            if fact.status == FactStatus.ACTIVE and not fact.category
        ]
        if len(uncategorized) >= 5:
            items.append(
                _item(
                    severity="info",
                    action="backfill_fact_taxonomy",
                    target_type="fact_set",
                    target_id=None,
                    profile_id=sample.profile_id,
                    reason=f"{len(uncategorized)} active facts have no category.",
                    metadata={"uncategorized_active_count": len(uncategorized)},
                )
            )
        for document in sample.documents:
            if (
                document.status.value == "active"
                and sample.document_chunk_counts.get(str(document.id), 0) == 0
            ):
                items.append(
                    _item(
                        severity="warning",
                        action="process_document",
                        target_type="document",
                        target_id=str(document.id),
                        profile_id=sample.profile_id,
                        reason="Active document has no indexed chunks.",
                        preview=_preview(document.title),
                    )
                )
        dead_captures = sample.capture_status_counts.get(ConsolidationStatus.DEAD.value, 0)
        if dead_captures:
            items.append(
                _item(
                    severity="critical",
                    action="inspect_dead_captures",
                    target_type="capture_queue",
                    target_id=None,
                    profile_id=sample.profile_id,
                    reason=f"{dead_captures} capture consolidations are dead.",
                    metadata={"dead_capture_count": dead_captures},
                )
            )
    return sorted(items, key=_action_sort_key)


def _health_score(metrics: dict[str, object]) -> float:
    facts = metrics["facts"]
    documents = metrics["documents"]
    suggestions = metrics["suggestions"]
    captures = metrics["captures"]
    penalty = 0.0
    penalty += min(25.0, float(suggestions["pending"]) * 1.2)
    penalty += min(20.0, float(facts["expired_active"]) * 2.0)
    penalty += min(15.0, float(captures["attention_needed"]) * 1.5)
    penalty += min(12.0, float(documents["without_chunks"]) * 2.0)
    if facts["active"]:
        uncategorized_ratio = float(facts["uncategorized_active"]) / float(facts["active"])
        penalty += min(10.0, uncategorized_ratio * 10.0)
    return round(max(0.0, 100.0 - penalty), 2)


def _item(
    *,
    severity: str,
    action: str,
    target_type: str,
    target_id: str | None,
    profile_id: str,
    reason: str,
    preview: str | None = None,
    metadata: dict[str, object] | None = None,
) -> MemoryInsightActionItem:
    stable = "|".join((severity, action, target_type, str(target_id), profile_id, reason))
    digest = hashlib.sha256(stable.encode("utf-8")).hexdigest()[:24]
    return MemoryInsightActionItem(
        id=f"mai_{digest}",
        severity=severity,
        action=action,
        target_type=target_type,
        target_id=target_id,
        profile_id=profile_id,
        reason=reason,
        preview=preview,
        metadata=metadata or {},
    )


def _action_sort_key(item: MemoryInsightActionItem) -> tuple[int, str, str]:
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    return (
        severity_rank.get(item.severity, 3),
        item.profile_id,
        item.target_id or item.action,
    )


def _dedupe_facts(facts: tuple[MemoryFact, ...]) -> tuple[MemoryFact, ...]:
    by_id: dict[str, MemoryFact] = {}
    for fact in facts:
        by_id[str(fact.id)] = fact
    return tuple(by_id.values())


def _dedupe_suggestions(
    suggestions: tuple[MemorySuggestion, ...],
) -> tuple[MemorySuggestion, ...]:
    by_id: dict[str, MemorySuggestion] = {}
    for suggestion in suggestions:
        by_id[str(suggestion.id)] = suggestion
    return tuple(by_id.values())


def _is_expired(expires_at: datetime | None, now: datetime) -> bool:
    if expires_at is None:
        return False
    safe_expires_at = expires_at
    safe_now = now
    if safe_expires_at.tzinfo is None:
        safe_expires_at = safe_expires_at.replace(tzinfo=UTC)
    if safe_now.tzinfo is None:
        safe_now = safe_now.replace(tzinfo=UTC)
    return safe_expires_at <= safe_now


def _preview(value: str, *, max_chars: int = 240) -> str:
    redacted = redact_sensitive_text(value, marker="[redacted]")
    return redacted if len(redacted) <= max_chars else redacted[:max_chars] + "...[truncated]"


def _top_counts(counter: Counter[str], *, limit: int = 20) -> list[dict[str, object]]:
    return [
        {"value": value, "count": count}
        for value, count in counter.most_common(limit)
    ]
