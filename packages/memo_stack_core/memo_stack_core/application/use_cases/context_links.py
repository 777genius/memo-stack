"""Context-link creation and suggestion use cases."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from math import log

from memo_stack_core.application.dto import (
    ContextLinkCandidate,
    ContextLinkResult,
    ContextLinkSuggestionsResult,
    CreateContextLinkCommand,
    DeleteContextLinkCommand,
    ListContextLinksQuery,
    SuggestContextLinksCommand,
)
from memo_stack_core.domain.assets import MemoryContextLink, MemoryContextLinkId
from memo_stack_core.domain.errors import MemoryNotFoundError, MemoryValidationError
from memo_stack_core.ports.clock import ClockPort
from memo_stack_core.ports.ids import IdGeneratorPort
from memo_stack_core.ports.unit_of_work import UnitOfWorkFactoryPort, UnitOfWorkPort

_TERM_PATTERN = re.compile(r"[\w.@:/#-]+", re.UNICODE)
_MAX_CANDIDATE_PREVIEW = 220
_ALLOWED_ENDPOINT_STATUSES: dict[str, set[str]] = {
    "asset": {"stored"},
    "capture": {"accepted"},
    "chunk": {"active"},
    "document": {"active"},
    "fact": {"active", "disputed", "superseded"},
    "suggestion": {"pending", "approved", "rejected"},
}


class CreateContextLinkUseCase:
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

    async def execute(self, command: CreateContextLinkCommand) -> ContextLinkResult:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            await _assert_endpoint_visible(
                uow,
                endpoint_type=command.source_type,
                endpoint_id=command.source_id,
                space_id=str(command.space_id),
                memory_scope_id=str(command.memory_scope_id),
                role="source",
            )
            await _assert_endpoint_visible(
                uow,
                endpoint_type=command.target_type,
                endpoint_id=command.target_id,
                space_id=str(command.space_id),
                memory_scope_id=str(command.memory_scope_id),
                role="target",
            )
            existing = await uow.context_links.find_active(
                space_id=str(command.space_id),
                memory_scope_id=str(command.memory_scope_id),
                source_type=command.source_type,
                source_id=command.source_id,
                target_type=command.target_type,
                target_id=command.target_id,
                relation_type=command.relation_type,
            )
            if existing is not None:
                return ContextLinkResult(link=existing, duplicate=True)
            link = MemoryContextLink.create(
                link_id=MemoryContextLinkId(self._ids.new_id("ctxlink")),
                space_id=command.space_id,
                memory_scope_id=command.memory_scope_id,
                source_type=command.source_type,
                source_id=command.source_id,
                target_type=command.target_type,
                target_id=command.target_id,
                relation_type=command.relation_type,
                confidence=command.confidence,
                reason=command.reason,
                metadata=command.metadata,
                now=now,
            )
            saved = await uow.context_links.create(link)
            await uow.commit()
        return ContextLinkResult(link=saved)


class ListContextLinksUseCase:
    def __init__(self, *, uow_factory: UnitOfWorkFactoryPort) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: ListContextLinksQuery) -> list[MemoryContextLink]:
        async with self._uow_factory() as uow:
            return await uow.context_links.list_for_source(
                space_id=str(query.space_id),
                memory_scope_id=str(query.memory_scope_id),
                source_type=query.source_type,
                source_id=query.source_id,
                status=query.status,
                limit=query.limit,
            )


class DeleteContextLinkUseCase:
    def __init__(self, *, uow_factory: UnitOfWorkFactoryPort, clock: ClockPort) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, command: DeleteContextLinkCommand) -> ContextLinkResult:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            link = await uow.context_links.get_by_id(command.context_link_id)
            if link is None:
                raise MemoryNotFoundError("Context link not found")
            saved = await uow.context_links.save(link.delete(now=now))
            await uow.commit()
        return ContextLinkResult(link=saved)


class SuggestContextLinksUseCase:
    def __init__(self, *, uow_factory: UnitOfWorkFactoryPort, clock: ClockPort) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, command: SuggestContextLinksCommand) -> ContextLinkSuggestionsResult:
        query_text = command.text.strip()
        diagnostics: dict[str, object] = {
            "resolver_version": "context-link-rule-v1",
            "source_type": command.source_type,
            "source_id": command.source_id,
        }
        async with self._uow_factory() as uow:
            source_thread_id = str(command.thread_id) if command.thread_id else None
            if command.source_type == "capture" and command.source_id:
                capture = await uow.captures.get_by_id(command.source_id)
                if capture is not None and _same_scope(capture, command):
                    query_text = _join_text(query_text, capture.text)
                    if capture.thread_id:
                        source_thread_id = str(capture.thread_id)
            facts = await uow.facts.find_active(
                space_id=str(command.space_id),
                memory_scope_ids=(str(command.memory_scope_id),),
                thread_id=source_thread_id,
                query=query_text,
                limit=max(command.limit * 3, 12),
            )
            recent_facts = await uow.facts.list_for_scope(
                space_id=str(command.space_id),
                memory_scope_id=str(command.memory_scope_id),
                thread_id=source_thread_id,
                status="active",
                limit=max(command.limit, 8),
            )
            captures = await uow.captures.list_for_scope(
                space_id=str(command.space_id),
                memory_scope_id=str(command.memory_scope_id),
                status="accepted",
                consolidation_status=None,
                limit=max(command.limit, 8),
            )
            suggestions = await uow.suggestions.list_for_scope(
                space_id=str(command.space_id),
                memory_scope_id=str(command.memory_scope_id),
                status="pending",
                operation=None,
                category=None,
                tag=None,
                limit=max(command.limit, 8),
            )
            assets = await uow.assets.list_for_scope(
                space_id=str(command.space_id),
                memory_scope_id=str(command.memory_scope_id),
                thread_id=source_thread_id,
                status="stored",
                limit=max(command.limit, 8),
            )

        terms = _terms(query_text)
        candidates: list[ContextLinkCandidate] = []
        seen: set[tuple[str, str]] = set()
        for fact in [*facts, *recent_facts]:
            key = ("fact", str(fact.id))
            if key in seen or _is_same_source(key, command):
                continue
            seen.add(key)
            score, reasons = _score_text_candidate(
                query_terms=terms,
                target_text=fact.text,
                updated_at=fact.updated_at,
                now=self._clock.now(),
                base=52,
            )
            if fact.thread_id and str(fact.thread_id) == source_thread_id:
                score += 12
                reasons.append("same thread")
            if fact.category:
                reasons.append(f"category:{fact.category}")
            candidates.append(
                _candidate(
                    target_type="fact",
                    target_id=str(fact.id),
                    label=fact.category or fact.kind.value,
                    preview=fact.text,
                    score=score,
                    reasons=reasons,
                    metadata={"version": fact.version, "tags": list(fact.tags)},
                )
            )
        for capture in captures:
            key = ("capture", str(capture.id))
            if key in seen or _is_same_source(key, command):
                continue
            seen.add(key)
            score, reasons = _score_text_candidate(
                query_terms=terms,
                target_text=capture.text,
                updated_at=capture.created_at,
                now=self._clock.now(),
                base=36,
            )
            candidates.append(
                _candidate(
                    target_type="capture",
                    target_id=str(capture.id),
                    label=capture.event_type,
                    preview=capture.text,
                    score=score,
                    reasons=reasons,
                    metadata={"source_agent": capture.source_agent},
                )
            )
        for suggestion in suggestions:
            key = ("suggestion", str(suggestion.id))
            if key in seen or _is_same_source(key, command):
                continue
            seen.add(key)
            score, reasons = _score_text_candidate(
                query_terms=terms,
                target_text=suggestion.candidate_text,
                updated_at=suggestion.created_at,
                now=self._clock.now(),
                base=42,
            )
            candidates.append(
                _candidate(
                    target_type="suggestion",
                    target_id=str(suggestion.id),
                    label=suggestion.operation.value,
                    preview=suggestion.candidate_text,
                    score=score,
                    reasons=reasons,
                    metadata={"confidence": suggestion.confidence.value},
                )
            )
        for asset in assets:
            key = ("asset", str(asset.id))
            if key in seen or _is_same_source(key, command):
                continue
            seen.add(key)
            target_text = f"{asset.filename} {asset.content_type}"
            score, reasons = _score_text_candidate(
                query_terms=terms,
                target_text=target_text,
                updated_at=asset.created_at,
                now=self._clock.now(),
                base=34,
            )
            candidates.append(
                _candidate(
                    target_type="asset",
                    target_id=str(asset.id),
                    label=asset.filename,
                    preview=target_text,
                    score=score,
                    reasons=reasons,
                    metadata={"content_type": asset.content_type, "byte_size": asset.byte_size},
                )
            )

        ranked = sorted(
            candidates,
            key=lambda item: (-item.score, item.target_type, item.target_id),
        )
        diagnostics["query_terms"] = list(terms)
        diagnostics["candidate_count"] = len(ranked)
        return ContextLinkSuggestionsResult(
            candidates=tuple(ranked[: command.limit]),
            diagnostics=diagnostics,
        )


async def _assert_endpoint_visible(
    uow: UnitOfWorkPort,
    *,
    endpoint_type: str,
    endpoint_id: str,
    space_id: str,
    memory_scope_id: str,
    role: str,
) -> None:
    normalized_type = endpoint_type.strip().lower()
    allowed_statuses = _ALLOWED_ENDPOINT_STATUSES.get(normalized_type)
    if allowed_statuses is None:
        return

    entity = await _load_endpoint(uow, endpoint_type=normalized_type, endpoint_id=endpoint_id)
    if entity is None:
        raise MemoryValidationError(f"Context link {role} does not exist or is not visible")
    if str(entity.space_id) != space_id or str(entity.memory_scope_id) != memory_scope_id:
        raise MemoryValidationError(f"Context link {role} does not belong to scope")
    status = _status_value(getattr(entity, "status", None))
    if status not in allowed_statuses:
        raise MemoryValidationError(f"Context link {role} status is not linkable")


async def _load_endpoint(
    uow: UnitOfWorkPort,
    *,
    endpoint_type: str,
    endpoint_id: str,
) -> object | None:
    if endpoint_type == "asset":
        return await uow.assets.get_by_id(endpoint_id)
    if endpoint_type == "capture":
        return await uow.captures.get_by_id(endpoint_id)
    if endpoint_type == "chunk":
        return await uow.chunks.get_by_id(endpoint_id)
    if endpoint_type == "document":
        return await uow.documents.get_by_id(endpoint_id)
    if endpoint_type == "fact":
        return await uow.facts.get_by_id(endpoint_id)
    if endpoint_type == "suggestion":
        return await uow.suggestions.get_by_id(endpoint_id)
    return None


def _status_value(status: object) -> str:
    value = getattr(status, "value", status)
    return str(value)


def _same_scope(entity: object, command: SuggestContextLinksCommand) -> bool:
    return str(entity.space_id) == str(command.space_id) and str(entity.memory_scope_id) == str(
        command.memory_scope_id
    )


def _join_text(left: str, right: str) -> str:
    return " ".join(part for part in (left.strip(), right.strip()) if part)


def _terms(text: str) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for raw in _TERM_PATTERN.findall(text.lower()):
        term = raw.strip("._-:/#")
        if len(term) >= 3 and term not in seen:
            seen[term] = None
    return tuple(seen)


def _score_text_candidate(
    *,
    query_terms: tuple[str, ...],
    target_text: str,
    updated_at: datetime,
    now: datetime,
    base: float,
) -> tuple[float, list[str]]:
    score = base
    reasons: list[str] = []
    lowered = target_text.lower()
    hits = [term for term in query_terms if term in lowered]
    if hits:
        score += min(28.0, 9.0 * len(hits))
        reasons.append("matching text")
    age_hours = _age_hours(updated_at, now)
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
    return min(score, 99.0), reasons


def _candidate(
    *,
    target_type: str,
    target_id: str,
    label: str,
    preview: str,
    score: float,
    reasons: list[str],
    metadata: dict[str, object],
) -> ContextLinkCandidate:
    return ContextLinkCandidate(
        target_type=target_type,
        target_id=target_id,
        label=label[:120],
        preview=preview[:_MAX_CANDIDATE_PREVIEW],
        score=round(score, 2),
        tier=_tier(score),
        reasons=tuple(dict.fromkeys(reasons)),
        metadata=metadata,
    )


def _tier(score: float) -> str:
    if score >= 75:
        return "likely"
    if score >= 55:
        return "possible"
    return "weak"


def _age_hours(value: datetime, now: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return max((now - value).total_seconds() / 3600, 0.0)


def _is_same_source(
    key: tuple[str, str],
    command: SuggestContextLinksCommand,
) -> bool:
    return key[0] == command.source_type and key[1] == command.source_id
