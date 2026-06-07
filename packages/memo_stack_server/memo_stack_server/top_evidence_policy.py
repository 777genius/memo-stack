"""Shared policy for publishable top-evidence reports."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

TOP_EVIDENCE_PROVENANCE_CHECKS = (
    "provenance_present",
    "provenance_schema_version_1",
    "provenance_suite_allowed",
    "provenance_generator_allowed",
    "provenance_git_commit_present",
    "provenance_dirty_state_present",
    "provenance_runtime_python_version_present",
    "provenance_runtime_platform_present",
)
FULL_PROVIDER_TOP_EVIDENCE_GENERATORS = frozenset({"scripts/clean_full_smoke.py"})
FULL_PROVIDER_TOP_EVIDENCE_SUITES = frozenset(
    {
        "memo-stack-full-provider-canary",
        "memo_stack_full_provider_canary",
        "memo-stack-clean-full-smoke",
        "clean-full-smoke",
        "clean_full_smoke",
    }
)
AGENT_BEHAVIOR_TOP_EVIDENCE_GENERATORS = frozenset(
    {"memo_stack_mcp.agent_behavior_bench"}
)
AGENT_BEHAVIOR_TOP_EVIDENCE_SUITES = frozenset({"memory_mcp_agent_behavior"})
PUBLIC_BENCHMARK_TOP_EVIDENCE_GENERATORS = frozenset(
    {
        "memo_stack_server.official_public_benchmark",
        "memo_stack_server.public_benchmark",
    }
)
PUBLIC_BENCHMARK_TOP_EVIDENCE_SUITES = frozenset(
    {
        "public-memory-benchmark",
        "public_memory_benchmark",
        "memory-public-benchmarks",
        "locomo",
        "longmemeval",
    }
)
FULL_PROVIDER_NESTED_TOP_EVIDENCE_KEYS = ("agent_behavior", "public_benchmark")


@dataclass(frozen=True)
class TopEvidenceReportPolicy:
    expected_generators: frozenset[str]
    provenance_suites: frozenset[str]


TOP_EVIDENCE_REPORT_POLICIES = {
    **{
        suite: TopEvidenceReportPolicy(
            expected_generators=FULL_PROVIDER_TOP_EVIDENCE_GENERATORS,
            provenance_suites=FULL_PROVIDER_TOP_EVIDENCE_SUITES,
        )
        for suite in FULL_PROVIDER_TOP_EVIDENCE_SUITES
    },
    **{
        suite: TopEvidenceReportPolicy(
            expected_generators=AGENT_BEHAVIOR_TOP_EVIDENCE_GENERATORS,
            provenance_suites=AGENT_BEHAVIOR_TOP_EVIDENCE_SUITES,
        )
        for suite in AGENT_BEHAVIOR_TOP_EVIDENCE_SUITES
    },
    **{
        suite: TopEvidenceReportPolicy(
            expected_generators=PUBLIC_BENCHMARK_TOP_EVIDENCE_GENERATORS,
            provenance_suites=PUBLIC_BENCHMARK_TOP_EVIDENCE_SUITES,
        )
        for suite in PUBLIC_BENCHMARK_TOP_EVIDENCE_SUITES
    },
}


def top_evidence_report_policy(suite: object) -> TopEvidenceReportPolicy | None:
    if not isinstance(suite, str):
        return None
    return TOP_EVIDENCE_REPORT_POLICIES.get(suite)


def top_evidence_provenance_summary(
    result: Mapping[str, object],
    *,
    policy: TopEvidenceReportPolicy | None = None,
) -> dict[str, object]:
    resolved_policy = policy or top_evidence_report_policy(result.get("suite"))
    expected_generators = (
        resolved_policy.expected_generators if resolved_policy is not None else frozenset()
    )
    provenance_suites = (
        resolved_policy.provenance_suites if resolved_policy is not None else frozenset()
    )
    provenance = result.get("provenance")
    provenance_map = provenance if isinstance(provenance, Mapping) else {}
    git = provenance_map.get("git")
    git_map = git if isinstance(git, Mapping) else {}
    runtime = provenance_map.get("runtime")
    runtime_map = runtime if isinstance(runtime, Mapping) else {}
    generated_by = provenance_map.get("generated_by")
    suite = provenance_map.get("suite")
    commit = git_map.get("commit")
    dirty = git_map.get("dirty")
    python_version = runtime_map.get("python_version")
    runtime_platform = runtime_map.get("platform")
    checks = {
        "provenance_present": bool(provenance_map),
        "provenance_schema_version_1": provenance_map.get("schema_version") == 1,
        "provenance_suite_allowed": suite in provenance_suites,
        "provenance_generator_allowed": generated_by in expected_generators,
        "provenance_git_commit_present": isinstance(commit, str) and bool(commit),
        "provenance_dirty_state_present": isinstance(dirty, bool),
        "provenance_runtime_python_version_present": (
            isinstance(python_version, str) and bool(python_version)
        ),
        "provenance_runtime_platform_present": (
            isinstance(runtime_platform, str) and bool(runtime_platform)
        ),
    }
    failed_checks = sorted(check for check, ok in checks.items() if ok is not True)
    return {
        "ok": not failed_checks,
        "checks": checks,
        "failed_checks": failed_checks,
        "generated_by": generated_by if isinstance(generated_by, str) else None,
        "suite": suite if isinstance(suite, str) else None,
        "git_commit_present": checks["provenance_git_commit_present"],
        "dirty": dirty if isinstance(dirty, bool) else None,
        "runtime_present": (
            checks["provenance_runtime_python_version_present"]
            and checks["provenance_runtime_platform_present"]
        ),
    }
