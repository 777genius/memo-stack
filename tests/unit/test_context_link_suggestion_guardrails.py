import asyncio
from datetime import UTC, datetime

from memo_stack_core.application.dto import SuggestContextLinksCommand
from memo_stack_core.application.use_cases.context_link_suggestions import (
    MAX_CONTEXT_LINK_SUGGESTION_LIMIT,
    SuggestContextLinksUseCase,
)
from memo_stack_core.domain.entities import (
    LifecycleStatus,
    MemoryChunk,
    MemoryChunkId,
    MemoryChunkKind,
    MemoryDocumentId,
    MemoryScopeId,
    SpaceId,
    ThreadId,
)


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


def test_context_link_suggestions_explains_multimodal_chunk_matches() -> None:
    uow = _RecordingUnitOfWork(chunks=[_multimodal_transcript_chunk()])
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
                text="Link this to Alex renewal transcript.",
                source_type="capture",
                source_id="capture_1",
                limit=10,
            )
        )
    )

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.target_type == "chunk"
    assert "transcript match" in candidate.reasons
    assert candidate.metadata is not None
    assert "text_match" in candidate.metadata["reason_codes"]
    assert "transcript_match" in candidate.metadata["reason_codes"]
    assert candidate.metadata["evidence_kinds"] == ["transcript_segment"]
    assert candidate.metadata["evidence_modalities"] == ["audio", "time_range"]
    assert candidate.metadata["evidence_has_time_range_ref"] is True
    assert candidate.metadata["policy_decision_canonical"] == "pending_review"


class _FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 1, 1, tzinfo=UTC)


class _Ids:
    def new_id(self, prefix: str) -> str:
        return f"{prefix}_guardrail"


class _RecordingUnitOfWork:
    def __init__(self, *, chunks: list[MemoryChunk] | None = None) -> None:
        self.limits: dict[str, int] = {}
        self.scope = _RecordingRepository("scope", self.limits)
        self.facts = _RecordingRepository("facts", self.limits)
        self.episodes = _RecordingRepository("episodes", self.limits)
        self.captures = _RecordingRepository("captures", self.limits)
        self.suggestions = _RecordingRepository("suggestions", self.limits)
        self.assets = _RecordingRepository("assets", self.limits)
        self.documents = _RecordingRepository("documents", self.limits)
        self.chunks = _RecordingRepository(
            "chunks",
            self.limits,
            keyword_search_result=chunks or [],
        )
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
    def __init__(
        self,
        name: str,
        limits: dict[str, int],
        *,
        keyword_search_result: list[object] | None = None,
    ) -> None:
        self._name = name
        self._limits = limits
        self._keyword_search_result = keyword_search_result or []

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
        return list(self._keyword_search_result)

    async def list_threads(self, *_args: object, **kwargs: object) -> list[object]:
        self._record("list_threads", kwargs)
        return []

    def _record(self, method: str, kwargs: object) -> None:
        if isinstance(kwargs, dict):
            limit = kwargs.get("limit")
            if isinstance(limit, int):
                self._limits[f"{self._name}.{method}"] = limit


def _multimodal_transcript_chunk() -> MemoryChunk:
    text = "Alex renewal transcript confirms the memory scope migration."
    return MemoryChunk(
        id=MemoryChunkId("chunk_transcript_1"),
        space_id=SpaceId("space_guardrail"),
        memory_scope_id=MemoryScopeId("scope_guardrail"),
        thread_id=ThreadId("thread_alex"),
        document_id=MemoryDocumentId("doc_transcript_1"),
        episode_id=None,
        source_type="asset_extraction",
        source_external_id="extract_audio_1",
        source_hash="hash_transcript_1",
        kind=MemoryChunkKind.DOCUMENT_SECTION,
        text=text,
        normalized_text=text.lower(),
        status=LifecycleStatus.ACTIVE,
        sequence=1,
        char_start=0,
        char_end=len(text),
        token_estimate=12,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        metadata={
            "asset_id": "asset_audio_1",
            "extraction_job_id": "extract_audio_1",
            "normalized_content_type": "audio/mpeg",
            "parser_name": "speech_transcription",
            "source_refs": [
                {
                    "source_type": "asset_extraction",
                    "source_id": "extract_audio_1",
                    "kind": "transcript_segment",
                    "time_start_ms": 1200,
                    "time_end_ms": 3400,
                    "quote_preview": "Alex renewal transcript",
                }
            ],
        },
    )
