"""Derived semantic relations between canonical memory anchors."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from infinity_context_core.domain.entities import MemoryAnchor, MemoryAnchorKind

_RELATION_SCHEMA_VERSION = "anchor-relation-projection-v1"


@dataclass(frozen=True)
class ProjectedAnchorRelation:
    id: str
    source_anchor: MemoryAnchor
    target_anchor: MemoryAnchor
    relation_type: str
    relation_key: str
    confidence: str
    reason: str
    metadata: dict[str, object]


def project_event_anchor_relations(
    anchors: tuple[MemoryAnchor, ...],
    *,
    limit: int = 200,
    source_anchor_ids: Collection[str] | None = None,
) -> tuple[ProjectedAnchorRelation, ...]:
    if not anchors or limit <= 0:
        return ()
    anchors_by_identity = _anchors_by_identity_key(anchors)
    relations: list[ProjectedAnchorRelation] = []
    emitted: set[tuple[str, str, str]] = set()
    for source_anchor in anchors:
        if source_anchor.kind != MemoryAnchorKind.EVENT:
            continue
        if source_anchor_ids is not None and str(source_anchor.id) not in source_anchor_ids:
            continue
        for target_kind, relation_type, relation_key in event_relation_specs(source_anchor):
            candidates = anchors_by_identity.get((target_kind, relation_key.casefold()), ())
            for target_anchor in candidates:
                if target_anchor.id == source_anchor.id:
                    continue
                relation_identity = (
                    str(source_anchor.id),
                    relation_type,
                    str(target_anchor.id),
                )
                if relation_identity in emitted:
                    continue
                emitted.add(relation_identity)
                relations.append(
                    _project_relation(
                        source_anchor=source_anchor,
                        target_anchor=target_anchor,
                        relation_type=relation_type,
                        relation_key=relation_key,
                    )
                )
                if len(relations) >= limit:
                    return tuple(relations)
    return tuple(relations)


def event_relation_specs(
    anchor: MemoryAnchor,
) -> tuple[tuple[MemoryAnchorKind, str, str], ...]:
    participant_key = _metadata_key(anchor.metadata.get("event_participant_canonical_key"))
    if not participant_key:
        participant_key = _metadata_key(anchor.metadata.get("event_participant_label"))
    project_key = _metadata_key(
        anchor.metadata.get("event_project_canonical_key")
        or anchor.metadata.get("project_canonical_key")
    )
    if not project_key:
        project_key = _metadata_key(anchor.metadata.get("event_project_label"))
    specs: list[tuple[MemoryAnchorKind, str, str]] = []
    if participant_key:
        specs.append((MemoryAnchorKind.PERSON, "event_participant", participant_key))
    if project_key:
        specs.append((MemoryAnchorKind.PROJECT, "event_project", project_key))
    return tuple(specs)


def anchor_identity_keys(anchor: MemoryAnchor) -> tuple[str, ...]:
    keys: list[str] = []
    for value in (
        anchor.normalized_key,
        anchor.label,
        *anchor.aliases,
        anchor.metadata.get("canonical_key"),
        anchor.metadata.get("person_canonical_key"),
        anchor.metadata.get("project_canonical_key"),
        anchor.metadata.get("organization_canonical_key"),
    ):
        text = _metadata_key(value)
        if text:
            keys.append(text)
    alias_terms = anchor.metadata.get("alias_identity_terms")
    if isinstance(alias_terms, list | tuple):
        keys.extend(text for item in alias_terms if (text := _metadata_key(item)))
    return _dedupe_keys(keys)


def _anchors_by_identity_key(
    anchors: tuple[MemoryAnchor, ...],
) -> dict[tuple[MemoryAnchorKind, str], tuple[MemoryAnchor, ...]]:
    grouped: dict[tuple[MemoryAnchorKind, str], list[MemoryAnchor]] = {}
    for anchor in anchors:
        for key in anchor_identity_keys(anchor):
            grouped.setdefault((anchor.kind, key), []).append(anchor)
    return {key: tuple(value) for key, value in grouped.items()}


def _project_relation(
    *,
    source_anchor: MemoryAnchor,
    target_anchor: MemoryAnchor,
    relation_type: str,
    relation_key: str,
) -> ProjectedAnchorRelation:
    return ProjectedAnchorRelation(
        id=f"anchor_relation:{source_anchor.id}:{relation_type}:{target_anchor.id}",
        source_anchor=source_anchor,
        target_anchor=target_anchor,
        relation_type=relation_type,
        relation_key=relation_key,
        confidence=_relation_confidence(source_anchor, target_anchor),
        reason="event metadata canonical key matched active anchor identity",
        metadata=_relation_metadata(
            source_anchor=source_anchor,
            target_anchor=target_anchor,
            relation_type=relation_type,
            relation_key=relation_key,
        ),
    )


def _relation_confidence(source_anchor: MemoryAnchor, target_anchor: MemoryAnchor) -> str:
    ranks = {"low": 0, "medium": 1, "high": 2}
    source = source_anchor.confidence.value
    target = target_anchor.confidence.value
    return source if ranks.get(source, 0) <= ranks.get(target, 0) else target


def _relation_metadata(
    *,
    source_anchor: MemoryAnchor,
    target_anchor: MemoryAnchor,
    relation_type: str,
    relation_key: str,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "schema_version": _RELATION_SCHEMA_VERSION,
        "source_anchor_kind": source_anchor.kind.value,
        "source_anchor_key": source_anchor.normalized_key,
        "target_anchor_kind": target_anchor.kind.value,
        "target_anchor_key": target_anchor.normalized_key,
        "relation_type": relation_type,
        "relation_key": relation_key,
        "projection_kind": "derived_from_event_anchor_metadata",
    }
    for key in (
        "event_type",
        "event_type_canonical",
        "event_temporal_phrase",
        "event_temporal_hint_code",
        "event_participant_label",
        "event_participant_relation",
        "event_participant_canonical_key",
        "event_project_label",
        "event_project_relation",
        "event_project_canonical_key",
    ):
        value = _safe_metadata_value(source_anchor.metadata.get(key))
        if value:
            metadata[key] = value
    return metadata


def _metadata_key(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().casefold().split())[:160]


def _safe_metadata_value(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()[:240]


def _dedupe_keys(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return tuple(result)
