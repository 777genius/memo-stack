"""Shared types for the auto-memory eval suite."""

from __future__ import annotations

from dataclasses import dataclass

from infinity_context_core.domain.entities import MemoryKind, TrustLevel
from infinity_context_core.ports.auto_memory import CandidateOperation


@dataclass(frozen=True)
class AutoMemoryCaseResult:
    case_id: str
    category: str
    request_ok: bool
    expected_suggestion: bool
    suggestion_ok: bool
    unexpected_suggestion_count: int
    wrong_auto_apply_count: int
    active_fact_before_review_count: int
    prompt_injection_promoted_count: int
    secret_leakage_count: int
    duplicate_suggestion_count: int
    replay_duplicate_suggestion_count: int
    temporary_durable_promotion_count: int
    assistant_low_trust_violation_count: int
    candidate_limit_violation_count: int
    target_resolution_violation_count: int
    review_operation_violation_count: int
    failures: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class AutoMemoryExtractionCase:
    case_id: str
    category: str
    text: str
    expected_candidate_count: int
    expected_operations: tuple[CandidateOperation, ...] = ()
    expected_kinds: tuple[MemoryKind, ...] = ()
    expected_admission_outcomes: tuple[str, ...] = ()
    expected_categories: tuple[str | None, ...] = ()
    expected_ttl_policies: tuple[str | None, ...] = ()
    expected_target_hints: tuple[str | None, ...] = ()
    source_type: str = "manual_prompt"
    trust_level: TrustLevel = TrustLevel.MEDIUM
    actor_role: str | None = None
    source_authority: str | None = None


@dataclass(frozen=True)
class AutoMemoryExtractionCaseResult:
    case_id: str
    category: str
    extraction_ok: bool
    operation_ok: bool
    kind_ok: bool
    admission_ok: bool
    category_ok: bool
    ttl_ok: bool
    target_hint_ok: bool
    validation_ok: bool
    false_positive_count: int = 0
    false_negative_count: int = 0
    operation_mismatch_count: int = 0
    kind_mismatch_count: int = 0
    admission_mismatch_count: int = 0
    category_mismatch_count: int = 0
    ttl_mismatch_count: int = 0
    target_hint_mismatch_count: int = 0
    unsafe_admission_count: int = 0
    prompt_injection_admission_violation_count: int = 0
    assistant_admission_violation_count: int = 0
    validation_rejection_count: int = 0
    failures: tuple[dict[str, object], ...] = ()
