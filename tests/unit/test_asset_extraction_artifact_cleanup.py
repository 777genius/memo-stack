from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

import pytest
from memo_stack_core.application.use_cases.asset_extractions import RunAssetExtractionUseCase
from memo_stack_core.domain.assets import MemoryAsset, MemoryAssetId
from memo_stack_core.domain.entities import MemoryScopeId, SpaceId, ThreadId
from memo_stack_core.domain.extraction import AssetExtractionJob, AssetExtractionJobId
from memo_stack_core.ports.assets import StoredBlob
from memo_stack_core.ports.extraction import ExtractionLimits, ExtractionResult


class _Clock:
    def now(self) -> datetime:
        return datetime(2026, 6, 18, tzinfo=UTC)


class _Ids:
    def __init__(self) -> None:
        self._counter = 0

    def new_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}_{self._counter}"

    def projection_id(self, adapter: str, aggregate_type: str, aggregate_id: str) -> str:
        return f"{adapter}:{aggregate_type}:{aggregate_id}"


class _BlobStorage:
    def __init__(self, *, fail_delete: bool = False) -> None:
        self.blobs: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.fail_delete = fail_delete

    async def write_bytes(self, *, storage_key: str, content: bytes) -> StoredBlob:
        self.blobs[storage_key] = content
        return StoredBlob(storage_key=storage_key, byte_size=len(content))

    async def read_bytes(self, *, storage_key: str) -> bytes:
        return self.blobs[storage_key]

    async def delete(self, *, storage_key: str) -> None:
        self.deleted.append(storage_key)
        if self.fail_delete:
            raise RuntimeError("delete outage")
        self.blobs.pop(storage_key, None)


class _FailingAssetExtractions:
    async def create_artifact(self, artifact: Any) -> Any:
        raise RuntimeError("metadata store outage")


class _Uow:
    def __init__(self) -> None:
        self.asset_extractions = _FailingAssetExtractions()
        self.committed = False

    async def __aenter__(self) -> _Uow:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


class _UowFactory:
    def __init__(self) -> None:
        self.instances: list[_Uow] = []

    def __call__(self) -> _Uow:
        uow = _Uow()
        self.instances.append(uow)
        return uow


def test_store_artifacts_cleans_written_blobs_when_metadata_persist_fails() -> None:
    use_case, blob_storage, uow_factory = _use_case()

    with pytest.raises(RuntimeError, match="metadata store outage"):
        _run(
            use_case._store_artifacts(  # noqa: SLF001 - focused cleanup contract test.
                asset=_asset(),
                job=_job(),
                result=_result(),
                markdown="searchable evidence",
            )
        )

    assert blob_storage.blobs == {}
    assert len(blob_storage.deleted) == 2
    assert all("/extractions/" in storage_key for storage_key in blob_storage.deleted)
    assert uow_factory.instances
    assert uow_factory.instances[-1].committed is False


def test_store_artifacts_preserves_metadata_error_when_cleanup_delete_fails() -> None:
    use_case, blob_storage, _uow_factory = _use_case(fail_delete=True)

    with pytest.raises(RuntimeError, match="metadata store outage"):
        _run(
            use_case._store_artifacts(  # noqa: SLF001 - focused cleanup contract test.
                asset=_asset(),
                job=_job(),
                result=_result(),
                markdown="searchable evidence",
            )
        )

    assert len(blob_storage.blobs) == 2
    assert len(blob_storage.deleted) == 2


def _use_case(
    *,
    fail_delete: bool = False,
) -> tuple[RunAssetExtractionUseCase, _BlobStorage, _UowFactory]:
    blob_storage = _BlobStorage(fail_delete=fail_delete)
    uow_factory = _UowFactory()
    use_case = RunAssetExtractionUseCase(
        uow_factory=uow_factory,
        blob_storage=blob_storage,
        detector=object(),
        extractor=object(),
        ingest_document=object(),
        clock=_Clock(),
        ids=_Ids(),
        limits=ExtractionLimits(max_bytes=1_000_000),
    )
    return use_case, blob_storage, uow_factory


def _asset() -> MemoryAsset:
    content = b"asset"
    return MemoryAsset.create(
        asset_id=MemoryAssetId("asset_1"),
        space_id=SpaceId("space_1"),
        memory_scope_id=MemoryScopeId("scope_1"),
        thread_id=ThreadId("thread_1"),
        filename="capture.txt",
        content_type="text/plain",
        byte_size=len(content),
        sha256_hex=sha256(content).hexdigest(),
        storage_backend="local",
        storage_key="assets/asset_1.bin",
        now=datetime(2026, 6, 18, tzinfo=UTC),
    )


def _job() -> AssetExtractionJob:
    return AssetExtractionJob.create(
        job_id=AssetExtractionJobId("extract_1"),
        asset_id=MemoryAssetId("asset_1"),
        space_id=SpaceId("space_1"),
        memory_scope_id=MemoryScopeId("scope_1"),
        thread_id=ThreadId("thread_1"),
        parser_profile="standard_local",
        parser_config_hash="profile_hash",
        source_sha256_hex=sha256(b"asset").hexdigest(),
        now=datetime(2026, 6, 18, tzinfo=UTC),
    )


def _result() -> ExtractionResult:
    return ExtractionResult(
        status="succeeded",
        normalized_content_type="text/plain",
        title="capture.txt",
        markdown="searchable evidence",
        parser_name="test_parser",
        parser_version="v1",
    )


def _run(awaitable: Any) -> Any:
    import asyncio

    return asyncio.run(awaitable)
