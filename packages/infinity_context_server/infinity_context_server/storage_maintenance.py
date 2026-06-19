"""Scheduled asset storage maintenance orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from hashlib import blake2b
from time import perf_counter
from typing import TYPE_CHECKING

from infinity_context_core.application import (
    BlobStorageCleanupCommand,
    BlobStorageCleanupResult,
    BlobStorageIntegrityAuditCommand,
    BlobStorageIntegrityAuditResult,
)
from sqlalchemy import text

if TYPE_CHECKING:
    from infinity_context_server.composition import Container

_IN_PROCESS_LOCK = asyncio.Lock()
_LOCK_KEY = int.from_bytes(
    blake2b(
        b"infinity-context:asset-storage-maintenance:v1",
        digest_size=8,
    ).digest(),
    byteorder="big",
    signed=True,
)


@dataclass(frozen=True)
class MaintenanceLock:
    acquired: bool
    backend: str


async def run_asset_storage_maintenance(container: Container) -> dict[str, object]:
    settings = container.settings
    started_at = container.clock.now()
    started_monotonic = perf_counter()
    trace: dict[str, object] = {
        "span": "asset_storage.maintenance",
        "status": "ok",
        "started_at": started_at,
        "storage_backend": settings.asset_storage_backend,
        "maintenance_enabled": settings.asset_storage_maintenance_enabled,
    }
    async with acquire_asset_storage_maintenance_lock(container) as lock:
        trace["lock_backend"] = lock.backend
        trace["lock_acquired"] = lock.acquired
        if not lock.acquired:
            trace["status"] = "skipped"
            trace["lock_skipped"] = True
            return _record_trace(container, trace, started_at, started_monotonic)
        cleanup_result = await _run_cleanup(container)
        integrity_result = await _run_integrity_audit(container)
        trace.update(_cleanup_trace(cleanup_result))
        trace.update(_integrity_trace(integrity_result))
        if cleanup_result["status"] != "ok" or integrity_result["status"] != "ok":
            trace["status"] = "degraded"
        return _record_trace(container, trace, started_at, started_monotonic)


@asynccontextmanager
async def acquire_asset_storage_maintenance_lock(
    container: Container,
) -> AsyncIterator[MaintenanceLock]:
    dialect_name = container.engine.dialect.name
    if dialect_name == "postgresql":
        async with container.engine.connect() as connection:
            acquired = bool(
                await connection.scalar(
                    text("select pg_try_advisory_lock(:lock_key)"),
                    {"lock_key": _LOCK_KEY},
                )
            )
            if not acquired:
                yield MaintenanceLock(acquired=False, backend="postgres_advisory_lock")
                return
            try:
                yield MaintenanceLock(acquired=True, backend="postgres_advisory_lock")
            finally:
                await connection.scalar(
                    text("select pg_advisory_unlock(:lock_key)"),
                    {"lock_key": _LOCK_KEY},
                )
        return
    if _IN_PROCESS_LOCK.locked():
        yield MaintenanceLock(acquired=False, backend="in_process")
        return
    await _IN_PROCESS_LOCK.acquire()
    try:
        yield MaintenanceLock(acquired=True, backend="in_process")
    finally:
        _IN_PROCESS_LOCK.release()


async def _run_cleanup(container: Container) -> dict[str, object]:
    settings = container.settings
    try:
        result = await container.run_blob_storage_cleanup.execute(
            BlobStorageCleanupCommand(
                storage_backend=settings.asset_storage_backend,
                prefix=settings.asset_storage_maintenance_prefix,
                dry_run=not settings.asset_storage_cleanup_apply_enabled,
                max_objects=settings.asset_storage_maintenance_limit,
                max_deletions=settings.asset_storage_cleanup_max_deletions,
                grace_period_seconds=settings.asset_storage_cleanup_grace_period_seconds,
            )
        )
        return {"status": result.status, "result": result}
    except Exception as exc:
        return {"status": "degraded", "safe_error_code": exc.__class__.__name__}


async def _run_integrity_audit(container: Container) -> dict[str, object]:
    settings = container.settings
    try:
        result = await container.run_blob_storage_integrity_audit.execute(
            BlobStorageIntegrityAuditCommand(
                storage_backend=settings.asset_storage_backend,
                prefix=settings.asset_storage_maintenance_prefix,
                max_references=settings.asset_storage_maintenance_limit,
                max_blob_read_bytes=settings.asset_storage_integrity_max_blob_read_bytes,
            )
        )
        return {"status": result.status, "result": result}
    except Exception as exc:
        return {"status": "degraded", "safe_error_code": exc.__class__.__name__}


def _cleanup_trace(payload: dict[str, object]) -> dict[str, object]:
    result = payload.get("result")
    if not isinstance(result, BlobStorageCleanupResult):
        return {
            "cleanup_status": "degraded",
            "safe_error_code": payload.get("safe_error_code") or "storage_cleanup_error",
        }
    return {
        "cleanup_status": result.status,
        "cleanup_dry_run": result.dry_run,
        "cleanup_scanned_count": result.scanned_count,
        "cleanup_orphan_candidate_count": result.orphan_candidate_count,
        "cleanup_deleted_count": result.deleted_count,
        "cleanup_delete_error_count": result.delete_error_count,
    }


def _integrity_trace(payload: dict[str, object]) -> dict[str, object]:
    result = payload.get("result")
    if not isinstance(result, BlobStorageIntegrityAuditResult):
        return {
            "integrity_status": "degraded",
            "safe_error_code": payload.get("safe_error_code") or "storage_integrity_error",
        }
    return {
        "integrity_status": result.status,
        "integrity_scanned_count": result.scanned_count,
        "integrity_missing_count": result.missing_count,
        "integrity_byte_size_mismatch_count": result.byte_size_mismatch_count,
        "integrity_checksum_mismatch_count": result.checksum_mismatch_count,
        "integrity_checksum_skipped_count": result.checksum_skipped_count,
        "integrity_read_error_count": result.read_error_count,
        "integrity_stat_error_count": result.stat_error_count,
    }


def _record_trace(
    container: Container,
    trace: dict[str, object],
    started_at,
    started_monotonic: float,
) -> dict[str, object]:
    finished_at = container.clock.now()
    trace["finished_at"] = finished_at
    trace["duration_ms"] = round(max(0.0, (perf_counter() - started_monotonic) * 1000), 2)
    container.runtime_metrics.record_storage_maintenance(
        trace=trace,
        started_at=started_at,
    )
    return trace
