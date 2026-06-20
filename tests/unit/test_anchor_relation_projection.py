from datetime import UTC, datetime

from infinity_context_core.application.anchor_relation_projection import (
    anchor_identity_keys,
    project_event_anchor_relations,
)
from infinity_context_core.domain.entities import (
    Confidence,
    MemoryAnchor,
    MemoryAnchorId,
    MemoryAnchorKind,
    MemoryScopeId,
    SpaceId,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_project_event_anchor_relations_links_event_to_person_and_project() -> None:
    person = _anchor(
        anchor_id="anchor_person_alex",
        kind=MemoryAnchorKind.PERSON,
        normalized_key="alex",
        label="Alex",
    )
    project = _anchor(
        anchor_id="anchor_project_atlas",
        kind=MemoryAnchorKind.PROJECT,
        normalized_key="project atlas",
        label="Project Atlas",
        aliases=("Atlas",),
    )
    event = _anchor(
        anchor_id="anchor_event_launch_review",
        kind=MemoryAnchorKind.EVENT,
        normalized_key="launch review",
        label="Launch review",
        metadata={
            "event_type": "meeting",
            "event_participant_canonical_key": "alex",
            "event_project_canonical_key": "atlas",
            "event_temporal_phrase": "last week",
        },
        confidence=Confidence.HIGH,
    )

    relations = project_event_anchor_relations((event, person, project))

    assert {relation.relation_type for relation in relations} == {
        "event_participant",
        "event_project",
    }
    assert {str(relation.target_anchor.id) for relation in relations} == {
        "anchor_person_alex",
        "anchor_project_atlas",
    }
    assert all(relation.confidence == "medium" for relation in relations)
    assert all(relation.metadata["schema_version"] for relation in relations)


def test_project_event_anchor_relations_uses_alias_identity_terms_without_duplicates() -> None:
    project = _anchor(
        anchor_id="anchor_project_atlas",
        kind=MemoryAnchorKind.PROJECT,
        normalized_key="project atlas",
        label="Project Atlas",
        aliases=("Atlas",),
        metadata={"alias_identity_terms": ["atlas", " Project Atlas "]},
    )
    event = _anchor(
        anchor_id="anchor_event_atlas_call",
        kind=MemoryAnchorKind.EVENT,
        normalized_key="atlas call",
        label="Atlas call",
        metadata={"event_project_canonical_key": "atlas"},
    )

    relations = project_event_anchor_relations((event, project))

    assert len(relations) == 1
    assert relations[0].target_anchor.id == project.id
    assert anchor_identity_keys(project).count("atlas") == 1


def test_project_event_anchor_relations_does_not_emit_missing_targets() -> None:
    event = _anchor(
        anchor_id="anchor_event_unknown_person",
        kind=MemoryAnchorKind.EVENT,
        normalized_key="unknown person call",
        label="Unknown person call",
        metadata={"event_participant_canonical_key": "unknown"},
    )

    assert project_event_anchor_relations((event,)) == ()


def test_project_event_anchor_relations_can_filter_source_events_before_limit() -> None:
    person = _anchor(
        anchor_id="anchor_person_alex",
        kind=MemoryAnchorKind.PERSON,
        normalized_key="alex",
        label="Alex",
    )
    skipped_event = _anchor(
        anchor_id="anchor_event_skipped",
        kind=MemoryAnchorKind.EVENT,
        normalized_key="skipped",
        label="Skipped event",
        metadata={"event_participant_canonical_key": "alex"},
    )
    selected_event = _anchor(
        anchor_id="anchor_event_selected",
        kind=MemoryAnchorKind.EVENT,
        normalized_key="selected",
        label="Selected event",
        metadata={"event_participant_canonical_key": "alex"},
    )

    relations = project_event_anchor_relations(
        (skipped_event, selected_event, person),
        limit=1,
        source_anchor_ids={str(selected_event.id)},
    )

    assert len(relations) == 1
    assert relations[0].source_anchor.id == selected_event.id


def _anchor(
    *,
    anchor_id: str,
    kind: MemoryAnchorKind,
    normalized_key: str,
    label: str,
    aliases: tuple[str, ...] = (),
    metadata: dict[str, object] | None = None,
    confidence: Confidence = Confidence.MEDIUM,
) -> MemoryAnchor:
    return MemoryAnchor.create(
        anchor_id=MemoryAnchorId(anchor_id),
        space_id=SpaceId("space_test"),
        memory_scope_id=MemoryScopeId("scope_test"),
        kind=kind,
        normalized_key=normalized_key,
        label=label,
        aliases=aliases,
        confidence=confidence,
        metadata=metadata or {},
        now=NOW,
    )
