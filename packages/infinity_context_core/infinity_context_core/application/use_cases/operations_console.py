"""Operational read model for memory ingestion and link review."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from infinity_context_core.application.dto import (
    MemoryOperationsConsoleQuery,
    MemoryOperationsConsoleResult,
)
from infinity_context_core.domain.assets import MemoryContextLinkSuggestion
from infinity_context_core.domain.extraction import AssetExtractionJob, AssetExtractionStatus
from infinity_context_core.ports.clock import ClockPort
from infinity_context_core.ports.unit_of_work import UnitOfWorkFactoryPort

_RETRYABLE_EXTRACTION_STATUSES = {
    AssetExtractionStatus.FAILED.value,
    AssetExtractionStatus.UNSUPPORTED.value,
    AssetExtractionStatus.CANCELED.value,
    AssetExtractionStatus.STALE.value,
}


class BuildMemoryOperationsConsoleUseCase:
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactoryPort,
        clock: ClockPort,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(
        self,
        query: MemoryOperationsConsoleQuery,
    ) -> MemoryOperationsConsoleResult:
        limit = max(1, min(query.limit, 200))
        thread_id = str(query.thread_id) if query.thread_id else None
        async with self._uow_factory() as uow:
            extraction_counts = await uow.asset_extractions.count_by_status_for_scope(
                space_id=str(query.space_id),
                memory_scope_id=str(query.memory_scope_id),
                thread_id=thread_id,
            )
            link_suggestion_counts = await uow.context_link_suggestions.count_by_status_for_scope(
                space_id=str(query.space_id),
                memory_scope_id=str(query.memory_scope_id),
            )
            extraction_jobs = await uow.asset_extractions.list_for_scope(
                space_id=str(query.space_id),
                memory_scope_id=str(query.memory_scope_id),
                thread_id=thread_id,
                status=None,
                limit=limit,
            )
            suggestions = await uow.context_link_suggestions.list_for_scope(
                space_id=str(query.space_id),
                memory_scope_id=str(query.memory_scope_id),
                status=None,
                limit=limit,
            )

        diagnostics = _diagnostics(
            extraction_status_counts=extraction_counts,
            link_suggestion_status_counts=link_suggestion_counts,
            extraction_jobs=extraction_jobs,
            suggestions=suggestions,
            extraction_job_count=len(extraction_jobs),
            suggestion_count=len(suggestions),
        )
        return MemoryOperationsConsoleResult(
            generated_at=self._clock.now(),
            scope={
                "space_id": str(query.space_id),
                "memory_scope_id": str(query.memory_scope_id),
                "thread_id": thread_id,
            },
            extraction_status_counts=extraction_counts,
            link_suggestion_status_counts=link_suggestion_counts,
            extraction_jobs=tuple(extraction_jobs),
            context_link_suggestions=tuple(suggestions),
            diagnostics=diagnostics,
        )


def _diagnostics(
    *,
    extraction_status_counts: dict[str, int],
    link_suggestion_status_counts: dict[str, int],
    extraction_jobs: Iterable[AssetExtractionJob],
    suggestions: Iterable[MemoryContextLinkSuggestion],
    extraction_job_count: int,
    suggestion_count: int,
) -> dict[str, object]:
    extraction_job_items = tuple(extraction_jobs)
    suggestion_items = tuple(suggestions)
    retryable_count = sum(
        extraction_status_counts.get(status, 0) for status in _RETRYABLE_EXTRACTION_STATUSES
    )
    active_count = sum(
        extraction_status_counts.get(status, 0)
        for status in (AssetExtractionStatus.PENDING.value, AssetExtractionStatus.RUNNING.value)
    )
    pending_suggestions = link_suggestion_status_counts.get("pending", 0)
    reviewed_suggestions = sum(
        link_suggestion_status_counts.get(status, 0) for status in ("approved", "rejected")
    )
    return {
        "console_version": "memory-operations-console-v1",
        "extraction_active_count": active_count,
        "extraction_retryable_count": retryable_count,
        "extraction_returned_count": extraction_job_count,
        "extraction_attempt_count_max": max(
            (job.attempt_count for job in extraction_job_items),
            default=0,
        ),
        "extraction_cancellation_requested_count": sum(
            1 for job in extraction_job_items if job.cancellation_requested_at is not None
        ),
        "extraction_degraded_fallback_count": sum(
            1 for job in extraction_job_items if job.metadata.get("degraded_fallback") is True
        ),
        "extraction_provider_retryable_count": sum(
            1 for job in extraction_job_items if _metadata_bool_suffix(job.metadata, "retryable")
        ),
        "extraction_timeout_count": sum(
            1 for job in extraction_job_items if _safe_text(job.safe_error_code).endswith("timeout")
        ),
        "extraction_retry_disposition_counts": _counts(
            job.retry_disposition.value if job.retry_disposition else "none"
            for job in extraction_job_items
        ),
        "extraction_error_code_counts": _counts(
            _safe_text(job.safe_error_code) for job in extraction_job_items if job.safe_error_code
        ),
        "extraction_parser_counts": _counts(
            _safe_text(job.parser_name) for job in extraction_job_items if job.parser_name
        ),
        "extraction_content_type_counts": _counts(
            _metadata_text(job.metadata, "normalized_content_type")
            or _metadata_text(job.metadata, "detected_content_type")
            for job in extraction_job_items
            if _metadata_text(job.metadata, "normalized_content_type")
            or _metadata_text(job.metadata, "detected_content_type")
        ),
        "link_suggestion_pending_count": pending_suggestions,
        "link_suggestion_reviewed_count": reviewed_suggestions,
        "link_suggestion_returned_count": suggestion_count,
        "link_suggestion_target_type_counts": _counts(
            suggestion.target_type for suggestion in suggestion_items
        ),
        "link_suggestion_relation_type_counts": _counts(
            suggestion.relation_type for suggestion in suggestion_items
        ),
        "link_suggestion_review_gate_counts": _counts(
            _metadata_text(suggestion.metadata, "review_gate")
            for suggestion in suggestion_items
            if _metadata_text(suggestion.metadata, "review_gate")
        ),
        "link_suggestion_evidence_modality_counts": _list_value_counts(
            suggestion.metadata.get("evidence_modalities") for suggestion in suggestion_items
        ),
        "link_suggestion_auto_approve_eligible_count": sum(
            1
            for suggestion in suggestion_items
            if suggestion.metadata.get("auto_approve_eligible") is True
        ),
        "link_suggestion_prompt_injection_review_count": sum(
            1
            for suggestion in suggestion_items
            if suggestion.metadata.get("review_gate_reason") == "prompt_injection_evidence"
        ),
        "link_suggestion_bbox_evidence_count": sum(
            1 for suggestion in suggestion_items if suggestion.metadata.get("evidence_has_bbox_ref")
        ),
        "link_suggestion_page_evidence_count": sum(
            1 for suggestion in suggestion_items if suggestion.metadata.get("evidence_has_page_ref")
        ),
        "link_suggestion_time_range_evidence_count": sum(
            1
            for suggestion in suggestion_items
            if suggestion.metadata.get("evidence_has_time_range_ref")
        ),
        "link_suggestion_explainability": {
            "stored_fields": (
                "reason",
                "score",
                "confidence",
                "reviewed_at",
                "review_reason",
                "metadata.target_label",
                "metadata.target_preview",
                "metadata.target_tier",
                "metadata.resolver_version",
                "metadata.reason_codes",
                "metadata.matched_terms",
                "metadata.evidence_modalities",
                "metadata.evidence_kinds",
                "metadata.evidence_refs",
                "metadata.review_gate",
                "metadata.review_gate_reason",
            ),
            "no_suggestion_note": (
                "Suggestions are stored only when persisted link discovery finds visible "
                "same-scope candidates for a capture or asset. Empty results usually mean "
                "no visible candidate matched the source text strongly enough, the source "
                "was not persisted, or an active link already exists."
            ),
            "no_suggestion_reasons": (
                {
                    "code": "no_visible_same_scope_candidate",
                    "label": (
                        "No visible same-scope memory matched the source text strongly enough."
                    ),
                },
                {
                    "code": "source_not_persisted",
                    "label": (
                        "The source capture or asset may not be persisted with a stable id yet."
                    ),
                },
                {
                    "code": "already_linked",
                    "label": "An active link may already exist, so duplicates are hidden.",
                },
                {
                    "code": "not_pending",
                    "label": (
                        "Suggestions that were approved, rejected, expired, or "
                        "superseded are outside the pending queue."
                    ),
                },
            ),
        },
        "extraction_observability": {
            "stored_fields": (
                "status",
                "attempt_count",
                "safe_error_code",
                "safe_error_message",
                "progress",
                "execution.lease_owner",
                "execution.heartbeat_at",
                "execution.retry_after_at",
                "execution.retry_disposition",
                "execution.cancellation_requested_at",
                "metadata.cancellation_status",
                "metadata.cancellation_message",
                "metadata.normalized_content_type",
                "metadata.detected_content_type",
                "metadata.degraded_fallback",
                "metadata.*_provider_retryable",
            )
        },
    }


def _counts(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for raw in values:
        value = _safe_text(raw)
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _list_value_counts(values: Iterable[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for raw in values:
        if not isinstance(raw, (list, tuple)):
            continue
        for item in raw:
            value = _safe_text(item)
            if not value:
                continue
            counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _metadata_text(metadata: Mapping[str, object], key: str) -> str:
    return _safe_text(metadata.get(key))


def _metadata_bool_suffix(metadata: Mapping[str, object], suffix: str) -> bool:
    return any(str(key).endswith(suffix) and value is True for key, value in metadata.items())


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()[:160]
