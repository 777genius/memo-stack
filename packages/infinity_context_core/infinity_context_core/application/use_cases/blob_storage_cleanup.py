"""Production-safe blob storage cleanup use case."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256

from infinity_context_core.domain.errors import MemoryValidationError
from infinity_context_core.ports.assets import BlobStorageMaintenancePort, StoredBlobObject
from infinity_context_core.ports.clock import ClockPort
from infinity_context_core.ports.unit_of_work import UnitOfWorkFactoryPort

_MAX_REPORT_ITEMS = 200


@dataclass(frozen=True)
class BlobStorageCleanupCommand:
    storage_backend: str
    prefix: str = ""
    dry_run: bool = True
    max_objects: int = 500
    max_deletions: int = 100
    grace_period_seconds: int = 86_400
    cursor: str | None = None


@dataclass(frozen=True)
class BlobStorageCleanupDecision:
    action: str
    reason: str
    storage_key_hash: str
    storage_key_extension: str | None
    storage_key_path_depth: int
    byte_size: int | None
    updated_at: datetime | None


@dataclass(frozen=True)
class BlobStorageCleanupResult:
    status: str
    dry_run: bool
    storage_backend: str
    prefix: str
    scanned_count: int
    referenced_count: int
    recent_count: int
    unknown_updated_at_count: int
    orphan_candidate_count: int
    delete_attempt_count: int
    deleted_count: int
    delete_error_count: int
    deletion_limit_count: int
    next_cursor: str | None
    decisions: tuple[BlobStorageCleanupDecision, ...]
    diagnostics: dict[str, object]


class RunBlobStorageCleanupUseCase:
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactoryPort,
        blob_storage: BlobStorageMaintenancePort,
        clock: ClockPort,
    ) -> None:
        self._uow_factory = uow_factory
        self._blob_storage = blob_storage
        self._clock = clock

    async def execute(self, command: BlobStorageCleanupCommand) -> BlobStorageCleanupResult:
        storage_backend = _required_text(command.storage_backend, "storage_backend", max_chars=80)
        prefix = _normalize_prefix(command.prefix)
        max_objects = max(1, min(command.max_objects, 5_000))
        max_deletions = max(0, min(command.max_deletions, max_objects))
        grace_period_seconds = max(60, min(command.grace_period_seconds, 90 * 86_400))

        page = await self._blob_storage.list_objects(
            prefix=prefix,
            limit=max_objects,
            cursor=command.cursor,
        )
        cutoff = self._clock.now() - timedelta(seconds=grace_period_seconds)
        objects = tuple(
            item for item in page.objects if _is_under_prefix(item.storage_key, prefix=prefix)
        )
        old_objects: list[StoredBlobObject] = []
        recent_count = 0
        unknown_updated_at_count = 0
        decisions: list[BlobStorageCleanupDecision] = []
        for item in objects:
            if item.updated_at is None:
                unknown_updated_at_count += 1
                _append_decision(
                    decisions,
                    item=item,
                    action="skip",
                    reason="unknown_updated_at",
                )
                continue
            if item.updated_at > cutoff:
                recent_count += 1
                _append_decision(
                    decisions,
                    item=item,
                    action="skip",
                    reason="within_grace_period",
                )
                continue
            old_objects.append(item)

        candidate_keys = tuple(item.storage_key for item in old_objects)
        referenced_keys: set[str] = set()
        if candidate_keys:
            async with self._uow_factory() as uow:
                referenced_keys = await uow.assets.list_stored_storage_keys(
                    storage_backend=storage_backend,
                    storage_keys=candidate_keys,
                )
                referenced_keys.update(
                    await uow.asset_extractions.list_retained_artifact_storage_keys(
                        storage_backend=storage_backend,
                        storage_keys=candidate_keys,
                    )
                )

        deleted_count = 0
        delete_attempt_count = 0
        delete_error_count = 0
        orphan_candidate_count = 0
        deletion_limit_count = 0
        for item in old_objects:
            if item.storage_key in referenced_keys:
                _append_decision(
                    decisions,
                    item=item,
                    action="skip",
                    reason="referenced_by_canonical_memory",
                )
                continue
            orphan_candidate_count += 1
            if delete_attempt_count >= max_deletions:
                deletion_limit_count += 1
                _append_decision(
                    decisions,
                    item=item,
                    action="skip",
                    reason="deletion_limit_reached",
                )
                continue
            if command.dry_run:
                _append_decision(
                    decisions,
                    item=item,
                    action="would_delete",
                    reason="orphan_blob",
                )
                delete_attempt_count += 1
                continue
            delete_attempt_count += 1
            try:
                await self._blob_storage.delete(storage_key=item.storage_key)
            except Exception:
                delete_error_count += 1
                _append_decision(
                    decisions,
                    item=item,
                    action="delete_failed",
                    reason="storage_delete_error",
                )
                continue
            deleted_count += 1
            _append_decision(
                decisions,
                item=item,
                action="deleted",
                reason="orphan_blob",
            )

        return BlobStorageCleanupResult(
            status="ok" if delete_error_count == 0 else "degraded",
            dry_run=command.dry_run,
            storage_backend=storage_backend,
            prefix=prefix,
            scanned_count=len(objects),
            referenced_count=len(referenced_keys),
            recent_count=recent_count,
            unknown_updated_at_count=unknown_updated_at_count,
            orphan_candidate_count=orphan_candidate_count,
            delete_attempt_count=delete_attempt_count,
            deleted_count=deleted_count,
            delete_error_count=delete_error_count,
            deletion_limit_count=deletion_limit_count,
            next_cursor=page.next_cursor,
            decisions=tuple(decisions),
            diagnostics={
                "cleanup_policy_version": "blob-storage-cleanup-v1",
                "grace_period_seconds": grace_period_seconds,
                "max_objects": max_objects,
                "max_deletions": max_deletions,
                "report_items_truncated": len(decisions) >= _MAX_REPORT_ITEMS,
                "storage_keys_are_redacted": True,
            },
        )


def _append_decision(
    decisions: list[BlobStorageCleanupDecision],
    *,
    item: StoredBlobObject,
    action: str,
    reason: str,
) -> None:
    if len(decisions) >= _MAX_REPORT_ITEMS:
        return
    decisions.append(
        BlobStorageCleanupDecision(
            action=action,
            reason=reason,
            storage_key_hash=sha256(item.storage_key.encode("utf-8")).hexdigest()[:16],
            storage_key_extension=_extension(item.storage_key),
            storage_key_path_depth=sum(1 for part in item.storage_key.split("/") if part),
            byte_size=item.byte_size,
            updated_at=item.updated_at,
        )
    )


def _normalize_prefix(prefix: str) -> str:
    normalized = prefix.strip().replace("\\", "/").strip("/")
    if not normalized:
        return ""
    if (
        normalized.startswith("/")
        or "\x00" in normalized
        or any(ord(char) < 32 for char in normalized)
        or any(part in {"", ".", ".."} for part in normalized.split("/"))
    ):
        raise MemoryValidationError("Invalid blob cleanup prefix")
    return normalized


def _is_under_prefix(storage_key: str, *, prefix: str) -> bool:
    if not prefix:
        return True
    return storage_key == prefix or storage_key.startswith(f"{prefix}/")


def _required_text(value: str, field: str, *, max_chars: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise MemoryValidationError(f"{field} is required")
    return normalized[:max_chars]


def _extension(storage_key: str) -> str | None:
    filename = storage_key.rsplit("/", 1)[-1]
    if "." not in filename:
        return None
    suffix = filename.rsplit(".", 1)[-1].strip().lower()
    if not suffix or len(suffix) > 24:
        return None
    return f".{suffix}"
