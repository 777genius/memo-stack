"""Search and prompt-context API."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from memory_core.application import BuildContextQuery
from pydantic import BaseModel, Field

from memory_server.api.auth import require_service_token
from memory_server.api.dependencies import get_container
from memory_server.api.policy import should_retrieve
from memory_server.api.v1.scope_resolution import resolve_context_scope
from memory_server.composition import Container

router = APIRouter(tags=["context"], dependencies=[Depends(require_service_token)])


class ContextRequest(BaseModel):
    space_id: str | None = Field(default=None, min_length=1, max_length=80)
    profile_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    thread_id: str | None = Field(default=None, max_length=80)
    space_slug: str | None = Field(default=None, min_length=1, max_length=160)
    profile_external_ref: str | None = Field(default=None, min_length=1, max_length=200)
    profile_external_refs: list[str] | None = Field(default=None, min_length=1, max_length=20)
    thread_external_ref: str | None = Field(default=None, min_length=1, max_length=200)
    query: str = Field(min_length=1, max_length=12000)
    token_budget: int = Field(default=1800, ge=64, le=16000)
    max_facts: int = Field(default=20, ge=0, le=100)
    max_chunks: int = Field(default=30, ge=0, le=200)


def context_item_to_response(item) -> dict[str, Any]:
    diagnostics = item.diagnostics or {}
    return {
        "item_id": item.item_id,
        "item_type": item.item_type,
        "profile_id": diagnostics.get("profile_id"),
        "text": item.text,
        "score": item.score,
        "source_refs": [
            {
                "source_type": ref.source_type,
                "source_id": ref.source_id,
                "chunk_id": ref.chunk_id,
                "char_start": ref.char_start,
                "char_end": ref.char_end,
                "quote_preview": ref.quote_preview,
            }
            for ref in item.source_refs
        ],
        "is_instruction": item.is_instruction,
        "diagnostics": diagnostics,
    }


@router.post("/context")
async def build_context(
    request: ContextRequest,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    if not should_retrieve(container):
        return _empty_context_response(policy_mode=container.settings.policy_mode.value)
    scope = await resolve_context_scope(
        container,
        space_id=request.space_id,
        profile_ids=request.profile_ids,
        thread_id=request.thread_id,
        space_slug=request.space_slug,
        profile_external_ref=request.profile_external_ref,
        profile_external_refs=request.profile_external_refs,
        thread_external_ref=request.thread_external_ref,
    )
    bundle = await container.build_context.execute(
        BuildContextQuery(
            space_id=scope.space_id,
            profile_ids=scope.profile_ids,
            thread_id=scope.thread_id,
            query=request.query,
            token_budget=request.token_budget,
            max_rendered_chars=container.settings.max_context_chars,
            max_facts=request.max_facts,
            max_chunks=request.max_chunks,
        )
    )
    return {
        "data": {
            "bundle_id": bundle.bundle_id,
            "rendered_text": bundle.rendered_text,
            "items": [context_item_to_response(item) for item in bundle.items],
            "diagnostics": bundle.diagnostics,
        }
    }


@router.post("/search")
async def search_memory(
    request: ContextRequest,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    if not should_retrieve(container):
        return {
            "data": {
                "items": [],
                "next_cursor": None,
                "diagnostics": {
                    "policy_mode": container.settings.policy_mode.value,
                    "retrieval_disabled": True,
                },
            }
        }
    scope = await resolve_context_scope(
        container,
        space_id=request.space_id,
        profile_ids=request.profile_ids,
        thread_id=request.thread_id,
        space_slug=request.space_slug,
        profile_external_ref=request.profile_external_ref,
        profile_external_refs=request.profile_external_refs,
        thread_external_ref=request.thread_external_ref,
    )
    bundle = await container.build_context.execute(
        BuildContextQuery(
            space_id=scope.space_id,
            profile_ids=scope.profile_ids,
            thread_id=scope.thread_id,
            query=request.query,
            token_budget=request.token_budget,
            max_rendered_chars=container.settings.max_context_chars,
            max_facts=request.max_facts,
            max_chunks=request.max_chunks,
        )
    )
    return {
        "data": {
            "items": [context_item_to_response(item) for item in bundle.items],
            "next_cursor": None,
            "diagnostics": bundle.diagnostics,
        }
    }


def _empty_context_response(*, policy_mode: str) -> dict[str, Any]:
    return {
        "data": {
            "bundle_id": "ctx_disabled",
            "rendered_text": "",
            "items": [],
            "diagnostics": {
                "policy_mode": policy_mode,
                "retrieval_disabled": True,
            },
        }
    }
