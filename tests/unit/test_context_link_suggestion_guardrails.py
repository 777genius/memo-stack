import asyncio
from datetime import UTC, datetime

from memo_stack_core.application.dto import SuggestContextLinksCommand
from memo_stack_core.application.use_cases.context_link_suggestions import (
    MAX_CONTEXT_LINK_SUGGESTION_LIMIT,
    SuggestContextLinksUseCase,
)
from memo_stack_core.domain.entities import MemoryScopeId, SpaceId


def test_context_link_suggestions_clamps_large_internal_limit_and_fanout() -> None:
    uow = _RecordingUnitOfWork()
    use_case = SuggestContextLinksUseCase(
        uow_factory=lambda: uow,
        clock=_FixedClock(),
        ids=_Ids(),
    )

    result = asyncio.run(
        use_case.execute(
            SuggestContextLinksCommand(
                space_id=SpaceId("space_guardrail"),
                memory_scope_id=MemoryScopeId("scope_guardrail"),
                text="Alex mentioned the Atlas migration in yesterday's review.",
                limit=999,
            )
        )
    )

    assert result.candidates == ()
    assert result.diagnostics["requested_limit"] == 999
    assert result.diagnostics["effective_limit"] == MAX_CONTEXT_LINK_SUGGESTION_LIMIT
    assert result.diagnostics["limit_clamped"] is True
    assert result.diagnostics["link_policy_max_suggestions_per_source"] == (
        MAX_CONTEXT_LINK_SUGGESTION_LIMIT
    )
    assert uow.limits == {
        "facts.find_active": 90,
        "facts.list_for_scope": 30,
        "episodes.list_for_scope": 30,
        "captures.list_for_scope": 30,
        "suggestions.list_for_scope": 30,
        "assets.list_for_scope": 30,
        "documents.list_for_scope": 30,
        "chunks.keyword_search": 60,
        "scope.list_threads": 30,
        "anchors.list_for_scope": 90,
    }


def test_context_link_suggestions_clamps_zero_internal_limit_to_one() -> None:
    uow = _RecordingUnitOfWork()
    use_case = SuggestContextLinksUseCase(
        uow_factory=lambda: uow,
        clock=_FixedClock(),
        ids=_Ids(),
    )

    result = asyncio.run(
        use_case.execute(
            SuggestContextLinksCommand(
                space_id=SpaceId("space_guardrail"),
                memory_scope_id=MemoryScopeId("scope_guardrail"),
                text="No strong match expected.",
                limit=0,
            )
        )
    )

    assert result.diagnostics["requested_limit"] == 0
    assert result.diagnostics["effective_limit"] == 1
    assert result.diagnostics["limit_clamped"] is True
    assert result.diagnostics["link_policy_max_suggestions_per_source"] == 1
    assert uow.limits == {
        "facts.find_active": 12,
        "facts.list_for_scope": 8,
        "episodes.list_for_scope": 8,
        "captures.list_for_scope": 8,
        "suggestions.list_for_scope": 8,
        "assets.list_for_scope": 8,
        "documents.list_for_scope": 8,
        "chunks.keyword_search": 12,
        "scope.list_threads": 8,
        "anchors.list_for_scope": 24,
    }


class _FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 1, 1, tzinfo=UTC)


class _Ids:
    def new_id(self, prefix: str) -> str:
        return f"{prefix}_guardrail"


class _RecordingUnitOfWork:
    def __init__(self) -> None:
        self.limits: dict[str, int] = {}
        self.scope = _RecordingRepository("scope", self.limits)
        self.facts = _RecordingRepository("facts", self.limits)
        self.episodes = _RecordingRepository("episodes", self.limits)
        self.captures = _RecordingRepository("captures", self.limits)
        self.suggestions = _RecordingRepository("suggestions", self.limits)
        self.assets = _RecordingRepository("assets", self.limits)
        self.documents = _RecordingRepository("documents", self.limits)
        self.chunks = _RecordingRepository("chunks", self.limits)
        self.anchors = _RecordingRepository("anchors", self.limits)

    async def __aenter__(self) -> "_RecordingUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        return None


class _RecordingRepository:
    def __init__(self, name: str, limits: dict[str, int]) -> None:
        self._name = name
        self._limits = limits

    async def get_by_id(self, *_args: object, **_kwargs: object) -> None:
        return None

    async def find_active(self, *_args: object, **kwargs: object) -> list[object]:
        self._record("find_active", kwargs)
        return []

    async def list_for_scope(self, *_args: object, **kwargs: object) -> list[object]:
        self._record("list_for_scope", kwargs)
        return []

    async def keyword_search(self, *_args: object, **kwargs: object) -> list[object]:
        self._record("keyword_search", kwargs)
        return []

    async def list_threads(self, *_args: object, **kwargs: object) -> list[object]:
        self._record("list_threads", kwargs)
        return []

    def _record(self, method: str, kwargs: object) -> None:
        if isinstance(kwargs, dict):
            limit = kwargs.get("limit")
            if isinstance(limit, int):
                self._limits[f"{self._name}.{method}"] = limit
