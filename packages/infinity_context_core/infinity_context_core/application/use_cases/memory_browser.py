"""Read model for browsing a memory scope."""

from __future__ import annotations

from collections.abc import Sequence

from infinity_context_core.application.dto import MemoryBrowserQuery, MemoryBrowserResult
from infinity_context_core.domain.errors import MemoryNotFoundError
from infinity_context_core.ports.clock import ClockPort
from infinity_context_core.ports.unit_of_work import UnitOfWorkFactoryPort


class BuildMemoryBrowserUseCase:
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactoryPort,
        clock: ClockPort,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, query: MemoryBrowserQuery) -> MemoryBrowserResult:
        limit = max(1, min(query.limit, 200))
        space_id = str(query.space_id)
        memory_scope_id = str(query.memory_scope_id)
        async with self._uow_factory() as uow:
            memory_scope = await uow.scope.get_memory_scope(memory_scope_id)
            if memory_scope is None or str(memory_scope.space_id) != space_id:
                raise MemoryNotFoundError("MemoryScope not found")

            facts = await uow.facts.list_for_scope(
                space_id=space_id,
                memory_scope_id=memory_scope_id,
                thread_id=None,
                status=query.fact_status,
                limit=limit,
            )
            episodes = await uow.episodes.list_for_scope(
                space_id=space_id,
                memory_scope_id=memory_scope_id,
                thread_id=None,
                status=query.episode_status,
                limit=limit,
            )
            documents = await uow.documents.list_for_scope(
                space_id=space_id,
                memory_scope_id=memory_scope_id,
                thread_id=None,
                status=query.document_status,
                limit=limit,
            )
            chunks = await uow.chunks.list_for_scope(
                space_id=space_id,
                memory_scope_id=memory_scope_id,
                thread_id=None,
                status=query.chunk_status,
                limit=limit,
            )
            extraction_jobs = await uow.asset_extractions.list_for_scope(
                space_id=space_id,
                memory_scope_id=memory_scope_id,
                thread_id=None,
                status=query.extraction_status,
                limit=limit,
            )
            threads = await uow.scope.list_threads(
                space_id=space_id,
                memory_scope_id=memory_scope_id,
                status=query.thread_status,
                limit=limit,
            )
            captures = await uow.captures.list_for_scope(
                space_id=space_id,
                memory_scope_id=memory_scope_id,
                status=query.capture_status,
                consolidation_status=None,
                limit=limit,
            )
            assets = await uow.assets.list_for_scope(
                space_id=space_id,
                memory_scope_id=memory_scope_id,
                thread_id=None,
                status=query.asset_status,
                limit=limit,
            )
            anchors = await uow.anchors.list_for_scope(
                space_id=space_id,
                memory_scope_id=memory_scope_id,
                kind=None,
                status=query.anchor_status,
                limit=limit,
            )
            context_links = await uow.context_links.list_for_scope(
                space_id=space_id,
                memory_scope_id=memory_scope_id,
                status=query.link_status,
                limit=limit,
            )
            suggestions = await uow.context_link_suggestions.list_for_scope(
                space_id=space_id,
                memory_scope_id=memory_scope_id,
                status=query.suggestion_status,
                limit=limit,
            )

        stats = {
            "facts": len(facts),
            "episodes": len(episodes),
            "documents": len(documents),
            "chunks": len(chunks),
            "extraction_jobs": len(extraction_jobs),
            "threads": len(threads),
            "captures": len(captures),
            "assets": len(assets),
            "anchors": len(anchors),
            "context_links": len(context_links),
            "context_link_suggestions": len(suggestions),
            "pending_context_link_suggestions": sum(
                1 for suggestion in suggestions if suggestion.status.value == "pending"
            ),
            "active_context_links": sum(
                1 for link in context_links if link.status.value == "active"
            ),
        }
        visual_summary = _build_visual_summary(
            stats=stats,
            limit=limit,
            facts=facts,
            episodes=episodes,
            documents=documents,
            chunks=chunks,
            extraction_jobs=extraction_jobs,
            threads=threads,
            captures=captures,
            assets=assets,
            anchors=anchors,
        )
        quick_actions = _build_quick_actions(visual_summary=visual_summary, stats=stats)
        return MemoryBrowserResult(
            generated_at=self._clock.now(),
            memory_scope=memory_scope,
            facts=tuple(facts),
            episodes=tuple(episodes),
            documents=tuple(documents),
            chunks=tuple(chunks),
            extraction_jobs=tuple(extraction_jobs),
            threads=tuple(threads),
            captures=tuple(captures),
            assets=tuple(assets),
            anchors=tuple(anchors),
            context_links=tuple(context_links),
            context_link_suggestions=tuple(suggestions),
            stats=stats,
            visual_summary=visual_summary,
            quick_actions=tuple(quick_actions),
            diagnostics={
                "browser_version": "memory-browser-v1",
                "visual_summary_version": "visual-memory-summary-v1",
                "limit": limit,
                "statuses": {
                    "fact": query.fact_status,
                    "episode": query.episode_status,
                    "document": query.document_status,
                    "chunk": query.chunk_status,
                    "extraction": query.extraction_status,
                    "thread": query.thread_status,
                    "capture": query.capture_status,
                    "asset": query.asset_status,
                    "anchor": query.anchor_status,
                    "link": query.link_status,
                    "suggestion": query.suggestion_status,
                },
            },
        )


