from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from memo_stack_adapters.postgres.mappers import (
    anchor_row_to_domain,
    fact_relation_row_to_domain,
)
from memo_stack_core.domain.entities import Confidence


def test_anchor_row_to_domain_defaults_missing_lifecycle_fields() -> None:
    created_at = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    row = SimpleNamespace(
        id="anchor_legacy_openai",
        space_id="space_legacy",
        memory_scope_id="scope_legacy",
        kind="organization",
        normalized_key="openai",
        label="OpenAI",
        aliases_json=["Open AI"],
        description=None,
        status="active",
        metadata_json={},
        created_at=created_at,
        updated_at=created_at,
    )

    anchor = anchor_row_to_domain(row)

    assert anchor.confidence == Confidence.MEDIUM
    assert anchor.evidence_refs == ()
    assert anchor.observed_at == created_at
    assert anchor.valid_from is None
    assert anchor.valid_to is None


def test_fact_relation_row_to_domain_defaults_missing_temporal_fields() -> None:
    created_at = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    row = SimpleNamespace(
        id="relation_legacy_supports",
        space_id="space_legacy",
        memory_scope_id="scope_legacy",
        source_fact_id="fact_source",
        target_fact_id="fact_target",
        relation_type="supports",
        reason="legacy relation",
        status="active",
        created_at=created_at,
        updated_at=created_at,
    )

    relation = fact_relation_row_to_domain(row)

    assert relation.observed_at == created_at
    assert relation.valid_from is None
    assert relation.valid_to is None
