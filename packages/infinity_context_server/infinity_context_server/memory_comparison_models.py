"""Models and ports for side-by-side memory benchmark runs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from infinity_context_server.public_benchmark_models import PublicBenchmarkCase

Verdict = Literal["correct", "incorrect", "error"]


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class RetrievedMemory:
    text: str
    rank: int
    score: float = 0.0
    item_id: str | None = None
    created_at: str | None = None
    source_refs: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class IngestionOperation:
    step: int
    operation_type: str
    success: bool
    latency_ms: float = 0.0
    memory: str | None = None
    item_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class BackendIngestResult:
    items_processed: int
    items_failed: int = 0
    total_memories_created: int | None = None
    latency_ms: float = 0.0
    reused: bool = False
    operations: tuple[IngestionOperation, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class BackendSearchResult:
    query: str
    memories: tuple[RetrievedMemory, ...]
    latency_ms: float = 0.0
    total_results: int | None = None
    context_token_count: int | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    model: str = "deterministic"
    latency_ms: float = 0.0
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class JudgeResult:
    verdict: Verdict
    score: float
    reason: str = ""
    model: str = "deterministic"
    latency_ms: float = 0.0
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    metadata: Mapping[str, object] = field(default_factory=dict)


class MemoryComparisonBackendPort(Protocol):
    name: str

    def reset(self, *, run_id: str) -> None:
        """Prepare isolated benchmark state for this run."""

    def ingest(
        self,
        case: PublicBenchmarkCase,
        *,
        run_id: str,
        corpus_key: str,
    ) -> BackendIngestResult:
        """Ingest one reusable conversation/corpus for subsequent searches."""

    def search(
        self,
        case: PublicBenchmarkCase,
        *,
        run_id: str,
        top_k: int,
    ) -> BackendSearchResult:
        """Retrieve memories for a benchmark question."""


class MemoryComparisonAnswererPort(Protocol):
    model: str

    def answer(
        self,
        case: PublicBenchmarkCase,
        memories: Sequence[RetrievedMemory],
        *,
        backend_name: str,
        cutoff: int,
    ) -> AnswerResult:
        """Generate an answer from retrieved memories."""


class MemoryComparisonJudgePort(Protocol):
    model: str

    def judge(
        self,
        case: PublicBenchmarkCase,
        answer: AnswerResult,
        memories: Sequence[RetrievedMemory],
        *,
        backend_name: str,
        cutoff: int,
    ) -> JudgeResult:
        """Judge generated answer against the benchmark ground truth."""


def token_usage_payload(usage: TokenUsage) -> dict[str, int]:
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }


def retrieved_memory_payload(memory: RetrievedMemory) -> dict[str, object]:
    payload: dict[str, object] = {
        "rank": memory.rank,
        "memory": memory.text,
        "score": memory.score,
    }
    if memory.item_id:
        payload["id"] = memory.item_id
    if memory.created_at:
        payload["created_at"] = memory.created_at
    if memory.source_refs:
        payload["source_refs"] = list(memory.source_refs)
    if memory.metadata:
        payload["metadata"] = dict(memory.metadata)
    return payload


def ingestion_payload(result: BackendIngestResult) -> dict[str, object]:
    payload: dict[str, object] = {
        "items_processed": result.items_processed,
        "items_failed": result.items_failed,
        "latency_ms": result.latency_ms,
        "reused": result.reused,
    }
    if result.total_memories_created is not None:
        payload["total_memories_created"] = result.total_memories_created
    if result.operations:
        payload["operations"] = [
            {
                "step": operation.step,
                "type": operation.operation_type,
                "success": operation.success,
                "latency_ms": operation.latency_ms,
                **({"memory": operation.memory} if operation.memory else {}),
                **({"id": operation.item_id} if operation.item_id else {}),
                **({"metadata": dict(operation.metadata)} if operation.metadata else {}),
            }
            for operation in result.operations
        ]
    if result.metadata:
        payload["metadata"] = dict(result.metadata)
    return payload


def search_payload(result: BackendSearchResult) -> dict[str, object]:
    payload: dict[str, object] = {
        "query": result.query,
        "latency_ms": result.latency_ms,
        "results": [retrieved_memory_payload(memory) for memory in result.memories],
        "total_results": result.total_results
        if result.total_results is not None
        else len(result.memories),
    }
    if result.context_token_count is not None:
        payload["context_token_count"] = result.context_token_count
    if result.metadata:
        payload["metadata"] = dict(result.metadata)
    return payload


def answer_payload(result: AnswerResult) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": result.model,
        "answer": result.answer,
        "latency_ms": result.latency_ms,
        "token_usage": token_usage_payload(result.token_usage),
    }
    if result.metadata:
        payload["metadata"] = dict(result.metadata)
    return payload


def judge_payload(result: JudgeResult) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": result.model,
        "verdict": result.verdict,
        "score": result.score,
        "reason": result.reason,
        "latency_ms": result.latency_ms,
        "token_usage": token_usage_payload(result.token_usage),
    }
    if result.metadata:
        payload["metadata"] = dict(result.metadata)
    return payload


def as_public_mapping(value: Any) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}
