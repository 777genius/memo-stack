"""Build prompt-safe memory context from canonical and derived candidates."""

from __future__ import annotations

from memory_core.application.context_packer import ContextPacker
from memory_core.application.dto import BuildContextQuery, ContextBundle, ContextItem
from memory_core.domain.entities import SourceRef
from memory_core.ports.adapters import EmbeddingPort, GraphMemoryPort, PortStatus, VectorMemoryPort
from memory_core.ports.ids import IdGeneratorPort
from memory_core.ports.unit_of_work import UnitOfWorkFactoryPort


class BuildContextUseCase:
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactoryPort,
        ids: IdGeneratorPort,
        vector_index: VectorMemoryPort,
        graph_index: GraphMemoryPort,
        embedder: EmbeddingPort,
        packer: ContextPacker | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._ids = ids
        self._vector_index = vector_index
        self._graph_index = graph_index
        self._embedder = embedder
        self._packer = packer or ContextPacker()

    async def execute(self, query: BuildContextQuery) -> ContextBundle:
        profile_ids = tuple(str(profile_id) for profile_id in query.profile_ids)
        async with self._uow_factory() as uow:
            facts = await uow.facts.find_active(
                space_id=str(query.space_id),
                profile_ids=profile_ids,
                thread_id=str(query.thread_id) if query.thread_id else None,
                query=query.query,
                limit=query.max_facts,
            )
            keyword_chunks = await uow.chunks.keyword_search(
                space_id=str(query.space_id),
                profile_ids=profile_ids,
                thread_id=str(query.thread_id) if query.thread_id else None,
                query=query.query,
                limit=query.max_chunks,
            )

        diagnostics: dict[str, object] = {
            "facts_considered": len(facts),
            "keyword_chunks_considered": len(keyword_chunks),
            "vector_status": "disabled",
            "graph_status": "disabled",
            "stale_vector_drop_count": 0,
            "stale_graph_drop_count": 0,
        }
        vector_chunks = await self._vector_chunks(query, profile_ids, diagnostics)
        graph_items = await self._graph_items(query, profile_ids, diagnostics)

        items: list[ContextItem] = []
        for fact in facts:
            items.append(
                ContextItem(
                    item_id=str(fact.id),
                    item_type="fact",
                    text=fact.text,
                    score=0.95,
                    source_refs=fact.source_refs,
                    diagnostics={
                        "profile_id": str(fact.profile_id),
                        "retrieval_source": "postgres_facts",
                    },
                )
            )
        for chunk in [*keyword_chunks, *vector_chunks]:
            items.append(
                ContextItem(
                    item_id=str(chunk.id),
                    item_type="chunk",
                    text=chunk.text,
                    score=0.75 if chunk in keyword_chunks else 0.82,
                    source_refs=(
                        SourceRef(
                            source_type=chunk.source_type,
                            source_id=chunk.source_external_id,
                            chunk_id=str(chunk.id),
                            char_start=chunk.char_start,
                            char_end=chunk.char_end,
                            quote_preview=chunk.text[:200],
                        ),
                    ),
                    diagnostics={
                        "profile_id": str(chunk.profile_id),
                        "retrieval_source": "chunks",
                    },
                )
            )
        items.extend(graph_items)

        deduped = await self._revalidate_visible_items(
            _dedupe_items(tuple(items)),
            query=query,
            profile_ids=profile_ids,
        )
        result = self._packer.pack(
            bundle_id=self._ids.new_id("ctx"),
            items=deduped,
            token_budget=query.token_budget,
            max_rendered_chars=query.max_rendered_chars,
        )
        diagnostics.update(result.bundle.diagnostics)
        return ContextBundle(
            bundle_id=result.bundle.bundle_id,
            rendered_text=result.bundle.rendered_text,
            items=result.bundle.items,
            token_estimate=result.bundle.token_estimate,
            diagnostics=diagnostics,
        )

    async def _vector_chunks(
        self,
        query: BuildContextQuery,
        profile_ids: tuple[str, ...],
        diagnostics: dict[str, object],
    ) -> list:
        if query.max_chunks <= 0:
            diagnostics["vector_status"] = "skipped"
            return []
        capabilities = await self._vector_index.capabilities()
        if not capabilities.enabled:
            diagnostics["vector_status"] = (
                "disabled" if capabilities.degraded_reason == "disabled" else "degraded"
            )
            if capabilities.degraded_reason:
                diagnostics["vector_degraded_reason"] = capabilities.degraded_reason
            return []
        if not capabilities.healthy or not capabilities.supports_search:
            diagnostics["vector_status"] = "degraded"
            if capabilities.degraded_reason:
                diagnostics["vector_degraded_reason"] = capabilities.degraded_reason
            return []

        embedding = await self._embedder.embed_texts((query.query,))
        if embedding.status != PortStatus.OK or not embedding.vectors:
            diagnostics["vector_status"] = embedding.status.value
            if embedding.diagnostics:
                diagnostics["vector_degraded_reason"] = embedding.diagnostics[0].code
            return []
        result = await self._vector_index.search_chunks(
            space_id=str(query.space_id),
            profile_ids=profile_ids,
            query_vector=embedding.vectors[0],
            limit=query.max_chunks,
        )
        diagnostics["vector_status"] = result.status.value
        if result.diagnostics:
            diagnostics["vector_degraded_reason"] = result.diagnostics[0].code
        if result.status != PortStatus.OK or not result.items:
            return []
        chunk_ids = tuple(candidate.chunk_id for candidate in result.items)
        async with self._uow_factory() as uow:
            chunks = await uow.chunks.hydrate_visible_chunks(
                chunk_ids=chunk_ids,
                space_id=str(query.space_id),
                profile_ids=profile_ids,
                thread_id=str(query.thread_id) if query.thread_id else None,
            )
        hydrated_ids = {str(chunk.id) for chunk in chunks}
        diagnostics["stale_vector_drop_count"] = sum(
            1 for chunk_id in chunk_ids if chunk_id not in hydrated_ids
        )
        return chunks

    async def _graph_items(
        self,
        query: BuildContextQuery,
        profile_ids: tuple[str, ...],
        diagnostics: dict[str, object],
    ) -> list[ContextItem]:
        if not query.include_graph or query.max_facts <= 0:
            diagnostics["graph_status"] = "skipped"
            return []
        capabilities = await self._graph_index.capabilities()
        if not capabilities.enabled:
            diagnostics["graph_status"] = (
                "disabled" if capabilities.degraded_reason == "disabled" else "degraded"
            )
            if capabilities.degraded_reason:
                diagnostics["graph_degraded_reason"] = capabilities.degraded_reason
            return []
        if not capabilities.healthy or not capabilities.supports_search:
            diagnostics["graph_status"] = "degraded"
            if capabilities.degraded_reason:
                diagnostics["graph_degraded_reason"] = capabilities.degraded_reason
            return []
        result = await self._graph_index.search(
            space_id=str(query.space_id),
            profile_ids=profile_ids,
            query=query.query,
            limit=query.max_facts,
        )
        diagnostics["graph_status"] = result.status.value
        if result.diagnostics:
            diagnostics["graph_degraded_reason"] = result.diagnostics[0].code
        if result.status != PortStatus.OK or not result.items:
            return []

        fact_ids = tuple(
            fact_id for candidate in result.items for fact_id in candidate.source_fact_ids
        )
        if not fact_ids:
            return []
        async with self._uow_factory() as uow:
            hydrated = []
            stale_count = 0
            for fact_id in fact_ids:
                fact = await uow.facts.get_by_id(fact_id)
                if (
                    fact is not None
                    and str(fact.space_id) == str(query.space_id)
                    and str(fact.profile_id) in profile_ids
                    and fact.status.value == "active"
                    and _thread_is_visible(fact.thread_id, query.thread_id)
                ):
                    hydrated.append(
                        ContextItem(
                            item_id=str(fact.id),
                            item_type="fact",
                            text=fact.text,
                            score=0.78,
                            source_refs=fact.source_refs,
                            diagnostics={
                                "profile_id": str(fact.profile_id),
                                "retrieval_source": "graph_hydrated",
                            },
                        )
                    )
                else:
                    stale_count += 1
            diagnostics["stale_graph_drop_count"] = stale_count
            return hydrated

    async def _revalidate_visible_items(
        self,
        items: tuple[ContextItem, ...],
        *,
        query: BuildContextQuery,
        profile_ids: tuple[str, ...],
    ) -> tuple[ContextItem, ...]:
        if not items:
            return ()

        chunk_ids = tuple(item.item_id for item in items if item.item_type == "chunk")
        async with self._uow_factory() as uow:
            visible_chunks = {
                str(chunk.id): chunk
                for chunk in await uow.chunks.hydrate_visible_chunks(
                    chunk_ids=chunk_ids,
                    space_id=str(query.space_id),
                    profile_ids=profile_ids,
                    thread_id=str(query.thread_id) if query.thread_id else None,
                )
            }
            visible_facts = {}
            for item in items:
                if item.item_type != "fact":
                    continue
                fact = await uow.facts.get_by_id(item.item_id)
                if (
                    fact is not None
                    and str(fact.space_id) == str(query.space_id)
                    and str(fact.profile_id) in profile_ids
                    and fact.status.value == "active"
                    and fact.classification != "restricted"
                    and _thread_is_visible(fact.thread_id, query.thread_id)
                ):
                    visible_facts[str(fact.id)] = fact

        visible_items: list[ContextItem] = []
        for item in items:
            if item.item_type == "fact":
                fact = visible_facts.get(item.item_id)
                if fact is None:
                    continue
                visible_items.append(
                    ContextItem(
                        item_id=str(fact.id),
                        item_type=item.item_type,
                        text=fact.text,
                        score=item.score,
                        source_refs=fact.source_refs,
                        is_instruction=item.is_instruction,
                        diagnostics=item.diagnostics,
                    )
                )
            elif item.item_type == "chunk":
                chunk = visible_chunks.get(item.item_id)
                if chunk is None:
                    continue
                visible_items.append(
                    ContextItem(
                        item_id=str(chunk.id),
                        item_type=item.item_type,
                        text=chunk.text,
                        score=item.score,
                        source_refs=(
                            SourceRef(
                                source_type=chunk.source_type,
                                source_id=chunk.source_external_id,
                                chunk_id=str(chunk.id),
                                char_start=chunk.char_start,
                                char_end=chunk.char_end,
                                quote_preview=chunk.text[:200],
                            ),
                        ),
                        is_instruction=item.is_instruction,
                        diagnostics=item.diagnostics,
                    )
                )
        return tuple(visible_items)


def _dedupe_items(items: tuple[ContextItem, ...]) -> tuple[ContextItem, ...]:
    by_key: dict[tuple[str, str], ContextItem] = {}
    for item in items:
        key = (item.item_type, item.item_id)
        existing = by_key.get(key)
        if existing is None or item.score > existing.score:
            by_key[key] = item
    return tuple(by_key.values())


def _thread_is_visible(item_thread_id: object | None, query_thread_id: object | None) -> bool:
    if query_thread_id is None:
        return True
    return item_thread_id is None or str(item_thread_id) == str(query_thread_id)
