"""Production-safe diagnostics API."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from infinity_context_server.api.auth import require_service_token
from infinity_context_server.api.dependencies import get_container
from infinity_context_server.composition import Container
from infinity_context_server.diagnostics import (
    adapter_diagnostics,
    memory_scope_diagnostics,
    operational_metrics,
    outbox_diagnostics,
)

router = APIRouter(
    prefix="/diagnostics",
    tags=["diagnostics"],
    dependencies=[Depends(require_service_token)],
)


@router.get("/adapters")
async def get_adapter_diagnostics(
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    return {"data": await adapter_diagnostics(container)}


@router.get("/outbox")
async def get_outbox_diagnostics(
    container: Annotated[Container, Depends(get_container)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> dict[str, Any]:
    return {
        "data": await outbox_diagnostics(container, limit=limit, cursor=cursor),
    }


@router.get("/memory-scope/{memory_scope_id}")
async def get_memory_scope_diagnostics(
    memory_scope_id: str,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    return {"data": await memory_scope_diagnostics(container, memory_scope_id=memory_scope_id)}


@router.get("/metrics")
async def get_operational_metrics(
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    return {"data": await operational_metrics(container)}
