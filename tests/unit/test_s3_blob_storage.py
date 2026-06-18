import asyncio

import pytest
from infinity_context_adapters.s3_blob import S3BlobStorage
from infinity_context_core.domain.errors import MemoryNotFoundError, MemoryValidationError
from infinity_context_server import composition
from infinity_context_server.config import DeployProfile, Settings


class _FakeBody:
    def __init__(self, content: bytes) -> None:
        self._content = content
        self.closed = False

    def read(self) -> bytes:
        return self._content

    def close(self) -> None:
        self.closed = True


class _FakeS3NotFound(Exception):
    response = {"Error": {"Code": "NoSuchKey"}}


class _FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.deleted: list[tuple[str, str]] = []

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> None:
        self.objects[(Bucket, Key)] = Body

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        content = self.objects.get((Bucket, Key))
        if content is None:
            raise _FakeS3NotFound
        return {"Body": _FakeBody(content)}

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.deleted.append((Bucket, Key))
        self.objects.pop((Bucket, Key), None)


def test_s3_blob_storage_round_trips_with_prefix() -> None:
    async def run() -> None:
        client = _FakeS3Client()
        storage = S3BlobStorage(bucket="memory-assets", prefix="team-a/assets", client=client)

        stored = await storage.write_bytes(
            storage_key="space/scope/aa/blob.txt",
            content=b"hello",
        )
        content = await storage.read_bytes(storage_key=stored.storage_key)
        await storage.delete(storage_key=stored.storage_key)

        assert stored.byte_size == 5
        assert content == b"hello"
        assert client.objects == {}
        assert client.deleted == [("memory-assets", "team-a/assets/space/scope/aa/blob.txt")]

    asyncio.run(run())


def test_s3_blob_storage_missing_object_raises_not_found() -> None:
    async def run() -> None:
        storage = S3BlobStorage(bucket="memory-assets", client=_FakeS3Client())

        with pytest.raises(MemoryNotFoundError):
            await storage.read_bytes(storage_key="space/scope/missing.txt")

    asyncio.run(run())


@pytest.mark.parametrize(
    "storage_key",
    ["", "/absolute/key", "space/../secret", "space//secret", "space/\x00secret"],
)
def test_s3_blob_storage_rejects_unsafe_storage_keys(storage_key: str) -> None:
    async def run() -> None:
        storage = S3BlobStorage(bucket="memory-assets", client=_FakeS3Client())

        with pytest.raises(MemoryValidationError):
            await storage.write_bytes(storage_key=storage_key, content=b"blocked")

    asyncio.run(run())


def test_s3_blob_storage_rejects_unsafe_prefix() -> None:
    with pytest.raises(MemoryValidationError):
        S3BlobStorage(bucket="memory-assets", prefix="team-a/../assets", client=_FakeS3Client())


def test_container_wires_s3_storage_backend(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    created: dict[str, object] = {}

    class _FakeStorage:
        def __init__(self, **kwargs: object) -> None:
            created.update(kwargs)

        async def write_bytes(self, *, storage_key: str, content: bytes):  # pragma: no cover
            raise AssertionError("not used")

        async def read_bytes(self, *, storage_key: str) -> bytes:  # pragma: no cover
            raise AssertionError("not used")

        async def delete(self, *, storage_key: str) -> None:  # pragma: no cover
            raise AssertionError("not used")

    monkeypatch.setattr(composition, "S3BlobStorage", _FakeStorage)

    container = composition.build_container(
        Settings(
            deploy_profile=DeployProfile.TEST,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 's3-composition.db'}",
            asset_storage_backend="s3",
            asset_storage_s3_bucket="memory-assets",
            asset_storage_s3_prefix="tenant-a",
            asset_storage_s3_endpoint_url="https://s3.example.test",
            asset_storage_s3_region="us-east-1",
            asset_storage_s3_force_path_style=True,
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
        )
    )
    try:
        assert created["bucket"] == "memory-assets"
        assert created["prefix"] == "tenant-a"
        assert created["endpoint_url"] == "https://s3.example.test"
        assert created["region_name"] == "us-east-1"
        assert created["force_path_style"] is True
        assert container.create_asset._storage_backend == "s3"
        assert container.run_asset_extraction._artifact_storage_backend == "s3"
    finally:
        asyncio.run(container.aclose())
