from __future__ import annotations

import json
from pathlib import Path

from memo_stack_server.public_benchmark import run_public_memory_benchmark


def test_public_memory_benchmark_runs_locomo_and_longmemeval_like_cases(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "public-benchmark.jsonl"
    report = tmp_path / "public-benchmark-report.json"
    rows = [
        {
            "benchmark": "locomo",
            "case_id": "locomo-single-hop",
            "question": "Where does Alice keep Kubernetes manifests?",
            "memories": [
                "Alice keeps Kubernetes manifests in helmfile overlays for project Atlas."
            ],
            "expected_terms": ["helmfile overlays"],
            "forbidden_terms": ["vault root token"],
        },
        {
            "benchmark": "longmemeval",
            "case_id": "longmem-document-deadline",
            "query": "What is the Project Falcon migration deadline?",
            "documents": [
                {
                    "title": "Falcon migration notes",
                    "text": "Project Falcon migration deadline is 2026-08-15.",
                }
            ],
            "answer": "2026-08-15",
        },
    ]
    dataset.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    result = run_public_memory_benchmark(
        dataset_path=dataset,
        report_out=report,
        min_accuracy=1.0,
    )

    assert result["ok"] is True
    assert result["suite"] == "public-memory-benchmark"
    assert result["metrics"]["case_count"] == 2
    assert result["metrics"]["accuracy"] == 1.0
    assert result["metrics"]["locomo_accuracy"] == 1.0
    assert result["metrics"]["longmemeval_accuracy"] == 1.0
    assert {item["name"] for item in result["benchmarks"]} == {"locomo", "longmemeval"}
    assert all(case["status"] == "ok" for case in result["cases"])
    assert report.exists()
    assert json.loads(report.read_text(encoding="utf-8"))["ok"] is True


def test_public_memory_benchmark_reports_missing_expected_terms(tmp_path: Path) -> None:
    dataset = tmp_path / "public-benchmark-failing.json"
    dataset.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "benchmark": "locomo",
                        "id": "missing-expected",
                        "question": "Where is the release checklist?",
                        "facts": ["The release checklist lives in Linear."],
                        "expected_terms": ["Notion"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = run_public_memory_benchmark(dataset_path=dataset, min_accuracy=1.0)

    assert result["ok"] is False
    assert result["metrics"]["accuracy"] == 0.0
    assert result["benchmarks"][0]["ok"] is False
    assert result["cases"][0]["missing_terms"] == ["Notion"]
    assert result["failures"][0]["reason"] == "missing_expected_terms"
