from __future__ import annotations

from datetime import UTC, datetime

from memo_stack_core.application import BuildMemoryDigestQuery, ConsistencyMode
from memo_stack_core.application.dto import ContextBundle, ContextItem
from memo_stack_core.application.use_cases.build_memory_digest import BuildMemoryDigestUseCase
from memo_stack_core.domain.entities import (
    Confidence,
    MemoryKind,
    MemorySuggestion,
    MemorySuggestionId,
    ProfileId,
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
                    diagnostics={"profile_id": "profile_1"},
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
                    diagnostics={"profile_id": "profile_1"},
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
                profile_id=ProfileId(kwargs["profile_id"]),
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
    async def list_for_scope(self, **_kwargs):
        return []


class FakeUow:
    def __init__(self) -> None:
        self.suggestions = FakeSuggestionRepo()
        self.facts = FakeFactRepo()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


def fake_uow_factory() -> FakeUow:
    return FakeUow()


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
                profile_ids=(ProfileId("profile_1"),),
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
