"""Context-link suggestion and approval API."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from memo_stack_core.application import (
    ContextLinkSuggestionVisibleFilter,
    CreateContextLinkCommand,
    DeleteContextLinkCommand,
    ListContextLinksQuery,
    ListContextLinkSuggestionsQuery,
    ReviewContextLinkSuggestionBatchItemCommand,
    ReviewContextLinkSuggestionCommand,
    ReviewContextLinkSuggestionsBatchCommand,
    SuggestContextLinksCommand,
    UpdateContextLinkCommand,
)
from memo_stack_core.domain.assets import MemoryContextLink, MemoryContextLinkSuggestion
from memo_stack_core.domain.errors import MemoryValidationError
from pydantic import BaseModel, ConfigDict, Field

from memo_stack_server.api.auth import require_service_token
from memo_stack_server.api.dependencies import get_container
from memo_stack_server.api.policy import ensure_server_writes_enabled
from memo_stack_server.api.public_payload import (
    safe_public_metadata,
    safe_public_reason,
    safe_public_text,
)
from memo_stack_server.api.v1.scope_resolution import (
    resolve_existing_single_scope,
    resolve_single_scope,
)
from memo_stack_server.composition import Container

router = APIRouter(
    tags=["context-links"],
    dependencies=[Depends(require_service_token)],
)

_MAX_PUBLIC_REVIEW_AUDIT_EVENTS = 10
_PUBLIC_REVIEW_AUDIT_FIELDS = {
    "event_type": 120,
    "suggestion_id": 160,
    "space_id": 80,
    "memory_scope_id": 80,
    "source_type": 80,
    "source_id": 160,
    "target_type": 80,
    "target_id": 160,
    "relation_type": 80,
    "action": 16,
    "previous_status": 40,
    "new_status": 40,
    "reviewed_at": 80,
    "policy_version": 120,
    "reason": 320,
}


class SuggestContextLinksRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    space_id: str | None = Field(default=None, min_length=1, max_length=80)
    memory_scope_id: str | None = Field(default=None, min_length=1, max_length=80)
    thread_id: str | None = Field(default=None, min_length=1, max_length=80)
    space_slug: str | None = Field(default=None, min_length=1, max_length=160)
    memory_scope_external_ref: str | None = Field(default=None, min_length=1, max_length=200)
    thread_external_ref: str | None = Field(default=None, min_length=1, max_length=200)
    text: str = Field(default="", max_length=20_000)
    source_type: str | None = Field(default=None, max_length=80)
    source_id: str | None = Field(default=None, max_length=160)
    limit: int = Field(default=10, ge=1, le=30)
    persist: bool = False


class CreateContextLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    space_id: str | None = Field(default=None, min_length=1, max_length=80)
    memory_scope_id: str | None = Field(default=None, min_length=1, max_length=80)
    space_slug: str | None = Field(default=None, min_length=1, max_length=160)
    memory_scope_external_ref: str | None = Field(default=None, min_length=1, max_length=200)
    source_type: str = Field(min_length=1, max_length=80)
    source_id: str = Field(min_length=1, max_length=160)
    target_type: str = Field(min_length=1, max_length=80)
    target_id: str = Field(min_length=1, max_length=160)
    relation_type: str = Field(default="related_to", min_length=1, max_length=80)
    confidence: str = Field(default="medium", min_length=1, max_length=40)
    reason: str = Field(min_length=1, max_length=320)
    metadata: dict[str, Any] | None = None


class ReviewContextLinkSuggestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(min_length=1, max_length=16)
    reason: str | None = Field(default=None, max_length=320)
    target_type: str | None = Field(default=None, min_length=1, max_length=80)
    target_id: str | None = Field(default=None, min_length=1, max_length=160)
    relation_type: str | None = Field(default=None, min_length=1, max_length=80)
    confidence: str | None = Field(default=None, min_length=1, max_length=40)
    link_reason: str | None = Field(default=None, min_length=1, max_length=320)


class ReviewContextLinkSuggestionBatchItemRequest(ReviewContextLinkSuggestionRequest):
    suggestion_id: str = Field(min_length=1, max_length=160)


class ReviewContextLinkSuggestionsBatchVisibleFilterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    space_id: str | None = Field(default=None, min_length=1, max_length=80)
    memory_scope_id: str | None = Field(default=None, min_length=1, max_length=80)
    space_slug: str | None = Field(default=None, min_length=1, max_length=160)
    memory_scope_external_ref: str | None = Field(default=None, min_length=1, max_length=200)
    source_type: str | None = Field(default=None, min_length=1, max_length=80)
    source_id: str | None = Field(default=None, min_length=1, max_length=160)
    target_type: str | None = Field(default=None, min_length=1, max_length=80)
    target_id: str | None = Field(default=None, min_length=1, max_length=160)
    relation_type: str | None = Field(default=None, min_length=1, max_length=80)
    status: str | None = Field(default="pending", max_length=40)
    statuses: str | None = Field(default=None, max_length=240)
    limit: int = Field(default=50, ge=1, le=200)


class ReviewContextLinkSuggestionsBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReviewContextLinkSuggestionBatchItemRequest] = Field(
        min_length=1,
        max_length=50,
    )
    continue_on_error: bool = False
    visible_filter: ReviewContextLinkSuggestionsBatchVisibleFilterRequest | None = None


class UpdateContextLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str | None = Field(default=None, min_length=1, max_length=80)
    source_id: str | None = Field(default=None, min_length=1, max_length=160)
    target_type: str | None = Field(default=None, min_length=1, max_length=80)
    target_id: str | None = Field(default=None, min_length=1, max_length=160)
    relation_type: str | None = Field(default=None, min_length=1, max_length=80)
    confidence: str | None = Field(default=None, min_length=1, max_length=40)
    reason: str | None = Field(default=None, min_length=1, max_length=320)
    metadata: dict[str, Any] | None = None


@router.post("/link-suggestions")
async def suggest_context_links(
    request: SuggestContextLinksRequest,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    if request.persist:
        ensure_server_writes_enabled(container)
    scope = await resolve_existing_single_scope(
        container,
        space_id=request.space_id,
        memory_scope_id=request.memory_scope_id,
        thread_id=request.thread_id,
        space_slug=request.space_slug,
        memory_scope_external_ref=request.memory_scope_external_ref,
        thread_external_ref=request.thread_external_ref,
        thread_required=False,
    )
    if scope is None:
        return {"data": {"candidates": [], "diagnostics": {"scope_not_found": True}}}
    result = await container.suggest_context_links.execute(
        SuggestContextLinksCommand(
            space_id=scope.space_id,
            memory_scope_id=scope.memory_scope_id,
            thread_id=scope.thread_id,
            text=request.text,
            source_type=request.source_type,
            source_id=request.source_id,
            limit=request.limit,
            persist=request.persist,
        )
    )
    return {
        "data": {
            "candidates": [
                {
                    "target_type": item.target_type,
                    "target_id": item.target_id,
                    "label": item.label,
                    "preview": item.preview,
                    "score": item.score,
                    "tier": item.tier,
                    "reasons": list(item.reasons),
                    "suggestion_id": item.suggestion_id,
                    "status": item.status,
                    "metadata": safe_public_metadata(item.metadata),
                }
                for item in result.candidates
            ],
            "diagnostics": safe_public_metadata(result.diagnostics),
        }
    }


@router.post("/context-links")
async def create_context_link(
    request: CreateContextLinkRequest,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    ensure_server_writes_enabled(container)
    scope = await resolve_single_scope(
        container,
        space_id=request.space_id,
        memory_scope_id=request.memory_scope_id,
        thread_id=None,
        space_slug=request.space_slug,
        memory_scope_external_ref=request.memory_scope_external_ref,
        thread_external_ref=None,
        thread_required=False,
    )
    result = await container.create_context_link.execute(
        CreateContextLinkCommand(
            space_id=scope.space_id,
            memory_scope_id=scope.memory_scope_id,
            source_type=request.source_type,
            source_id=request.source_id,
            target_type=request.target_type,
            target_id=request.target_id,
            relation_type=request.relation_type,
            confidence=request.confidence,
            reason=request.reason,
            metadata=request.metadata,
        )
    )
    return {"data": {**context_link_to_response(result.link), "duplicate": result.duplicate}}


@router.get("/context-links")
async def list_context_links(
    container: Annotated[Container, Depends(get_container)],
    source_type: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    source_id: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    target_type: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    target_id: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    relation_type: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    space_id: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    memory_scope_id: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    space_slug: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    memory_scope_external_ref: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    status_filter: Annotated[str | None, Query(alias="status", max_length=40)] = "active",
    statuses_filter: Annotated[str | None, Query(alias="statuses", max_length=240)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    scope = await resolve_existing_single_scope(
        container,
        space_id=space_id,
        memory_scope_id=memory_scope_id,
        thread_id=None,
        space_slug=space_slug,
        memory_scope_external_ref=memory_scope_external_ref,
        thread_external_ref=None,
        thread_required=False,
    )
    if scope is None:
        return {"data": []}
    links = await container.list_context_links.execute(
        ListContextLinksQuery(
            space_id=scope.space_id,
            memory_scope_id=scope.memory_scope_id,
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relation_type=relation_type,
            status=None,
            statuses=_normalize_status_filter(status_filter, statuses_filter),
            limit=limit,
        )
    )
    return {"data": [context_link_to_response(link) for link in links]}


@router.get("/context-link-suggestions")
async def list_context_link_suggestions(
    container: Annotated[Container, Depends(get_container)],
    space_id: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    memory_scope_id: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    space_slug: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    memory_scope_external_ref: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    source_type: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    source_id: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    target_type: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    target_id: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    relation_type: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    status_filter: Annotated[str | None, Query(alias="status", max_length=40)] = "pending",
    statuses_filter: Annotated[str | None, Query(alias="statuses", max_length=240)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    scope = await resolve_existing_single_scope(
        container,
        space_id=space_id,
        memory_scope_id=memory_scope_id,
        thread_id=None,
        space_slug=space_slug,
        memory_scope_external_ref=memory_scope_external_ref,
        thread_external_ref=None,
        thread_required=False,
    )
    if scope is None:
        return {"data": []}
    suggestions = await container.list_context_link_suggestions.execute(
        ListContextLinkSuggestionsQuery(
            space_id=scope.space_id,
            memory_scope_id=scope.memory_scope_id,
            status=None,
            statuses=_normalize_status_filter(status_filter, statuses_filter),
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relation_type=relation_type,
            limit=limit,
        )
    )
    return {"data": [context_link_suggestion_to_response(item) for item in suggestions]}


@router.patch("/context-links/{context_link_id}")
async def update_context_link(
    context_link_id: str,
    request: UpdateContextLinkRequest,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    ensure_server_writes_enabled(container)
    result = await container.update_context_link.execute(
        UpdateContextLinkCommand(
            context_link_id=context_link_id,
            source_type=request.source_type,
            source_id=request.source_id,
            target_type=request.target_type,
            target_id=request.target_id,
            relation_type=request.relation_type,
            confidence=request.confidence,
            reason=request.reason,
            metadata=request.metadata,
        )
    )
    return {"data": context_link_to_response(result.link)}


@router.post("/context-link-suggestions/review-batch")
async def review_context_link_suggestions_batch(
    request: ReviewContextLinkSuggestionsBatchRequest,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    ensure_server_writes_enabled(container)
    visible_filter = await _resolve_batch_visible_filter(request.visible_filter, container)
    result = await container.review_context_link_suggestions_batch.execute(
        ReviewContextLinkSuggestionsBatchCommand(
            items=tuple(
                ReviewContextLinkSuggestionBatchItemCommand(
                    suggestion_id=item.suggestion_id,
                    action=item.action,
                    reason=item.reason,
                    target_type=item.target_type,
                    target_id=item.target_id,
                    relation_type=item.relation_type,
                    confidence=item.confidence,
                    link_reason=item.link_reason,
                )
                for item in request.items
            ),
            continue_on_error=request.continue_on_error,
            visible_filter=visible_filter,
        )
    )
    return {"data": _review_context_link_batch_to_response(result)}


@router.post("/context-link-suggestions/{context_link_suggestion_id}/review")
async def review_context_link_suggestion(
    context_link_suggestion_id: str,
    request: ReviewContextLinkSuggestionRequest,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    ensure_server_writes_enabled(container)
    result = await container.review_context_link_suggestion.execute(
        ReviewContextLinkSuggestionCommand(
            suggestion_id=context_link_suggestion_id,
            action=request.action,
            reason=request.reason,
            target_type=request.target_type,
            target_id=request.target_id,
            relation_type=request.relation_type,
            confidence=request.confidence,
            link_reason=request.link_reason,
        )
    )
    return {
        "data": {
            "suggestion": context_link_suggestion_to_response(result.suggestion),
            "link": context_link_to_response(result.link) if result.link else None,
            "duplicate_link": result.duplicate_link,
        }
    }


@router.delete("/context-links/{context_link_id}")
async def delete_context_link(
    context_link_id: str,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    ensure_server_writes_enabled(container)
    result = await container.delete_context_link.execute(
        DeleteContextLinkCommand(context_link_id=context_link_id)
    )
    return {"data": context_link_to_response(result.link)}


def _review_context_link_batch_to_response(result: Any) -> dict[str, Any]:
    return {
        "applied": result.applied,
        "failed": result.failed,
        "stopped": result.stopped,
        "diagnostics": safe_public_metadata(result.diagnostics, max_items=40),
        "results": [
            {
                "suggestion_id": item.suggestion_id,
                "action": item.action,
                "status": item.status,
                **_review_context_link_batch_item_payload(item),
            }
            for item in result.results
        ],
    }


def _review_context_link_batch_item_payload(item: Any) -> dict[str, Any]:
    if item.result is None:
        return {
            "error_code": item.error_code,
            "error_message": item.error_message,
        }
    return {
        "suggestion": context_link_suggestion_to_response(item.result.suggestion),
        "link": context_link_to_response(item.result.link) if item.result.link else None,
        "duplicate_link": item.result.duplicate_link,
    }


async def _resolve_batch_visible_filter(
    request: ReviewContextLinkSuggestionsBatchVisibleFilterRequest | None,
    container: Container,
) -> ContextLinkSuggestionVisibleFilter | None:
    if request is None:
        return None
    scope = await resolve_existing_single_scope(
        container,
        space_id=request.space_id,
        memory_scope_id=request.memory_scope_id,
        thread_id=None,
        space_slug=request.space_slug,
        memory_scope_external_ref=request.memory_scope_external_ref,
        thread_external_ref=None,
        thread_required=False,
    )
    if scope is None:
        raise MemoryValidationError("Context link batch visible filter scope not found")
    return ContextLinkSuggestionVisibleFilter(
        space_id=scope.space_id,
        memory_scope_id=scope.memory_scope_id,
        status=request.status,
        statuses=_normalize_status_filter(request.status, request.statuses),
        limit=request.limit,
        source_type=request.source_type,
        source_id=request.source_id,
        target_type=request.target_type,
        target_id=request.target_id,
        relation_type=request.relation_type,
    )


def context_link_to_response(link: MemoryContextLink) -> dict[str, Any]:
    return {
        "id": str(link.id),
        "space_id": str(link.space_id),
        "memory_scope_id": str(link.memory_scope_id),
        "source_type": link.source_type,
        "source_id": link.source_id,
        "target_type": link.target_type,
        "target_id": link.target_id,
        "relation_type": link.relation_type,
        "confidence": link.confidence,
        "reason": safe_public_reason(link.reason, limit=320),
        "status": link.status.value,
        "metadata": _safe_metadata(link.metadata),
        "created_at": link.created_at.isoformat(),
        "updated_at": link.updated_at.isoformat(),
    }


def context_link_suggestion_to_response(
    suggestion: MemoryContextLinkSuggestion,
) -> dict[str, Any]:
    return {
        "id": str(suggestion.id),
        "space_id": str(suggestion.space_id),
        "memory_scope_id": str(suggestion.memory_scope_id),
        "source_type": suggestion.source_type,
        "source_id": suggestion.source_id,
        "target_type": suggestion.target_type,
        "target_id": suggestion.target_id,
        "relation_type": suggestion.relation_type,
        "confidence": suggestion.confidence,
        "reason": safe_public_reason(suggestion.reason, limit=320),
        "score": suggestion.score,
        "status": suggestion.status.value,
        "metadata": _safe_metadata(suggestion.metadata),
        "created_at": suggestion.created_at.isoformat(),
        "updated_at": suggestion.updated_at.isoformat(),
        "reviewed_at": suggestion.reviewed_at.isoformat() if suggestion.reviewed_at else None,
        "review_reason": _safe_optional_text(suggestion.review_reason, limit=320),
        "review_audit": _review_audit_to_response(suggestion),
    }


def _safe_metadata(metadata: Any) -> dict[str, Any]:
    return safe_public_metadata(metadata)


def _review_audit_to_response(suggestion: MemoryContextLinkSuggestion) -> dict[str, Any]:
    raw_events = suggestion.metadata.get("review_events")
    events = (
        [item for item in raw_events if isinstance(item, dict)]
        if isinstance(raw_events, list)
        else []
    )
    public_events = [
        _review_audit_event_to_response(item)
        for item in events[-_MAX_PUBLIC_REVIEW_AUDIT_EVENTS:]
    ]
    return {
        "events": public_events,
        "event_count": len(events),
        "truncated": len(events) > len(public_events),
    }


def _review_audit_event_to_response(event: dict[str, Any]) -> dict[str, Any]:
    public: dict[str, Any] = {}
    for key, limit in _PUBLIC_REVIEW_AUDIT_FIELDS.items():
        value = event.get(key)
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            sanitizer = safe_public_reason if key == "reason" else safe_public_text
            public[key] = sanitizer(str(value), limit=limit)
    return public


def _safe_optional_text(value: str | None, *, limit: int) -> str | None:
    if value is None:
        return None
    return safe_public_reason(value, limit=limit)


def _normalize_status_filter(
    status_filter: str | None,
    statuses_filter: str | None,
) -> tuple[str, ...] | None:
    raw_values = statuses_filter.split(",") if statuses_filter is not None else [status_filter]
    values: list[str] = []
    for raw_value in raw_values:
        value = (raw_value or "").strip().lower()
        if not value:
            continue
        if value in {"all", "*"}:
            return None
        if value not in values:
            values.append(value)
    return tuple(values) if values else None
