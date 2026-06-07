"""Official public memory benchmark canary orchestration.

This module owns the reusable public benchmark canary workflow. CLI scripts and
full-provider smoke tests call this package module instead of importing from
``scripts/`` so the benchmark evidence path stays testable and reusable.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from memo_stack_core.reporting import with_report_provenance

from memo_stack_server.public_benchmark import run_public_memory_benchmark

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PUBLIC_MEMORY_BENCHMARK_SUITE = "public-memory-benchmark"
LOCOMO_URL = "https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json"
LONGMEMEVAL_URL = (
    "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/"
    "longmemeval_s_cleaned.json"
)
DEFAULT_MAX_CASES = 2
DEFAULT_MIN_ACCURACY = 0.5
DEFAULT_TIMEOUT_SECONDS = 180


@dataclass(frozen=True)
class OfficialDataset:
    name: str
    url: str
    filename: str


OFFICIAL_DATASETS = {
    "locomo": OfficialDataset("locomo", LOCOMO_URL, "locomo10.json"),
    "longmemeval": OfficialDataset(
        "longmemeval",
        LONGMEMEVAL_URL,
        "longmemeval_s_cleaned.json",
    ),
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark",
        choices=("all", "locomo", "longmemeval"),
        default=os.getenv("MEMORY_PUBLIC_BENCHMARK_NAME", "all"),
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=int(os.getenv("MEMORY_PUBLIC_BENCHMARK_MAX_CASES", str(DEFAULT_MAX_CASES))),
    )
    parser.add_argument(
        "--min-accuracy",
        type=float,
        default=float(
            os.getenv("MEMORY_PUBLIC_BENCHMARK_MIN_ACCURACY", str(DEFAULT_MIN_ACCURACY))
        ),
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("MEMORY_PUBLIC_BENCHMARK_API_URL") or None,
    )
    parser.add_argument(
        "--auth-token",
        default=(
            os.getenv("MEMORY_PUBLIC_BENCHMARK_AUTH_TOKEN")
            or os.getenv("MEMORY_SERVICE_TOKEN")
            or None
        ),
    )
    parser.add_argument("--locomo-dataset", type=Path, default=None)
    parser.add_argument("--longmemeval-dataset", type=Path, default=None)
    parser.add_argument(
        "--download-timeout-seconds",
        type=float,
        default=float(
            os.getenv(
                "MEMORY_PUBLIC_BENCHMARK_DOWNLOAD_TIMEOUT_SECONDS",
                str(DEFAULT_TIMEOUT_SECONDS),
            )
        ),
    )
    parser.add_argument(
        "--report-out",
        type=Path,
        default=(
            Path(os.environ["MEMORY_PUBLIC_BENCHMARK_REPORT_OUT"])
            if os.getenv("MEMORY_PUBLIC_BENCHMARK_REPORT_OUT")
            else None
        ),
    )
    args = parser.parse_args(argv)
    result = run_official_public_benchmark_canary(
        benchmark=args.benchmark,
        max_cases=args.max_cases,
        min_accuracy=args.min_accuracy,
        api_url=args.api_url,
        auth_token=args.auth_token,
        locomo_dataset=args.locomo_dataset,
        longmemeval_dataset=args.longmemeval_dataset,
        download_timeout_seconds=args.download_timeout_seconds,
        report_out=args.report_out,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


def run_official_public_benchmark_canary(
    *,
    benchmark: str = "all",
    max_cases: int = DEFAULT_MAX_CASES,
    min_accuracy: float = DEFAULT_MIN_ACCURACY,
    api_url: str | None = None,
    auth_token: str | None = None,
    locomo_dataset: Path | None = None,
    longmemeval_dataset: Path | None = None,
    download_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    report_out: Path | None = None,
) -> dict[str, object]:
    if max_cases < 1:
        raise ValueError("max_cases must be greater than zero")
    selected = _selected_benchmarks(benchmark)
    run_id = f"official-public-{time.time_ns()}"
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="memo-official-public-benchmark-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        reports: list[dict[str, object]] = []
        for name in selected:
            dataset = _dataset_path(
                name=name,
                tmp_dir=tmp_path,
                locomo_dataset=locomo_dataset,
                longmemeval_dataset=longmemeval_dataset,
                timeout_seconds=download_timeout_seconds,
            )
            reports.append(
                run_public_memory_benchmark(
                    dataset_path=dataset,
                    api_url=api_url,
                    auth_token=auth_token,
                    benchmark=name,
                    max_cases=max_cases,
                    min_accuracy=min_accuracy,
                )
            )

    result = _merge_reports(
        reports=reports,
        benchmark=benchmark,
        max_cases=max_cases,
        min_accuracy=min_accuracy,
        api_url=api_url,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    result = with_report_provenance(
        result,
        generated_by="memo_stack_server.official_public_benchmark",
        run_id=run_id,
        cwd=PROJECT_ROOT,
    )
    _write_report(result, report_out)
    return result


def _selected_benchmarks(value: str) -> tuple[str, ...]:
    normalized = value.strip().lower()
    if normalized == "all":
        return ("locomo", "longmemeval")
    if normalized in OFFICIAL_DATASETS:
        return (normalized,)
    raise ValueError(f"Unsupported benchmark: {value}")


def _dataset_path(
    *,
    name: str,
    tmp_dir: Path,
    locomo_dataset: Path | None,
    longmemeval_dataset: Path | None,
    timeout_seconds: float,
) -> Path:
    override = locomo_dataset if name == "locomo" else longmemeval_dataset
    if override is not None:
        return override
    dataset = OFFICIAL_DATASETS[name]
    destination = tmp_dir / dataset.filename
    _download(dataset.url, destination, timeout_seconds=timeout_seconds)
    return destination


def _download(url: str, destination: Path, *, timeout_seconds: float) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "memo-stack-benchmark/1"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        destination.write_bytes(response.read())


def _merge_reports(
    *,
    reports: Sequence[Mapping[str, object]],
    benchmark: str,
    max_cases: int,
    min_accuracy: float,
    api_url: str | None,
    elapsed_ms: float,
) -> dict[str, object]:
    cases: list[object] = []
    benchmarks: list[object] = []
    failures: list[object] = []
    checks = {
        "official_sources_configured": True,
        "case_count": True,
        "minimum_accuracy_met": True,
        "no_request_failures": True,
    }
    metrics: dict[str, object] = {
        "benchmark_count": len(reports),
        "case_count": 0,
        "accuracy": 0.0,
    }
    ok = bool(reports)
    passed_cases = 0
    total_cases = 0
    for report in reports:
        ok = ok and report.get("ok") is True
        report_checks = report.get("checks")
        if isinstance(report_checks, Mapping):
            checks["minimum_accuracy_met"] = (
                checks["minimum_accuracy_met"]
                and report_checks.get("minimum_accuracy_met") is True
            )
            checks["no_request_failures"] = (
                checks["no_request_failures"]
                and report_checks.get("no_request_failures") is True
            )
        report_cases = report.get("cases")
        if isinstance(report_cases, list):
            cases.extend(report_cases)
            total_cases += len(report_cases)
            passed_cases += sum(
                1
                for item in report_cases
                if isinstance(item, Mapping) and item.get("status") == "ok"
            )
        report_benchmarks = report.get("benchmarks")
        if isinstance(report_benchmarks, list):
            benchmarks.extend(report_benchmarks)
        report_failures = report.get("failures")
        if isinstance(report_failures, list):
            failures.extend(report_failures)
        report_metrics = report.get("metrics")
        if isinstance(report_metrics, Mapping):
            for key, value in report_metrics.items():
                if key.endswith("_accuracy") or key.endswith("_case_count"):
                    metrics[key] = value
    metrics["case_count"] = total_cases
    metrics["accuracy"] = round(passed_cases / total_cases, 4) if total_cases else 0.0
    checks["case_count"] = total_cases > 0
    return {
        "suite": PUBLIC_MEMORY_BENCHMARK_SUITE,
        "status": "ok" if ok else "failed",
        "ok": ok,
        "benchmark_scope": "official_public_memory_retrieval_canary",
        "evaluation_mode": "retrieved_expected_terms",
        "source_urls": {
            name: OFFICIAL_DATASETS[name].url for name in _selected_benchmarks(benchmark)
        },
        "api_url": api_url,
        "max_cases_per_benchmark": max_cases,
        "min_accuracy": min_accuracy,
        "checks": checks,
        "metrics": metrics,
        "benchmarks": benchmarks,
        "cases": cases,
        "failures": failures,
        "elapsed_ms": elapsed_ms,
    }


def _write_report(result: dict[str, object], report_out: Path | None) -> None:
    if report_out is None:
        return
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
