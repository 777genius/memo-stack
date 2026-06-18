"""Thread-scoped memory lifecycle API."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from infinity_context_core.application import DeleteThreadMemoryCommand, GetSessionStatusQuery
from pydantic import BaseModel, ConfigDict, Field

from infinity_context_server.api.auth import require_service_token
from infinity_context_server.api.dependencies import get_container
from infinity_context_server.api.policy import ensure_server_writes_enabled
from infinity_context_server.api.v1.scope_resolution import resolve_existing_single_scope
from infinity_context_server.composition import Container

router = APIRouter(
    prefix="/thread-memory",
    tags=["thread-memory"],
    dependencies=[Depends(require_service_token)],
)


class ThreadMemoryScopeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    space_id: str | None = Field(default=None, min_length=1, max_length=80)
    memory_scope_id: str | None = Field(default=None, min_length=1, max_length=80)
    thread_id: str | None = Field(default=None, min_length=1, max_length=80)
    space_slug: str | None = Field(default=None, min_length=1, max_length=160)
    memory_scope_external_ref: str | None = Field(default=None, min_length=1, max_length=200)
    thread_external_ref: str | None = Field(default=None, min_length=1, max_length=200)


@router.post("/status")
async def thread_memory_status(
    request: ThreadMemoryScopeRequest,
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
        thread_required=True,
    )
    if scope is None:
        return {"data": _empty_status_counts()}
    result = await container.get_session_status.execute(
        GetSessionStatusQuery(
            space_id=scope.space_id,
            memory_scope_id=scope.memory_scope_id,
            thread_id=scope.thread_id,
        )
    )
    return {
        "data": {
            "chunks": result.chunks,
            "facts": result.facts,
            "jobs": result.jobs,
            "pending_jobs": result.pending_jobs,
        }
    }


@router.delete("")
async def delete_thread_memory(
    request: ThreadMemoryScopeRequest,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    ensure_server_writes_enabled(container)
    scope = await resolve_existing_single_scope(
        container,
        space_id=request.space_id,
        memory_scope_id=request.memory_scope_id,
        thread_id=request.thread_id,
        space_slug=request.space_slug,
        memory_scope_external_ref=request.memory_scope_external_ref,
        thread_external_ref=request.thread_external_ref,
        thread_required=True,
    )
    if scope is None:
        return {"data": _empty_delete_counts()}
    result = await container.delete_thread_memory.execute(
        DeleteThreadMemoryCommand(
            space_id=scope.space_id,
            memory_scope_id=scope.memory_scope_id,
            thread_id=scope.thread_id,
        )
    )
    return {
        "data": {
            "deleted_chunks": result.deleted_chunks,
            "deleted_facts": result.deleted_facts,
            "deleted_jobs": result.deleted_jobs,
        }
    }


@router.post("/delete")
async def delete_thread_memory_compat(
    request: ThreadMemoryScopeRequest,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    return await delete_thread_memory(request, container)


def _empty_status_counts() -> dict[str, int]:
    return {
        "chunks": 0,
        "facts": 0,
        "jobs": 0,
        "pending_jobs": 0,
    }


def _empty_delete_counts() -> dict[str, int]:
    return {
        "deleted_chunks": 0,
        "deleted_facts": 0,
        "deleted_jobs": 0,
    }
