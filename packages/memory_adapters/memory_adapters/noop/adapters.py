"""Noop adapters used when optional engines are disabled."""

from memory_core.ports.adapters import (
    AdapterCapabilities,
    EmbeddingResult,
    GraphSearchResult,
    VectorSearchResult,
    VectorWriteResult,
)


class NoopVectorMemoryAdapter:
    def __init__(self, name: str = "qdrant") -> None:
        self._name = name

    async def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            name=self._name,
            enabled=False,
            healthy=True,
            supports_upsert=False,
            supports_delete=False,
            supports_search=False,
            supports_filters=False,
            degraded_reason="disabled",
        )

    async def search_chunks(self, *_args: object, **_kwargs: object) -> VectorSearchResult:
        return VectorSearchResult.degraded("vector.disabled", retryable=False)

    async def upsert_chunks(self, *_args: object, **_kwargs: object) -> VectorWriteResult:
        return VectorWriteResult.degraded("vector.disabled", retryable=False)

    async def delete_chunks(self, *_args: object, **_kwargs: object) -> VectorWriteResult:
        return VectorWriteResult.degraded("vector.disabled", retryable=False)


class NoopGraphMemoryAdapter:
    def __init__(self, name: str = "graphiti") -> None:
        self._name = name

    async def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            name=self._name,
            enabled=False,
            healthy=True,
            supports_upsert=False,
            supports_delete=False,
            supports_search=False,
            supports_filters=False,
            supports_temporal_queries=False,
            degraded_reason="disabled",
        )

    async def search(self, *_args: object, **_kwargs: object) -> GraphSearchResult:
        return GraphSearchResult.degraded("graph.disabled", retryable=False)

    async def upsert_fact(self, *_args: object, **_kwargs: object) -> VectorWriteResult:
        return VectorWriteResult.degraded("graph.disabled", retryable=False)

    async def delete_fact(self, *_args: object, **_kwargs: object) -> VectorWriteResult:
        return VectorWriteResult.degraded("graph.disabled", retryable=False)


class NoopEmbeddingAdapter:
    def __init__(self, name: str = "embeddings") -> None:
        self._name = name

    async def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            name=self._name,
            enabled=False,
            healthy=True,
            supports_upsert=False,
            supports_delete=False,
            supports_search=False,
            supports_filters=False,
            degraded_reason="disabled",
        )

    async def embed_texts(self, *_args: object, **_kwargs: object) -> EmbeddingResult:
        return EmbeddingResult.degraded("embeddings.disabled", retryable=False)
