"""Fast deterministic canary for semantic retrieval false positives."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from infinity_context_core.application.context_collectors import (
    _bounded_derived_retrieval_queries,
)
from infinity_context_core.application.context_inference_evidence import (
    inference_evidence_rerank_signal,
)
from infinity_context_core.application.context_query_expansion import (
    build_query_expansion_plan,
)
from infinity_context_core.application.context_ranking import best_query_relevance

from infinity_context_server.eval_common import _git_report, _write_redacted_report
from infinity_context_server.eval_constants import SEMANTIC_RETRIEVAL_CANARY_SUITE


@dataclass(frozen=True)
class _TextExpectation:
    text: str
    allowed_reasons: frozenset[str]
    forbidden_reasons: frozenset[str] = frozenset()


@dataclass(frozen=True)
class _PlanCanaryCase:
    case_id: str
    category: str
    query: str
    required_bounded_reasons: frozenset[str]
    forbidden_bounded_reasons: frozenset[str] = frozenset()
    text_expectations: tuple[_TextExpectation, ...] = ()


@dataclass(frozen=True)
class _SignalCanaryCase:
    case_id: str
    category: str
    query: str
    text: str
    expected_reason: str
    expect_boost: bool = False
    expect_penalty: bool = False


def run_semantic_retrieval_canary(*, report_out: Path | None = None) -> dict[str, object]:
    """Run cheap retrieval/rerank guards for known semantic false-positive classes."""

    plan_results = tuple(_run_plan_case(case) for case in _plan_cases())
    signal_results = tuple(_run_signal_case(case) for case in _signal_cases())
    cases = (*plan_results, *signal_results)
    failures = tuple(failure for case in cases for failure in _case_failures(case))
    metrics = {
        "case_count": len(cases),
        "passed_case_count": sum(1 for case in cases if case["ok"] is True),
        "failed_case_count": len(failures),
        "plan_case_count": len(plan_results),
        "signal_case_count": len(signal_results),
    }
    gates = {
        "all_cases_passed": not failures,
        "case_count": len(cases) >= 7,
    }
    result = {
        "suite": SEMANTIC_RETRIEVAL_CANARY_SUITE,
        "status": "passed" if all(gates.values()) else "failed",
        "ok": all(gates.values()),
        "metrics": metrics,
        "gates": gates,
        "cases": list(cases),
        "failures": list(failures),
        "git": _git_report(),
    }
    _write_redacted_report(result, report_out)
    return result


def _plan_cases() -> tuple[_PlanCanaryCase, ...]:
    return (
        _PlanCanaryCase(
            case_id="membership_self_identification_beats_ally_support",
            category="community_membership",
            query="Would Melanie be considered a member of the LGBTQ community?",
            required_bounded_reasons=frozenset(
                {
                    "community_membership_bridge",
                    "community_membership_support_bridge",
                    "decomposition_community_membership_evidence",
                }
            ),
            text_expectations=(
                _TextExpectation(
                    text=(
                        "Melanie identifies as part of the LGBTQ community and joined "
                        "the pride group."
                    ),
                    allowed_reasons=frozenset(
                        {
                            "community_membership_bridge",
                            "decomposition_community_membership_evidence",
                        }
                    ),
                ),
                _TextExpectation(
                    text=(
                        "Melanie is supportive of Caroline and encourages the LGBTQ "
                        "community as an ally."
                    ),
                    allowed_reasons=frozenset({"community_membership_support_bridge"}),
                    forbidden_reasons=frozenset(
                        {
                            "community_membership_bridge",
                            "decomposition_community_membership_evidence",
                        }
                    ),
                ),
            ),
        ),
        _PlanCanaryCase(
            case_id="ally_support_does_not_use_subject_identity_noise",
            category="ally_support",
            query="Would Melanie be considered an ally to the transgender community?",
            required_bounded_reasons=frozenset(
                {
                    "ally_support_bridge",
                    "decomposition_ally_support_evidence",
                    "decomposition_inference_support",
                }
            ),
            forbidden_bounded_reasons=frozenset(
                {
                    "identity_bridge",
                    "decomposition_identity_attribute",
                }
            ),
            text_expectations=(
                _TextExpectation(
                    text=(
                        "Melanie used supportive and encouraging kind words about "
                        "Caroline and accepted her transgender journey."
                    ),
                    allowed_reasons=frozenset(
                        {"ally_support_bridge", "decomposition_ally_support_evidence"}
                    ),
                ),
                _TextExpectation(
                    text=(
                        "Melanie shared her pronouns and described her own gender "
                        "identity as a trans woman."
                    ),
                    allowed_reasons=frozenset({"identity_bridge"}),
                    forbidden_reasons=frozenset(
                        {"ally_support_bridge", "decomposition_ally_support_evidence"}
                    ),
                ),
            ),
        ),
        _PlanCanaryCase(
            case_id="relative_time_message_query_keeps_conversation_recency",
            category="relative_time",
            query="What did Alex tell me an hour ago?",
            required_bounded_reasons=frozenset(
                {
                    "decomposition_relative_time",
                    "decomposition_conversation_recency",
                }
            ),
            text_expectations=(
                _TextExpectation(
                    text=(
                        "Call transcript from an hour ago: Alex told me the Atlas "
                        "budget decision."
                    ),
                    allowed_reasons=frozenset(
                        {
                            "decomposition_conversation_recency",
                            "decomposition_relative_time",
                        }
                    ),
                ),
                _TextExpectation(
                    text="Last week Alex told me about a different Atlas topic.",
                    allowed_reasons=frozenset(
                        {
                            "decomposition_event_context",
                            "decomposition_action_role",
                            "original_query",
                        }
                    ),
                    forbidden_reasons=frozenset({"decomposition_conversation_recency"}),
                ),
            ),
        ),
    )


def _signal_cases() -> tuple[_SignalCanaryCase, ...]:
    return (
        _SignalCanaryCase(
            case_id="religious_church_evidence_boosted",
            category="religious_inference",
            query="Would Caroline be considered religious?",
            text="Caroline made stained glass artwork for a local church.",
            expected_reason="inference_religious_fit_evidence",
            expect_boost=True,
        ),
        _SignalCanaryCase(
            case_id="religious_contrast_context_bounded",
            category="religious_inference",
            query="Would Caroline be considered religious?",
            text=(
                "Caroline said religious conservatives made her feel unwelcoming "
                "during her transgender journey."
            ),
            expected_reason="inference_religious_contrast_evidence",
            expect_penalty=True,
        ),
        _SignalCanaryCase(
            case_id="membership_self_identification_boosted",
            category="community_membership",
            query="Would Melanie be considered a member of the LGBTQ community?",
            text=(
                "Melanie identifies as part of the LGBTQ community and joined the "
                "pride support group."
            ),
            expected_reason="inference_community_membership_evidence",
            expect_boost=True,
        ),
        _SignalCanaryCase(
            case_id="membership_ally_only_penalized",
            category="community_membership",
            query="Would Melanie be considered a member of the LGBTQ community?",
            text=(
                "Melanie is supportive of Caroline and encourages the LGBTQ community "
                "as an ally."
            ),
            expected_reason="inference_community_membership_ally_noise",
            expect_penalty=True,
        ),
    )


def _run_plan_case(case: _PlanCanaryCase) -> dict[str, object]:
    plan = build_query_expansion_plan(case.query)
    bounded_reasons = tuple(
        query.reason
        for query in _bounded_derived_retrieval_queries(plan, fallback=case.query, limit=6)
    )
    all_reasons = tuple(query.reason for query in plan.retrieval_queries)
    text_checks = tuple(
        _run_text_expectation(plan, expectation)
        for expectation in case.text_expectations
    )
    missing_required = tuple(
        reason for reason in sorted(case.required_bounded_reasons) if reason not in bounded_reasons
    )
    forbidden_present = tuple(
        reason for reason in sorted(case.forbidden_bounded_reasons) if reason in bounded_reasons
    )
    failures = (
        *_failures_for_missing_reasons(missing_required),
        *_failures_for_forbidden_reasons(forbidden_present),
        *(failure for check in text_checks for failure in check["failures"]),
    )
    return {
        "case_id": case.case_id,
        "category": case.category,
        "type": "query_plan",
        "ok": not failures,
        "query": case.query,
        "bounded_reasons": list(bounded_reasons),
        "all_reasons": list(all_reasons),
        "text_checks": list(text_checks),
        "failures": list(failures),
    }


def _run_text_expectation(plan, expectation: _TextExpectation) -> dict[str, object]:
    _, reason, relevance = best_query_relevance(plan, text=expectation.text)
    failures: list[dict[str, object]] = []
    if reason not in expectation.allowed_reasons:
        failures.append(
            {
                "reason": "unexpected_best_query_reason",
                "expected_any": sorted(expectation.allowed_reasons),
                "actual": reason,
            }
        )
    if reason in expectation.forbidden_reasons:
        failures.append(
            {
                "reason": "forbidden_best_query_reason",
                "forbidden": sorted(expectation.forbidden_reasons),
                "actual": reason,
            }
        )
    return {
        "best_reason": reason,
        "distinctive_term_hits": relevance.distinctive_term_hits,
        "unique_term_hits": relevance.unique_term_hits,
        "failures": failures,
    }


def _run_signal_case(case: _SignalCanaryCase) -> dict[str, object]:
    signal = inference_evidence_rerank_signal(query=case.query, text=case.text)
    failures: list[dict[str, object]] = []
    if signal.reason != case.expected_reason:
        failures.append(
            {
                "reason": "unexpected_signal_reason",
                "expected": case.expected_reason,
                "actual": signal.reason,
            }
        )
    if case.expect_boost and signal.boost <= 0:
        failures.append({"reason": "expected_positive_boost", "actual": signal.boost})
    if case.expect_penalty and signal.penalty <= 0:
        failures.append({"reason": "expected_positive_penalty", "actual": signal.penalty})
    return {
        "case_id": case.case_id,
        "category": case.category,
        "type": "rerank_signal",
        "ok": not failures,
        "query": case.query,
        "signal_reason": signal.reason,
        "boost": signal.boost,
        "penalty": signal.penalty,
        "failures": failures,
    }


def _failures_for_missing_reasons(reasons: Iterable[str]) -> tuple[dict[str, object], ...]:
    return tuple({"reason": "missing_bounded_reason", "missing": reason} for reason in reasons)


def _failures_for_forbidden_reasons(reasons: Iterable[str]) -> tuple[dict[str, object], ...]:
    return tuple({"reason": "forbidden_bounded_reason", "forbidden": reason} for reason in reasons)


def _case_failures(case: dict[str, object]) -> tuple[dict[str, object], ...]:
    failures = case.get("failures")
    if not isinstance(failures, list):
        return ()
    return tuple(
        {
            "case_id": str(case.get("case_id", "")),
            "category": str(case.get("category", "")),
            **failure,
        }
        for failure in failures
        if isinstance(failure, dict)
    )
