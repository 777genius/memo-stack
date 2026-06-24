from __future__ import annotations

import json

import infinity_context_server.public_benchmark as public_benchmark_module
import infinity_context_server.public_benchmark_environment as environment_module
from infinity_context_server.public_benchmark import run_public_memory_benchmark
from infinity_context_server.public_benchmark_environment import (
    BenchmarkEnvironmentPreflight,
    check_local_benchmark_environment,
)


def test_local_benchmark_environment_preflight_reports_missing_aiosqlite(
    monkeypatch,
) -> None:
    def import_module(name: str):
        if name == "aiosqlite":
            raise ModuleNotFoundError("aiosqlite")
        return object()

    monkeypatch.setattr(environment_module.importlib, "import_module", import_module)

    result = check_local_benchmark_environment()

    assert result.ok is False
    assert result.reason == "local_environment_aiosqlite_unavailable"
    assert result.diagnostics["database_url_scheme"] == "sqlite+aiosqlite"
    assert any(
        item["module"] == "aiosqlite" and item["available"] is False
        for item in result.diagnostics["module_checks"]
    )


def test_public_benchmark_returns_bounded_local_environment_failure(
    tmp_path,
    monkeypatch,
) -> None:
    dataset = tmp_path / "public-benchmark.jsonl"
    report_out = tmp_path / "report.json"
    progress_out = tmp_path / "progress.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "benchmark": "locomo",
                "case_id": "environment-preflight",
                "question": "Where is the marker?",
                "documents": [
                    {
                        "title": "Marker",
                        "text": "ENVIRONMENT_PREFLIGHT_MARKER is stored here.",
                    }
                ],
                "expected_terms": ["ENVIRONMENT_PREFLIGHT_MARKER"],
            }
        ),
        encoding="utf-8",
    )
    diagnostics = {
        "schema_version": "public-benchmark-local-environment-v1",
        "module_checks": (
            {
                "module": "aiosqlite",
                "available": False,
                "reason": "local_environment_aiosqlite_unavailable",
                "error_type": "ModuleNotFoundError",
            },
        ),
    }

    monkeypatch.setattr(
        public_benchmark_module,
        "check_local_benchmark_environment",
        lambda: BenchmarkEnvironmentPreflight(
            ok=False,
            reason="local_environment_aiosqlite_unavailable",
            diagnostics=diagnostics,
        ),
    )

    result = run_public_memory_benchmark(
        dataset_path=dataset,
        report_out=report_out,
        progress_out=progress_out,
        min_accuracy=1.0,
    )
    rendered = report_out.read_text(encoding="utf-8")
    progress_events = [
        json.loads(line) for line in progress_out.read_text(encoding="utf-8").splitlines()
    ]

    assert result["ok"] is False
    assert result["checks"]["local_environment_ready"] is False
    assert result["checks"]["auth_token_configured"] is True
    assert result["failures"] == [
        {
            "case_id": "suite_setup",
            "category": "setup",
            "reason": "local_environment_aiosqlite_unavailable",
        }
    ]
    assert progress_events[0]["event_type"] == "run_setup_failed"
    assert progress_events[0]["reason"] == "local_environment_aiosqlite_unavailable"
    assert progress_events[0]["total_case_count"] == 1
    assert "ENVIRONMENT_PREFLIGHT_MARKER" not in rendered
    assert "ENVIRONMENT_PREFLIGHT_MARKER" not in progress_out.read_text(encoding="utf-8")
    assert "ModuleNotFoundError" in rendered
