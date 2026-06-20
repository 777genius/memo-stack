import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from infinity_context_core.application.use_cases.blob_storage_cleanup import (
    BlobStorageCleanupCommand,
    RunBlobStorageCleanupUseCase,
)
from infinity_context_core.domain.errors import MemoryValidationError
from infinity_context_core.ports.assets import StoredBlob, StoredBlobObject, StoredBlobPage

NOW = datetime(2026, 6, 19, 12, 0, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return NOW


class _BlobStorage:
    def __init__(self, objects: tuple[StoredBlobObject, ...]) -> None:
        self.objects = objects
        self.deleted: list[str] = []
        self.fail_delete_for: set[str] = set()

    async def write_bytes(self, *, storage_key: str, content: bytes) -> StoredBlob:
        raise AssertionError("not used")

    async def read_bytes(self, *, storage_key: str) -> bytes:
        raise AssertionError("not used")

    async def delete(self, *, storage_key: str) -> None:
        self.deleted.append(storage_key)
        if storage_key in self.fail_delete_for:
            raise RuntimeError("delete outage")

    async def list_objects(
        self,
        *,
        prefix: str = "",
        limit: int = 500,
        cursor: str | None = None,
    ) -> StoredBlobPage:
        del limit, cursor
        objects = tuple(
            item
            for item in self.objects
            if not prefix or item.storage_key == prefix or item.storage_key.startswith(f"{prefix}/")
        )
        return StoredBlobPage(objects=objects, next_cursor="next-page")


class _Assets:
    def __init__(self, referenced: set[str]) -> None:
        self.referenced = referenced
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    async def list_stored_storage_keys(
        self,
        *,
        storage_backend: str,
        storage_keys: tuple[str, ...],
    ) -> set[str]:
        self.calls.append((storage_backend, storage_keys))
        return set(storage_keys).intersection(self.referenced)


class _AssetExtractions:
    def __init__(self, referenced: set[str]) -> None:
        self.referenced = referenced
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    async def list_retained_artifact_storage_keys(
        self,
        *,
        storage_backend: str,
        storage_keys: tuple[str, ...],
    ) -> set[str]:
        self.calls.append((storage_backend, storage_keys))
        return set(storage_keys).intersection(self.referenced)


class _Uow:
    def __init__(self, assets: _Assets, asset_extractions: _AssetExtractions) -> None:
        self.assets = assets
        self.asset_extractions = asset_extractions

    async def __aenter__(self) -> "_Uow":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class _UowFactory:
    def __init__(self, assets: _Assets, asset_extractions: _AssetExtractions) -> None:
        self.assets = assets
        self.asset_extractions = asset_extractions

    def __call__(self) -> _Uow:
        return _Uow(self.assets, self.asset_extractions)


def test_blob_storage_cleanup_dry_run_keeps_referenced_recent_and_unknown_objects() -> None:
    async def run() -> None:
        storage = _BlobStorage(
            (
                _object("space/scope/old-orphan.txt", age_hours=48),
                _object("space/scope/referenced-asset.png", age_hours=48),
                _object("space/scope/referenced-artifact.md", age_hours=48),
                _object("space/scope/recent.wav", age_hours=1),
                StoredBlobObject(storage_key="space/scope/no-timestamp.bin", byte_size=20),
            )
        )
        assets = _Assets({"space/scope/referenced-asset.png"})
        asset_extractions = _AssetExtractions({"space/scope/referenced-artifact.md"})

        result = await _use_case(
            storage=storage,
            assets=assets,
            asset_extractions=asset_extractions,
        ).execute(
            BlobStorageCleanupCommand(
                storage_backend="local",
                prefix="space/scope",
                dry_run=True,
                grace_period_seconds=86_400,
            )
        )

        assert result.status == "ok"
        assert result.dry_run is True
        assert result.scanned_count == 5
        assert result.orphan_candidate_count == 1
        assert result.referenced_count == 2
        assert result.recent_count == 1
        assert result.unknown_updated_at_count == 1
        assert result.deleted_count == 0
        assert storage.deleted == []
        assert {decision.action for decision in result.decisions} == {"skip", "would_delete"}
        assert all(not hasattr(decision, "storage_key") for decision in result.decisions)
        assert result.diagnostics["storage_keys_are_redacted"] is True

    asyncio.run(run())


def test_blob_storage_cleanup_apply_deletes_only_old_orphans() -> None:
    async def run() -> None:
        storage = _BlobStorage(
            (
                _object("space/scope/old-orphan.txt", age_hours=48),
                _object("space/scope/referenced-asset.png", age_hours=48),
                _object("space/scope/recent.wav", age_hours=1),
            )
        )

        result = await _use_case(
            storage=storage,
            assets=_Assets({"space/scope/referenced-asset.png"}),
            asset_extractions=_AssetExtractions(set()),
        ).execute(
            BlobStorageCleanupCommand(
                storage_backend="local",
                prefix="space/scope",
                dry_run=False,
                grace_period_seconds=86_400,
            )
        )

        assert result.deleted_count == 1
        assert storage.deleted == ["space/scope/old-orphan.txt"]
        assert [decision.action for decision in result.decisions].count("deleted") == 1

    asyncio.run(run())


def test_blob_storage_cleanup_skips_unsafe_returned_keys_before_delete() -> None:
    async def run() -> None:
        storage = _BlobStorage(
            (
                _object("space/scope/old-orphan.txt", age_hours=48),
                _object("../outside.txt", age_hours=48),
                _object("/absolute.txt", age_hours=48),
                _object("space//empty-part.txt", age_hours=48),
                _object("space/./dot-part.txt", age_hours=48),
                _object("space\\scope\\backslash.txt", age_hours=48),
                _object("space/scope/control-\x01.txt", age_hours=48),
                _object(" space/scope/trimmed.txt", age_hours=48),
            )
        )

        result = await _use_case(
            storage=storage,
            assets=_Assets(set()),
            asset_extractions=_AssetExtractions(set()),
        ).execute(
            BlobStorageCleanupCommand(
                storage_backend="local",
                prefix="",
                dry_run=False,
                grace_period_seconds=86_400,
            )
        )

        assert result.status == "degraded"
        assert result.scanned_count == 8
        assert result.unsafe_storage_key_count == 7
        assert result.orphan_candidate_count == 1
        assert result.deleted_count == 1
        assert storage.deleted == ["space/scope/old-orphan.txt"]
        assert result.diagnostics["unsafe_storage_keys_skipped"] == 7
        assert result.diagnostics["degraded_reasons"] == ("unsafe_storage_key",)
        assert [decision.reason for decision in result.decisions].count("unsafe_storage_key") == 7

    asyncio.run(run())


def test_blob_storage_cleanup_reports_delete_errors_without_stopping_batch() -> None:
    async def run() -> None:
        storage = _BlobStorage(
            (
                _object("space/scope/fail.txt", age_hours=48),
                _object("space/scope/delete.txt", age_hours=48),
            )
        )
        storage.fail_delete_for.add("space/scope/fail.txt")

        result = await _use_case(
            storage=storage,
            assets=_Assets(set()),
            asset_extractions=_AssetExtractions(set()),
        ).execute(
            BlobStorageCleanupCommand(
                storage_backend="local",
                prefix="space/scope",
                dry_run=False,
                grace_period_seconds=86_400,
            )
        )

        assert result.status == "degraded"
        assert result.delete_error_count == 1
        assert result.deleted_count == 1
        assert storage.deleted == ["space/scope/fail.txt", "space/scope/delete.txt"]
        assert {decision.action for decision in result.decisions} == {
            "delete_failed",
            "deleted",
        }

    asyncio.run(run())


def test_blob_storage_cleanup_deletion_limit_counts_failed_attempts() -> None:
    async def run() -> None:
        storage = _BlobStorage(
            (
                _object("space/scope/fail.txt", age_hours=48),
                _object("space/scope/not-attempted.txt", age_hours=48),
            )
        )
        storage.fail_delete_for.add("space/scope/fail.txt")

        result = await _use_case(
            storage=storage,
            assets=_Assets(set()),
            asset_extractions=_AssetExtractions(set()),
        ).execute(
            BlobStorageCleanupCommand(
                storage_backend="local",
                prefix="space/scope",
                dry_run=False,
                max_deletions=1,
                grace_period_seconds=86_400,
            )
        )

        assert result.status == "degraded"
        assert result.delete_attempt_count == 1
        assert result.delete_error_count == 1
        assert result.deleted_count == 0
        assert result.deletion_limit_count == 1
        assert storage.deleted == ["space/scope/fail.txt"]

    asyncio.run(run())


def test_blob_storage_cleanup_respects_deletion_limit() -> None:
    async def run() -> None:
        storage = _BlobStorage(
            (
                _object("space/scope/a.txt", age_hours=48),
                _object("space/scope/b.txt", age_hours=48),
            )
        )

        result = await _use_case(
            storage=storage,
            assets=_Assets(set()),
            asset_extractions=_AssetExtractions(set()),
        ).execute(
            BlobStorageCleanupCommand(
                storage_backend="local",
                prefix="space/scope",
                dry_run=False,
                max_deletions=1,
                grace_period_seconds=86_400,
            )
        )

        assert result.orphan_candidate_count == 2
        assert result.delete_attempt_count == 1
        assert result.deleted_count == 1
        assert result.deletion_limit_count == 1
        assert len(storage.deleted) == 1

    asyncio.run(run())


def test_blob_storage_cleanup_rejects_unsafe_prefix() -> None:
    async def run() -> None:
        with pytest.raises(MemoryValidationError):
            await _use_case(
                storage=_BlobStorage(tuple()),
                assets=_Assets(set()),
                asset_extractions=_AssetExtractions(set()),
            ).execute(BlobStorageCleanupCommand(storage_backend="local", prefix="../secret"))

    asyncio.run(run())


def _use_case(
    *,
    storage: _BlobStorage,
    assets: _Assets,
    asset_extractions: _AssetExtractions,
) -> RunBlobStorageCleanupUseCase:
    return RunBlobStorageCleanupUseCase(
        uow_factory=_UowFactory(assets, asset_extractions),
        blob_storage=storage,
        clock=_Clock(),
    )


def _object(storage_key: str, *, age_hours: int) -> StoredBlobObject:
    return StoredBlobObject(
        storage_key=storage_key,
        byte_size=10,
        updated_at=NOW - timedelta(hours=age_hours),
    )
