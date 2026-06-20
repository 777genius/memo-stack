"""Related canonical anchor expansion for prompt context."""

from __future__ import annotations

from datetime import datetime

from infinity_context_core.application.anchor_relation_projection import (
    project_event_anchor_relations,
)
from infinity_context_core.application.context_anchors import related_anchor_context_item
from infinity_context_core.application.context_policy import is_context_anchor_visible
from infinity_context_core.application.dto import BuildContextQuery, ContextItem
from infinity_context_core.domain.entities import MemoryAnchor

_MAX_RELATED_ANCHOR_ITEMS = 8


def related_anchor_context_items(
    *,
    anchors: tuple[MemoryAnchor, ...],
    selected_anchor_items: tuple[tuple[MemoryAnchor, ContextItem], ...],
    query: BuildContextQuery,
    memory_scope_ids: tuple[str, ...],
    now: datetime | None,
) -> tuple[tuple[ContextItem, ...], int]:
    if not anchors or not selected_anchor_items:
        return (), 0
    items: list[ContextItem] = []
    emitted_target_ids: set[str] = set()
    item_limit = min(_MAX_RELATED_ANCHOR_ITEMS, max(1, query.max_facts))
    source_scores = {
        str(anchor.id): item.score for anchor, item in selected_anchor_items
    }
    projected_relations = project_event_anchor_relations(
        anchors,
        limit=item_limit * 4,
        source_anchor_ids=source_scores.keys(),
    )
    for relation in projected_relations:
        source_score = source_scores.get(str(relation.source_anchor.id))
        if source_score is None:
            continue
        target_anchor = relation.target_anchor
        target_id = str(target_anchor.id)
        if target_id in emitted_target_ids:
            continue
        if not is_context_anchor_visible(
            target_anchor,
            query=query,
            memory_scope_ids=memory_scope_ids,
            now=now,
        ):
            continue
        emitted_target_ids.add(target_id)
        items.append(
            related_anchor_context_item(
                target_anchor,
                source_anchor=relation.source_anchor,
                relation_type=relation.relation_type,
                relation_key=relation.relation_key,
                parent_score=source_score,
                now=now,
            )
        )
        if len(items) >= item_limit:
            return tuple(items), len(projected_relations)
    return tuple(items), len(projected_relations)
