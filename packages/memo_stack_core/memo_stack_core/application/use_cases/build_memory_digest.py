"""Build source-bound memory digests from canonical and derived evidence."""

from __future__ import annotations

from memo_stack_core.application.dto import (
    BuildContextQuery,
    BuildMemoryDigestQuery,
    ContextItem,
    MemoryDigest,
    MemoryDigestSection,
)
from memo_stack_core.application.memory_digest_renderer import MemoryDigestRenderer
from memo_stack_core.application.use_cases.build_context import BuildContextUseCase
from memo_stack_core.domain.entities import SourceRef
from memo_stack_core.ports.ids import IdGeneratorPort
from memo_stack_core.ports.unit_of_work import UnitOfWorkFactoryPort


class BuildMemoryDigestUseCase:
    """Build a read-only digest. The digest is derived evidence, not canonical memory."""

    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactoryPort,
        ids: IdGeneratorPort,
        context_builder: BuildContextUseCase,
        renderer: MemoryDigestRenderer | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._ids = ids
        self._context_builder = context_builder
        self._renderer = renderer or MemoryDigestRenderer()

    async def execute(self, query: BuildMemoryDigestQuery) -> MemoryDigest:
        context = await self._context_builder.execute(
            BuildContextQuery(
                space_id=query.space_id,
                memory_scope_ids=query.memory_scope_ids,
                thread_id=query.thread_id,
                query=query.topic,
                consistency_mode=query.consistency_mode,
                token_budget=query.token_budget,
                max_rendered_chars=query.max_rendered_chars,
                max_facts=query.max_facts,
                max_chunks=query.max_chunks,
                include_graph=query.include_related,
            )
        )
        pending_suggestions = (
            await self._pending_suggestion_items(query)
            if query.include_pending_suggestions and query.max_suggestions > 0
            else ()
        )
        superseded_items = (
            await self._superseded_fact_items(query) if query.include_superseded else ()
        )
        fact_items = tuple(item for item in context.items if item.item_type == "fact")
        chunk_items = tuple(item for item in context.items if item.item_type == "chunk")
        related_items = tuple(
            item for item in context.items if item.item_type not in {"fact", "chunk"}
        )
        sections = (
            MemoryDigestSection("Active facts", fact_items),
            MemoryDigestSection("Relevant documents", chunk_items),
            MemoryDigestSection("Related graph and RAG evidence", related_items),
            MemoryDigestSection("Pending suggestions", pending_suggestions),
            MemoryDigestSection("Superseded or stale memory", superseded_items),
        )
        source_refs = _dedupe_source_refs(
            tuple(
                ref
                for section in sections
                for item in section.items
                for ref in item.source_refs
            )
        )
        diagnostics = {
            **context.diagnostics,
            "evidence_only": True,
            "context_bundle_id": context.bundle_id,
            "context_items_used": len(context.items),
            "pending_suggestions_considered": len(pending_suggestions),
            "superseded_facts_considered": len(superseded_items),
            "include_pending_suggestions": query.include_pending_suggestions,
            "include_superseded": query.include_superseded,
            "include_related": query.include_related,
        }
        return self._renderer.render(
            digest_id=self._ids.new_id("dig"),
            topic=query.topic,
            sections=sections,
            diagnostics=diagnostics,
            source_refs=source_refs,
            max_rendered_chars=query.max_rendered_chars,
        )

    async def _pending_suggestion_items(
        self,
        query: BuildMemoryDigestQuery,
    ) -> tuple[ContextItem, ...]:
        items: list[ContextItem] = []
        remaining = query.max_suggestions
        async with self._uow_factory() as uow:
            for memory_scope_id in query.memory_scope_ids:
                if remaining <= 0:
                    break
                suggestions = await uow.suggestions.list_for_scope(
                    space_id=str(query.space_id),
                    memory_scope_id=str(memory_scope_id),
                    status="pending",
                    operation=None,
                    category=None,
                    tag=None,
                    limit=remaining,
                )
                for suggestion in suggestions:
                    items.append(
                        ContextItem(
                            item_id=str(suggestion.id),
                            item_type="suggestion",
                            text=suggestion.candidate_text,
                            score=0.5,
                            source_refs=suggestion.source_refs,
                            diagnostics={
                                "memory_scope_id": str(suggestion.memory_scope_id),
                                "status": suggestion.status.value,
                                "operation": suggestion.operation.value,
                                "kind": suggestion.kind.value,
                                "canonical": False,
                                "safe_reason": suggestion.safe_reason,
                            },
                        )
                    )
                remaining -= len(suggestions)
        return tuple(items)

    async def _superseded_fact_items(
        self,
        query: BuildMemoryDigestQuery,
    ) -> tuple[ContextItem, ...]:
        items: list[ContextItem] = []
        remaining = max(0, min(query.max_facts, 20))
        async with self._uow_factory() as uow:
            for memory_scope_id in query.memory_scope_ids:
                if remaining <= 0:
                    break
                facts = await uow.facts.list_for_scope(
                    space_id=str(query.space_id),
                    memory_scope_id=str(memory_scope_id),
                    thread_id=str(query.thread_id) if query.thread_id else None,
                    status="superseded",
                    limit=remaining,
                )
                for fact in facts:
                    items.append(
                        ContextItem(
                            item_id=str(fact.id),
                            item_type="fact",
                            text=fact.text,
                            score=0.25,
                            source_refs=fact.source_refs,
                            diagnostics={
                                "memory_scope_id": str(fact.memory_scope_id),
                                "retrieval_source": "superseded_review",
                                "retrieval_sources": ["superseded_review"],
                                "ranking_reason": (
                                    "included only because include_superseded requested "
                                    "review evidence"
                                ),
                                "score_signals": {
                                    "base_score": 0.25,
                                    "canonical": False,
                                    "review_only": True,
                                },
                                "provenance": {
                                    "retrieval_sources": ["superseded_review"],
                                    "source_ref_count": len(fact.source_refs),
                                    "fact_status": fact.status.value,
                                    "fact_version": fact.version,
                                    "visibility": "review_only",
                                },
                                "status": fact.status.value,
                                "kind": fact.kind.value,
                                "canonical": False,
                                "review_only": True,
                            },
                        )
                    )
                remaining -= len(facts)
        return tuple(items)


def _dedupe_source_refs(source_refs: tuple[SourceRef, ...]) -> tuple[SourceRef, ...]:
    seen: set[tuple[str, str, str | None, int | None, int | None]] = set()
    deduped: list[SourceRef] = []
    for ref in source_refs:
        key = (ref.source_type, ref.source_id, ref.chunk_id, ref.char_start, ref.char_end)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return tuple(deduped)
