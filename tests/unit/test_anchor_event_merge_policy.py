from datetime import UTC, datetime

from infinity_context_core.application.anchor_extraction import (
    structured_anchor_metadata_for_label,
)
from infinity_context_core.application.use_cases.anchors import _merge_score, _rank_merge_candidates
from infinity_context_core.domain.entities import (
    Confidence,
    MemoryAnchor,
    MemoryAnchorId,
    MemoryAnchorKind,
    MemoryScopeId,
    SpaceId,
)


def test_event_merge_policy_rejects_same_participant_different_relative_time() -> None:
    score, reasons, metadata = _merge_score(
        _event_anchor("anchor_call_two_hours", "Call with Alex 2 hours ago"),
        _event_anchor("anchor_call_three_hours", "Call with Alex 3 hours ago"),
    )

    assert score == 0.0
    assert reasons == []
    assert metadata["event_identity_conflict"] == "temporal_mismatch"


def test_event_merge_policy_allows_equivalent_relative_time_variants() -> None:
    score, reasons, metadata = _merge_score(
        _event_anchor("anchor_chat_an_hour", "Chat with Alex an hour ago"),
        _event_anchor("anchor_chat_hour", "Chat with Alex hour ago"),
    )

    assert score >= 86
    assert reasons == ["event identity similarity"]
    assert metadata["event_identity"]["source"]["temporal"] == "hours_ago:1:hour"
    assert metadata["event_identity"]["target"]["temporal"] == "hours_ago:1:hour"


def test_event_merge_policy_rejects_same_participant_time_different_projects() -> None:
    score, reasons, metadata = _merge_score(
        _event_anchor("anchor_call_atlas", "Call with Alex about Project Atlas 2 hours ago"),
        _event_anchor("anchor_call_orion", "Call with Alex about Project Orion 2 hours ago"),
    )

    assert score == 0.0
    assert reasons == []
    assert metadata["event_identity_conflict"] == "project_mismatch"
    assert metadata["event_identity"]["source"]["project"] == "atlas"
    assert metadata["event_identity"]["target"]["project"] == "orion"


def test_event_merge_policy_rejects_same_project_different_relative_time() -> None:
    score, reasons, metadata = _merge_score(
        _event_anchor("anchor_call_atlas_two", "Call with Alex about Project Atlas 2 hours ago"),
        _event_anchor("anchor_call_atlas_three", "Call with Alex about Project Atlas 3 hours ago"),
    )

    assert score == 0.0
    assert reasons == []
    assert metadata["event_identity_conflict"] == "temporal_mismatch"
    assert metadata["event_identity"]["source"]["project"] == "atlas"
    assert metadata["event_identity"]["target"]["project"] == "atlas"


def test_event_merge_policy_allows_same_project_identity_variants() -> None:
    score, reasons, metadata = _merge_score(
        _event_anchor(
            "anchor_call_project_atlas",
            "Call with Alex about Project Atlas 2 hours ago",
        ),
        _event_anchor("anchor_call_atlas", "Call with Alex about Atlas 2 hours ago"),
    )

    assert score >= 86
    assert reasons == ["event identity similarity"]
    assert metadata["event_identity"]["source"]["project"] == "atlas"
    assert metadata["event_identity"]["target"]["project"] == "atlas"


def test_event_merge_suggestions_exclude_shared_project_different_event_time() -> None:
    candidates = _rank_merge_candidates(
        [
            _event_anchor(
                "anchor_call_atlas_two",
                "Call with Alex about Project Atlas 2 hours ago",
            ),
            _event_anchor(
                "anchor_call_atlas_three",
                "Call with Alex about Project Atlas 3 hours ago",
            ),
        ]
    )

    assert candidates == []


def test_event_merge_suggestions_include_same_project_identity_variants() -> None:
    candidates = _rank_merge_candidates(
        [
            _event_anchor(
                "anchor_call_project_atlas",
                "Call with Alex about Project Atlas 2 hours ago",
            ),
            _event_anchor("anchor_call_atlas", "Call with Alex about Atlas 2 hours ago"),
        ]
    )

    assert len(candidates) == 1
    assert candidates[0].reasons == ("event identity similarity",)
    assert candidates[0].metadata["event_identity"]["source"]["project"] == "atlas"
    assert candidates[0].metadata["event_identity"]["target"]["project"] == "atlas"


def _event_anchor(anchor_id: str, label: str) -> MemoryAnchor:
    now = datetime(2026, 6, 19, tzinfo=UTC)
    return MemoryAnchor.create(
        anchor_id=MemoryAnchorId(anchor_id),
        space_id=SpaceId("space_event_policy"),
        memory_scope_id=MemoryScopeId("memory_scope_event_policy"),
        kind=MemoryAnchorKind.EVENT,
        normalized_key=label.casefold(),
        label=label,
        aliases=(),
        confidence=Confidence.MEDIUM,
        metadata=structured_anchor_metadata_for_label(MemoryAnchorKind.EVENT, label),
        now=now,
    )
