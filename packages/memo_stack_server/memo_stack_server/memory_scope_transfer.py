"""MemoryScope export/import lite.

This is a local portability tool, not a sync protocol. It reads and writes
canonical Postgres rows only and never serializes derived Qdrant/Graphiti state.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from memo_stack_adapters.postgres.models import (
    MemoryChunkRow,
    MemoryDocumentRow,
    MemoryEpisodeRow,
    MemoryFactRelationRow,
    MemoryFactRow,
    MemoryOutboxRow,
    MemoryScopeRow,
    MemorySourceRefRow,
    MemorySpaceRow,
    MemoryThreadRow,
)
from memo_stack_core.memory_scope_snapshot_preview import (
    build_memory_scope_snapshot_import_preview,
    import_counts,
    skipped_snapshot_ids,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from memo_stack_server.memory_scope_transfer_conflicts import memory_scope_snapshot_conflicts
from memo_stack_server.memory_scope_transfer_records import (
    bounded_optional_text as _bounded_optional_text,
)
from memo_stack_server.memory_scope_transfer_records import (
    chunk_from_json as _chunk_from_json,
)
from memo_stack_server.memory_scope_transfer_records import (
    chunk_to_json as _chunk_to_json,
)
from memo_stack_server.memory_scope_transfer_records import (
    contains_redacted_memory as _contains_redacted_memory,
)
from memo_stack_server.memory_scope_transfer_records import (
    document_from_json as _document_from_json,
)
from memo_stack_server.memory_scope_transfer_records import (
    document_to_json as _document_to_json,
)
from memo_stack_server.memory_scope_transfer_records import (
    episode_from_json as _episode_from_json,
)
from memo_stack_server.memory_scope_transfer_records import (
    episode_to_json as _episode_to_json,
)
from memo_stack_server.memory_scope_transfer_records import (
    fact_from_json as _fact_from_json,
)
from memo_stack_server.memory_scope_transfer_records import (
    fact_to_json as _fact_to_json,
)
from memo_stack_server.memory_scope_transfer_records import (
    source_ref_from_json as _source_ref_from_json,
)
from memo_stack_server.memory_scope_transfer_records import (
    source_ref_to_json as _source_ref_to_json,
)
from memo_stack_server.memory_scope_transfer_relations import (
    relation_from_json,
    relation_to_json,
    remap_relation,
)

SCHEMA_VERSION = 3
SUPPORTED_SCHEMA_VERSIONS = {1, 2, 3}
SUPPORTED_MERGE_STRATEGIES = {
    "fail_on_conflict",
    "skip_existing",
    "create_new_memory_scope",
    "supersede_matching_facts",
}


async def export_memory_scope(
    *,
    engine: AsyncEngine,
    space_slug: str,
    memory_scope_external_ref: str,
    out_path: Path,
    redacted: bool,
) -> dict[str, object]:
    result = await export_memory_scope_payload(
        engine=engine,
        space_slug=space_slug,
        memory_scope_external_ref=memory_scope_external_ref,
        redacted=redacted,
    )
    if result["status"] != "ok":
        return {"status": result["status"], "out": str(out_path)}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result["snapshot"], ensure_ascii=False, indent=2), "utf-8")
    counts = result["counts"]
    return {
        "status": "ok",
        "out": str(out_path),
        "facts": counts["facts"],
        "documents": counts["documents"],
        "episodes": counts["episodes"],
        "chunks": counts["chunks"],
        "relations": counts["relations"],
        "redacted": redacted,
    }


async def export_memory_scope_payload(
    *,
    engine: AsyncEngine,
    space_slug: str,
    memory_scope_external_ref: str,
    redacted: bool,
) -> dict[str, object]:
    async with AsyncSession(engine) as session:
        scope = await _load_scope(
            session,
            space_slug=space_slug,
            memory_scope_external_ref=memory_scope_external_ref,
        )
        if scope is None:
            return {"status": "not_found"}
        space, memory_scope = scope
        facts = list(
            (
                await session.execute(
                    select(MemoryFactRow)
                    .where(
                        MemoryFactRow.space_id == space.id,
                        MemoryFactRow.memory_scope_id == memory_scope.id,
                    )
                    .order_by(MemoryFactRow.created_at, MemoryFactRow.id)
                )
            ).scalars()
        )
        documents = list(
            (
                await session.execute(
                    select(MemoryDocumentRow)
                    .where(
                        MemoryDocumentRow.space_id == space.id,
                        MemoryDocumentRow.memory_scope_id == memory_scope.id,
                    )
                    .order_by(MemoryDocumentRow.created_at, MemoryDocumentRow.id)
                )
            ).scalars()
        )
        episodes = list(
            (
                await session.execute(
                    select(MemoryEpisodeRow)
                    .where(
                        MemoryEpisodeRow.space_id == space.id,
                        MemoryEpisodeRow.memory_scope_id == memory_scope.id,
                    )
                    .order_by(MemoryEpisodeRow.occurred_at, MemoryEpisodeRow.id)
                )
            ).scalars()
        )
        chunks = list(
            (
                await session.execute(
                    select(MemoryChunkRow)
                    .where(
                        MemoryChunkRow.space_id == space.id,
                        MemoryChunkRow.memory_scope_id == memory_scope.id,
                    )
                    .order_by(MemoryChunkRow.created_at, MemoryChunkRow.id)
                )
            ).scalars()
        )
        fact_ids = [fact.id for fact in facts]
        source_refs = []
        relations = []
        if fact_ids:
            source_refs = list(
                (
                    await session.execute(
                        select(MemorySourceRefRow)
                        .where(MemorySourceRefRow.fact_id.in_(fact_ids))
                        .order_by(MemorySourceRefRow.fact_id, MemorySourceRefRow.id)
                    )
                ).scalars()
            )
            relations = list(
                (
                    await session.execute(
                        select(MemoryFactRelationRow)
                        .where(
                            MemoryFactRelationRow.space_id == space.id,
                            MemoryFactRelationRow.memory_scope_id == memory_scope.id,
                            MemoryFactRelationRow.source_fact_id.in_(fact_ids),
                            MemoryFactRelationRow.target_fact_id.in_(fact_ids),
                        )
                        .order_by(MemoryFactRelationRow.created_at, MemoryFactRelationRow.id)
                    )
                ).scalars()
            )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "space": {"slug": space.slug, "id": space.id},
        "memory_scope": {"external_ref": memory_scope.external_ref, "id": memory_scope.id},
        "facts": [_fact_to_json(fact, redacted=redacted) for fact in facts],
        "documents": [_document_to_json(document) for document in documents],
        "episodes": [_episode_to_json(episode, redacted=redacted) for episode in episodes],
        "chunks": [_chunk_to_json(chunk, redacted=redacted) for chunk in chunks],
        "relations": [relation_to_json(relation) for relation in relations],
        "source_refs": [_source_ref_to_json(ref, redacted=redacted) for ref in source_refs],
        "exported_at": datetime.now(UTC).isoformat(),
        "redacted": redacted,
    }
    return {
        "status": "ok",
        "snapshot": payload,
        "counts": {
            "facts": len(facts),
            "documents": len(documents),
            "episodes": len(episodes),
            "chunks": len(chunks),
            "relations": len(relations),
            "source_refs": len(source_refs),
        },
        "redacted": redacted,
    }


async def import_memory_scope(
    *,
    engine: AsyncEngine,
    now: datetime,
    space_id: str,
    memory_scope_id: str,
    in_path: Path,
    dry_run: bool,
    merge_strategy: str,
) -> dict[str, object]:
    payload = json.loads(in_path.read_text(encoding="utf-8"))
    return await import_memory_scope_payload(
        engine=engine,
        now=now,
        space_id=space_id,
        memory_scope_id=memory_scope_id,
        payload=payload,
        dry_run=dry_run,
        merge_strategy=merge_strategy,
        source_name=in_path.name,
    )


async def import_memory_scope_payload(
    *,
    engine: AsyncEngine,
    now: datetime,
    space_id: str,
    memory_scope_id: str,
    payload: dict[str, Any],
    dry_run: bool,
    merge_strategy: str,
    source_name: str = "memory_scope-snapshot",
) -> dict[str, object]:
    if int(payload.get("schema_version", 0)) not in SUPPORTED_SCHEMA_VERSIONS:
        return {"status": "failed", "reason": "unsupported_schema_version"}
    if merge_strategy not in SUPPORTED_MERGE_STRATEGIES:
        return {"status": "failed", "reason": "unsupported_merge_strategy"}

    facts = list(payload.get("facts", []))
    documents = list(payload.get("documents", []))
    episodes = list(payload.get("episodes", []))
    chunks = list(payload.get("chunks", []))
    relations = list(payload.get("relations", []))
    source_refs = list(payload.get("source_refs", []))
    if not dry_run and _contains_redacted_memory(
        payload,
        facts=facts,
        episodes=episodes,
        chunks=chunks,
    ):
        return {"status": "refused", "reason": "redacted_memory_scope_export_cannot_be_imported"}

    async with AsyncSession(engine) as session:
        target_memory_scope_id = memory_scope_id
        created_memory_scope: dict[str, str] | None = None
        import_batch_id = _stable_id("import", source_name, now.isoformat())
        fact_id_map: dict[str, str] = {}
        document_id_map: dict[str, str] = {}
        episode_id_map: dict[str, str] = {}
        chunk_id_map: dict[str, str] = {}
        relation_id_map: dict[str, str] = {}
        thread_id_map: dict[str, str] = {}

        if merge_strategy == "create_new_memory_scope" and not dry_run:
            memory_scope = await _create_import_memory_scope(
                session,
                space_id=space_id,
                base_memory_scope_id=memory_scope_id,
                now=now,
            )
            target_memory_scope_id = memory_scope.id
            created_memory_scope = {
                "id": memory_scope.id,
                "external_ref": memory_scope.external_ref,
            }
            fact_id_map = _build_id_map("fact", facts, target_memory_scope_id, import_batch_id)
            document_id_map = _build_id_map(
                "doc", documents, target_memory_scope_id, import_batch_id
            )
            episode_id_map = _build_id_map(
                "episode", episodes, target_memory_scope_id, import_batch_id
            )
            chunk_id_map = _build_id_map("chunk", chunks, target_memory_scope_id, import_batch_id)
            relation_id_map = _build_id_map(
                "relation", relations, target_memory_scope_id, import_batch_id
            )
            thread_id_map = _build_thread_id_map(
                episodes=episodes,
                memory_scope_id=target_memory_scope_id,
                import_batch_id=import_batch_id,
            )
        if episodes and not dry_run and not thread_id_map:
            thread_id_map = _build_thread_id_map(
                episodes=episodes,
                memory_scope_id=target_memory_scope_id,
                import_batch_id=import_batch_id,
            )

        conflict_ids = (
            []
            if merge_strategy == "create_new_memory_scope"
            else await memory_scope_snapshot_conflicts(
                session,
                space_id=space_id,
                memory_scope_id=target_memory_scope_id,
                facts=facts,
                documents=documents,
                episodes=episodes,
                chunks=chunks,
                relations=relations,
            )
        )
        conflict_id_set = set(conflict_ids)
        preview = build_memory_scope_snapshot_import_preview(
            payload=payload,
            merge_strategy=merge_strategy,
            conflict_ids=conflict_id_set,
        )
        if conflict_ids and merge_strategy == "fail_on_conflict":
            return {
                "status": "conflict",
                "conflict_count": len(conflict_ids),
                "conflict_ids": conflict_ids[:20],
                "dry_run": dry_run,
                "preview": preview,
            }
        if dry_run:
            skipped = skipped_snapshot_ids(
                merge_strategy=merge_strategy,
                conflict_ids=conflict_id_set,
                facts=facts,
                documents=documents,
                episodes=episodes,
                chunks=chunks,
                relations=relations,
            )
            result: dict[str, object] = {
                "status": "ok",
                "dry_run": True,
                "would_import": import_counts(
                    facts=facts,
                    documents=documents,
                    episodes=episodes,
                    chunks=chunks,
                    relations=relations,
                    source_refs=source_refs,
                    skipped=skipped,
                ),
                "conflict_count": len(conflict_ids),
                "merge_strategy": merge_strategy,
                "preview": preview,
            }
            if merge_strategy == "create_new_memory_scope":
                result["would_create_memory_scope"] = True
                preview["would_create_memory_scope"] = True
            return {
                **result,
            }

        skipped = skipped_snapshot_ids(
            merge_strategy=merge_strategy,
            conflict_ids=conflict_id_set,
            facts=facts,
            documents=documents,
            episodes=episodes,
            chunks=chunks,
            relations=relations,
        )
        if merge_strategy == "supersede_matching_facts":
            superseded_fact_ids = _fact_conflict_ids(
                facts=facts,
                conflict_ids=conflict_id_set,
            )
            fact_id_map = {
                fact_id: _stable_id("fact", target_memory_scope_id, fact_id, import_batch_id)
                for fact_id in superseded_fact_ids
            }
            await _supersede_facts(session, fact_ids=superseded_fact_ids, now=now)
            for fact_id in superseded_fact_ids:
                session.add(
                    _outbox(
                        event_type="graph.delete_fact",
                        aggregate_type="fact",
                        aggregate_id=fact_id,
                        now=now,
                        payload={"fact_id": fact_id},
                    )
                )

        imported_fact_versions: dict[str, int] = {}
        for fact in facts:
            if str(fact["id"]) in skipped["facts"]:
                continue
            mapped = _remap_fact(fact, fact_id_map=fact_id_map)
            session.add(
                _fact_from_json(
                    mapped,
                    space_id=space_id,
                    memory_scope_id=target_memory_scope_id,
                    now=now,
                )
            )
            imported_fact_versions[str(mapped["id"])] = int(mapped.get("version", 1))
        for document in documents:
            if str(document["id"]) in skipped["documents"]:
                continue
            mapped = _remap_document(document, document_id_map=document_id_map)
            session.add(
                _document_from_json(
                    mapped,
                    space_id=space_id,
                    memory_scope_id=target_memory_scope_id,
                    now=now,
                )
            )
        await _ensure_import_threads(
            session,
            episodes=episodes,
            skipped_episode_ids=skipped["episodes"],
            thread_id_map=thread_id_map,
            space_id=space_id,
            memory_scope_id=target_memory_scope_id,
            now=now,
        )
        for episode in episodes:
            if str(episode["id"]) in skipped["episodes"]:
                continue
            mapped = _remap_episode(
                episode,
                episode_id_map=episode_id_map,
                thread_id_map=thread_id_map,
            )
            session.add(
                _episode_from_json(
                    mapped,
                    space_id=space_id,
                    memory_scope_id=target_memory_scope_id,
                    now=now,
                )
            )
        for chunk in chunks:
            if str(chunk["id"]) in skipped["chunks"]:
                continue
            mapped = _remap_chunk(
                chunk,
                document_id_map=document_id_map,
                episode_id_map=episode_id_map,
                chunk_id_map=chunk_id_map,
                thread_id_map=thread_id_map,
            )
            session.add(
                _chunk_from_json(
                    mapped,
                    space_id=space_id,
                    memory_scope_id=target_memory_scope_id,
                    now=now,
                )
            )
            session.add(
                _outbox(
                    event_type="vector.upsert_chunk",
                    aggregate_type="chunk",
                    aggregate_id=str(mapped["id"]),
                    now=now,
                    payload={"chunk_id": str(mapped["id"])},
                )
            )
        imported_refs_by_fact: set[str] = set()
        for ref in source_refs:
            if str(ref["fact_id"]) in skipped["facts"]:
                continue
            if ref.get("chunk_id") is not None and str(ref["chunk_id"]) in skipped["chunks"]:
                continue
            mapped = _remap_source_ref(
                ref,
                fact_id_map=fact_id_map,
                chunk_id_map=chunk_id_map,
                skipped_chunk_ids=skipped["chunks"],
            )
            fact_id = str(mapped["fact_id"])
            if fact_id not in imported_fact_versions:
                continue
            session.add(_source_ref_from_json(mapped))
            imported_refs_by_fact.add(fact_id)
        for relation in relations:
            if str(relation["id"]) in skipped["relations"]:
                continue
            if str(relation["source_fact_id"]) in skipped["facts"]:
                continue
            if str(relation["target_fact_id"]) in skipped["facts"]:
                continue
            mapped = remap_relation(
                relation,
                fact_id_map=fact_id_map,
                relation_id_map=relation_id_map,
            )
            session.add(
                relation_from_json(
                    mapped,
                    space_id=space_id,
                    memory_scope_id=target_memory_scope_id,
                    now=now,
                )
            )
        for fact_id, fact_version in imported_fact_versions.items():
            if fact_id in imported_refs_by_fact:
                continue
            session.add(
                MemorySourceRefRow(
                    fact_id=fact_id,
                    fact_version=fact_version,
                    source_type="import",
                    source_id=_bounded_optional_text(f"memory_scope-import:{source_name}", 160)
                    or "memory_scope-import",
                    chunk_id=None,
                    char_start=None,
                    char_end=None,
                    quote_preview=None,
                )
            )
        for fact in facts:
            if str(fact["id"]) in skipped["facts"] or str(fact.get("status", "active")) != "active":
                continue
            mapped_fact_id = fact_id_map.get(str(fact["id"]), str(fact["id"]))
            session.add(
                _outbox(
                    event_type="graph.upsert_fact",
                    aggregate_type="fact",
                    aggregate_id=mapped_fact_id,
                    aggregate_version=int(fact.get("version", 1)),
                    now=now,
                    payload={"fact_id": mapped_fact_id},
                )
            )
        await session.commit()

    result = {
        "status": "ok",
        "dry_run": False,
        "merge_strategy": merge_strategy,
        "imported": import_counts(
            facts=facts,
            documents=documents,
            episodes=episodes,
            chunks=chunks,
            relations=relations,
            source_refs=source_refs,
            skipped=skipped,
        ),
        "preview": preview,
    }
    if created_memory_scope is not None:
        result["created_memory_scope"] = created_memory_scope
    return result


async def _load_scope(
    session: AsyncSession,
    *,
    space_slug: str,
    memory_scope_external_ref: str,
) -> tuple[MemorySpaceRow, MemoryScopeRow] | None:
    space = (
        await session.execute(
            select(MemorySpaceRow).where(
                MemorySpaceRow.slug == space_slug,
                MemorySpaceRow.status == "active",
            )
        )
    ).scalar_one_or_none()
    if space is None:
        return None
    memory_scope = (
        await session.execute(
            select(MemoryScopeRow).where(
                MemoryScopeRow.space_id == space.id,
                MemoryScopeRow.external_ref == memory_scope_external_ref,
                MemoryScopeRow.status == "active",
            )
        )
    ).scalar_one_or_none()
    if memory_scope is None:
        return None
    return space, memory_scope


def _fact_conflict_ids(
    *,
    facts: list[dict[str, Any]],
    conflict_ids: set[str],
) -> set[str]:
    return {str(item["id"]) for item in facts if str(item["id"]) in conflict_ids}


async def _supersede_facts(
    session: AsyncSession,
    *,
    fact_ids: set[str],
    now: datetime,
) -> None:
    if not fact_ids:
        return
    rows = (
        await session.execute(
            select(MemoryFactRow)
            .where(MemoryFactRow.id.in_(fact_ids), MemoryFactRow.status == "active")
            .with_for_update()
        )
    ).scalars()
    for row in rows:
        row.status = "superseded"
        row.version += 1
        row.updated_at = now


async def _create_import_memory_scope(
    session: AsyncSession,
    *,
    space_id: str,
    base_memory_scope_id: str,
    now: datetime,
) -> MemoryScopeRow:
    base_memory_scope = await session.get(MemoryScopeRow, base_memory_scope_id)
    if base_memory_scope is None:
        msg = "Base memory_scope not found"
        raise ValueError(msg)
    external_ref = await _next_import_memory_scope_ref(
        session,
        space_id=space_id,
        base_external_ref=base_memory_scope.external_ref,
        now=now,
    )
    row = MemoryScopeRow(
        id=_stable_id("memory_scope", space_id, external_ref),
        space_id=space_id,
        external_ref=external_ref,
        name=f"{base_memory_scope.name} import",
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    return row


async def _next_import_memory_scope_ref(
    session: AsyncSession,
    *,
    space_id: str,
    base_external_ref: str,
    now: datetime,
) -> str:
    base = _bounded_external_ref(
        f"{base_external_ref}-import-{now.strftime('%Y%m%d%H%M%S')}",
        suffix="",
    )
    candidate = base
    suffix = 2
    while await _memory_scope_ref_exists(session, space_id=space_id, external_ref=candidate):
        candidate = _bounded_external_ref(base, suffix=f"-{suffix}")
        suffix += 1
    return candidate


async def _memory_scope_ref_exists(
    session: AsyncSession,
    *,
    space_id: str,
    external_ref: str,
) -> bool:
    return (
        await session.scalar(
            select(MemoryScopeRow.id).where(
                MemoryScopeRow.space_id == space_id,
                MemoryScopeRow.external_ref == external_ref,
            )
        )
        is not None
    )


def _bounded_external_ref(value: str, *, suffix: str) -> str:
    limit = 200 - len(suffix)
    return f"{value[:limit].rstrip('-')}{suffix}"


def _build_id_map(
    prefix: str,
    items: list[dict[str, Any]],
    memory_scope_id: str,
    import_batch_id: str,
) -> dict[str, str]:
    return {
        str(item["id"]): _stable_id(prefix, memory_scope_id, str(item["id"]), import_batch_id)
        for item in items
    }


def _build_thread_id_map(
    *,
    episodes: list[dict[str, Any]],
    memory_scope_id: str,
    import_batch_id: str,
) -> dict[str, str]:
    source_thread_ids = sorted(
        {
            _episode_source_thread_id(episode)
            for episode in episodes
            if episode.get("id") is not None
        }
    )
    return {
        thread_id: _stable_id("thread", memory_scope_id, thread_id, import_batch_id)
        for thread_id in source_thread_ids
    }


async def _ensure_import_threads(
    session: AsyncSession,
    *,
    episodes: list[dict[str, Any]],
    skipped_episode_ids: set[str],
    thread_id_map: dict[str, str],
    space_id: str,
    memory_scope_id: str,
    now: datetime,
) -> None:
    needed = {
        _episode_source_thread_id(episode): thread_id_map.get(
            _episode_source_thread_id(episode),
            _episode_source_thread_id(episode),
        )
        for episode in episodes
        if str(episode.get("id")) not in skipped_episode_ids
    }
    if not needed:
        return
    existing = set(
        (
            await session.execute(
                select(MemoryThreadRow.id).where(MemoryThreadRow.id.in_(set(needed.values())))
            )
        ).scalars()
    )
    for source_thread_id, target_thread_id in needed.items():
        if target_thread_id in existing:
            continue
        session.add(
            MemoryThreadRow(
                id=target_thread_id,
                space_id=space_id,
                memory_scope_id=memory_scope_id,
                external_ref=_import_thread_external_ref(source_thread_id, target_thread_id),
                status="active",
                created_at=now,
                updated_at=now,
            )
        )


def _remap_fact(item: dict[str, Any], *, fact_id_map: dict[str, str]) -> dict[str, Any]:
    fact_id = str(item["id"])
    if fact_id not in fact_id_map:
        return item
    return {**item, "id": fact_id_map[fact_id]}


def _remap_document(
    item: dict[str, Any],
    *,
    document_id_map: dict[str, str],
) -> dict[str, Any]:
    document_id = str(item["id"])
    if document_id not in document_id_map:
        return item
    return {**item, "id": document_id_map[document_id]}


def _remap_episode(
    item: dict[str, Any],
    *,
    episode_id_map: dict[str, str],
    thread_id_map: dict[str, str],
) -> dict[str, Any]:
    episode_id = str(item["id"])
    source_thread_id = _episode_source_thread_id(item)
    return {
        **item,
        "id": episode_id_map.get(episode_id, episode_id),
        "thread_id": thread_id_map.get(source_thread_id, source_thread_id),
    }


def _remap_chunk(
    item: dict[str, Any],
    *,
    document_id_map: dict[str, str],
    episode_id_map: dict[str, str],
    chunk_id_map: dict[str, str],
    thread_id_map: dict[str, str],
) -> dict[str, Any]:
    chunk_id = str(item["id"])
    document_id = item.get("document_id")
    episode_id = item.get("episode_id")
    thread_id = item.get("thread_id")
    mapped_thread_id = None
    if episode_id is not None and thread_id is not None:
        mapped_thread_id = thread_id_map.get(str(thread_id), str(thread_id))
    return {
        **item,
        "id": chunk_id_map.get(chunk_id, chunk_id),
        "thread_id": mapped_thread_id,
        "document_id": (
            document_id_map.get(str(document_id), str(document_id))
            if document_id is not None
            else None
        ),
        "episode_id": (
            episode_id_map.get(str(episode_id), str(episode_id))
            if episode_id is not None
            else None
        ),
    }


def _remap_source_ref(
    item: dict[str, Any],
    *,
    fact_id_map: dict[str, str],
    chunk_id_map: dict[str, str],
    skipped_chunk_ids: set[str],
) -> dict[str, Any]:
    chunk_id = item.get("chunk_id")
    mapped_chunk_id = None
    if chunk_id is not None and str(chunk_id) not in skipped_chunk_ids:
        mapped_chunk_id = chunk_id_map.get(str(chunk_id), str(chunk_id))
    return {
        **item,
        "fact_id": fact_id_map.get(str(item["fact_id"]), str(item["fact_id"])),
        "chunk_id": mapped_chunk_id,
    }


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("\u241f".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _episode_source_thread_id(item: dict[str, Any]) -> str:
    return str(item.get("thread_id") or item["id"])


def _import_thread_external_ref(source_thread_id: str, target_thread_id: str) -> str:
    return _bounded_external_ref(
        f"imported-{source_thread_id}",
        suffix=f"-{target_thread_id[-8:]}",
    )


def _outbox(
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    now: datetime,
    payload: dict[str, object],
    aggregate_version: int | None = None,
) -> MemoryOutboxRow:
    return MemoryOutboxRow(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        aggregate_version=aggregate_version,
        workload_class="projection",
        fairness_key=f"{aggregate_type}:{aggregate_id}",
        payload_json=payload,
        status="pending",
        attempt_count=0,
        next_attempt_at=now,
        last_safe_error=None,
        created_at=now,
        updated_at=now,
    )
