"""Small support helpers for MemoryScope snapshot transfer."""

from __future__ import annotations

import re
from datetime import datetime
from hashlib import sha256
from typing import Any

from memo_stack_adapters.postgres.models import MemoryOutboxRow

from memo_stack_server.memory_scope_transfer_remap import episode_source_thread_id

_MAX_FILENAME_CHARS = 240
_SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("\u241f".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def bounded_external_ref(value: str, *, suffix: str) -> str:
    limit = 200 - len(suffix)
    return f"{value[:limit].rstrip('-')}{suffix}"


def build_id_map(
    prefix: str,
    items: list[dict[str, Any]],
    memory_scope_id: str,
    import_batch_id: str,
) -> dict[str, str]:
    return {
        str(item["id"]): stable_id(prefix, memory_scope_id, str(item["id"]), import_batch_id)
        for item in items
    }


def build_thread_id_map(
    *,
    episodes: list[dict[str, Any]],
    memory_scope_id: str,
    import_batch_id: str,
) -> dict[str, str]:
    source_thread_ids = sorted(
        {
            episode_source_thread_id(episode)
            for episode in episodes
            if episode.get("id") is not None
        }
    )
    return {
        thread_id: stable_id("thread", memory_scope_id, thread_id, import_batch_id)
        for thread_id in source_thread_ids
    }


def import_thread_external_ref(source_thread_id: str, target_thread_id: str) -> str:
    return bounded_external_ref(
        f"imported-{source_thread_id}",
        suffix=f"-{target_thread_id[-8:]}",
    )


def asset_storage_key(*, space_id: str, memory_scope_id: str, digest: str, filename: str) -> str:
    safe_name = _safe_filename(filename)
    return f"{space_id}/{memory_scope_id}/{digest[:2]}/{digest}/{safe_name}"


def outbox(
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


def _safe_filename(filename: str) -> str:
    value = _SAFE_FILENAME_PATTERN.sub("_", filename.strip())[:_MAX_FILENAME_CHARS]
    return value.strip("._") or "asset.bin"
