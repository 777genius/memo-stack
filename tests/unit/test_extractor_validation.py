from datetime import UTC, datetime

from memo_stack_core.application.extractor import validate_extractor_candidates
from memo_stack_core.domain.entities import Confidence, MemoryKind, SourceRef
from memo_stack_core.ports.auto_memory import CandidateOperation, MemoryCandidate


def test_extractor_validation_rejects_invalid_validity_window() -> None:
    result = validate_extractor_candidates(
        candidates=(
            _candidate(
                valid_from=datetime(2026, 1, 2, tzinfo=UTC),
                valid_until=datetime(2026, 1, 1, tzinfo=UTC),
            ),
        ),
        source_text="TEMPORAL_MARKER fact from source.",
    )

    assert result.candidates == ()
    assert result.rejected_codes == ("invalid_validity_window",)


def test_extractor_validation_rejects_ambiguous_datetime() -> None:
    result = validate_extractor_candidates(
        candidates=(
            _candidate(
                valid_from=datetime(2026, 1, 1),
                valid_until=datetime(2026, 1, 2, tzinfo=UTC),
            ),
        ),
        source_text="TEMPORAL_MARKER fact from source.",
    )

    assert result.candidates == ()
    assert result.rejected_codes == ("ambiguous_datetime",)


def test_extractor_validation_rejects_missing_source_refs() -> None:
    result = validate_extractor_candidates(
        candidates=(
            _candidate(
                valid_from=None,
                valid_until=None,
                source_refs=(),
            ),
        ),
        source_text="TEMPORAL_MARKER fact from source.",
    )

    assert result.candidates == ()
    assert result.rejected_codes == ("source_ref_required",)


def test_extractor_validation_rejects_source_refs_without_evidence_quote() -> None:
    result = validate_extractor_candidates(
        candidates=(
            _candidate(
                valid_from=None,
                valid_until=None,
                source_refs=(
                    SourceRef(
                        source_type="capture:hook",
                        source_id="cap_temporal",
                    ),
                ),
            ),
        ),
        source_text="TEMPORAL_MARKER fact from source.",
    )

    assert result.candidates == ()
    assert result.rejected_codes == ("evidence_quote_required",)


def test_extractor_validation_rejects_add_target_metadata() -> None:
    result = validate_extractor_candidates(
        candidates=(
            _candidate(
                valid_from=None,
                valid_until=None,
                operation=CandidateOperation.ADD,
                target_hint="old fact text",
            ),
        ),
        source_text="TEMPORAL_MARKER fact from source.",
    )

    assert result.candidates == ()
    assert result.rejected_codes == ("target_hint_not_allowed",)


def test_extractor_validation_rejects_review_target_fact_id() -> None:
    result = validate_extractor_candidates(
        candidates=(
            _candidate(
                valid_from=None,
                valid_until=None,
                operation=CandidateOperation.REVIEW,
                target_fact_id="fact_existing",
                target_fact_version=3,
            ),
        ),
        source_text="TEMPORAL_MARKER fact from source.",
    )

    assert result.candidates == ()
    assert result.rejected_codes == ("target_fact_not_allowed",)


def test_extractor_validation_allows_review_target_hint() -> None:
    result = validate_extractor_candidates(
        candidates=(
            _candidate(
                valid_from=None,
                valid_until=None,
                operation=CandidateOperation.REVIEW,
                target_hint="old fact text",
            ),
        ),
        source_text="TEMPORAL_MARKER fact from source.",
    )

    assert len(result.candidates) == 1
    assert result.rejected_codes == ()


def _candidate(
    *,
    valid_from: datetime | None,
    valid_until: datetime | None,
    source_refs: tuple[SourceRef, ...] | None = None,
    operation: CandidateOperation = CandidateOperation.ADD,
    target_fact_id: str | None = None,
    target_fact_version: int | None = None,
    target_hint: str | None = None,
) -> MemoryCandidate:
    return MemoryCandidate(
        text="TEMPORAL_MARKER fact from source.",
        kind=MemoryKind.NOTE,
        confidence=Confidence.MEDIUM,
        source_refs=source_refs
        if source_refs is not None
        else (
            SourceRef(
                source_type="capture:hook",
                source_id="cap_temporal",
                quote_preview="TEMPORAL_MARKER",
            ),
        ),
        safe_reason="test",
        operation_hint=operation,
        target_fact_id=target_fact_id,
        target_fact_version=target_fact_version,
        target_hint=target_hint,
        valid_from=valid_from,
        valid_until=valid_until,
    )
