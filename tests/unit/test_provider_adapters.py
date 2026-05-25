import asyncio
from types import SimpleNamespace

from memory_adapters.graphiti import GraphitiGraphMemoryAdapter
from memory_adapters.qdrant import QdrantVectorMemoryAdapter
from memory_core.ports.adapters import PortStatus, VectorUpsertItem
from memory_server.config import Settings


class FakeGraphiti:
    def __init__(self) -> None:
        self.built = 0
        self.episodes: list[dict[str, object]] = []
        self.deleted: list[str] = []

    async def build_indices_and_constraints(self) -> None:
        self.built += 1

    async def add_episode(self, **kwargs: object) -> None:
        self.episodes.append(kwargs)

    async def delete_episode(self, *, name: str) -> None:
        self.deleted.append(name)

    async def search(self, **_kwargs: object) -> list[object]:
        return [SimpleNamespace(name="fact:fact_graphiti", score=0.8)]


def test_graphiti_adapter_hydrates_only_canonical_fact_ids() -> None:
    async def run() -> None:
        fake = FakeGraphiti()
        adapter = GraphitiGraphMemoryAdapter(client=fake, build_indices=True)

        capabilities = await adapter.capabilities()
        upsert = await adapter.upsert_fact(
            "fact_graphiti",
            "Graphiti projection source text.",
            {
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "updated_at": "2026-05-25T10:00:00+00:00",
            },
        )
        search = await adapter.search(
            space_id="space_hackinterview",
            profile_ids=("profile_default",),
            query="Graphiti projection",
            limit=3,
        )
        deleted = await adapter.delete_fact("fact_graphiti")

        assert capabilities.enabled is True
        assert fake.built == 1
        assert upsert.status == PortStatus.OK
        assert fake.episodes[0]["name"] == "fact:fact_graphiti"
        assert search.items[0].source_fact_ids == ("fact_graphiti",)
        assert deleted.status == PortStatus.OK
        assert fake.deleted == ["fact:fact_graphiti"]

    asyncio.run(run())


def test_configured_graphiti_without_client_degrades_instead_of_disabling() -> None:
    async def run() -> None:
        adapter = GraphitiGraphMemoryAdapter(
            neo4j_uri="bolt://graphiti.test:7687",
            neo4j_user="neo4j",
            neo4j_password="memorygraph",
        )

        capabilities = await adapter.capabilities()
        upsert = await adapter.upsert_fact(
            "fact_graphiti_missing",
            "Graphiti unavailable projection text.",
            {
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "updated_at": "2026-05-25T10:00:00+00:00",
            },
        )
        search = await adapter.search(
            space_id="space_hackinterview",
            profile_ids=("profile_default",),
            query="Graphiti unavailable",
            limit=3,
        )

        assert capabilities.enabled is False
        assert capabilities.healthy is False
        assert capabilities.degraded_reason == "graphiti_unavailable"
        assert upsert.status == PortStatus.DEGRADED
        assert upsert.diagnostics[0].code == "graph.unavailable"
        assert upsert.diagnostics[0].retryable is True
        assert search.status == PortStatus.DEGRADED
        assert search.diagnostics[0].code == "graph.unavailable"
        assert search.diagnostics[0].retryable is True

    asyncio.run(run())


class FakeQdrantModels:
    class Distance:
        COSINE = "Cosine"

    class VectorParams:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class PointStruct:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class PointIdsList:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class Filter:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FieldCondition:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class MatchValue:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class MatchAny:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs


class FakeQdrantClient:
    def __init__(self) -> None:
        self.collections: set[str] = set()
        self.upserts = 0

    async def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.collections

    async def create_collection(self, *, collection_name: str, vectors_config: object) -> None:
        self.collections.add(collection_name)
        assert vectors_config is not None

    async def upsert(self, *, collection_name: str, points: list[object], wait: bool) -> None:
        assert collection_name in self.collections
        assert points
        assert wait is False
        self.upserts += 1

    async def delete(self, **_kwargs: object) -> None:
        return None

    async def query_points(self, **_kwargs: object) -> object:
        return SimpleNamespace(
            points=[
                SimpleNamespace(
                    payload={
                        "chunk_id": "chunk_1",
                        "space_id": "space_hackinterview",
                        "profile_id": "profile_default",
                        "projection_version": "v1",
                    },
                    score=0.9,
                )
            ]
        )


class FakeQdrantWrongSizeClient(FakeQdrantClient):
    def __init__(self) -> None:
        super().__init__()
        self.collections.add("memory_chunks_v1")

    async def get_collection(self, *, collection_name: str) -> object:
        assert collection_name == "memory_chunks_v1"
        return SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(vectors=SimpleNamespace(size=2)),
            )
        )


class FakeQdrantUnavailableClient(FakeQdrantClient):
    async def collection_exists(self, collection_name: str) -> bool:
        raise TimeoutError("qdrant unavailable")


