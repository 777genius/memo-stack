"""Context-link graph helpers for MemoryScope snapshot transfer."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from memo_stack_adapters.postgres.models import (
    MemoryContextLinkRow,
    MemoryContextLinkSuggestionRow,
)
from memo_stack_core.application.safe_payload import safe_metadata
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memo_stack_server.memory_scope_transfer_records import (
    bounded_optional_text,
    context_link_from_json,
)
from memo_stack_server.memory_scope_transfer_records import (
    context_link_to_json as _record_context_link_to_json,
)
from memo_stack_server.memory_scope_transfer_remap import (
    remap_context_link,
    remap_context_link_review_events,
    remap_endpoint_id,
)


async def load_context_records(
    session: AsyncSession,
    *,
    space_id: str,
    memory_scope_id: str,
) -> tuple[list[MemoryContextLinkRow], list[MemoryContextLinkSuggestionRow]]:
    context_links = list(
        (
            await session.execute(
                select(MemoryContextLinkRow)
                .where(
                    MemoryContextLinkRow.space_id == space_id,
                    MemoryContextLinkRow.memory_scope_id == memory_scope_id,
                )
                .order_by(MemoryContextLinkRow.created_at, MemoryContextLinkRow.id)
            )
        ).scalars()
    )
    context_link_suggestions = list(
        (
            await session.execute(
                select(MemoryContextLinkSuggestionRow)
                .where(
                    MemoryContextLinkSuggestionRow.space_id == space_id,
                    MemoryContextLinkSuggestionRow.memory_scope_id == memory_scope_id,
                )
                .order_by(
                    MemoryContextLinkSuggestionRow.created_at,
                    MemoryContextLinkSuggestionRow.id,
                )
            )
        ).scalars()
    )
    return context_links, context_link_suggestions


def context_link_suggestion_to_json(row: MemoryContextLinkSuggestionRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "relation_type": row.relation_type,
        "confidence": row.confidence,
        "reason": row.reason,
        "score": row.score,
        "status": row.status,
        "metadata_json": safe_metadata(row.metadata_json),
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "review_reason": row.review_reason,
    }


def context_link_to_json(row: MemoryContextLinkRow) -> dict[str, Any]:
    return _record_context_link_to_json(row)


def context_link_suggestion_from_json(
    item: dict[str, Any],
    *,
    space_id: str,
    memory_scope_id: str,
    now: datetime,
) -> MemoryContextLinkSuggestionRow:
    return MemoryContextLinkSuggestionRow(
        id=str(item["id"]),
        space_id=space_id,
        memory_scope_id=memory_scope_id,
        source_type=str(item.get("source_type", "unknown")),
        source_id=str(item.get("source_id", item["id"])),
        target_type=str(item.get("target_type", "unknown")),
        target_id=str(item.get("target_id", item["id"])),
        relation_type=str(item.get("relation_type", "related_to")),
        confidence=str(item.get("confidence", "medium")),
        reason=str(item.get("reason", "Imported context-link suggestion"))[:320],
        score=float(item.get("score", 0.0) or 0.0),
        status=str(item.get("status", "pending")),
        metadata_json=safe_metadata(item.get("metadata_json") or item.get("metadata") or {}),
        created_at=_parse_dt(item.get("created_at"), now),
        updated_at=_parse_dt(item.get("updated_at"), now),
        reviewed_at=_parse_optional_dt(item.get("reviewed_at")),
        review_reason=bounded_optional_text(item.get("review_reason"), 320),
    )


def remap_context_link_suggestion(
    item: dict[str, Any],
    *,
    context_link_suggestion_id_map: dict[str, str],
    fact_id_map: dict[str, str],
    document_id_map: dict[str, str],
    episode_id_map: dict[str, str],
    chunk_id_map: dict[str, str],
    capture_id_map: dict[str, str],
    asset_id_map: dict[str, str],
    anchor_id_map: dict[str, str],
    thread_id_map: dict[str, str] | None = None,
    extraction_job_id_map: dict[str, str],
    extraction_artifact_id_map: dict[str, str],
) -> dict[str, Any]:
    suggestion_id = str(item["id"])
    source_type = str(item.get("source_type") or "")
    target_type = str(item.get("target_type") or "")
    metadata = dict(item.get("metadata_json") or item.get("metadata") or {})
    if "review_events" in metadata:
        metadata["review_events"] = remap_context_link_review_events(
            metadata.get("review_events"),
            context_link_suggestion_id_map=context_link_suggestion_id_map,
            fact_id_map=fact_id_map,
            thread_id_map=thread_id_map or {},
            document_id_map=document_id_map,
            episode_id_map=episode_id_map,
            chunk_id_map=chunk_id_map,
            capture_id_map=capture_id_map,
            asset_id_map=asset_id_map,
            anchor_id_map=anchor_id_map,
            extraction_job_id_map=extraction_job_id_map,
            extraction_artifact_id_map=extraction_artifact_id_map,
        )
    return {
        **item,
        "id": context_link_suggestion_id_map.get(suggestion_id, suggestion_id),
        "source_id": remap_endpoint_id(
            source_type=source_type,
            source_id=str(item.get("source_id")),
            fact_id_map=fact_id_map,
            thread_id_map=thread_id_map or {},
            document_id_map=document_id_map,
            episode_id_map=episode_id_map,
            chunk_id_map=chunk_id_map,
            capture_id_map=capture_id_map,
            asset_id_map=asset_id_map,
            anchor_id_map=anchor_id_map,
            extraction_job_id_map=extraction_job_id_map,
            extraction_artifact_id_map=extraction_artifact_id_map,
        ),
        "target_id": remap_endpoint_id(
            source_type=target_type,
            source_id=str(item.get("target_id")),
            fact_id_map=fact_id_map,
            thread_id_map=thread_id_map or {},
            document_id_map=document_id_map,
            episode_id_map=episode_id_map,
            chunk_id_map=chunk_id_map,
            capture_id_map=capture_id_map,
            asset_id_map=asset_id_map,
            anchor_id_map=anchor_id_map,
            extraction_job_id_map=extraction_job_id_map,
            extraction_artifact_id_map=extraction_artifact_id_map,
        ),
        "metadata_json": metadata,
    }


def import_context_records(
    session: AsyncSession,
    *,
    context_links: list[dict[str, Any]],
    context_link_suggestions: list[dict[str, Any]],
    skipped: dict[str, set[str]],
    context_link_id_map: dict[str, str],
    context_link_suggestion_id_map: dict[str, str],
    fact_id_map: dict[str, str],
    document_id_map: dict[str, str],
    episode_id_map: dict[str, str],
    chunk_id_map: dict[str, str],
    capture_id_map: dict[str, str],
    asset_id_map: dict[str, str],
    anchor_id_map: dict[str, str],
    thread_id_map: dict[str, str],
    extraction_job_id_map: dict[str, str],
    extraction_artifact_id_map: dict[str, str],
    space_id: str,
    memory_scope_id: str,
    now: datetime,
) -> None:
    for context_link in context_links:
        if str(context_link["id"]) in skipped["context_links"]:
            continue
        mapped = remap_context_link(
            context_link,
            context_link_id_map=context_link_id_map,
            context_link_suggestion_id_map=context_link_suggestion_id_map,
            fact_id_map=fact_id_map,
            document_id_map=document_id_map,
            episode_id_map=episode_id_map,
            chunk_id_map=chunk_id_map,
            capture_id_map=capture_id_map,
            asset_id_map=asset_id_map,
            anchor_id_map=anchor_id_map,
            thread_id_map=thread_id_map,
            extraction_job_id_map=extraction_job_id_map,
            extraction_artifact_id_map=extraction_artifact_id_map,
        )
        session.add(
            context_link_from_json(
                mapped,
                space_id=space_id,
                memory_scope_id=memory_scope_id,
                now=now,
            )
        )
    skipped_suggestion_ids = skipped.get("context_link_suggestions", set())
    for suggestion in context_link_suggestions:
        if str(suggestion["id"]) in skipped_suggestion_ids:
            continue
        mapped = remap_context_link_suggestion(
            suggestion,
            context_link_suggestion_id_map=context_link_suggestion_id_map,
            fact_id_map=fact_id_map,
            document_id_map=document_id_map,
            episode_id_map=episode_id_map,
            chunk_id_map=chunk_id_map,
            capture_id_map=capture_id_map,
            asset_id_map=asset_id_map,
            anchor_id_map=anchor_id_map,
            thread_id_map=thread_id_map,
            extraction_job_id_map=extraction_job_id_map,
            extraction_artifact_id_map=extraction_artifact_id_map,
        )
        session.add(
            context_link_suggestion_from_json(
                mapped,
                space_id=space_id,
                memory_scope_id=memory_scope_id,
                now=now,
            )
        )


def _parse_dt(value: object, fallback: datetime) -> datetime:
    parsed = _parse_optional_dt(value)
    return parsed or fallback


def _parse_optional_dt(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
