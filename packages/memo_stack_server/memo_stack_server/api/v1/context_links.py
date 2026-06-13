"""Context-link suggestion and approval API."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from memo_stack_core.application import (
    CreateContextLinkCommand,
    DeleteContextLinkCommand,
    ListContextLinksQuery,
    SuggestContextLinksCommand,
)
from memo_stack_core.domain.assets import MemoryContextLink
from pydantic import BaseModel, ConfigDict, Field

from memo_stack_server.api.auth import require_service_token
from memo_stack_server.api.dependencies import get_container
from memo_stack_server.api.policy import ensure_server_writes_enabled
from memo_stack_server.api.v1.scope_resolution import (
    resolve_existing_single_scope,
    resolve_single_scope,
)
from memo_stack_server.composition import Container

router = APIRouter(
    tags=["context-links"],
    dependencies=[Depends(require_service_token)],
)


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


@router.post("/link-suggestions")
async def suggest_context_links(
    request: SuggestContextLinksRequest,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
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
                    "metadata": item.metadata or {},
                }
                for item in result.candidates
            ],
            "diagnostics": result.diagnostics,
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
    source_type: Annotated[str, Query(min_length=1, max_length=80)],
    source_id: Annotated[str, Query(min_length=1, max_length=160)],
    space_id: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    memory_scope_id: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    space_slug: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    memory_scope_external_ref: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    status_filter: Annotated[str | None, Query(alias="status", max_length=40)] = "active",
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
            status=status_filter,
            limit=limit,
        )
    )
    return {"data": [context_link_to_response(link) for link in links]}


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
        "reason": link.reason,
        "status": link.status.value,
        "metadata": _safe_metadata(link.metadata),
        "created_at": link.created_at.isoformat(),
        "updated_at": link.updated_at.isoformat(),
    }


def _safe_metadata(metadata: Any) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    return {
        str(key): value
        for key, value in metadata.items()
        if isinstance(value, (str, int, float, bool, type(None)))
    }