def test_qdrant_adapter_creates_collection_before_upsert_and_search() -> None:
    async def run() -> None:
        fake = FakeQdrantClient()
        adapter = QdrantVectorMemoryAdapter(
            url="http://qdrant.test",
            collection_name="memory_chunks_v1",
            vector_size=3,
        )
        adapter._client = lambda: _fake_qdrant_client(fake)  # type: ignore[method-assign]

        upsert = await adapter.upsert_chunks(
            (
                VectorUpsertItem(
                    chunk_id="chunk_1",
                    space_id="space_hackinterview",
                    profile_id="profile_default",
                    thread_id=None,
                    text="Qdrant projection text.",
                    vector=(0.1, 0.2, 0.3),
                    projection_version="v1",
                ),
            )
        )
        search = await adapter.search_chunks(
            space_id="space_hackinterview",
            profile_ids=("profile_default",),
            query_vector=(0.1, 0.2, 0.3),
            limit=3,
        )

        assert upsert.status == PortStatus.OK
        assert fake.upserts == 1
        assert search.items[0].chunk_id == "chunk_1"

    asyncio.run(run())


def test_qdrant_dimension_mismatch_fails_closed() -> None:
    async def run() -> None:
        fake = FakeQdrantWrongSizeClient()
        adapter = QdrantVectorMemoryAdapter(
            url="http://qdrant.test",
            collection_name="memory_chunks_v1",
            vector_size=3,
        )
        adapter._client = lambda: _fake_qdrant_client(fake)  # type: ignore[method-assign]

        capabilities = await adapter.capabilities()
        upsert = await adapter.upsert_chunks(
            (
                VectorUpsertItem(
                    chunk_id="chunk_1",
                    space_id="space_hackinterview",
                    profile_id="profile_default",
                    thread_id=None,
                    text="Qdrant projection text.",
                    vector=(0.1, 0.2, 0.3),
                    projection_version="v1",
                ),
            )
        )
        search = await adapter.search_chunks(
            space_id="space_hackinterview",
            profile_ids=("profile_default",),
            query_vector=(0.1, 0.2, 0.3),
            limit=3,
        )

        assert capabilities.healthy is False
        assert capabilities.degraded_reason == "qdrant.dimension_mismatch"
        assert upsert.status == PortStatus.DEGRADED
        assert upsert.diagnostics[0].code == "qdrant.dimension_mismatch"
        assert upsert.diagnostics[0].retryable is False
        assert search.status == PortStatus.DEGRADED
        assert search.diagnostics[0].code == "qdrant.dimension_mismatch"
        assert fake.upserts == 0

    asyncio.run(run())


def test_qdrant_client_unavailable_fails_capability_closed() -> None:
    async def run() -> None:
        async def unavailable_client():
            raise ModuleNotFoundError("qdrant_client")

        adapter = QdrantVectorMemoryAdapter(
            url="http://qdrant.test",
            collection_name="memory_chunks_v1",
            vector_size=3,
        )
        adapter._client = unavailable_client  # type: ignore[method-assign]

        capabilities = await adapter.capabilities()

        assert capabilities.enabled is False
        assert capabilities.healthy is False
        assert capabilities.degraded_reason == "qdrant_sdk_missing"

    asyncio.run(run())


def test_qdrant_server_unavailable_reports_configured_adapter_degraded() -> None:
    async def run() -> None:
        fake = FakeQdrantUnavailableClient()
        adapter = QdrantVectorMemoryAdapter(
            url="http://qdrant.test",
            collection_name="memory_chunks_v1",
            vector_size=3,
        )
        adapter._client = lambda: _fake_qdrant_client(fake)  # type: ignore[method-assign]

        capabilities = await adapter.capabilities()

        assert capabilities.enabled is True
        assert capabilities.healthy is False
        assert capabilities.supports_search is False
        assert capabilities.degraded_reason == "qdrant_unavailable"

    asyncio.run(run())


async def _fake_qdrant_client(client: FakeQdrantClient) -> tuple[FakeQdrantClient, type]:
    return client, FakeQdrantModels


def test_graphiti_enabled_requires_neo4j_password() -> None:
    settings = Settings(graphiti_enabled=True)

    try:
        settings.validate_for_startup()
    except RuntimeError as exc:
        assert "MEMORY_GRAPHITI_NEO4J_PASSWORD" in str(exc)
    else:
        raise AssertionError("Expected Graphiti config validation to fail")


def test_embeddings_enabled_requires_supported_provider_and_api_key() -> None:
    noop_settings = Settings(embeddings_enabled=True, embeddings_provider="noop")
    missing_key_settings = Settings(embeddings_enabled=True, embeddings_provider="openai")

    try:
        noop_settings.validate_for_startup()
    except RuntimeError as exc:
        assert "MEMORY_EMBEDDINGS_PROVIDER" in str(exc)
    else:
        raise AssertionError("Expected noop embedding provider validation to fail")

    try:
        missing_key_settings.validate_for_startup()
    except RuntimeError as exc:
        assert "MEMORY_OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected missing OpenAI key validation to fail")
