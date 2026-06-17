"""ID remapping helpers for memory_scope snapshot imports."""

from __future__ import annotations

from typing import Any

from memo_stack_server.memory_scope_transfer_records import bounded_optional_text


def remap_fact(item: dict[str, Any], *, fact_id_map: dict[str, str]) -> dict[str, Any]:
    fact_id = str(item["id"])
    if fact_id not in fact_id_map:
        return item
    return {**item, "id": fact_id_map[fact_id]}


def remap_document(
    item: dict[str, Any],
    *,
    document_id_map: dict[str, str],
) -> dict[str, Any]:
    document_id = str(item["id"])
    if document_id not in document_id_map:
        return item
    return {**item, "id": document_id_map[document_id]}


def remap_episode(
    item: dict[str, Any],
    *,
    episode_id_map: dict[str, str],
    thread_id_map: dict[str, str],
) -> dict[str, Any]:
    episode_id = str(item["id"])
    source_thread_id = episode_source_thread_id(item)
    return {
        **item,
        "id": episode_id_map.get(episode_id, episode_id),
        "thread_id": thread_id_map.get(source_thread_id, source_thread_id),
    }


def remap_chunk(
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


def remap_source_ref(
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


def remap_capture(
    item: dict[str, Any],
    *,
    fact_id_map: dict[str, str],
    document_id_map: dict[str, str],
    episode_id_map: dict[str, str],
    chunk_id_map: dict[str, str],
    capture_id_map: dict[str, str],
    anchor_id_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    capture_id = str(item["id"])
    mapped_capture_id = capture_id_map.get(capture_id, capture_id)
    parent_capture_id = item.get("parent_capture_id")
    return {
        **item,
        "id": mapped_capture_id,
        "idempotency_key": _remap_capture_idempotency_key(
            item,
            mapped_capture_id=mapped_capture_id,
        ),
        "parent_capture_id": (
            capture_id_map.get(str(parent_capture_id), str(parent_capture_id))
            if parent_capture_id is not None
            else None
        ),
        "evidence_refs": _remap_capture_evidence_refs(
            item.get("evidence_refs"),
            fact_id_map=fact_id_map,
            document_id_map=document_id_map,
            episode_id_map=episode_id_map,
            chunk_id_map=chunk_id_map,
            capture_id_map=capture_id_map,
            anchor_id_map=anchor_id_map or {},
        ),
    }


def remap_anchor(
    item: dict[str, Any],
    *,
    anchor_id_map: dict[str, str],
) -> dict[str, Any]:
    anchor_id = str(item["id"])
    if anchor_id not in anchor_id_map:
        return item
    return {**item, "id": anchor_id_map[anchor_id]}


def remap_context_link(
    item: dict[str, Any],
    *,
    context_link_id_map: dict[str, str],
    fact_id_map: dict[str, str],
    document_id_map: dict[str, str],
    episode_id_map: dict[str, str],
    chunk_id_map: dict[str, str],
    capture_id_map: dict[str, str],
    anchor_id_map: dict[str, str],
) -> dict[str, Any]:
    link_id = str(item["id"])
    source_type = str(item.get("source_type") or "")
    target_type = str(item.get("target_type") or "")
    return {
        **item,
        "id": context_link_id_map.get(link_id, link_id),
        "source_id": remap_endpoint_id(
            source_type=source_type,
            source_id=str(item.get("source_id")),
            fact_id_map=fact_id_map,
            document_id_map=document_id_map,
            episode_id_map=episode_id_map,
            chunk_id_map=chunk_id_map,
            capture_id_map=capture_id_map,
            anchor_id_map=anchor_id_map,
        ),
        "target_id": remap_endpoint_id(
            source_type=target_type,
            source_id=str(item.get("target_id")),
            fact_id_map=fact_id_map,
            document_id_map=document_id_map,
            episode_id_map=episode_id_map,
            chunk_id_map=chunk_id_map,
            capture_id_map=capture_id_map,
            anchor_id_map=anchor_id_map,
        ),
    }


def episode_source_thread_id(item: dict[str, Any]) -> str:
    return str(item.get("thread_id") or item["id"])


def _remap_capture_idempotency_key(
    item: dict[str, Any],
    *,
    mapped_capture_id: str,
) -> str:
    capture_id = str(item["id"])
    if mapped_capture_id == capture_id:
        return str(item.get("idempotency_key") or capture_id)
    return bounded_optional_text(f"imported-{mapped_capture_id}", 120) or mapped_capture_id


def _remap_capture_evidence_refs(
    value: object,
    *,
    fact_id_map: dict[str, str],
    document_id_map: dict[str, str],
    episode_id_map: dict[str, str],
    chunk_id_map: dict[str, str],
    capture_id_map: dict[str, str],
    anchor_id_map: dict[str, str],
) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    refs: list[dict[str, object]] = []
    for ref in value:
        if not isinstance(ref, dict):
            continue
        next_ref = dict(ref)
        source_type = str(next_ref.get("source_type") or "")
        source_id = next_ref.get("source_id")
        if source_id is not None:
            next_ref["source_id"] = _remap_evidence_source_id(
                source_type=source_type,
                source_id=str(source_id),
                fact_id_map=fact_id_map,
                document_id_map=document_id_map,
                episode_id_map=episode_id_map,
                chunk_id_map=chunk_id_map,
                capture_id_map=capture_id_map,
                anchor_id_map=anchor_id_map,
            )
        chunk_id = next_ref.get("chunk_id")
        if chunk_id is not None:
            next_ref["chunk_id"] = chunk_id_map.get(str(chunk_id), str(chunk_id))
        refs.append(next_ref)
    return refs


def _remap_evidence_source_id(
    *,
    source_type: str,
    source_id: str,
    fact_id_map: dict[str, str],
    document_id_map: dict[str, str],
    episode_id_map: dict[str, str],
    chunk_id_map: dict[str, str],
    capture_id_map: dict[str, str],
    anchor_id_map: dict[str, str],
) -> str:
    return remap_endpoint_id(
        source_type=source_type,
        source_id=source_id,
        fact_id_map=fact_id_map,
        document_id_map=document_id_map,
        episode_id_map=episode_id_map,
        chunk_id_map=chunk_id_map,
        capture_id_map=capture_id_map,
        anchor_id_map=anchor_id_map,
    )


def remap_endpoint_id(
    *,
    source_type: str,
    source_id: str,
    fact_id_map: dict[str, str],
    document_id_map: dict[str, str],
    episode_id_map: dict[str, str],
    chunk_id_map: dict[str, str],
    capture_id_map: dict[str, str],
    anchor_id_map: dict[str, str],
) -> str:
    if source_type == "fact":
        return fact_id_map.get(source_id, source_id)
    if source_type == "document":
        return document_id_map.get(source_id, source_id)
    if source_type == "episode":
        return episode_id_map.get(source_id, source_id)
    if source_type == "chunk":
        return chunk_id_map.get(source_id, source_id)
    if source_type == "capture":
        return capture_id_map.get(source_id, source_id)
    if source_type == "anchor":
        return anchor_id_map.get(source_id, source_id)
    return source_id
