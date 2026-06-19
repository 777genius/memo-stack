from datetime import UTC, datetime

from infinity_context_core.application.anchor_extraction import (
    structured_anchor_metadata_for_label,
)
from infinity_context_core.application.context_anchors import (
    anchor_context_item,
    anchor_retrieval_text,
)
from infinity_context_core.application.context_relevance import score_query_relevance
from infinity_context_core.domain.entities import (
    Confidence,
    MemoryAnchor,
    MemoryAnchorId,
    MemoryAnchorKind,
    MemoryScopeId,
    SpaceId,
)


def test_event_anchor_context_includes_project_identity_metadata() -> None:
    now = datetime(2026, 6, 19, tzinfo=UTC)
    anchor = MemoryAnchor.create(
        anchor_id=MemoryAnchorId("anchor_call_atlas"),
        space_id=SpaceId("space_context_anchors"),
        memory_scope_id=MemoryScopeId("memory_scope_context_anchors"),
        kind=MemoryAnchorKind.EVENT,
        normalized_key="call with alex about atlas 2 hours ago",
        label="Call with Alex about Atlas 2 hours ago",
        aliases=(),
        confidence=Confidence.HIGH,
        metadata=structured_anchor_metadata_for_label(
            MemoryAnchorKind.EVENT,
            "Call with Alex about Atlas 2 hours ago",
        ),
        now=now,
    )

    retrieval_text = anchor_retrieval_text(anchor)
    item = anchor_context_item(
        anchor,
        relevance=score_query_relevance(query="Atlas call", text=retrieval_text),
        identity_relevance=score_query_relevance(
            query="Atlas call",
            text=retrieval_text,
        ),
        now=now,
    )

    assert "atlas" in retrieval_text
    assert "about: atlas" in item.text
    assert item.diagnostics["identity_scope"] == "event"
    assert item.diagnostics["identity_key"] == "event:call with aleks about atlas 2 hours ago"
    assert item.diagnostics["event_project_label"] == "atlas"
    assert item.diagnostics["project_canonical_key"] == "atlas"


def test_person_anchor_context_includes_alias_identity_terms() -> None:
    now = datetime(2026, 6, 19, tzinfo=UTC)
    anchor = MemoryAnchor.create(
        anchor_id=MemoryAnchorId("anchor_alexander"),
        space_id=SpaceId("space_context_anchors"),
        memory_scope_id=MemoryScopeId("memory_scope_context_anchors"),
        kind=MemoryAnchorKind.PERSON,
        normalized_key="alexander",
        label="Alexander",
        aliases=("Alex", "Алекс"),
        confidence=Confidence.HIGH,
        metadata=structured_anchor_metadata_for_label(
            MemoryAnchorKind.PERSON,
            "Alexander",
            aliases=("Alex", "Алекс"),
        ),
        now=now,
    )

    retrieval_text = anchor_retrieval_text(anchor)
    item = anchor_context_item(
        anchor,
        relevance=score_query_relevance(query="Alex", text=retrieval_text),
        identity_relevance=score_query_relevance(
            query="aleks",
            text=retrieval_text,
        ),
        now=now,
    )

    assert "aleksander" in retrieval_text
    assert "aleks" in retrieval_text
    assert "identity: aleksander, aleks" in item.text
    assert item.diagnostics["alias_identity_terms"] == ["aleks"]
    assert item.diagnostics["identity_metadata"]["alias_identity_terms"] == ["aleks"]
