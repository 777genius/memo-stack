from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from memo_stack_adapters.postgres import build_async_engine, create_schema
from memo_stack_adapters.postgres.models import (
    MemoryAnchorRow,
    MemoryContextLinkRow,
    MemoryContextLinkSuggestionRow,
    MemoryScopeRow,
    MemorySpaceRow,
    MemoryThreadRow,
)
from memo_stack_server.memory_scope_transfer_conflicts import memory_scope_snapshot_conflicts
from sqlalchemy.ext.asyncio import AsyncSession


def test_memory_scope_snapshot_anchor_conflicts_match_exact_key_pairs(tmp_path: Path) -> None:
    async def run() -> list[str]:
        engine = build_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'conflicts.db'}")
        try:
            await create_schema(engine)
            now = datetime.now(UTC)
            async with AsyncSession(engine) as session:
                session.add_all(
                    [
                        MemorySpaceRow(
                            id="space_conflict",
                            slug="conflict-space",
                            name="Conflict Space",
                            created_at=now,
                            updated_at=now,
                        ),
                        MemoryScopeRow(
                            id="scope_conflict",
                            space_id="space_conflict",
                            external_ref="default",
                            name="Default",
                            status="active",
                            created_at=now,
                            updated_at=now,
                        ),
                        MemoryThreadRow(
                            id="thread_existing_daily",
                            space_id="space_conflict",
                            memory_scope_id="scope_conflict",
                            external_ref="daily-standup",
                            status="active",
                            created_at=now,
                            updated_at=now,
                        ),
                        MemoryAnchorRow(
                            id="anchor_existing_person_atlas",
                            space_id="space_conflict",
                            memory_scope_id="scope_conflict",
                            kind="person",
                            normalized_key="atlas",
                            label="Atlas Person",
                            aliases_json=[],
                            description=None,
                            status="active",
                            metadata_json={},
                            created_at=now,
                            updated_at=now,
                        ),
                        MemoryAnchorRow(
                            id="anchor_existing_project_atlas",
                            space_id="space_conflict",
                            memory_scope_id="scope_conflict",
                            kind="project",
                            normalized_key="atlas",
                            label="Atlas Project",
                            aliases_json=[],
                            description=None,
                            status="active",
                            metadata_json={},
                            created_at=now,
                            updated_at=now,
                        ),
                        MemoryContextLinkRow(
                            id="context_link_existing_cross_pair",
                            space_id="space_conflict",
                            memory_scope_id="scope_conflict",
                            source_type="capture",
                            source_id="capture_a",
                            target_type="anchor",
                            target_id="anchor_b",
                            relation_type="mentions",
                            confidence="medium",
                            reason="Existing non-matching link.",
                            status="active",
                            metadata_json={},
                            created_at=now,
                            updated_at=now,
                        ),
                        MemoryContextLinkSuggestionRow(
                            id="context_link_suggestion_existing_pending",
                            space_id="space_conflict",
                            memory_scope_id="scope_conflict",
                            source_type="capture",
                            source_id="capture_a",
                            target_type="anchor",
                            target_id="anchor_b",
                            relation_type="related_to",
                            confidence="medium",
                            reason="Existing pending suggestion.",
                            score=0.9,
                            status="pending",
                            metadata_json={},
                            created_at=now,
                            updated_at=now,
                            reviewed_at=None,
                            review_reason=None,
                        ),
                        MemoryContextLinkSuggestionRow(
                            id="context_link_suggestion_existing_rejected",
                            space_id="space_conflict",
                            memory_scope_id="scope_conflict",
                            source_type="capture",
                            source_id="capture_c",
                            target_type="anchor",
                            target_id="anchor_c",
                            relation_type="related_to",
                            confidence="medium",
                            reason="Existing rejected suggestion.",
                            score=0.2,
                            status="rejected",
                            metadata_json={},
                            created_at=now,
                            updated_at=now,
                            reviewed_at=now,
                            review_reason="not relevant",
                        ),
                    ]
                )
                await session.commit()
            async with AsyncSession(engine) as session:
                return await memory_scope_snapshot_conflicts(
                    session,
                    space_id="space_conflict",
                    memory_scope_id="scope_conflict",
                    threads=[
                        {
                            "id": "thread_snapshot_daily",
                            "external_ref": "daily-standup",
                        },
                        {
                            "id": "thread_snapshot_planning",
                            "external_ref": "planning",
                        },
                    ],
                    facts=[],
                    documents=[],
                    episodes=[],
                    chunks=[],
                    assets=[],
                    asset_extraction_jobs=[],
                    extraction_artifacts=[],
                    captures=[],
                    anchors=[
                        {
                            "id": "anchor_snapshot_project_atlas",
                            "kind": "project",
                            "normalized_key": "atlas",
                        },
                        {
                            "id": "anchor_snapshot_person_alex",
                            "kind": "person",
                            "normalized_key": "alex",
                        },
                    ],
                    context_links=[
                        {
                            "id": "context_link_snapshot",
                            "source_type": "capture",
                            "source_id": "capture_a",
                            "target_type": "anchor",
                            "target_id": "anchor_a",
                            "relation_type": "mentions",
                        }
                    ],
                    context_link_suggestions=[
                        {
                            "id": "context_link_suggestion_snapshot_pending",
                            "source_type": "capture",
                            "source_id": "capture_a",
                            "target_type": "anchor",
                            "target_id": "anchor_b",
                            "relation_type": "related_to",
                            "status": "pending",
                        },
                        {
                            "id": "context_link_suggestion_snapshot_rejected_history",
                            "source_type": "capture",
                            "source_id": "capture_c",
                            "target_type": "anchor",
                            "target_id": "anchor_c",
                            "relation_type": "related_to",
                            "status": "pending",
                        },
                    ],
                    relations=[],
                )
        finally:
            await engine.dispose()

    conflicts = asyncio.run(run())

    assert conflicts == [
        "anchor_snapshot_project_atlas",
        "context_link_suggestion_snapshot_pending",
        "thread_snapshot_daily",
    ]
