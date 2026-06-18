import asyncio
from datetime import UTC, datetime

from infinity_context_core.application.context_hydration import ContextHydrator
from infinity_context_core.application.dto import BuildContextQuery, ContextItem
from infinity_context_core.domain.entities import (
    MemoryFact,
    MemoryFactId,
    MemoryKind,
    MemoryScopeId,
    SourceRef,
    SpaceId,
)

NOW = datetime(2026, 6, 18, tzinfo=UTC)


def test_hydrator_revalidates_fact_items_with_single_batch_lookup() -> None:
    repo = _BatchOnlyFactRepo(
        facts={
            "fact_1": _fact("fact_1", text="Fact one is visible."),
            "fact_2": _fact("fact_2", text="Fact two is visible."),
        }
    )
    chunks = _FailingChunkRepo()
    hydrator = ContextHydrator(uow_factory=_FakeUowFactory(facts=repo, chunks=chunks))

    result = asyncio.run(
        hydrator.revalidate_visible_items(
            (
                _item("fact_1"),
                _item("fact_2"),
                _item("fact_missing"),
            ),
            query=_query(),
            memory_scope_ids=("scope_1",),
        )
    )

    assert [item.item_id for item in result] == ["fact_1", "fact_2"]
    assert [item.text for item in result] == ["Fact one is visible.", "Fact two is visible."]
    assert repo.get_by_ids_calls == [("fact_1", "fact_2", "fact_missing")]
    assert repo.get_by_id_calls == []
    assert chunks.hydrate_visible_chunks_calls == []


def test_hydrator_hydrates_graph_facts_with_single_batch_lookup() -> None:
    repo = _BatchOnlyFactRepo(
        facts={
            "fact_1": _fact("fact_1", text="Graph fact one is visible."),
            "fact_2": _fact("fact_2", text="Graph fact two is visible."),
        }
    )
    hydrator = ContextHydrator(
        uow_factory=_FakeUowFactory(facts=repo, chunks=_FailingChunkRepo())
    )

    items, stale_count = asyncio.run(
        hydrator.hydrate_graph_facts(
            fact_ids=("fact_1", "fact_missing", "fact_2"),
            query=_query(),
            memory_scope_ids=("scope_1",),
        )
    )

    assert [item.item_id for item in items] == ["fact_1", "fact_2"]
    assert [item.text for item in items] == [
        "Graph fact one is visible.",
        "Graph fact two is visible.",
    ]
    assert stale_count == 1
    assert repo.get_by_ids_calls == [("fact_1", "fact_missing", "fact_2")]
    assert repo.get_by_id_calls == []


class _BatchOnlyFactRepo:
    def __init__(self, *, facts: dict[str, MemoryFact]) -> None:
        self._facts = facts
        self.get_by_ids_calls: list[tuple[str, ...]] = []
        self.get_by_id_calls: list[str] = []

    async def get_by_ids(self, fact_ids: tuple[str, ...]) -> list[MemoryFact]:
        self.get_by_ids_calls.append(fact_ids)
        return [fact for fact_id in fact_ids if (fact := self._facts.get(fact_id)) is not None]

    async def get_by_id(self, fact_id: str) -> MemoryFact | None:
        self.get_by_id_calls.append(fact_id)
        raise AssertionError("context hydration must use batch fact lookup")


class _FailingChunkRepo:
    def __init__(self) -> None:
        self.hydrate_visible_chunks_calls: list[tuple[str, ...]] = []

    async def hydrate_visible_chunks(self, *, chunk_ids: tuple[str, ...], **_kwargs):
        self.hydrate_visible_chunks_calls.append(chunk_ids)
        raise AssertionError("empty chunk hydration should not call chunk repository")


class _FakeUow:
    def __init__(self, *, facts: _BatchOnlyFactRepo, chunks: _FailingChunkRepo) -> None:
        self.facts = facts
        self.chunks = chunks

    async def __aenter__(self) -> "_FakeUow":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class _FakeUowFactory:
    def __init__(self, *, facts: _BatchOnlyFactRepo, chunks: _FailingChunkRepo) -> None:
        self._facts = facts
        self._chunks = chunks

    def __call__(self) -> _FakeUow:
        return _FakeUow(facts=self._facts, chunks=self._chunks)


def _fact(fact_id: str, *, text: str) -> MemoryFact:
    return MemoryFact.create(
        fact_id=MemoryFactId(fact_id),
        space_id=SpaceId("space_1"),
        memory_scope_id=MemoryScopeId("scope_1"),
        text=text,
        kind=MemoryKind.NOTE,
        source_refs=(SourceRef(source_type="manual", source_id=fact_id),),
        now=NOW,
    )


def _item(item_id: str) -> ContextItem:
    return ContextItem(
        item_id=item_id,
        item_type="fact",
        text=f"Stale text for {item_id}",
        score=0.7,
        source_refs=(),
        diagnostics={"retrieval_source": "test"},
    )


def _query() -> BuildContextQuery:
    return BuildContextQuery(
        space_id=SpaceId("space_1"),
        memory_scope_ids=(MemoryScopeId("scope_1"),),
        query="visible fact",
        token_budget=512,
    )