def _build_visual_summary(
    *,
    stats: dict[str, int],
    limit: int,
    facts: Sequence[object],
    episodes: Sequence[object],
    documents: Sequence[object],
    chunks: Sequence[object],
    extraction_jobs: Sequence[object],
    threads: Sequence[object],
    captures: Sequence[object],
    assets: Sequence[object],
    anchors: Sequence[object],
) -> dict[str, object]:
    evidence_count = (
        stats["facts"]
        + stats["episodes"]
        + stats["documents"]
        + stats["chunks"]
        + stats["captures"]
        + stats["assets"]
    )
    relationship_count = (
        stats["anchors"] + stats["context_links"] + stats["context_link_suggestions"]
    )
    pending_review_count = stats["pending_context_link_suggestions"]
    active_link_count = stats["active_context_links"]
    processing_job_count = _status_count(extraction_jobs, {"pending", "running"})
    failed_job_count = _status_count(extraction_jobs, {"failed", "unsupported", "canceled"})
    limit_reached = any(
        len(items) >= limit
        for items in (
            facts,
            episodes,
            documents,
            chunks,
            extraction_jobs,
            threads,
            captures,
            assets,
            anchors,
        )
    )
    visible_sources = _visible_sources(
        facts=facts,
        episodes=episodes,
        documents=documents,
        chunks=chunks,
        captures=captures,
        assets=assets,
    )
    health_hints = _visual_health_hints(
        evidence_count=evidence_count,
        relationship_count=relationship_count,
        pending_review_count=pending_review_count,
        processing_job_count=processing_job_count,
        failed_job_count=failed_job_count,
        active_link_count=active_link_count,
        limit_reached=limit_reached,
        chunk_count=stats["chunks"],
        anchor_count=stats["anchors"],
    )
    if evidence_count == 0 and relationship_count == 0:
        status = "empty"
    elif failed_job_count > 0:
        status = "attention_needed"
    elif pending_review_count > 0:
        status = "review_needed"
    elif processing_job_count > 0:
        status = "processing"
    else:
        status = "ready"
    return {
        "status": status,
        "evidence_count": evidence_count,
        "relationship_count": relationship_count,
        "pending_review_count": pending_review_count,
        "active_link_count": active_link_count,
        "processing_job_count": processing_job_count,
        "failed_job_count": failed_job_count,
        "visible_sources": visible_sources,
        "limit_reached": limit_reached,
        "health_hints": health_hints,
    }


