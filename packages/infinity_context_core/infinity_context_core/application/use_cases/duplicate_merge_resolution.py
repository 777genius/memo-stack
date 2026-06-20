"""Resolve duplicate fact merge reviews."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

from infinity_context_core.application.dto import ResolveDuplicateMergeCommand, SuggestionResult
from infinity_context_core.application.review_payloads import DUPLICATE_FACT_MERGE_REVIEW_KIND
from infinity_context_core.application.sensitive_text import redact_sensitive_text
from infinity_context_core.domain.entities import (
    FactStatus,
    MemoryFact,
    MemoryFactId,
    MemorySuggestion,
    SuggestionStatus,
    TrustLevel,
)
from infinity_context_core.domain.errors import (
    MemoryConflictError,
    MemoryNotFoundError,
    MemoryValidationError,
)
from infinity_context_core.domain.events import OutboxEvent
from infinity_context_core.ports.clock import ClockPort
from infinity_context_core.ports.ids import IdGeneratorPort
from infinity_context_core.ports.unit_of_work import UnitOfWorkFactoryPort

_TRUST_RANK = {TrustLevel.LOW: 1, TrustLevel.MEDIUM: 2, TrustLevel.HIGH: 3}
_ASSISTANT_SOURCES = {"ai_response", "assistant_answer", "assistant_summary"}
_DUPLICATE_MERGE_ACTION_ALIASES = {
    "merge_source_refs": "merge_source_refs",
    "merge": "merge_source_refs",
    "approve_merge": "merge_source_refs",
    "keep_separate_fact": "keep_separate_fact",
    "keep_separate": "keep_separate_fact",
    "create_separate_fact": "keep_separate_fact",
    "reject_candidate": "reject_candidate",
    "reject_duplicate": "reject_candidate",
    "expire_candidate": "expire_candidate",
    "expire_duplicate": "expire_candidate",
}


class ResolveDuplicateMergeUseCase:
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

    async def execute(self, command: ResolveDuplicateMergeCommand) -> SuggestionResult:
        action = _normalize_duplicate_merge_action(command.action)
        async with self._uow_factory() as uow:
            suggestion = await uow.suggestions.get_for_update(command.suggestion_id)
            if suggestion is None:
                raise MemoryNotFoundError("Suggestion not found")
            payload = _duplicate_fact_merge_review_payload(suggestion)
            if suggestion.status != SuggestionStatus.PENDING:
                raise MemoryConflictError("Only pending duplicate merge suggestion can be resolved")
            now = self._clock.now()
            reason = _duplicate_merge_resolution_reason(
                action=action,
                reason=command.reason,
                fallback=suggestion.safe_reason,
            )

            if action == "reject_candidate":
                saved = await uow.suggestions.save(
                    _annotate_duplicate_merge_resolution(
                        suggestion,
                        action=action,
                        effect="keep_existing_fact_without_candidate_source_refs",
                        now=now,
                        reason=reason,
                    ).reject(now=now, reason=reason)
                )
                await uow.commit()
                return SuggestionResult(suggestion=saved)

            if action == "expire_candidate":
                saved = await uow.suggestions.save(
                    _annotate_duplicate_merge_resolution(
                        suggestion,
                        action=action,
                        effect="hide_pending_duplicate_merge_review",
                        now=now,
                        reason=reason,
                    ).expire(now=now, reason=reason)
                )
                await uow.commit()
                return SuggestionResult(suggestion=saved)

            _ensure_duplicate_candidate_has_independent_source(suggestion)
            duplicate_fact = await _load_duplicate_merge_fact_for_resolution(
                uow,
                suggestion=suggestion,
            )
            expected_version = _duplicate_merge_target_version(payload, suggestion)
            if duplicate_fact.version != expected_version:
                raise MemoryConflictError("Stale duplicate fact version")

            if action == "merge_source_refs":
                return await _merge_source_refs(
                    uow,
                    suggestion=suggestion,
                    duplicate_fact=duplicate_fact,
                    expected_version=expected_version,
                    reason=reason,
                    now=now,
                    force=command.force,
                )

            return await _keep_candidate_separate(
                uow,
                ids=self._ids,
                suggestion=suggestion,
                duplicate_fact=duplicate_fact,
                reason=reason,
                now=now,
            )


async def _merge_source_refs(
    uow: Any,
    *,
    suggestion: MemorySuggestion,
    duplicate_fact: MemoryFact,
    expected_version: int,
    reason: str,
    now: datetime,
    force: bool,
) -> SuggestionResult:
    if _TRUST_RANK[suggestion.trust_level] < _TRUST_RANK[duplicate_fact.trust_level] and not force:
        raise MemoryConflictError("Weak duplicate suggestion cannot merge stronger fact")
    fact = duplicate_fact.merge_source_refs(
        expected_version=expected_version,
        source_refs=suggestion.source_refs,
        reason=reason,
        now=now,
    )
    fact = await uow.facts.save(fact)
    reviewed = _annotate_duplicate_merge_resolution(
        suggestion,
        action="merge_source_refs",
        effect="merge_source_refs_into_existing_fact",
        now=now,
        reason=reason,
        duplicate_fact=duplicate_fact,
        applied_fact=fact,
    ).approve(now=now, reason=reason)
    saved = await uow.suggestions.save(reviewed)
    await _enqueue_fact_projection(uow, fact)
    await uow.commit()
    return SuggestionResult(suggestion=saved, fact=fact, indexing_status="pending")


async def _keep_candidate_separate(
    uow: Any,
    *,
    ids: IdGeneratorPort,
    suggestion: MemorySuggestion,
    duplicate_fact: MemoryFact,
    reason: str,
    now: datetime,
) -> SuggestionResult:
    fact = MemoryFact.create(
        fact_id=MemoryFactId(ids.new_id("fact")),
        space_id=suggestion.space_id,
        memory_scope_id=suggestion.memory_scope_id,
        text=suggestion.candidate_text,
        kind=suggestion.kind,
        source_refs=suggestion.source_refs,
        confidence=suggestion.confidence,
        trust_level=suggestion.trust_level,
        category=suggestion.category,
        tags=suggestion.tags,
        ttl_policy=suggestion.ttl_policy,
        expires_at=suggestion.expires_at,
        now=now,
    )
    fact = await uow.facts.create(fact)
    reviewed = _annotate_duplicate_merge_resolution(
        suggestion,
        action="keep_separate_fact",
        effect="create_new_fact_keep_existing_fact",
        now=now,
        reason=reason,
        duplicate_fact=duplicate_fact,
        applied_fact=fact,
    ).approve(now=now, reason=reason)
    saved = await uow.suggestions.save(reviewed)
    await _enqueue_fact_projection(uow, fact)
    await uow.commit()
    return SuggestionResult(suggestion=saved, fact=fact, indexing_status="pending")


def _normalize_duplicate_merge_action(action: str) -> str:
    normalized = action.strip().lower()
    resolved = _DUPLICATE_MERGE_ACTION_ALIASES.get(normalized)
    if resolved is None:
        raise MemoryValidationError("Unknown duplicate merge resolution action")
    return resolved


def _duplicate_fact_merge_review_payload(suggestion: MemorySuggestion) -> dict[str, object]:
    payload = dict(suggestion.review_payload or {})
    if payload.get("review_kind") != DUPLICATE_FACT_MERGE_REVIEW_KIND:
        raise MemoryValidationError("Suggestion is not a duplicate merge review")
    if suggestion.target_fact_id is None:
        raise MemoryValidationError("Duplicate merge review requires target_fact_id")
    _duplicate_merge_target_version(payload, suggestion)
    return payload


def _duplicate_merge_target_version(
    payload: dict[str, object],
    suggestion: MemorySuggestion,
) -> int:
    value = payload.get("duplicate_fact_version")
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit() and int(value) > 0:
        return int(value)
    if suggestion.target_fact_version is not None and suggestion.target_fact_version > 0:
        return suggestion.target_fact_version
    raise MemoryValidationError("Duplicate merge review requires duplicate_fact_version")


async def _load_duplicate_merge_fact_for_resolution(
    uow: Any,
    *,
    suggestion: MemorySuggestion,
) -> MemoryFact:
    if suggestion.target_fact_id is None:
        raise MemoryValidationError("Duplicate merge review requires target_fact_id")
    fact = await uow.facts.get_for_update(str(suggestion.target_fact_id))
    if fact is None:
        raise MemoryNotFoundError("Duplicate fact not found")
    if fact.space_id != suggestion.space_id or fact.memory_scope_id != suggestion.memory_scope_id:
        raise MemoryConflictError("Duplicate fact scope mismatch")
    if fact.status == FactStatus.DELETED:
        raise MemoryConflictError("Deleted duplicate fact cannot be resolved")
    return fact


def _ensure_duplicate_candidate_has_independent_source(suggestion: MemorySuggestion) -> None:
    if not any(ref.source_type not in _ASSISTANT_SOURCES for ref in suggestion.source_refs):
        raise MemoryValidationError("Duplicate merge resolution requires non-assistant source refs")


def _duplicate_merge_resolution_reason(
    *,
    action: str,
    reason: str | None,
    fallback: str,
) -> str:
    base = (reason or fallback or "duplicate merge resolved").strip()
    text = f"duplicate_merge_resolution:{action}; {base}"
    return redact_sensitive_text(text)[:320]


def _annotate_duplicate_merge_resolution(
    suggestion: MemorySuggestion,
    *,
    action: str,
    effect: str,
    now: datetime,
    reason: str,
    duplicate_fact: MemoryFact | None = None,
    applied_fact: MemoryFact | None = None,
) -> MemorySuggestion:
    payload = dict(suggestion.review_payload or {})
    updates: dict[str, object] = {
        "resolved_duplicate_action": action,
        "resolved_duplicate_effect": effect,
        "resolved_at": now.isoformat(),
        "resolution_reason": redact_sensitive_text(reason)[:320],
    }
    if duplicate_fact is not None:
        updates["resolved_duplicate_fact_id"] = str(duplicate_fact.id)
        updates["resolved_duplicate_fact_version"] = duplicate_fact.version
        updates["resolved_duplicate_fact_status"] = duplicate_fact.status.value
    if applied_fact is not None:
        updates["resolved_fact_id"] = str(applied_fact.id)
        updates["resolved_fact_version"] = applied_fact.version
        updates["resolved_fact_status"] = applied_fact.status.value
    payload.update(updates)
    return replace(suggestion, review_payload=payload, updated_at=now)


async def _enqueue_fact_projection(uow: Any, fact: MemoryFact) -> None:
    await uow.outbox.enqueue(
        OutboxEvent(
            event_type="graph.upsert_fact",
            aggregate_type="fact",
            aggregate_id=str(fact.id),
            aggregate_version=fact.version,
            payload={"fact_id": str(fact.id), "version": fact.version},
        )
    )
