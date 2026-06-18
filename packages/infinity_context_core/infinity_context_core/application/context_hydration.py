"""Hydrate derived candidates through canonical repositories."""

from __future__ import annotations

from infinity_context_core.application.context_policy import (
    is_context_anchor_visible,
    is_context_fact_visible,
    is_graph_fact_visible,
)
from infinity_context_core.application.document_text import document_chunk_retrieval_text
from infinity_context_core.application.dto import BuildContextQuery, ContextItem
from infinity_context_core.application.source_refs import chunk_source_refs
from infinity_context_core.domain.entities import MemoryChunk
from infinity_context_core.ports.clock import ClockPort
from infinity_context_core.ports.unit_of_work import UnitOfWorkFactoryPort


class ContextHydrator:
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactoryPort,
        clock: ClockPort | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def hydrate_visible_chunks(
        self,
        *,
        chunk_ids: tuple[str, ...],
        query: BuildContextQuery,
        memory_scope_ids: tuple[str, ...],
    ) -> tuple[MemoryChunk, ...]:
        if not chunk_ids:
            return ()
        async with self._uow_factory() as uow:
            chunks = await uow.chunks.hydrate_visible_chunks(
                chunk_ids=chunk_ids,
                space_id=str(query.space_id),
                memory_scope_ids=memory_scope_ids,
                thread_id=str(query.thread_id) if query.thread_id else None,
            )
        return tuple(chunks)

    async def hydrate_graph_facts(
        self,
        *,
        fact_ids: tuple[str, ...],
        query: BuildContextQuery,
        memory_scope_ids: tuple[str, ...],
    ) -> tuple[tuple[ContextItem, ...], int]:
        if not fact_ids:
            return (), 0
        async with self._uow_factory() as uow:
            hydrated: list[ContextItem] = []
            stale_count = 0
            now = self._clock.now() if self._clock is not None else None
            facts_by_id = {str(fact.id): fact for fact in await uow.facts.get_by_ids(fact_ids)}
            for fact_id in fact_ids:
                fact = facts_by_id.get(fact_id)
                if fact is not None and is_graph_fact_visible(
                    fact,
                    query=query,
                    memory_scope_ids=memory_scope_ids,
                    now=now,
                ):
                    hydrated.append(
                        ContextItem(
                            item_id=str(fact.id),
                            item_type="fact",
                            text=fact.text,
                            score=0.78,
                            source_refs=fact.source_refs,
                            diagnostics={
                                "memory_scope_id": str(fact.memory_scope_id),
                                "retrieval_source": "graph_hydrated",
                                "retrieval_sources": ["graph_hydrated"],
                                "ranking_reason": "graph candidate resolved to visible active fact",
                                "score_signals": {
                                    "base_score": 0.78,
                                    "retrieval_channel": "graph_hydrated",
                                    "fact_status": fact.status.value,
                                },
                                "provenance": {
                                    "retrieval_sources": ["graph_hydrated"],
                                    "source_ref_count": len(fact.source_refs),
                                    "fact_status": fact.status.value,
                                    "fact_version": fact.version,
                                },
                            },
                        )
                    )
                else:
                    stale_count += 1
        return tuple(hydrated), stale_count

    async def revalidate_visible_items(
        self,
        items: tuple[ContextItem, ...],
        *,
        query: BuildContextQuery,
        memory_scope_ids: tuple[str, ...],
    ) -> tuple[ContextItem, ...]:
        if not items:
            return ()

        chunk_ids = tuple(
            dict.fromkeys(item.item_id for item in items if item.item_type == "chunk")
        )
        visible_chunks = {
            str(chunk.id): chunk
            for chunk in await self.hydrate_visible_chunks(
                chunk_ids=chunk_ids,
                query=query,
                memory_scope_ids=memory_scope_ids,
            )
        }
        fact_ids = tuple(dict.fromkeys(item.item_id for item in items if item.item_type == "fact"))
        visible_facts = {}
        if fact_ids:
            async with self._uow_factory() as uow:
                now = self._clock.now() if self._clock is not None else None
                for fact in await uow.facts.get_by_ids(fact_ids):
                    if is_context_fact_visible(
                        fact,
                        query=query,
                        memory_scope_ids=memory_scope_ids,
                        now=now,
                    ):
                        visible_facts[str(fact.id)] = fact
        anchor_ids = tuple(
            dict.fromkeys(item.item_id for item in items if item.item_type == "anchor")
        )
        visible_anchors = {}
        if anchor_ids:
            async with self._uow_factory() as uow:
                now = self._clock.now() if self._clock is not None else None
                for anchor_id in anchor_ids:
                    anchor = await uow.anchors.get_by_id(anchor_id)
                    if anchor is not None and is_context_anchor_visible(
                        anchor,
                        query=query,
                        memory_scope_ids=memory_scope_ids,
                        now=now,
                    ):
                        visible_anchors[str(anchor.id)] = anchor

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
            elif item.item_type == "anchor":
                anchor = visible_anchors.get(item.item_id)
                if anchor is None:
                    continue
                visible_items.append(
                    ContextItem(
                        item_id=str(anchor.id),
                        item_type=item.item_type,
                        text=item.text,
                        score=item.score,
                        source_refs=anchor.evidence_refs,
                        is_instruction=item.is_instruction,
                        diagnostics=item.diagnostics,
                    )
                )
            elif item.item_type == "chunk":
                chunk = visible_chunks.get(item.item_id)
                if chunk is None:
                    continue
                chunk_text = document_chunk_retrieval_text(
                    text=chunk.text,
                    metadata=chunk.metadata,
                )
                visible_items.append(
                    ContextItem(
                        item_id=str(chunk.id),
                        item_type=item.item_type,
                        text=chunk_text,
                        score=item.score,
                        source_refs=chunk_source_refs(chunk, text_preview=chunk_text),
                        is_instruction=item.is_instruction,
                        diagnostics=item.diagnostics,
                    )
                )
        return tuple(visible_items)
