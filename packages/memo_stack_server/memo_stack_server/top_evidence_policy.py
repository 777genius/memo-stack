"""Shared policy for publishable top-evidence reports."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from memo_stack_core.application.sensitive_text import contains_sensitive_text

TOP_EVIDENCE_PROVENANCE_CHECKS = (
    "provenance_present",
    "provenance_schema_version_1",
    "provenance_suite_allowed",
    "provenance_generator_allowed",
    "provenance_git_commit_present",
    "provenance_dirty_state_present",
    "provenance_git_clean_or_dirty_allowed",
    "provenance_runtime_python_version_present",
    "provenance_runtime_platform_present",
)
TOP_EVIDENCE_SAFETY_CHECKS = ("no_sensitive_text", "no_local_home_paths")
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
AGENT_LIVE_SMOKE_TOP_EVIDENCE_GENERATORS = frozenset(
    {"scripts/agent_install_verification.py"}
)
AGENT_LIVE_SMOKE_TOP_EVIDENCE_SUITES = frozenset(
    {"memo-stack-agent-live-smoke", "memory-agent-live-smoke"}
)
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
_SAFE_PATH_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,63}$")
_LOCAL_HOME_PATH_PATTERNS = (
    re.compile(r"(?<![:A-Za-z0-9_])/(?:Users|home)/[^/\s]+(?:/[^\s'\"<>]+)*"),
    re.compile(r"\b[A-Za-z]:\\Users\\[^\\\s]+(?:\\[^\s'\"<>]+)*"),
)
_MAX_SENSITIVE_PATH_SAMPLES = 10


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
            expected_generators=AGENT_LIVE_SMOKE_TOP_EVIDENCE_GENERATORS,
            provenance_suites=AGENT_LIVE_SMOKE_TOP_EVIDENCE_SUITES,
        )
        for suite in AGENT_LIVE_SMOKE_TOP_EVIDENCE_SUITES
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
    allow_dirty_top_evidence: bool = False,
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
        "provenance_git_clean_or_dirty_allowed": isinstance(dirty, bool)
        and (dirty is False or allow_dirty_top_evidence),
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


def top_evidence_safety_summary(result: Mapping[str, object]) -> dict[str, object]:
    sensitive_path_samples: list[str] = []
    local_path_samples: list[str] = []
    sensitive_path_count = _collect_sensitive_paths(
        result,
        "$",
        sensitive_path_samples,
    )
    local_path_count = _collect_local_home_paths(result, "$", local_path_samples)
    checks = {
        "no_sensitive_text": sensitive_path_count == 0,
        "no_local_home_paths": local_path_count == 0,
    }
    failed_checks = sorted(check for check, ok in checks.items() if ok is not True)
    return {
        "ok": not failed_checks,
        "checks": checks,
        "failed_checks": failed_checks,
        "sensitive_path_count": sensitive_path_count,
        "sensitive_paths": sensitive_path_samples,
        "local_path_count": local_path_count,
        "local_paths": local_path_samples,
    }


def _collect_sensitive_paths(
    value: object,
    path: str,
    samples: list[str],
) -> int:
    if isinstance(value, str):
        return _record_sensitive_path(path, samples) if contains_sensitive_text(value) else 0
    if isinstance(value, Mapping):
        total = 0
        for key, child in value.items():
            child_path = f"{path}{_safe_path_key(key)}"
            if isinstance(key, str) and contains_sensitive_text(key):
                total += _record_sensitive_path(f"{path}.[sensitive-key]", samples)
            total += _collect_sensitive_paths(child, child_path, samples)
        return total
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        total = 0
        for index, child in enumerate(value):
            total += _collect_sensitive_paths(child, f"{path}[{index}]", samples)
        return total
    return 0


def _collect_local_home_paths(
    value: object,
    path: str,
    samples: list[str],
) -> int:
    if isinstance(value, str):
        return _record_sensitive_path(path, samples) if _has_local_home_path(value) else 0
    if isinstance(value, Mapping):
        total = 0
        for key, child in value.items():
            child_path = f"{path}{_safe_path_key(key)}"
            if isinstance(key, str) and _has_local_home_path(key):
                total += _record_sensitive_path(f"{path}.[local-home-path-key]", samples)
            total += _collect_local_home_paths(child, child_path, samples)
        return total
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        total = 0
        for index, child in enumerate(value):
            total += _collect_local_home_paths(child, f"{path}[{index}]", samples)
        return total
    return 0


def _has_local_home_path(value: str) -> bool:
    return any(pattern.search(value) for pattern in _LOCAL_HOME_PATH_PATTERNS)


def _record_sensitive_path(path: str, samples: list[str]) -> int:
    if len(samples) < _MAX_SENSITIVE_PATH_SAMPLES:
        samples.append(path)
    return 1


def _safe_path_key(key: object) -> str:
    if not isinstance(key, str):
        return ".[key]"
    if contains_sensitive_text(key):
        return ".[sensitive-key]"
    if _SAFE_PATH_KEY_PATTERN.fullmatch(key):
        return f".{key}"
    return ".[key]"
