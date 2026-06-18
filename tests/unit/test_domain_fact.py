from datetime import UTC, datetime

import pytest
from infinity_context_core.domain.entities import (
    MAX_SOURCE_REFS_PER_ITEM,
    FactStatus,
    MemoryFact,
    MemoryFactId,
    MemoryKind,
    MemoryScopeId,
    SourceRef,
    SpaceId,
)
from infinity_context_core.domain.errors import MemoryConflictError, MemoryValidationError


def test_active_fact_requires_source_refs() -> None:
    with pytest.raises(MemoryValidationError):
        MemoryFact.create(
            fact_id=MemoryFactId("fact_1"),
            space_id=SpaceId("space_1"),
            memory_scope_id=MemoryScopeId("memory_scope_1"),
            text="Postgres is canonical truth.",
            kind=MemoryKind.ARCHITECTURE_DECISION,
            source_refs=(),
            now=datetime(2026, 5, 25, tzinfo=UTC),
        )


def test_fact_source_refs_are_deduplicated_and_capped() -> None:
    refs = (
        SourceRef(source_type="manual", source_id="source_0"),
        *tuple(
            SourceRef(source_type="manual", source_id=f"source_{index}")
            for index in range(MAX_SOURCE_REFS_PER_ITEM + 5)
        ),
    )
    fact = MemoryFact.create(
        fact_id=MemoryFactId("fact_many_refs"),
        space_id=SpaceId("space_1"),
        memory_scope_id=MemoryScopeId("memory_scope_1"),
        text="Facts keep bounded source refs.",
        kind=MemoryKind.NOTE,
        source_refs=refs,
        now=datetime(2026, 5, 25, tzinfo=UTC),
    )

    updated = fact.update(
        expected_version=1,
        text="Facts still keep bounded source refs.",
        source_refs=tuple(
            SourceRef(source_type="manual", source_id=f"updated_{index}")
            for index in range(MAX_SOURCE_REFS_PER_ITEM + 5)
        ),
        reason="bounded refs",
        now=datetime(2026, 5, 26, tzinfo=UTC),
    )

    assert len(fact.source_refs) == MAX_SOURCE_REFS_PER_ITEM
    assert fact.source_refs[0].source_id == "source_0"
    assert fact.source_refs[-1].source_id == f"source_{MAX_SOURCE_REFS_PER_ITEM - 1}"
    assert len(updated.source_refs) == MAX_SOURCE_REFS_PER_ITEM
    assert updated.source_refs[-1].source_id == f"updated_{MAX_SOURCE_REFS_PER_ITEM - 1}"


def test_update_requires_expected_version() -> None:
    fact = MemoryFact.create(
        fact_id=MemoryFactId("fact_1"),
        space_id=SpaceId("space_1"),
        memory_scope_id=MemoryScopeId("memory_scope_1"),
        text="Postgres is canonical truth.",
        kind=MemoryKind.ARCHITECTURE_DECISION,
        source_refs=(SourceRef(source_type="manual", source_id="manual_1"),),
        now=datetime(2026, 5, 25, tzinfo=UTC),
    )

    with pytest.raises(MemoryConflictError):
        fact.update(
            expected_version=2,
            text="Postgres remains canonical truth.",
            source_refs=(SourceRef(source_type="manual", source_id="manual_2"),),
            reason="Correction",
            now=datetime(2026, 5, 25, tzinfo=UTC),
        )


def test_forget_is_idempotent() -> None:
    fact = MemoryFact.create(
        fact_id=MemoryFactId("fact_1"),
        space_id=SpaceId("space_1"),
        memory_scope_id=MemoryScopeId("memory_scope_1"),
        text="Postgres is canonical truth.",
        kind=MemoryKind.ARCHITECTURE_DECISION,
        source_refs=(SourceRef(source_type="manual", source_id="manual_1"),),
        now=datetime(2026, 5, 25, tzinfo=UTC),
    )

    forgotten = fact.forget(now=datetime(2026, 5, 25, tzinfo=UTC))
    forgotten_again = forgotten.forget(now=datetime(2026, 5, 25, tzinfo=UTC))

    assert forgotten_again == forgotten
    assert forgotten.version == 2


def test_mark_disputed_excludes_fact_from_active_currency() -> None:
    fact = MemoryFact.create(
        fact_id=MemoryFactId("fact_1"),
        space_id=SpaceId("space_1"),
        memory_scope_id=MemoryScopeId("memory_scope_1"),
        text="Postgres is canonical truth.",
        kind=MemoryKind.ARCHITECTURE_DECISION,
        source_refs=(SourceRef(source_type="manual", source_id="manual_1"),),
        now=datetime(2026, 5, 25, tzinfo=UTC),
    )

    disputed = fact.mark_disputed(now=datetime(2026, 5, 26, tzinfo=UTC))
    disputed_again = disputed.mark_disputed(now=datetime(2026, 5, 27, tzinfo=UTC))

    assert disputed.status == FactStatus.DISPUTED
    assert disputed.version == 2
    assert disputed_again == disputed


def test_fact_rejects_unknown_classification_value() -> None:
    with pytest.raises(MemoryValidationError):
        MemoryFact.create(
            fact_id=MemoryFactId("fact_bad_classification"),
            space_id=SpaceId("space_1"),
            memory_scope_id=MemoryScopeId("memory_scope_1"),
            text="Invalid classification should be rejected.",
            kind=MemoryKind.NOTE,
            source_refs=(SourceRef(source_type="manual", source_id="manual_1"),),
            now=datetime(2026, 5, 25, tzinfo=UTC),
            classification="secret",
        )
