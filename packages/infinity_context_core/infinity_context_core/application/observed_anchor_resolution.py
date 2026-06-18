"""Shared matching policy for rule-observed memory anchors."""

from __future__ import annotations

from infinity_context_core.application.anchor_extraction import (
    ObservedAnchor,
    canonical_anchor_key,
    normalize_anchor_key,
)
from infinity_context_core.domain.entities import (
    LifecycleStatus,
    MemoryAnchor,
    MemoryAnchorKind,
    MemoryScopeId,
    SpaceId,
)
from infinity_context_core.ports.unit_of_work import UnitOfWorkPort


async def find_active_by_observed_canonical_key(
    uow: UnitOfWorkPort,
    *,
    observed: ObservedAnchor,
    space_id: SpaceId,
    memory_scope_id: MemoryScopeId,
) -> MemoryAnchor | None:
    observed_key = observed_canonical_key(observed)
    if not observed_key:
        return None
    anchors = await uow.anchors.list_for_scope(
        space_id=str(space_id),
        memory_scope_id=str(memory_scope_id),
        kind=observed.kind.value,
        status=LifecycleStatus.ACTIVE.value,
        limit=500,
    )
    for anchor in anchors:
        if observed_key in canonical_anchor_keys(anchor) and _same_script_family(
            anchor.label,
            observed.label,
        ):
            return anchor
    return None


def preferred_observed_label(anchor: MemoryAnchor, observed: ObservedAnchor) -> str | None:
    observed_key = observed_canonical_key(observed)
    if (
        observed_key
        and observed_key in canonical_anchor_keys(anchor)
        and anchor.kind != MemoryAnchorKind.PERSON
    ):
        return None
    if (
        observed_key
        and observed_key in canonical_anchor_keys(anchor)
        and len(normalize_anchor_key(anchor.label)) <= len(normalize_anchor_key(observed.label))
    ):
        return None
    return observed.label


def should_promote_observed_key(anchor: MemoryAnchor, observed: ObservedAnchor) -> bool:
    observed_key = observed_canonical_key(observed)
    return bool(
        anchor.kind == MemoryAnchorKind.PERSON
        and observed.kind == MemoryAnchorKind.PERSON
        and observed_key
        and observed_key in canonical_anchor_keys(anchor)
        and _same_script_family(anchor.label, observed.label)
        and anchor.normalized_key != observed.normalized_key
        and len(normalize_anchor_key(observed.label)) < len(normalize_anchor_key(anchor.label))
    )


def observed_canonical_key(observed: ObservedAnchor) -> str | None:
    value = observed.metadata.get("canonical_key")
    return value.strip() if isinstance(value, str) and value.strip() else None


def canonical_anchor_keys(anchor: MemoryAnchor) -> set[str]:
    keys = {
        canonical_anchor_key(anchor.normalized_key),
        canonical_anchor_key(anchor.label),
    }
    keys.update(canonical_anchor_key(alias) for alias in anchor.aliases)
    metadata_key = anchor.metadata.get("canonical_key")
    if isinstance(metadata_key, str):
        keys.add(metadata_key)
    return {key for key in keys if key}


def _same_script_family(left: str, right: str) -> bool:
    left_family = _script_family(left)
    right_family = _script_family(right)
    return left_family == right_family and left_family != "mixed"


def _script_family(value: str) -> str:
    normalized = normalize_anchor_key(value)
    has_cyrillic = bool(any("а" <= char <= "я" or char == "ё" for char in normalized))
    has_latin = bool(any("a" <= char <= "z" for char in normalized))
    if has_cyrillic and has_latin:
        return "mixed"
    if has_cyrillic:
        return "cyrillic"
    if has_latin:
        return "latin"
    return "other"
