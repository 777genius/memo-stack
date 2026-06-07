"""Portable memory export API."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from memo_stack_core.application import ExportGraphQuery, GraphExportResult

from memo_stack_server.api.auth import require_service_token
from memo_stack_server.api.dependencies import get_container
from memo_stack_server.api.v1.scope_resolution import resolve_existing_single_scope
from memo_stack_server.composition import Container

router = APIRouter(
    prefix="/export",
    tags=["export"],
    dependencies=[Depends(require_service_token)],
)


@router.get("/graph.json")
async def export_graph_json(
    container: Annotated[Container, Depends(get_container)],
    space_id: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    profile_id: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    thread_id: Annotated[str | None, Query(max_length=80)] = None,
    space_slug: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    profile_external_ref: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    thread_external_ref: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    include_deleted: Annotated[bool, Query()] = False,
    include_restricted: Annotated[bool, Query()] = False,
    max_facts: Annotated[int, Query(ge=0, le=1_000)] = 250,
    max_documents: Annotated[int, Query(ge=0, le=500)] = 100,
    max_chunks: Annotated[int, Query(ge=0, le=2_000)] = 500,
) -> dict[str, Any]:
    scope = await resolve_existing_single_scope(
        container,
        space_id=space_id,
        profile_id=profile_id,
        thread_id=thread_id,
        space_slug=space_slug,
        profile_external_ref=profile_external_ref,
        thread_external_ref=thread_external_ref,
        thread_required=False,
    )
    if scope is None:
        return {
            "data": {
                "schema_version": "memo_stack.graph_export.v1",
                "scope": {"scope_not_found": True},
                "nodes": [],
                "edges": [],
                "counts": {"facts": 0, "documents": 0, "chunks": 0, "nodes": 0, "edges": 0},
                "truncated": False,
                "warnings": ["scope_not_found"],
            }
        }
    graph = await container.export_graph.execute(
        ExportGraphQuery(
            space_id=scope.space_id,
            profile_id=scope.profile_id,
            thread_id=scope.thread_id,
            include_deleted=include_deleted,
            include_restricted=include_restricted,
            max_facts=max_facts,
            max_documents=max_documents,
            max_chunks=max_chunks,
        )
    )
    return {"data": graph_export_to_response(graph)}


def graph_export_to_response(graph: GraphExportResult) -> dict[str, Any]:
    return {
        "schema_version": graph.schema_version,
        "scope": graph.scope,
        "nodes": [
            {
                "id": node.id,
                "type": node.type,
                "label": node.label,
                "data": node.data,
            }
            for node in graph.nodes
        ],
        "edges": [
            {
                "id": edge.id,
                "type": edge.type,
                "source": edge.source,
                "target": edge.target,
                "label": edge.label,
                "data": edge.data,
            }
            for edge in graph.edges
        ],
        "counts": graph.counts,
        "truncated": graph.truncated,
        "warnings": list(graph.warnings),
    }
