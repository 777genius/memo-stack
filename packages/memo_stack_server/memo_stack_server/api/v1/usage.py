"""Usage plan and quota API."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from memo_stack_core.application import UsageSummaryQuery, UsageSummaryResult
from memo_stack_core.domain.entities import SpaceId
from memo_stack_core.domain.errors import MemoryValidationError

from memo_stack_server.api.auth import require_service_token
from memo_stack_server.api.dependencies import get_container
from memo_stack_server.composition import Container

router = APIRouter(tags=["usage"], dependencies=[Depends(require_service_token)])


@router.get("/usage")
async def get_usage(
    container: Annotated[Container, Depends(get_container)],
    space_id: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    space_slug: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
) -> dict[str, Any]:
    resolved_space_id = await _resolve_space_id(
        container,
        space_id=space_id,
        space_slug=space_slug,
    )
    result = await container.get_usage_summary.execute(
        UsageSummaryQuery(space_id=resolved_space_id)
    )
    return {"data": usage_summary_to_response(result, space_id=resolved_space_id)}


def usage_summary_to_response(result: UsageSummaryResult, *, space_id: SpaceId) -> dict[str, Any]:
    return {
        "space_id": str(space_id),
        "plan": {
            "tier": result.plan.tier.value,
            "display_name": result.plan.display_name,
            "media_analysis_seconds_per_month": (
                result.plan.media_analysis_seconds_per_month
            ),
        },
        "resources": [
            {
                "resource": item.resource,
                "limit": item.limit,
                "used": item.used,
                "remaining": item.remaining,
                "window_start": item.window_start.isoformat(),
                "window_end": item.window_end.isoformat(),
            }
            for item in result.resources
        ],
    }


async def _resolve_space_id(
    container: Container,
    *,
    space_id: str | None,
    space_slug: str | None,
) -> SpaceId:
    if space_id and space_slug:
        raise MemoryValidationError("Use either space_id or space_slug, not both")
    if space_id:
        return SpaceId(space_id)
    target_slug = space_slug or container.settings.default_space_slug
    spaces = await container.list_spaces.execute(limit=500)
    for space in spaces:
        if space.slug == target_slug:
            return space.id
    raise MemoryValidationError("Space not found")