def _build_quick_actions(
    *,
    visual_summary: dict[str, object],
    stats: dict[str, int],
) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    status = visual_summary.get("status")
    if status == "empty":
        actions.append(
            _quick_action(
                "capture_first_memory",
                "Capture first memory",
                "Save a note, screenshot or file into this MemoryScope.",
                priority=1,
            )
        )
    if int(visual_summary.get("pending_review_count") or 0) > 0:
        actions.append(
            _quick_action(
                "review_pending_links",
                "Review pending links",
                "Approve, reject or edit suggested memory relationships.",
                priority=1,
            )
        )
    if int(visual_summary.get("failed_job_count") or 0) > 0:
        actions.append(
            _quick_action(
                "inspect_failed_extractions",
                "Inspect failed extractions",
                "Open failed or unsupported asset extraction jobs before relying on evidence.",
                priority=2,
            )
        )
    if int(visual_summary.get("processing_job_count") or 0) > 0:
        actions.append(
            _quick_action(
                "wait_for_processing",
                "Wait for processing",
                "Some files are still being extracted and may add more evidence.",
                priority=3,
            )
        )
    if stats["anchors"] == 0 and int(visual_summary.get("evidence_count") or 0) > 0:
        actions.append(
            _quick_action(
                "backfill_anchors",
                "Build anchors",
                "Extract people, projects and events to make navigation stronger.",
                priority=3,
            )
        )
    if stats["context_links"] == 0 and int(visual_summary.get("evidence_count") or 0) > 1:
        actions.append(
            _quick_action(
                "suggest_links",
                "Suggest links",
                "Find relationships between saved notes, files, anchors and threads.",
                priority=3,
            )
        )
    if not actions and int(visual_summary.get("evidence_count") or 0) > 0:
        actions.append(
            _quick_action(
                "search_memory",
                "Search memory",
                "Ask a question and use returned items as cited evidence.",
                priority=4,
            )
        )
    return actions[:5]


def _quick_action(
    action_id: str,
    label: str,
    description: str,
    *,
    priority: int,
) -> dict[str, object]:
    return {
        "id": action_id,
        "label": label,
        "description": description,
        "priority": priority,
    }


def _status_count(items: Sequence[object], statuses: set[str]) -> int:
    return sum(
        1
        for item in items
        if getattr(getattr(item, "status", None), "value", "") in statuses
    )


def _visible_sources(
    *,
    facts: Sequence[object],
    episodes: Sequence[object],
    documents: Sequence[object],
    chunks: Sequence[object],
    captures: Sequence[object],
    assets: Sequence[object],
) -> list[str]:
    sources: set[str] = set()
    if len(facts) > 0:
        sources.add("facts")
    if len(episodes) > 0:
        sources.add("episodes")
    if len(documents) > 0:
        sources.add("documents")
    if len(chunks) > 0:
        sources.add("chunks")
    if len(captures) > 0:
        sources.add("captures")
    if len(assets) > 0:
        sources.add("assets")
    return sorted(sources)


def _visual_health_hints(
    *,
    evidence_count: int,
    relationship_count: int,
    pending_review_count: int,
    processing_job_count: int,
    failed_job_count: int,
    active_link_count: int,
    limit_reached: bool,
    chunk_count: int,
    anchor_count: int,
) -> list[str]:
    hints: list[str] = []
    if evidence_count == 0 and relationship_count == 0:
        hints.append("empty_scope")
    if pending_review_count > 0:
        hints.append("pending_review")
    if processing_job_count > 0:
        hints.append("processing_evidence")
    if failed_job_count > 0:
        hints.append("failed_extractions")
    if evidence_count > 0 and anchor_count == 0:
        hints.append("anchors_missing")
    if evidence_count > 1 and active_link_count == 0:
        hints.append("links_missing")
    if evidence_count > 0 and chunk_count == 0:
        hints.append("retrieval_chunks_missing")
    if limit_reached:
        hints.append("browser_limit_may_hide_more")
    return hints
