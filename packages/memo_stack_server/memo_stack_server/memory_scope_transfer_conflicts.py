"""Conflict detection for memory_scope snapshot imports."""

from __future__ import annotations

from typing import Any

from memo_stack_adapters.postgres.models import (
    MemoryAnchorRow,
    MemoryAssetExtractionArtifactRow,
    MemoryAssetExtractionJobRow,
    MemoryAssetRow,
    MemoryCaptureRow,
    MemoryChunkRow,
    MemoryContextLinkRow,
    MemoryDocumentRow,
    MemoryEpisodeRow,
    MemoryFactRelationRow,
    MemoryFactRow,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def memory_scope_snapshot_conflicts(
    session: AsyncSession,
    *,
    space_id: str,
    memory_scope_id: str,
    facts: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    episodes: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    asset_extraction_jobs: list[dict[str, Any]],
    extraction_artifacts: list[dict[str, Any]],
    captures: list[dict[str, Any]],
    anchors: list[dict[str, Any]],
    context_links: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> list[str]:
    conflicts: list[str] = []
    fact_ids = [str(item["id"]) for item in facts]
    document_ids = [str(item["id"]) for item in documents]
    episode_ids = [str(item["id"]) for item in episodes]
    chunk_ids = [str(item["id"]) for item in chunks]
    asset_ids = [str(item["id"]) for item in assets]
    asset_extraction_job_ids = [str(item["id"]) for item in asset_extraction_jobs]
    extraction_artifact_ids = [str(item["id"]) for item in extraction_artifacts]
    capture_ids = [str(item["id"]) for item in captures]
    anchor_ids = [str(item["id"]) for item in anchors]
    context_link_ids = [str(item["id"]) for item in context_links]
    relation_ids = [str(item["id"]) for item in relations]
    for model, ids in (
        (MemoryFactRow, fact_ids),
        (MemoryDocumentRow, document_ids),
        (MemoryEpisodeRow, episode_ids),
        (MemoryChunkRow, chunk_ids),
        (MemoryAssetRow, asset_ids),
        (MemoryAssetExtractionJobRow, asset_extraction_job_ids),
        (MemoryAssetExtractionArtifactRow, extraction_artifact_ids),
        (MemoryCaptureRow, capture_ids),
        (MemoryAnchorRow, anchor_ids),
        (MemoryContextLinkRow, context_link_ids),
        (MemoryFactRelationRow, relation_ids),
    ):
        if not ids:
            continue
        result = await session.execute(select(model.id).where(model.id.in_(ids)))
        conflicts.extend(str(row_id) for row_id in result.scalars())
    conflicts.extend(
        await _document_hash_conflicts(
            session,
            space_id=space_id,
            memory_scope_id=memory_scope_id,
            documents=documents,
        )
    )
    conflicts.extend(
        await _chunk_hash_conflicts(
            session,
            space_id=space_id,
            memory_scope_id=memory_scope_id,
            chunks=chunks,
        )
    )
    conflicts.extend(
        await _asset_hash_conflicts(
            session,
            space_id=space_id,
            memory_scope_id=memory_scope_id,
            assets=assets,
        )
    )
    conflicts.extend(
        await _asset_extraction_job_signature_conflicts(
            session,
            space_id=space_id,
            memory_scope_id=memory_scope_id,
            jobs=asset_extraction_jobs,
        )
    )
    conflicts.extend(
        await _capture_idempotency_conflicts(
            session,
            space_id=space_id,
            captures=captures,
        )
    )
    conflicts.extend(
        await _anchor_key_conflicts(
            session,
            space_id=space_id,
            memory_scope_id=memory_scope_id,
            anchors=anchors,
        )
    )
    conflicts.extend(
        await _context_link_signature_conflicts(
            session,
            space_id=space_id,
            memory_scope_id=memory_scope_id,
            context_links=context_links,
        )
    )
    conflicts.extend(
        await _relation_signature_conflicts(
            session,
            space_id=space_id,
            memory_scope_id=memory_scope_id,
            relations=relations,
        )
    )
    return sorted(set(conflicts))


async def _document_hash_conflicts(
    session: AsyncSession,
    *,
    space_id: str,
    memory_scope_id: str,
    documents: list[dict[str, Any]],
) -> list[str]:
    by_hash = {
        str(item.get("content_hash")): str(item["id"])
        for item in documents
        if item.get("content_hash")
    }
    if not by_hash:
        return []
    rows = (
        await session.execute(
            select(MemoryDocumentRow.id, MemoryDocumentRow.content_hash).where(
                MemoryDocumentRow.space_id == space_id,
                MemoryDocumentRow.memory_scope_id == memory_scope_id,
                MemoryDocumentRow.status != "deleted",
                MemoryDocumentRow.content_hash.in_(by_hash),
            )
        )
    ).all()
    return [
        by_hash[str(content_hash)]
        for row_id, content_hash in rows
        if str(row_id) != by_hash[str(content_hash)]
    ]


async def _chunk_hash_conflicts(
    session: AsyncSession,
    *,
    space_id: str,
    memory_scope_id: str,
    chunks: list[dict[str, Any]],
) -> list[str]:
    by_hash = {
        str(item.get("source_hash")): str(item["id"]) for item in chunks if item.get("source_hash")
    }
    if not by_hash:
        return []
    rows = (
        await session.execute(
            select(MemoryChunkRow.id, MemoryChunkRow.source_hash).where(
                MemoryChunkRow.space_id == space_id,
                MemoryChunkRow.memory_scope_id == memory_scope_id,
                MemoryChunkRow.status != "deleted",
                MemoryChunkRow.source_hash.in_(by_hash),
            )
        )
    ).all()
    return [
        by_hash[str(source_hash)]
        for row_id, source_hash in rows
        if str(row_id) != by_hash[str(source_hash)]
    ]


async def _asset_hash_conflicts(
    session: AsyncSession,
    *,
    space_id: str,
    memory_scope_id: str,
    assets: list[dict[str, Any]],
) -> list[str]:
    by_hash = {
        str(item.get("sha256_hex")): str(item["id"])
        for item in assets
        if item.get("sha256_hex") and str(item.get("status", "stored")) == "stored"
    }
    if not by_hash:
        return []
    rows = (
        await session.execute(
            select(MemoryAssetRow.id, MemoryAssetRow.sha256_hex).where(
                MemoryAssetRow.space_id == space_id,
                MemoryAssetRow.memory_scope_id == memory_scope_id,
                MemoryAssetRow.status == "stored",
                MemoryAssetRow.sha256_hex.in_(by_hash),
            )
        )
    ).all()
    return [
        by_hash[str(sha256_hex)]
        for row_id, sha256_hex in rows
        if str(row_id) != by_hash[str(sha256_hex)]
    ]


async def _asset_extraction_job_signature_conflicts(
    session: AsyncSession,
    *,
    space_id: str,
    memory_scope_id: str,
    jobs: list[dict[str, Any]],
) -> list[str]:
    active_statuses = {"pending", "running", "succeeded"}
    by_signature = {
        (
            str(item.get("asset_id")),
            str(item.get("parser_profile")),
            str(item.get("parser_config_hash")),
            str(item.get("source_sha256_hex")),
        ): str(item["id"])
        for item in jobs
        if item.get("asset_id")
        and item.get("parser_profile")
        and item.get("parser_config_hash")
        and item.get("source_sha256_hex")
        and str(item.get("status", "pending")) in active_statuses
    }
    if not by_signature:
        return []
    rows = (
        await session.execute(
            select(
                MemoryAssetExtractionJobRow.id,
                MemoryAssetExtractionJobRow.asset_id,
                MemoryAssetExtractionJobRow.parser_profile,
                MemoryAssetExtractionJobRow.parser_config_hash,
                MemoryAssetExtractionJobRow.source_sha256_hex,
            ).where(
                MemoryAssetExtractionJobRow.space_id == space_id,
                MemoryAssetExtractionJobRow.memory_scope_id == memory_scope_id,
                MemoryAssetExtractionJobRow.status.in_(active_statuses),
                MemoryAssetExtractionJobRow.asset_id.in_({key[0] for key in by_signature}),
                MemoryAssetExtractionJobRow.parser_profile.in_(
                    {key[1] for key in by_signature}
                ),
                MemoryAssetExtractionJobRow.parser_config_hash.in_(
                    {key[2] for key in by_signature}
                ),
                MemoryAssetExtractionJobRow.source_sha256_hex.in_(
                    {key[3] for key in by_signature}
                ),
            )
        )
    ).all()
    return [
        by_signature[
            (
                str(asset_id),
                str(parser_profile),
                str(parser_config_hash),
                str(source_sha256_hex),
            )
        ]
        for row_id, asset_id, parser_profile, parser_config_hash, source_sha256_hex in rows
        if (
            str(asset_id),
            str(parser_profile),
            str(parser_config_hash),
            str(source_sha256_hex),
        )
        in by_signature
        and str(row_id)
        != by_signature[
            (
                str(asset_id),
                str(parser_profile),
                str(parser_config_hash),
                str(source_sha256_hex),
            )
        ]
    ]


async def _capture_idempotency_conflicts(
    session: AsyncSession,
    *,
    space_id: str,
    captures: list[dict[str, Any]],
) -> list[str]:
    by_key = {
        str(item.get("idempotency_key")): str(item["id"])
        for item in captures
        if item.get("idempotency_key")
    }
    if not by_key:
        return []
    rows = (
        await session.execute(
            select(MemoryCaptureRow.id, MemoryCaptureRow.idempotency_key).where(
                MemoryCaptureRow.space_id == space_id,
                MemoryCaptureRow.idempotency_key.in_(by_key),
            )
        )
    ).all()
    return [
        by_key[str(idempotency_key)]
        for row_id, idempotency_key in rows
        if str(row_id) != by_key[str(idempotency_key)]
    ]


async def _anchor_key_conflicts(
    session: AsyncSession,
    *,
    space_id: str,
    memory_scope_id: str,
    anchors: list[dict[str, Any]],
) -> list[str]:
    by_key = {
        (str(item.get("kind")), str(item.get("normalized_key"))): str(item["id"])
        for item in anchors
        if item.get("kind") and item.get("normalized_key")
    }
    if not by_key:
        return []
    rows = (
        await session.execute(
            select(MemoryAnchorRow.id, MemoryAnchorRow.kind, MemoryAnchorRow.normalized_key).where(
                MemoryAnchorRow.space_id == space_id,
                MemoryAnchorRow.memory_scope_id == memory_scope_id,
                MemoryAnchorRow.status == "active",
                MemoryAnchorRow.kind.in_({key[0] for key in by_key}),
                MemoryAnchorRow.normalized_key.in_({key[1] for key in by_key}),
            )
        )
    ).all()
    conflicts: list[str] = []
    for row_id, kind, normalized_key in rows:
        snapshot_id = by_key.get((kind, normalized_key))
        if snapshot_id is not None and str(row_id) != snapshot_id:
            conflicts.append(snapshot_id)
    return conflicts


async def _context_link_signature_conflicts(
    session: AsyncSession,
    *,
    space_id: str,
    memory_scope_id: str,
    context_links: list[dict[str, Any]],
) -> list[str]:
    by_signature = {
        (
            str(item.get("source_type")),
            str(item.get("source_id")),
            str(item.get("target_type")),
            str(item.get("target_id")),
            str(item.get("relation_type", "related_to")),
        ): str(item["id"])
        for item in context_links
        if item.get("source_type") and item.get("source_id") and item.get("target_type")
        and item.get("target_id")
    }
    if not by_signature:
        return []
    rows = (
        await session.execute(
            select(
                MemoryContextLinkRow.id,
                MemoryContextLinkRow.source_type,
                MemoryContextLinkRow.source_id,
                MemoryContextLinkRow.target_type,
                MemoryContextLinkRow.target_id,
                MemoryContextLinkRow.relation_type,
            ).where(
                MemoryContextLinkRow.space_id == space_id,
                MemoryContextLinkRow.memory_scope_id == memory_scope_id,
                MemoryContextLinkRow.status == "active",
                MemoryContextLinkRow.relation_type.in_(
                    {signature[4] for signature in by_signature}
                ),
            )
        )
    ).all()
    conflicts: list[str] = []
    for row in rows:
        row_id, source_type, source_id, target_type, target_id, relation_type = row
        snapshot_id = by_signature.get(
            (source_type, source_id, target_type, target_id, relation_type)
        )
        if snapshot_id is not None and str(row_id) != snapshot_id:
            conflicts.append(snapshot_id)
    return conflicts


async def _relation_signature_conflicts(
    session: AsyncSession,
    *,
    space_id: str,
    memory_scope_id: str,
    relations: list[dict[str, Any]],
) -> list[str]:
    by_signature = {
        (
            str(item.get("source_fact_id")),
            str(item.get("target_fact_id")),
            str(item.get("relation_type", "related_to")),
        ): str(item["id"])
        for item in relations
        if item.get("source_fact_id") and item.get("target_fact_id")
    }
    if not by_signature:
        return []
    rows = (
        await session.execute(
            select(
                MemoryFactRelationRow.id,
                MemoryFactRelationRow.source_fact_id,
                MemoryFactRelationRow.target_fact_id,
                MemoryFactRelationRow.relation_type,
            ).where(
                MemoryFactRelationRow.space_id == space_id,
                MemoryFactRelationRow.memory_scope_id == memory_scope_id,
                MemoryFactRelationRow.status == "active",
                MemoryFactRelationRow.relation_type.in_(
                    {signature[2] for signature in by_signature}
                ),
            )
        )
    ).all()
    conflicts: list[str] = []
    for row_id, source_fact_id, target_fact_id, relation_type in rows:
        snapshot_id = by_signature.get((source_fact_id, target_fact_id, relation_type))
        if snapshot_id is not None and str(row_id) != snapshot_id:
            conflicts.append(snapshot_id)
    return conflicts
