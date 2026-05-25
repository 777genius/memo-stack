import asyncio
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from memory_adapters.postgres.models import (
    MemoryChunkRow,
    MemoryFactRow,
    MemoryIdempotencyRecordRow,
)
from memory_server.admin import invariant_check, repair_projections
from memory_server.config import DeployProfile, Settings
from memory_server.main import create_app
from sqlalchemy.ext.asyncio import AsyncSession


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'memory.db'}",
            auto_create_schema=True,
            service_token="test-token",
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
        )
    )
    return TestClient(app)


def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def test_invariant_checker_is_scoped_and_omits_raw_text(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "test")
    monkeypatch.setenv("MEMORY_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'memory.db'}")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "test-token")
    with make_client(tmp_path) as client:
        space = client.post(
            "/v1/spaces",
            json={"slug": "hackinterview", "name": "HackInterview"},
            headers=auth_headers(),
        ).json()["data"]
        profile = client.post(
            "/v1/profiles",
            json={"space_id": space["id"], "external_ref": "default", "name": "Default"},
            headers=auth_headers(),
        ).json()["data"]
        asyncio.run(_insert_broken_rows(client, space_id=space["id"], profile_id=profile["id"]))

    scoped = asyncio.run(invariant_check(space="hackinterview", profile="default"))
    global_check = asyncio.run(invariant_check())

    assert scoped["status"] == "failed"
    assert _check_by_name(scoped, "active_fact_source_refs")["count"] == 1
    assert _check_by_name(scoped, "idempotency_results_exist")["count"] == 1
    assert "RAW_INVARIANT_SECRET" not in str(scoped)
    assert global_check["status"] == "failed"
    assert _check_by_name(global_check, "profile_scoped_rows_match_profile")["count"] >= 1
    assert _check_by_name(global_check, "active_chunk_parent_exists")["count"] >= 1
    assert "RAW_CHUNK_SECRET" not in str(global_check)


def test_repair_projections_requires_scope_and_dry_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "test")
    monkeypatch.setenv("MEMORY_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'memory.db'}")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "test-token")
    with make_client(tmp_path) as client:
        client.post(
            "/v1/spaces",
            json={"slug": "hackinterview", "name": "HackInterview"},
            headers=auth_headers(),
        )

    missing_scope = asyncio.run(repair_projections(space=None, profile=None, dry_run=True))
    missing_dry_run = asyncio.run(
        repair_projections(space="hackinterview", profile="default", dry_run=False)
    )

    assert missing_scope["status"] == "refused"
    assert missing_dry_run["status"] == "refused"


async def _insert_broken_rows(client: TestClient, *, space_id: str, profile_id: str) -> None:
    now = datetime.now(UTC)
    async with AsyncSession(client.app.state.container.engine) as session:
        session.add(
            MemoryFactRow(
                id="fact_broken_no_refs",
                space_id=space_id,
                profile_id=profile_id,
                thread_id=None,
                kind="note",
                text="RAW_INVARIANT_SECRET should never appear in invariant output.",
                status="active",
                confidence="medium",
                trust_level="medium",
                classification="internal",
                version=1,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            MemoryChunkRow(
                id="chunk_broken_parent",
                space_id=space_id,
                profile_id="profile_missing",
                thread_id=None,
                document_id=None,
                episode_id=None,
                source_type="manual",
                source_external_id="broken",
                source_hash="broken_hash",
                kind="document_section",
                text="RAW_CHUNK_SECRET should never appear in invariant output.",
                normalized_text="raw_chunk_secret should never appear in invariant output.",
                status="active",
                sequence=0,
                char_start=0,
                char_end=58,
                token_estimate=12,
                created_at=now,
                updated_at=now,
                metadata_json={},
            )
        )
        session.add(
            MemoryIdempotencyRecordRow(
                space_id=space_id,
                key="broken-idempotency",
                fingerprint="broken",
                result_type="fact",
                result_id="fact_missing",
                created_at=now,
            )
        )
        await session.commit()


def _check_by_name(result: dict[str, object], name: str) -> dict[str, object]:
    checks = result["checks"]
    assert isinstance(checks, list)
    for check in checks:
        if check["name"] == name:
            return check
    raise AssertionError(f"Missing check {name}")
