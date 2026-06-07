from memo_stack_server.top_evidence_policy import (
    FULL_PROVIDER_TOP_EVIDENCE_GENERATORS,
    FULL_PROVIDER_TOP_EVIDENCE_SUITES,
    PUBLIC_BENCHMARK_TOP_EVIDENCE_GENERATORS,
    top_evidence_provenance_summary,
    top_evidence_report_policy,
)


def _provenance(
    *,
    generated_by: str,
    suite: str,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "generated_by": generated_by,
        "suite": suite,
        "git": {"commit": "abc123", "dirty": False},
        "runtime": {"python_version": "3.13.5", "platform": "test-platform"},
    }


def test_top_evidence_policy_accepts_full_provider_aliases() -> None:
    for suite in FULL_PROVIDER_TOP_EVIDENCE_SUITES:
        policy = top_evidence_report_policy(suite)

        assert policy is not None
        assert policy.expected_generators == FULL_PROVIDER_TOP_EVIDENCE_GENERATORS
        assert policy.provenance_suites == FULL_PROVIDER_TOP_EVIDENCE_SUITES


def test_top_evidence_policy_summarizes_valid_public_benchmark_provenance() -> None:
    report = {
        "suite": "locomo",
        "provenance": _provenance(
            generated_by=next(iter(PUBLIC_BENCHMARK_TOP_EVIDENCE_GENERATORS)),
            suite="locomo",
        ),
    }

    summary = top_evidence_provenance_summary(report)

    assert summary["ok"] is True
    assert summary["failed_checks"] == []
    assert summary["git_commit_present"] is True
    assert summary["runtime_present"] is True


def test_top_evidence_policy_rejects_wrong_generator_and_missing_runtime() -> None:
    report = {
        "suite": "memory_mcp_agent_behavior",
        "provenance": {
            "schema_version": 1,
            "generated_by": "memo_stack_server.public_benchmark",
            "suite": "memory_mcp_agent_behavior",
            "git": {"commit": "abc123", "dirty": False},
        },
    }

    summary = top_evidence_provenance_summary(report)

    assert summary["ok"] is False
    assert summary["failed_checks"] == [
        "provenance_generator_allowed",
        "provenance_runtime_platform_present",
        "provenance_runtime_python_version_present",
    ]
