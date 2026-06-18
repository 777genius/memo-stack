from datetime import UTC, datetime

from memo_stack_core.domain.entities import (
    Confidence,
    MemoryAnchor,
    MemoryAnchorId,
    MemoryAnchorKind,
    MemoryScopeId,
    SourceRef,
    SpaceId,
)


def test_anchor_audit_reasons_redact_obvious_secret_markers() -> None:
    now = datetime(2026, 6, 17, tzinfo=UTC)
    target_observed_at = datetime(2026, 6, 1, tzinfo=UTC)
    source_observed_at = datetime(2026, 6, 10, tzinfo=UTC)
    target_valid_from = datetime(2026, 6, 1, tzinfo=UTC)
    target_valid_to = datetime(2026, 6, 30, tzinfo=UTC)
    source_valid_from = datetime(2026, 5, 1, tzinfo=UTC)
    source_valid_to = datetime(2026, 6, 15, tzinfo=UTC)
    target = _anchor(
        "anchor_target",
        label="Acme",
        confidence=Confidence.MEDIUM,
        evidence_refs=(SourceRef(source_type="manual", source_id="target-evidence"),),
        now=now,
        observed_at=target_observed_at,
        valid_from=target_valid_from,
        valid_to=target_valid_to,
    )
    source = _anchor(
        "anchor_source",
        label="Acme Research",
        confidence=Confidence.HIGH,
        evidence_refs=(SourceRef(source_type="manual", source_id="source-evidence"),),
        now=now,
        observed_at=source_observed_at,
        valid_from=source_valid_from,
        valid_to=source_valid_to,
    )

    merged = target.merge_source(
        source=source,
        reason="Authorization: Bearer sk-proj-anchor-secret-value",
        now=now,
    )
    deleted = merged.delete(reason="token sk-proj-delete-secret-value", now=now)
    split_source = merged.remove_alias(
        alias="Acme Research",
        reason="private_key sk-proj-split-secret-value",
        now=now,
    )
    merged_source = source.mark_merged_into(
        target_anchor_id=MemoryAnchorId("anchor_target"),
        reason="secret sk-proj-merge-secret-value",
        now=now,
    )

    assert merged.confidence == Confidence.HIGH
    assert {ref.source_id for ref in merged.evidence_refs} == {
        "target-evidence",
        "source-evidence",
    }
    assert merged.observed_at == source_observed_at
    assert merged.valid_from == source_valid_from
    assert merged.valid_to == target_valid_to
    assert merged.metadata["merge_events"][-1]["source_label"] == "Acme Research"
    assert merged.metadata["merge_events"][-1]["reason"] == "[redacted]"
    assert deleted.metadata["delete_reason"] == "[redacted]"
    assert split_source.metadata["split_events"][-1]["reason"] == "[redacted]"
    assert merged_source.metadata["merge_reason"] == "[redacted]"


def _anchor(
    anchor_id: str,
    *,
    label: str,
    confidence: Confidence,
    evidence_refs: tuple[SourceRef, ...],
    now: datetime,
    observed_at: datetime | None = None,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
) -> MemoryAnchor:
    return MemoryAnchor.create(
        anchor_id=MemoryAnchorId(anchor_id),
        space_id=SpaceId("space_1"),
        memory_scope_id=MemoryScopeId("memory_scope_1"),
        kind=MemoryAnchorKind.ORGANIZATION,
        normalized_key=label.lower(),
        label=label,
        aliases=(),
        confidence=confidence,
        evidence_refs=evidence_refs,
        observed_at=observed_at,
        valid_from=valid_from,
        valid_to=valid_to,
        now=now,
    )
