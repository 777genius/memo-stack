from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from infinity_context_core.application import BuildMemoryDigestQuery, ConsistencyMode
from infinity_context_core.application.dto import ContextBundle, ContextItem
from infinity_context_core.application.use_cases.build_memory_digest import BuildMemoryDigestUseCase
from infinity_context_core.domain.entities import (
    Confidence,
    FactStatus,
    MemoryFact,
    MemoryFactId,
    MemoryKind,
    MemoryScopeId,
    MemorySuggestion,
    MemorySuggestionId,
    SourceRef,
    SpaceId,
    SuggestionOperation,
    TrustLevel,
)


class FakeIds:
    def new_id(self, prefix: str) -> str:
        return f"{prefix}_test"


class FakeContextBuilder:
    def __init__(self) -> None:
        self.queries = []

    async def execute(self, query):
        self.queries.append(query)
        return ContextBundle(
            bundle_id="ctx_test",
            rendered_text="Relevant memory evidence.",
            items=(
                ContextItem(
                    item_id="fact_1",
                    item_type="fact",
                    text="Graphiti is the temporal graph projection.",
                    score=0.95,
                    source_refs=(SourceRef(source_type="manual", source_id="src_1"),),
                    diagnostics={"memory_scope_id": "memory_scope_1"},
                ),
                ContextItem(
                    item_id="chunk_1",
                    item_type="chunk",
                    text="Qdrant stores document chunks for vector recall.",
                    score=0.82,
                    source_refs=(
                        SourceRef(
                            source_type="document",
                            source_id="doc_1",
                            chunk_id="chunk_1",
                        ),
                    ),
                    diagnostics={"memory_scope_id": "memory_scope_1"},
                ),
            ),
            token_estimate=32,
            diagnostics={
                "consistency_mode": query.consistency_mode.value,
                "vector_status": "disabled",
                "graph_status": "skipped",
                "rag_status": "disabled",
            },
        )


class FakeSuggestionRepo:
    async def list_for_scope(self, **kwargs):
        if kwargs["status"] != "pending":
            return []
        return [
            MemorySuggestion.create(
                suggestion_id=MemorySuggestionId("sug_1"),
                space_id=SpaceId(kwargs["space_id"]),
                memory_scope_id=MemoryScopeId(kwargs["memory_scope_id"]),
                candidate_text="Add memory_digest as a read-only MCP tool.",
                kind=MemoryKind.ARCHITECTURE_DECISION,
                operation=SuggestionOperation.ADD,
                source_refs=(SourceRef(source_type="manual", source_id="src_2"),),
                safe_reason="review needed",
                confidence=Confidence.MEDIUM,
                trust_level=TrustLevel.MEDIUM,
                now=datetime(2026, 6, 6, tzinfo=UTC),
            )
        ]


class FakeFactRepo:
    def __init__(self, *, include_superseded: bool = False) -> None:
        self._include_superseded = include_superseded

    async def list_for_scope(self, **kwargs):
        if not self._include_superseded or kwargs["status"] != "superseded":
            return []
        now = datetime(2026, 6, 6, tzinfo=UTC)
        fact = MemoryFact.create(
            fact_id=MemoryFactId("fact_superseded"),
            space_id=SpaceId(kwargs["space_id"]),
            memory_scope_id=MemoryScopeId(kwargs["memory_scope_id"]),
            text="Legacy Graphiti owner was Alex.",
            kind=MemoryKind.NOTE,
            source_refs=(SourceRef(source_type="manual", source_id="superseded-review"),),
            now=now,
        )
        return [replace(fact, status=FactStatus.SUPERSEDED, version=2, updated_at=now)]


class FakeUow:
    def __init__(self, *, include_superseded: bool = False) -> None:
        self.suggestions = FakeSuggestionRepo()
        self.facts = FakeFactRepo(include_superseded=include_superseded)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


def fake_uow_factory() -> FakeUow:
    return FakeUow()


def fake_uow_factory_with_superseded() -> FakeUow:
    return FakeUow(include_superseded=True)


def test_memory_digest_builds_source_bound_sections() -> None:
    import asyncio

    async def run() -> None:
        context_builder = FakeContextBuilder()
        use_case = BuildMemoryDigestUseCase(
            uow_factory=fake_uow_factory,
            ids=FakeIds(),
            context_builder=context_builder,
        )

        digest = await use_case.execute(
            BuildMemoryDigestQuery(
                space_id=SpaceId("space_1"),
                memory_scope_ids=(MemoryScopeId("memory_scope_1"),),
                topic="Graphiti and Qdrant decisions",
                consistency_mode=ConsistencyMode.BEST_EFFORT,
                include_related=False,
            )
        )

        assert digest.digest_id == "dig_test"
        assert "Memory Digest: Graphiti and Qdrant decisions" in digest.rendered_markdown
        assert "Evidence only: true" in digest.rendered_markdown
        assert "Graphiti is the temporal graph projection." in digest.rendered_markdown
        assert "Qdrant stores document chunks" in digest.rendered_markdown
        assert "Add memory_digest as a read-only MCP tool." in digest.rendered_markdown
        assert "not_canonical" in digest.rendered_markdown
        assert digest.diagnostics["pending_suggestions_considered"] == 1
        assert digest.diagnostics["include_related"] is False
        assert context_builder.queries[0].include_graph is False

    asyncio.run(run())


def test_memory_digest_marks_superseded_items_as_review_only_evidence() -> None:
    import asyncio

    async def run() -> None:
        context_builder = FakeContextBuilder()
        use_case = BuildMemoryDigestUseCase(
            uow_factory=fake_uow_factory_with_superseded,
            ids=FakeIds(),
            context_builder=context_builder,
        )

        hidden_digest = await use_case.execute(
            BuildMemoryDigestQuery(
                space_id=SpaceId("space_1"),
                memory_scope_ids=(MemoryScopeId("memory_scope_1"),),
                topic="Graphiti owner",
                include_superseded=False,
            )
        )
        review_digest = await use_case.execute(
            BuildMemoryDigestQuery(
                space_id=SpaceId("space_1"),
                memory_scope_ids=(MemoryScopeId("memory_scope_1"),),
                topic="Graphiti owner",
                include_superseded=True,
            )
        )

        stale_section = next(
            section
            for section in review_digest.sections
            if section.title == "Superseded or stale memory"
        )
        stale_item = stale_section.items[0]

        assert "Legacy Graphiti owner was Alex." not in hidden_digest.rendered_markdown
        assert "Legacy Graphiti owner was Alex." in review_digest.rendered_markdown
        assert "not_canonical" in review_digest.rendered_markdown
        assert stale_item.diagnostics["review_only"] is True
        assert stale_item.diagnostics["retrieval_source"] == "superseded_review"
        assert stale_item.diagnostics["ranking_reason"] == (
            "included only because include_superseded requested review evidence"
        )
        assert stale_item.diagnostics["provenance"]["visibility"] == "review_only"
        assert review_digest.diagnostics["superseded_facts_considered"] == 1

    asyncio.run(run())
