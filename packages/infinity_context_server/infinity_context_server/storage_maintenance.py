"""Scheduled asset storage maintenance orchestration."""

from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING

from infinity_context_core.application import (
    BlobStorageCleanupCommand,
    BlobStorageCleanupResult,
    BlobStorageIntegrityAuditCommand,
    BlobStorageIntegrityAuditResult,
)

if TYPE_CHECKING:
    from infinity_context_server.composition import Container


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
    cleanup_result = await _run_cleanup(container)
    integrity_result = await _run_integrity_audit(container)
    trace.update(_cleanup_trace(cleanup_result))
    trace.update(_integrity_trace(integrity_result))
    if cleanup_result["status"] != "ok" or integrity_result["status"] != "ok":
        trace["status"] = "degraded"
    finished_at = container.clock.now()
    trace["finished_at"] = finished_at
    trace["duration_ms"] = round(max(0.0, (perf_counter() - started_monotonic) * 1000), 2)
    container.runtime_metrics.record_storage_maintenance(
        trace=trace,
        started_at=started_at,
    )
    return trace


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
