from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from infinity_context_server.public_benchmark_checkpoint import (
    CaseRunResult,
    load_checkpoint_resume_state_with_diagnostics,
)
from infinity_context_server.public_benchmark_metrics import case_failures, case_payload


def test_public_benchmark_case_payload_includes_bounded_question_preview() -> None:
    result = _case_result(question_preview="What did Alex decide about Atlas?" * 20)

    payload = case_payload(result)

    assert payload["question_preview"].startswith("What did Alex decide")
    assert len(payload["question_preview"]) == 240


def test_public_benchmark_case_failures_include_question_preview() -> None:
    result = _case_result(
        ok=False,
        missing_terms=("answer",),
        question_preview="Who supports Caroline?",
    )

    failures = case_failures((result,))

    assert failures == [
        {
            "case_id": "case-one",
            "category": "locomo",
            "capability": "locomo:temporal_reasoning",
            "reason": "missing_expected_terms",
            "missing_terms": ["answer"],
            "leaked_terms": [],
            "question_preview": "Who supports Caroline?",
        }
    ]


def test_public_benchmark_resume_accepts_checkpoint_without_question_preview(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(
        json.dumps(
            {
                "schema_version": "public-benchmark-checkpoint-v1",
                "dataset_hash": "dataset-hash",
                "case_selection": {"strategy": "first"},
                "cases": [
                    {
                        "benchmark": "locomo",
                        "case_id": "case-one",
                        "capability": "locomo:temporal_reasoning",
                        "status": "ok",
                        "expected_ok": True,
                        "forbidden_ok": True,
                        "missing_terms": [],
                        "leaked_terms": [],
                        "item_ids": ["chunk-one"],
                        "latency_ms": 12.5,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    loaded = load_checkpoint_resume_state_with_diagnostics(
        checkpoint_out=checkpoint,
        dataset_hash="dataset-hash",
        case_selection={"strategy": "first"},
        cases=(_Case("locomo", "case-one"),),
    )

    assert loaded.status == "loaded"
    assert loaded.state is not None
    assert loaded.state.run_results[0].question_preview == ""


@dataclass(frozen=True)
class _Case:
    benchmark: str
    case_id: str
    memory_scope_external_ref: str | None = None
    thread_external_ref: str | None = None
    memories: tuple[object, ...] = ()
    documents: tuple[object, ...] = ()


def _case_result(
    *,
    ok: bool = True,
    missing_terms: tuple[str, ...] = (),
    question_preview: str = "",
) -> CaseRunResult:
    return CaseRunResult(
        benchmark="locomo",
        case_id="case-one",
        capability="locomo:temporal_reasoning",
        ok=ok,
        expected_ok=not missing_terms,
        forbidden_ok=True,
        missing_terms=missing_terms,
        leaked_terms=(),
        item_ids=("chunk-one",),
        latency_ms=12.5,
        question_preview=question_preview,
    )
