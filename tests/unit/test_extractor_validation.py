from datetime import UTC, datetime

from memo_stack_core.application.extractor import validate_extractor_candidates
from memo_stack_core.domain.entities import Confidence, MemoryKind, SourceRef
from memo_stack_core.ports.auto_memory import MemoryCandidate


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


def _candidate(
    *,
    valid_from: datetime | None,
    valid_until: datetime | None,
    source_refs: tuple[SourceRef, ...] | None = None,
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
        valid_from=valid_from,
        valid_until=valid_until,
    )
