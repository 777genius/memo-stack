from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from memo_stack_adapters.postgres import build_async_engine, create_schema
from memo_stack_adapters.postgres.models import (
    MemoryAnchorRow,
    MemoryContextLinkRow,
    MemoryScopeRow,
    MemorySpaceRow,
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
                    ]
                )
                await session.commit()
            async with AsyncSession(engine) as session:
                return await memory_scope_snapshot_conflicts(
                    session,
                    space_id="space_conflict",
                    memory_scope_id="scope_conflict",
                    facts=[],
                    documents=[],
                    episodes=[],
                    chunks=[],
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
                    relations=[],
                )
        finally:
            await engine.dispose()

    conflicts = asyncio.run(run())

    assert conflicts == ["anchor_snapshot_project_atlas"]
