from __future__ import annotations

import json
import time
from pathlib import Path

from infinity_context_server.public_benchmark import _BenchmarkProgress
from infinity_context_server.public_benchmark_checkpoint import CaseRunResult


def _case_result(case_id: str = "case-one") -> CaseRunResult:
    return CaseRunResult(
        benchmark="locomo",
        case_id=case_id,
        capability="locomo:temporal_reasoning",
        ok=True,
        expected_ok=True,
        forbidden_ok=True,
        missing_terms=(),
        leaked_terms=(),
        item_ids=("chunk-one",),
        latency_ms=12.5,
    )


def test_public_benchmark_progress_writes_time_interval_checkpoint(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    progress = _BenchmarkProgress(
        dataset_path=tmp_path / "dataset.json",
        dataset_hash="dataset-hash",
        total_case_count=3,
        case_selection={"strategy": "first"},
        started=time.perf_counter() - 10,
        checkpoint_out=checkpoint,
        checkpoint_every_cases=100,
        checkpoint_min_interval_seconds=1.0,
    )

    progress.checkpoint(
        processed_case_count=1,
        run_results=(_case_result(),),
        failures=(),
        seeded_source_count=1,
    )

    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload["status"] == "running"
    assert payload["checkpoint_policy"] == {
        "checkpoint_every_cases": 100,
        "checkpoint_min_interval_seconds": 1.0,
        "checkpoint_reason": "time_interval",
    }
    assert payload["progress"]["checkpoint_reason"] == "time_interval"
    assert payload["progress"]["processed_case_count"] == 1
    assert payload["progress"]["elapsed_since_checkpoint_ms"] >= 1000


def test_public_benchmark_progress_throttles_time_checkpoint_until_due(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    progress = _BenchmarkProgress(
        dataset_path=tmp_path / "dataset.json",
        dataset_hash="dataset-hash",
        total_case_count=3,
        case_selection=None,
        started=time.perf_counter(),
        checkpoint_out=checkpoint,
        checkpoint_every_cases=100,
        checkpoint_min_interval_seconds=3600.0,
    )

    progress.checkpoint(
        processed_case_count=1,
        run_results=(_case_result(),),
        failures=(),
        seeded_source_count=1,
    )

    assert not checkpoint.exists()

    progress.checkpoint(
        processed_case_count=1,
        run_results=(_case_result(),),
        failures=(),
        seeded_source_count=1,
        force=True,
    )

    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload["checkpoint_policy"]["checkpoint_reason"] == "forced"
    assert payload["progress"]["checkpoint_reason"] == "forced"


def test_public_benchmark_progress_writes_completed_checkpoint_without_force(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    progress = _BenchmarkProgress(
        dataset_path=tmp_path / "dataset.json",
        dataset_hash="dataset-hash",
        total_case_count=1,
        case_selection=None,
        started=time.perf_counter(),
        checkpoint_out=checkpoint,
        checkpoint_every_cases=100,
        checkpoint_min_interval_seconds=3600.0,
    )

    progress.checkpoint(
        processed_case_count=1,
        run_results=(_case_result(),),
        failures=(),
        seeded_source_count=1,
    )

    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["checkpoint_policy"]["checkpoint_reason"] == "completed"
