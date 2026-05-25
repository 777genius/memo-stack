"""Thin optional Graphiti adapter.

Graphiti is treated as a derived temporal graph. The adapter returns candidate
canonical ids only; application use cases hydrate through Postgres.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from memory_core.ports.adapters import (
    AdapterCapabilities,
    GraphCandidate,
    GraphSearchResult,
    VectorWriteResult,
)


class GraphitiGraphMemoryAdapter:
    def __init__(
        self,
        *,
        client: object | None = None,
        neo4j_uri: str | None = None,
        neo4j_user: str | None = None,
        neo4j_password: str | None = None,
        build_indices: bool = False,
        group_id_prefix: str = "memory",
    ) -> None:
        self._client = client
        self._neo4j_uri = neo4j_uri
        self._neo4j_user = neo4j_user
        self._neo4j_password = neo4j_password
        self._build_indices = build_indices
        self._indices_built = not build_indices
        self._group_id_prefix = group_id_prefix

    async def capabilities(self) -> AdapterCapabilities:
        try:
            client = await self._client_or_none()
        except Exception:
            client = None
        if client is None:
            configured = self._is_configured()
            return AdapterCapabilities(
                name="graphiti",
                enabled=False,
                healthy=not configured,
                supports_upsert=False,
                supports_delete=False,
                supports_search=False,
                supports_filters=False,
                supports_temporal_queries=True,
                degraded_reason="graphiti_unavailable" if configured else "disabled",
            )
        return AdapterCapabilities(
            name="graphiti",
            enabled=True,
            healthy=True,
            supports_upsert=True,
            supports_delete=True,
            supports_search=True,
            supports_filters=True,
            supports_temporal_queries=True,
        )

    async def upsert_fact(
        self,
        fact_id: str,
        text: str,
        metadata: dict[str, str],
    ) -> VectorWriteResult:
        try:
            client = await self._client_or_none()
            if client is None:
                return self._unavailable_write_result()
            add_episode = getattr(client, "add_episode", None)
            if add_episode is None:
                return VectorWriteResult.degraded("graph.missing_add_episode", retryable=False)
            kwargs = {
                "name": f"fact:{fact_id}",
                "episode_body": text,
                "group_id": self._group_id(
                    metadata.get("space_id", ""),
                    metadata.get("profile_id", ""),
                ),
                "source_description": "canonical_memory_fact",
                "reference_time": _reference_time(metadata.get("updated_at")),
            }
            episode_type = _episode_type_text()
            if episode_type is not None:
                kwargs["source"] = episode_type
            await add_episode(**kwargs)
            return VectorWriteResult.ok(1)
        except Exception:
            return VectorWriteResult.degraded("graph.upsert_failed", retryable=True)

    async def delete_fact(self, fact_id: str) -> VectorWriteResult:
        try:
            client = await self._client_or_none()
            if client is None:
                return self._unavailable_write_result()
            delete_episode = getattr(client, "delete_episode", None)
            if delete_episode is None:
                return VectorWriteResult.degraded("graph.missing_delete_episode", retryable=False)
            await _call_delete_episode(delete_episode, f"fact:{fact_id}")
            return VectorWriteResult.ok(1)
        except Exception:
            return VectorWriteResult.degraded("graph.delete_failed", retryable=True)

    async def search(
        self,
        *,
        space_id: str,
        profile_ids: tuple[str, ...],
        query: str,
        limit: int,
    ) -> GraphSearchResult:
        try:
            client = await self._client_or_none()
            if client is None:
                if self._is_configured():
                    return GraphSearchResult.degraded("graph.unavailable", retryable=True)
                return GraphSearchResult.degraded("graph.disabled", retryable=False)
            search = getattr(client, "search", None)
            if search is None:
                return GraphSearchResult.degraded("graph.missing_search", retryable=False)
            candidates: list[GraphCandidate] = []
            for profile_id in profile_ids:
                results = await _call_search(
                    search,
                    query=query,
                    group_id=self._group_id(space_id, profile_id),
                    limit=limit,
                )
                for result in results:
                    fact_id = _canonical_fact_id(result)
                    if fact_id:
                        candidates.append(
                            GraphCandidate(
                                source_fact_ids=(fact_id,),
                                source_chunk_ids=(),
                                relation_label="graphiti_candidate",
                                score=float(getattr(result, "score", 0.5)),
                                diagnostics={"provider": "graphiti"},
                            )
                        )
            return GraphSearchResult.ok(candidates[:limit])
        except Exception:
            return GraphSearchResult.degraded("graph.search_failed", retryable=True)

    def _group_id(self, space_id: str, profile_id: str) -> str:
        return f"{self._group_id_prefix}:{space_id}:{profile_id}"

    def _is_configured(self) -> bool:
        return self._client is not None or bool(
            self._neo4j_uri and self._neo4j_user and self._neo4j_password
        )

    def _unavailable_write_result(self) -> VectorWriteResult:
        if self._is_configured():
            return VectorWriteResult.degraded("graph.unavailable", retryable=True)
        return VectorWriteResult.degraded("graph.disabled", retryable=False)

    async def _client_or_none(self) -> object | None:
        if self._client is not None:
            await self._build_indices_once(self._client)
            return self._client
        if not self._neo4j_uri or not self._neo4j_user or not self._neo4j_password:
            return None
        try:
            from graphiti_core import Graphiti
        except Exception:
            return None
        self._client = Graphiti(self._neo4j_uri, self._neo4j_user, self._neo4j_password)
        await self._build_indices_once(self._client)
        return self._client

    async def _build_indices_once(self, client: object) -> None:
        if self._indices_built:
            return
        build = getattr(client, "build_indices_and_constraints", None)
        if build is not None:
            await build()
        self._indices_built = True


def _canonical_fact_id(result: object) -> str | None:
    for attr in ("fact_id", "source_fact_id", "uuid", "id", "name", "episode_name"):
        value = getattr(result, attr, None)
        fact_id = _extract_fact_id(value)
        if fact_id:
            return fact_id
    return None


def _extract_fact_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    if value.startswith("fact:"):
        return value.removeprefix("fact:")
    if value.startswith("fact_"):
        return value
    return None


def _episode_type_text() -> object | None:
    try:
        from graphiti_core.nodes import EpisodeType
    except Exception:
        return None
    return EpisodeType.text


def _reference_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


async def _call_delete_episode(delete_episode: Any, name: str) -> None:
    try:
        await delete_episode(name=name)
    except TypeError:
        await delete_episode(name)


async def _call_search(search: Any, *, query: str, group_id: str, limit: int) -> list[object]:
    try:
        return list(await search(query=query, group_ids=[group_id], num_results=limit))
    except TypeError:
        try:
            return list(await search(query=query, group_id=group_id, num_results=limit))
        except TypeError:
            return list(await search(query, num_results=limit))
