"""Portable memory export API."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from infinity_context_core.application import (
    EnsureScopeCommand,
    ExportGraphQuery,
    GraphExportResult,
)
from infinity_context_core.domain.errors import MemoryValidationError
from infinity_context_core.memory_scope_snapshots import (
    build_snapshot_manifest,
    verify_snapshot_manifest_payload,
)
from pydantic import BaseModel, ConfigDict, Field

from infinity_context_server.api.auth import require_service_token
from infinity_context_server.api.dependencies import get_container
from infinity_context_server.api.policy import ensure_server_writes_enabled
from infinity_context_server.api.v1.scope_resolution import resolve_existing_single_scope
from infinity_context_server.composition import Container
from infinity_context_server.memory_scope_transfer import (
    SUPPORTED_MERGE_STRATEGIES,
    export_memory_scope_payload,
    import_memory_scope_payload,
)

router = APIRouter(
    prefix="/export",
    tags=["export"],
    dependencies=[Depends(require_service_token)],
)


class ImportMemoryScopeSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    space_slug: str = Field(min_length=1, max_length=160)
    memory_scope_external_ref: str = Field(min_length=1, max_length=200)
    snapshot: dict[str, Any]
    manifest: dict[str, Any] | None = None
    dry_run: bool = True
    merge_strategy: str = Field(default="fail_on_conflict", max_length=80)
    confirmed: bool = False
    source_name: str = Field(default="api-memory_scope-snapshot", max_length=160)


class PreviewMemoryScopeSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    space_slug: str = Field(min_length=1, max_length=160)
    memory_scope_external_ref: str = Field(min_length=1, max_length=200)
    snapshot: dict[str, Any]
    manifest: dict[str, Any] | None = None
    merge_strategy: str = Field(default="fail_on_conflict", max_length=80)


@router.get("/graph.json")
async def export_graph_json(
    container: Annotated[Container, Depends(get_container)],
    space_id: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    memory_scope_id: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    thread_id: Annotated[str | None, Query(max_length=80)] = None,
    space_slug: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    memory_scope_external_ref: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    thread_external_ref: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    include_deleted: Annotated[bool, Query()] = False,
    include_restricted: Annotated[bool, Query()] = False,
    max_facts: Annotated[int, Query(ge=0, le=1_000)] = 250,
    max_documents: Annotated[int, Query(ge=0, le=500)] = 100,
    max_episodes: Annotated[int, Query(ge=0, le=500)] = 100,
    max_chunks: Annotated[int, Query(ge=0, le=2_000)] = 500,
    max_anchors: Annotated[int, Query(ge=0, le=500)] = 100,
) -> dict[str, Any]:
    scope = await resolve_existing_single_scope(
        container,
        space_id=space_id,
        memory_scope_id=memory_scope_id,
        thread_id=thread_id,
        space_slug=space_slug,
        memory_scope_external_ref=memory_scope_external_ref,
        thread_external_ref=thread_external_ref,
        thread_required=False,
    )
    if scope is None:
        return {
            "data": {
                "schema_version": "infinity_context.graph_export.v1",
                "scope": {"scope_not_found": True},
                "nodes": [],
                "edges": [],
                "counts": {
                    "facts": 0,
                    "documents": 0,
                    "episodes": 0,
                    "chunks": 0,
                    "anchors": 0,
                    "nodes": 0,
                    "edges": 0,
                    "relations": 0,
                    "anchor_relations": 0,
                },
                "truncated": False,
                "warnings": ["scope_not_found"],
            }
        }
    graph = await container.export_graph.execute(
        ExportGraphQuery(
            space_id=scope.space_id,
            memory_scope_id=scope.memory_scope_id,
            thread_id=scope.thread_id,
            include_deleted=include_deleted,
            include_restricted=include_restricted,
            max_facts=max_facts,
            max_documents=max_documents,
            max_episodes=max_episodes,
            max_chunks=max_chunks,
            max_anchors=max_anchors,
        )
    )
    return {"data": graph_export_to_response(graph)}


@router.get("/memory_scope-snapshot")
async def export_memory_scope_snapshot(
    container: Annotated[Container, Depends(get_container)],
    space_slug: Annotated[str, Query(min_length=1, max_length=160)],
    memory_scope_external_ref: Annotated[str, Query(min_length=1, max_length=200)],
    redacted: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    result = await export_memory_scope_payload(
        engine=container.engine,
        space_slug=space_slug,
        memory_scope_external_ref=memory_scope_external_ref,
        redacted=redacted,
        blob_storage=container.blob_storage,
    )
    if result["status"] != "ok":
        return {"data": None, "status": result["status"]}
    snapshot = result["snapshot"]
    redacted = bool(result["redacted"])
    return {
        "data": snapshot,
        "status": "ok",
        "counts": result["counts"],
        "redacted": redacted,
        "manifest": build_snapshot_manifest(
            snapshot=snapshot,
            space_slug=space_slug,
            memory_scope_external_ref=memory_scope_external_ref,
            redacted=redacted,
        ),
    }


@router.post("/memory_scope-snapshot/import")
async def import_memory_scope_snapshot(
    request: ImportMemoryScopeSnapshotRequest,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    if request.merge_strategy not in SUPPORTED_MERGE_STRATEGIES:
        raise MemoryValidationError("Unsupported memory_scope snapshot merge strategy")
    if not request.dry_run and not request.confirmed:
        raise MemoryValidationError("MemoryScope snapshot import requires confirmed=true")
    _verify_memory_scope_snapshot_manifest(request.snapshot, request.manifest)

    if request.dry_run:
        scope = await resolve_existing_single_scope(
            container,
            space_id=None,
            memory_scope_id=None,
            thread_id=None,
            space_slug=request.space_slug,
            memory_scope_external_ref=request.memory_scope_external_ref,
            thread_external_ref=None,
            thread_required=False,
        )
        space_id = str(scope.space_id) if scope else ""
        memory_scope_id = str(scope.memory_scope_id) if scope else ""
    else:
        ensure_server_writes_enabled(container)
        scope_result = await container.ensure_scope.execute(
            EnsureScopeCommand(
                space_slug=request.space_slug,
                memory_scope_external_ref=request.memory_scope_external_ref,
            )
        )
        space_id = str(scope_result.space_id)
        memory_scope_id = str(scope_result.memory_scope_id)

    result = await import_memory_scope_payload(
        engine=container.engine,
        now=container.clock.now(),
        space_id=space_id,
        memory_scope_id=memory_scope_id,
        payload=request.snapshot,
        dry_run=request.dry_run,
        merge_strategy=request.merge_strategy,
        source_name=request.source_name,
        blob_storage=container.blob_storage,
    )
    return {"data": result}


@router.post("/memory_scope-snapshot/preview")
async def preview_memory_scope_snapshot_import(
    request: PreviewMemoryScopeSnapshotRequest,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    if request.merge_strategy not in SUPPORTED_MERGE_STRATEGIES:
        raise MemoryValidationError("Unsupported memory_scope snapshot merge strategy")
    _verify_memory_scope_snapshot_manifest(request.snapshot, request.manifest)
    scope = await resolve_existing_single_scope(
        container,
        space_id=None,
        memory_scope_id=None,
        thread_id=None,
        space_slug=request.space_slug,
        memory_scope_external_ref=request.memory_scope_external_ref,
        thread_external_ref=None,
        thread_required=False,
    )
    result = await import_memory_scope_payload(
        engine=container.engine,
        now=container.clock.now(),
        space_id=str(scope.space_id) if scope else "",
        memory_scope_id=str(scope.memory_scope_id) if scope else "",
        payload=request.snapshot,
        dry_run=True,
        merge_strategy=request.merge_strategy,
        source_name="api-memory_scope-snapshot-preview",
        blob_storage=container.blob_storage,
    )
    return {"data": result}


def _verify_memory_scope_snapshot_manifest(
    snapshot: dict[str, Any],
    manifest: dict[str, Any] | None,
) -> None:
    if manifest is None:
        return
    verification = verify_snapshot_manifest_payload(
        snapshot=snapshot,
        manifest=manifest,
        expected_snapshot_file=None,
    )
    if not verification["ok"]:
        errors = ", ".join(verification["errors"])
        raise MemoryValidationError(f"MemoryScope snapshot manifest verification failed: {errors}")


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
