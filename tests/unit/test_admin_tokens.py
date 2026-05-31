import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient
from memory_adapters.postgres.models import MemoryFactRow, MemoryOutboxRow, MemoryServiceTokenRow
from memory_server.admin import (
    export_profile_command,
    import_profile_command,
    reset_local,
    token_create,
    token_list,
    token_revoke,
)
from memory_server.auth_tokens import token_hash
from memory_server.config import DeployProfile, Settings
from memory_server.db import upgrade
from memory_server.main import create_app
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'tokens.db'}",
            auto_create_schema=True,
            service_token="root-token",
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
        )
    )
    return TestClient(app)


async def _load_service_token(tmp_path: Path, *, token_id: str) -> MemoryServiceTokenRow:
    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'tokens.db'}",
            auto_create_schema=True,
            service_token="root-token",
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
        )
    )
    try:
        async with AsyncSession(app.state.container.engine) as session:
            row = await session.get(MemoryServiceTokenRow, token_id)
            assert row is not None
            return row
    finally:
        await app.state.container.engine.dispose()


def test_admin_token_lifecycle_and_auth_without_raw_token_in_list(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "test")
    monkeypatch.setenv("MEMORY_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'tokens.db'}")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "root-token")
    asyncio.run(upgrade())

    created = asyncio.run(token_create(space_id=None, description="test token"))
    rotated = asyncio.run(token_create(space_id=None, description="rotated token"))
    listed = asyncio.run(token_list(space_id=None))

    with make_client(tmp_path) as client:
        authorized = client.get(
            "/v1/spaces",
            headers={"Authorization": f"Bearer {created['token']}"},
        )
        rotated_authorized = client.get(
            "/v1/spaces",
            headers={"Authorization": f"Bearer {rotated['token']}"},
        )

    revoked = asyncio.run(token_revoke(token_id=str(created["token_id"])))
    listed_after_revoke = asyncio.run(token_list(space_id=None))

    with make_client(tmp_path) as client:
        rejected = client.get(
            "/v1/spaces",
            headers={"Authorization": f"Bearer {created['token']}"},
        )
        rotated_still_authorized = client.get(
            "/v1/spaces",
            headers={"Authorization": f"Bearer {rotated['token']}"},
        )

    assert created["status"] == "created"
    assert str(created["token"]).startswith("mp_")
    assert created["profile_ids"] is None
    assert set(created["permissions"]) == {
        "memory:admin",
        "memory:delete",
        "memory:diagnostics",
        "memory:read",
        "memory:write",
    }
    listed_ids = {item["id"] for item in listed["tokens"]}
    assert {created["token_id"], rotated["token_id"]}.issubset(listed_ids)
    assert all("token" not in item for item in listed["tokens"])
    assert all("profile_ids" in item for item in listed["tokens"])
    assert all("permissions" in item for item in listed["tokens"])
    assert authorized.status_code == 200
    assert rotated_authorized.status_code == 200
    listed_after_use = asyncio.run(token_list(space_id=None))
    used_tokens = {item["id"]: item for item in listed_after_use["tokens"]}
    assert used_tokens[created["token_id"]]["last_used_at"] is not None
    assert used_tokens[rotated["token_id"]]["last_used_at"] is not None
    assert revoked == {"status": "revoked", "token_id": created["token_id"]}
    statuses = {item["id"]: item["status"] for item in listed_after_revoke["tokens"]}
    assert statuses[created["token_id"]] == "revoked"
    assert statuses[rotated["token_id"]] == "active"
    assert rejected.status_code == 401
    assert rotated_still_authorized.status_code == 200


def test_token_hash_is_stored_not_raw_token(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "test")
    monkeypatch.setenv("MEMORY_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'tokens.db'}")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "root-token")
    asyncio.run(upgrade())

    created = asyncio.run(token_create(space_id=None, description="hash check"))
    row = asyncio.run(_load_service_token(tmp_path, token_id=str(created["token_id"])))

    assert row.token_hash == token_hash(str(created["token"]))
    assert row.token_hash != created["token"]
    assert str(created["token"]) not in str(row.__dict__)


def test_expired_service_token_is_rejected_and_never_updates_last_used(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "test")
    monkeypatch.setenv("MEMORY_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'tokens.db'}")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "root-token")
    asyncio.run(upgrade())

    expired = asyncio.run(
        token_create(
            space_id=None,
            description="expired token",
            expires_at="2000-01-01T00:00:00+00:00",
        )
    )

    with make_client(tmp_path) as client:
        rejected = client.get(
            "/v1/spaces",
            headers={"Authorization": f"Bearer {expired['token']}"},
        )

    listed = asyncio.run(token_list(space_id=None))
    expired_row = next(item for item in listed["tokens"] if item["id"] == expired["token_id"])

    assert rejected.status_code == 401
    assert expired["expires_at"] == "2000-01-01T00:00:00+00:00"
    assert expired_row["expires_at"] is not None
    assert expired_row["last_used_at"] is None
    assert str(expired["token"]) not in str(listed)


def test_scoped_service_token_cannot_cross_space_or_use_unscoped_routes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "test")
    monkeypatch.setenv("MEMORY_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'scoped.db'}")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "root-token")
    asyncio.run(upgrade())

    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'scoped.db'}",
            auto_create_schema=True,
            service_token="root-token",
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
        )
    )
    root_headers = {"Authorization": "Bearer root-token"}
    with TestClient(app) as client:
        space_a = client.post(
            "/v1/spaces",
            json={"slug": "scope-a", "name": "Scope A"},
            headers=root_headers,
        ).json()["data"]
        profile_a = client.post(
            "/v1/profiles",
            json={"space_id": space_a["id"], "external_ref": "default", "name": "Default"},
            headers=root_headers,
        ).json()["data"]
        space_b = client.post(
            "/v1/spaces",
            json={"slug": "scope-b", "name": "Scope B"},
            headers=root_headers,
        ).json()["data"]
        profile_b = client.post(
            "/v1/profiles",
            json={"space_id": space_b["id"], "external_ref": "default", "name": "Default"},
            headers=root_headers,
        ).json()["data"]
        fact_b = client.post(
            "/v1/facts",
            json={
                "space_id": space_b["id"],
                "profile_id": profile_b["id"],
                "text": "SCOPED_TOKEN_LEAK_MARKER must not be readable by scope-a token.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "scope-b"}],
            },
            headers=root_headers,
        ).json()["data"]

    scoped = asyncio.run(token_create(space_id=space_a["id"], description="scope-a token"))
    scoped_headers = {"Authorization": f"Bearer {scoped['token']}"}
    with TestClient(app) as client:
        same_space = client.get(
            "/v1/facts",
            params={"space_id": space_a["id"], "profile_id": profile_a["id"]},
            headers=scoped_headers,
        )
        cross_space = client.get(
            "/v1/facts",
            params={"space_id": space_b["id"], "profile_id": profile_b["id"]},
            headers=scoped_headers,
        )
        cross_space_by_id = client.get(f"/v1/facts/{fact_b['id']}", headers=scoped_headers)
        capabilities = client.get("/v1/capabilities", headers=scoped_headers)
        unscoped = client.get("/v1/spaces", headers=scoped_headers)

    assert same_space.status_code == 200
    assert cross_space.status_code == 403
    assert cross_space.json()["error"]["code"] == "memory.forbidden"
    assert cross_space_by_id.status_code == 403
    assert capabilities.status_code == 200
    assert "SCOPED_TOKEN_LEAK_MARKER" not in cross_space_by_id.text
    assert unscoped.status_code == 403


def test_service_token_permissions_are_enforced(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "test")
    monkeypatch.setenv("MEMORY_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'perms.db'}")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "root-token")
    asyncio.run(upgrade())

    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'perms.db'}",
            auto_create_schema=True,
            service_token="root-token",
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
        )
    )
    root_headers = {"Authorization": "Bearer root-token"}
    with TestClient(app) as client:
        space = client.post(
            "/v1/spaces",
            json={"slug": "perm-space", "name": "Permission Space"},
            headers=root_headers,
        ).json()["data"]
        profile = client.post(
            "/v1/profiles",
            json={"space_id": space["id"], "external_ref": "default", "name": "Default"},
            headers=root_headers,
        ).json()["data"]
        fact = client.post(
            "/v1/facts",
            json={
                "space_id": space["id"],
                "profile_id": profile["id"],
                "text": "Permission matrix fact.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "permissions"}],
            },
            headers=root_headers,
        ).json()["data"]

    read_only = asyncio.run(
        token_create(
            space_id=None,
            description="read only",
            permissions=("memory:read",),
        )
    )
    write_only = asyncio.run(
        token_create(
            space_id=None,
            description="write only",
            permissions=("memory:write",),
        )
    )
    diagnostics_only = asyncio.run(
        token_create(
            space_id=None,
            description="diagnostics only",
            permissions=("memory:diagnostics",),
        )
    )
    admin_only = asyncio.run(
        token_create(
            space_id=None,
            description="admin only",
            permissions=("memory:admin",),
        )
    )

    read_headers = {"Authorization": f"Bearer {read_only['token']}"}
    write_headers = {"Authorization": f"Bearer {write_only['token']}"}
    diagnostics_headers = {"Authorization": f"Bearer {diagnostics_only['token']}"}
    admin_headers = {"Authorization": f"Bearer {admin_only['token']}"}
    with TestClient(app) as client:
        read_allowed = client.get(
            "/v1/facts",
            params={"space_id": space["id"], "profile_id": profile["id"]},
            headers=read_headers,
        )
        read_can_get_capabilities = client.get("/v1/capabilities", headers=read_headers)
        read_cannot_write = client.post(
            "/v1/facts",
            json={
                "space_id": space["id"],
                "profile_id": profile["id"],
                "text": "Read token must not create this.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "permissions"}],
            },
            headers=read_headers,
        )
        read_cannot_delete = client.delete(f"/v1/facts/{fact['id']}", headers=read_headers)
        read_cannot_diagnose = client.get("/v1/diagnostics/outbox", headers=read_headers)

        write_allowed = client.post(
            "/v1/facts",
            json={
                "space_id": space["id"],
                "profile_id": profile["id"],
                "text": "Write token may create this.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "permissions"}],
            },
            headers=write_headers,
        )
        write_cannot_read = client.get(
            "/v1/facts",
            params={"space_id": space["id"], "profile_id": profile["id"]},
            headers=write_headers,
        )
        write_cannot_delete = client.delete(f"/v1/facts/{fact['id']}", headers=write_headers)

        diagnostics_allowed = client.get(
            "/v1/diagnostics/outbox",
            headers=diagnostics_headers,
        )
        diagnostics_cannot_read = client.get(
            "/v1/facts",
            params={"space_id": space["id"], "profile_id": profile["id"]},
            headers=diagnostics_headers,
        )
        admin_can_read = client.get(
            "/v1/facts",
            params={"space_id": space["id"], "profile_id": profile["id"]},
            headers=admin_headers,
        )
        admin_can_write = client.post(
            "/v1/facts",
            json={
                "space_id": space["id"],
                "profile_id": profile["id"],
                "text": "Admin token may create this.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "admin-permission"}],
            },
            headers=admin_headers,
        )
        admin_can_diagnose = client.get("/v1/diagnostics/outbox", headers=admin_headers)

    assert read_allowed.status_code == 200
    assert read_can_get_capabilities.status_code == 200
    assert read_cannot_write.status_code == 403
    assert read_cannot_delete.status_code == 403
    assert read_cannot_diagnose.status_code == 403
    assert write_allowed.status_code == 201
    assert write_cannot_read.status_code == 403
    assert write_cannot_delete.status_code == 403
    assert diagnostics_allowed.status_code == 200
    assert diagnostics_cannot_read.status_code == 403
    assert admin_can_read.status_code == 200
    assert admin_can_write.status_code == 201
    assert admin_can_diagnose.status_code == 200
    assert read_cannot_write.json()["error"]["code"] == "memory.forbidden"


def test_profile_scoped_service_token_cannot_cross_profile_in_same_space(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "test")
    monkeypatch.setenv("MEMORY_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'profiles.db'}")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "root-token")
    asyncio.run(upgrade())

    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'profiles.db'}",
            auto_create_schema=True,
            service_token="root-token",
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
        )
    )
    root_headers = {"Authorization": "Bearer root-token"}
    with TestClient(app) as client:
        space = client.post(
            "/v1/spaces",
            json={"slug": "profile-scope", "name": "Profile Scope"},
            headers=root_headers,
        ).json()["data"]
        profile_a = client.post(
            "/v1/profiles",
            json={"space_id": space["id"], "external_ref": "alpha", "name": "Alpha"},
            headers=root_headers,
        ).json()["data"]
        profile_b = client.post(
            "/v1/profiles",
            json={"space_id": space["id"], "external_ref": "beta", "name": "Beta"},
            headers=root_headers,
        ).json()["data"]
        fact_b = client.post(
            "/v1/facts",
            json={
                "space_id": space["id"],
                "profile_id": profile_b["id"],
                "text": "PROFILE_SCOPE_LEAK_MARKER must not be visible.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "profile-b"}],
            },
            headers=root_headers,
        ).json()["data"]
        suggestion_b = client.post(
            "/v1/suggestions",
            json={
                "space_id": space["id"],
                "profile_id": profile_b["id"],
                "candidate_text": "PROFILE_SCOPE_SUGGESTION_LEAK must not be visible.",
                "kind": "note",
                "safe_reason": "scope_test",
                "source_refs": [{"source_type": "manual", "source_id": "profile-b-suggestion"}],
            },
            headers=root_headers,
        ).json()["data"]

    scoped = asyncio.run(
        token_create(
            space_id=space["id"],
            profile_ids=(profile_a["id"],),
            description="alpha only",
            permissions=("memory:read",),
        )
    )
    diagnostics_scoped = asyncio.run(
        token_create(
            space_id=space["id"],
            profile_ids=(profile_a["id"],),
            description="alpha diagnostics",
            permissions=("memory:diagnostics",),
        )
    )
    scoped_headers = {"Authorization": f"Bearer {scoped['token']}"}
    diagnostics_headers = {"Authorization": f"Bearer {diagnostics_scoped['token']}"}

    with TestClient(app) as client:
        same_profile = client.get(
            "/v1/facts",
            params={"space_id": space["id"], "profile_id": profile_a["id"]},
            headers=scoped_headers,
        )
        cross_profile = client.get(
            "/v1/facts",
            params={"space_id": space["id"], "profile_id": profile_b["id"]},
            headers=scoped_headers,
        )
        cross_profile_by_id = client.get(f"/v1/facts/{fact_b['id']}", headers=scoped_headers)
        same_profile_suggestions = client.get(
            "/v1/suggestions",
            params={
                "space_id": space["id"],
                "profile_id": profile_a["id"],
                "status": "pending",
            },
            headers=scoped_headers,
        )
        cross_profile_suggestions = client.get(
            "/v1/suggestions",
            params={
                "space_id": space["id"],
                "profile_id": profile_b["id"],
                "status": "pending",
            },
            headers=scoped_headers,
        )
        cross_profile_suggestion_by_id = client.post(
            f"/v1/suggestions/{suggestion_b['id']}/reject",
            json={"reason": "must not access"},
            headers=scoped_headers,
        )
        same_profile_diagnostics = client.get(
            f"/v1/diagnostics/profile/{profile_a['id']}",
            headers=scoped_headers,
        )
        scoped_same_profile_diagnostics = client.get(
            f"/v1/diagnostics/profile/{profile_a['id']}",
            headers=diagnostics_headers,
        )
        cross_profile_diagnostics = client.get(
            f"/v1/diagnostics/profile/{profile_b['id']}",
            headers=diagnostics_headers,
        )
        multi_profile_context = client.post(
            "/v1/context",
            json={
                "space_id": space["id"],
                "profile_ids": [profile_a["id"], profile_b["id"]],
                "query": "PROFILE_SCOPE_LEAK_MARKER",
            },
            headers=scoped_headers,
        )
        profile_capabilities = client.get("/v1/capabilities", headers=scoped_headers)

    assert scoped["profile_ids"] == [profile_a["id"]]
    assert same_profile.status_code == 200
    assert cross_profile.status_code == 403
    assert cross_profile_by_id.status_code == 403
    assert same_profile_suggestions.status_code == 200
    assert cross_profile_suggestions.status_code == 403
    assert cross_profile_suggestion_by_id.status_code == 403
    assert same_profile_diagnostics.status_code == 403
    assert scoped_same_profile_diagnostics.status_code == 200
    assert cross_profile_diagnostics.status_code == 403
    assert multi_profile_context.status_code == 403
    assert profile_capabilities.status_code == 200
    assert "PROFILE_SCOPE_LEAK_MARKER" not in cross_profile_by_id.text
    assert "PROFILE_SCOPE_SUGGESTION_LEAK" not in cross_profile_suggestions.text


def test_profile_scoped_service_token_requires_space_scope(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "test")
    monkeypatch.setenv("MEMORY_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'tokens.db'}")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "root-token")
    asyncio.run(upgrade())

    try:
        asyncio.run(
            token_create(
                space_id=None,
                profile_ids=("default",),
                description="ambiguous profile token",
            )
        )
    except ValueError as exc:
        assert "requires a space scope" in str(exc)
    else:
        raise AssertionError("Expected profile-scoped token without space to fail")


def test_profile_scoped_write_token_can_create_suggestion_only_in_scope(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "test")
    monkeypatch.setenv("MEMORY_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'suggest.db'}")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "root-token")
    asyncio.run(upgrade())

    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'suggest.db'}",
            auto_create_schema=True,
            service_token="root-token",
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
        )
    )
    root_headers = {"Authorization": "Bearer root-token"}
    with TestClient(app) as client:
        space = client.post(
            "/v1/spaces",
            json={"slug": "suggest-scope", "name": "Suggest Scope"},
            headers=root_headers,
        ).json()["data"]
        profile_a = client.post(
            "/v1/profiles",
            json={"space_id": space["id"], "external_ref": "alpha", "name": "Alpha"},
            headers=root_headers,
        ).json()["data"]
        client.post(
            "/v1/profiles",
            json={"space_id": space["id"], "external_ref": "beta", "name": "Beta"},
            headers=root_headers,
        )

    scoped = asyncio.run(
        token_create(
            space_id=space["id"],
            profile_ids=(profile_a["id"],),
            description="alpha write",
            permissions=("memory:write",),
        )
    )
    scoped_headers = {"Authorization": f"Bearer {scoped['token']}"}
    payload = {
        "space_slug": "suggest-scope",
        "profile_external_ref": "alpha",
        "candidate_text": "Scoped suggestion can be written.",
        "kind": "note",
        "safe_reason": "scope_test",
        "source_refs": [{"source_type": "manual", "source_id": "scope-write"}],
    }
    with TestClient(app) as client:
        same_profile = client.post(
            "/v1/suggestions",
            json=payload,
            headers=scoped_headers,
        )
        cross_profile = client.post(
            "/v1/suggestions",
            json={**payload, "profile_external_ref": "beta"},
            headers=scoped_headers,
        )

    assert same_profile.status_code == 201
    assert cross_profile.status_code == 403
    assert "Scoped suggestion can be written" not in cross_profile.text


def test_profile_scoped_service_token_accepts_external_refs_without_cross_profile_leak(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "test")
    monkeypatch.setenv("MEMORY_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'external.db'}")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "root-token")
    asyncio.run(upgrade())

    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'external.db'}",
            auto_create_schema=True,
            service_token="root-token",
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
        )
    )
    root_headers = {"Authorization": "Bearer root-token"}
    with TestClient(app) as client:
        space = client.post(
            "/v1/spaces",
            json={"slug": "external-scope", "name": "External Scope"},
            headers=root_headers,
        ).json()["data"]
        profile_alpha = client.post(
            "/v1/profiles",
            json={"space_id": space["id"], "external_ref": "alpha", "name": "Alpha"},
            headers=root_headers,
        ).json()["data"]
        client.post(
            "/v1/profiles",
            json={"space_id": space["id"], "external_ref": "beta", "name": "Beta"},
            headers=root_headers,
        )

    scoped = asyncio.run(
        token_create(
            space_id=space["id"],
            profile_ids=(profile_alpha["id"],),
            description="alpha external refs",
        )
    )
    scoped_headers = {"Authorization": f"Bearer {scoped['token']}"}
    allowed_scope = {
        "space_slug": "external-scope",
        "profile_external_ref": "alpha",
        "thread_external_ref": "external-session-alpha",
    }
    denied_scope = {
        "space_slug": "external-scope",
        "profile_external_ref": "beta",
        "thread_external_ref": "external-session-beta",
    }

    with TestClient(app) as client:
        episode = client.post(
            "/v1/episodes",
            json={
                **allowed_scope,
                "source_type": "system_audio",
                "source_external_id": "external-event-alpha",
                "text": "EXTERNAL_SCOPE_ALPHA_MARKER must be readable by alpha token.",
                "kind_hint": "constraint",
                "idempotency_key": "external-event-alpha",
            },
            headers=scoped_headers,
        )
        context = client.post(
            "/v1/context",
            json={
                **allowed_scope,
                "query": "EXTERNAL_SCOPE_ALPHA_MARKER",
                "token_budget": 512,
            },
            headers=scoped_headers,
        )
        denied_context = client.post(
            "/v1/context",
            json={**denied_scope, "query": "EXTERNAL_SCOPE_ALPHA_MARKER"},
            headers=scoped_headers,
        )
        denied_document = client.post(
            "/v1/documents",
            json={
                **denied_scope,
                "title": "Denied beta document",
                "text": "EXTERNAL_SCOPE_BETA_MARKER must not be written.",
                "source_type": "document",
                "source_external_id": "external-doc-beta",
            },
            headers=scoped_headers,
        )
        fact = client.post(
            "/v1/facts",
            json={
                **allowed_scope,
                "text": "EXTERNAL_SCOPE_FACT_ALPHA_MARKER can be written by alpha token.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "external-fact-alpha"}],
            },
            headers=scoped_headers,
        )
        denied_fact = client.post(
            "/v1/facts",
            json={
                **denied_scope,
                "text": "EXTERNAL_SCOPE_FACT_BETA_MARKER must not be written.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "external-fact-beta"}],
            },
            headers=scoped_headers,
        )

    assert episode.status_code == 200
    assert context.status_code == 200
    assert "EXTERNAL_SCOPE_ALPHA_MARKER" in context.json()["data"]["rendered_text"]
    assert denied_context.status_code == 403
    assert denied_document.status_code == 403
    assert fact.status_code == 201
    assert denied_fact.status_code == 403
    assert "EXTERNAL_SCOPE_BETA_MARKER" not in denied_document.text
    assert "EXTERNAL_SCOPE_FACT_BETA_MARKER" not in denied_fact.text


def test_reset_local_refuses_without_confirmation_and_server_profile(monkeypatch) -> None:
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "local")
    refused = asyncio.run(reset_local(confirmed=False))
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "server")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "root-token")
    server_refused = asyncio.run(reset_local(confirmed=True))

    assert refused["status"] == "refused"
    assert server_refused == {
        "status": "refused",
        "reason": "reset-local is forbidden in server profile",
    }


def test_export_redacted_mode_omits_restricted_text(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "transfer.db"
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "test")
    monkeypatch.setenv("MEMORY_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "root-token")
    asyncio.run(upgrade())

    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            database_url=f"sqlite+aiosqlite:///{db_path}",
            auto_create_schema=True,
            service_token="root-token",
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
        )
    )
    with TestClient(app) as client:
        space = client.post(
            "/v1/spaces",
            json={"slug": "hackinterview", "name": "HackInterview"},
            headers={"Authorization": "Bearer root-token"},
        ).json()["data"]
        profile = client.post(
            "/v1/profiles",
            json={"space_id": space["id"], "external_ref": "default", "name": "Default"},
            headers={"Authorization": "Bearer root-token"},
        ).json()["data"]
        client.post(
            "/v1/documents",
            json={
                "space_id": space["id"],
                "profile_id": profile["id"],
                "title": "Transfer notes",
                "text": "TRANSFER_SECRET_MARKER must be redacted from chunk export.",
                "source_type": "document",
                "source_external_id": "transfer-doc",
            },
            headers={"Authorization": "Bearer root-token"},
        )
        client.post(
            "/v1/facts",
            json={
                "space_id": space["id"],
                "profile_id": profile["id"],
                "text": "Transfer fact text should be redacted.",
                "kind": "note",
                "classification": "restricted",
                "source_refs": [
                    {
                        "source_type": "manual",
                        "source_id": "transfer-fact",
                        "quote_preview": "SOURCE_REF_SECRET_MARKER must be redacted from export.",
                    }
                ],
            },
            headers={"Authorization": "Bearer root-token"},
        )

    out = tmp_path / "profile-export.json"
    exported = asyncio.run(
        export_profile_command(
            space="hackinterview",
            profile="default",
            out=str(out),
            redacted=True,
        )
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    imported = asyncio.run(
        import_profile_command(
            space="dry-run-space",
            profile="dry-run-profile",
            file=str(out),
            dry_run=True,
            merge_strategy="fail_on_conflict",
        )
    )
    refused_import = asyncio.run(
        import_profile_command(
            space="write-space",
            profile="write-profile",
            file=str(out),
            dry_run=False,
            merge_strategy="skip_existing",
        )
    )
    dry_run_scope = asyncio.run(
        export_profile_command(
            space="dry-run-space",
            profile="dry-run-profile",
            out=str(tmp_path / "dry-run-export.json"),
            redacted=True,
        )
    )

    assert exported["status"] == "ok"
    assert exported["facts"] == 1
    assert exported["chunks"] == 1
    assert "TRANSFER_SECRET_MARKER" not in out.read_text(encoding="utf-8")
    assert "SOURCE_REF_SECRET_MARKER" not in out.read_text(encoding="utf-8")
    assert payload["facts"][0]["text"] is None
    assert payload["chunks"][0]["text"] is None
    assert payload["source_refs"][0]["quote_preview"] is None
    assert imported["status"] == "conflict"
    assert imported["dry_run"] is True
    assert refused_import == {
        "status": "refused",
        "reason": "import-profile requires --i-understand-this-writes-canonical-memory",
    }
    assert dry_run_scope["status"] == "not_found"


def test_import_profile_enqueues_projection_reindex_events(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "import.db"
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "test")
    monkeypatch.setenv("MEMORY_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "root-token")
    asyncio.run(upgrade())

    fixture = tmp_path / "profile-import.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "space": {"slug": "source-space"},
                "profile": {"external_ref": "source-profile"},
                "facts": [
                    {
                        "id": "fact_imported_reindex",
                        "kind": "architecture_decision",
                        "text": "Imported facts should enqueue graph reindex.",
                        "status": "active",
                        "confidence": "medium",
                        "trust_level": "medium",
                        "classification": "internal",
                        "version": 1,
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                    }
                ],
                "documents": [
                    {
                        "id": "doc_imported_reindex",
                        "title": "Imported document",
                        "source_type": "document",
                        "source_external_id": "doc-imported",
                        "content_hash": "doc-imported-hash",
                        "classification": "internal",
                        "status": "active",
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                    }
                ],
                "chunks": [
                    {
                        "id": "chunk_imported_reindex",
                        "document_id": "doc_imported_reindex",
                        "source_type": "document",
                        "source_external_id": "doc-imported",
                        "source_hash": "chunk-imported-hash",
                        "kind": "document_section",
                        "text": "Imported chunks should enqueue vector reindex.",
                        "normalized_text": "imported chunks should enqueue vector reindex.",
                        "status": "active",
                        "sequence": 0,
                        "char_start": 0,
                        "char_end": 48,
                        "token_estimate": 12,
                        "classification": "internal",
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                        "metadata_json": {},
                    }
                ],
                "source_refs": [
                    {
                        "fact_id": "fact_imported_reindex",
                        "fact_version": 1,
                        "source_type": "import",
                        "source_id": "fixture",
                        "chunk_id": "chunk_imported_reindex",
                        "quote_preview": "bounded source ref",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    imported = asyncio.run(
        import_profile_command(
            space="import-space",
            profile="default",
            file=str(fixture),
            dry_run=False,
            merge_strategy="fail_on_conflict",
            confirmed=True,
        )
    )
    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            database_url=f"sqlite+aiosqlite:///{db_path}",
            auto_create_schema=True,
            service_token="root-token",
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
        )
    )
    with TestClient(app) as client:
        outbox = client.get(
            "/v1/diagnostics/outbox",
            headers={"Authorization": "Bearer root-token"},
        )

    items = outbox.json()["data"]["items"]
    event_types = {item["event_type"] for item in items}
    fairness_keys = {item["fairness_key"] for item in items}

    assert imported["status"] == "ok"
    assert imported["imported"] == {
        "facts": 1,
        "documents": 1,
        "chunks": 1,
        "source_refs": 1,
    }
    assert event_types == {"graph.upsert_fact", "vector.upsert_chunk"}
    assert fairness_keys == {"fact:fact_imported_reindex", "chunk:chunk_imported_reindex"}
    assert all(item["workload_class"] == "projection" for item in items)


def test_import_profile_create_new_profile_rewrites_canonical_ids(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "create-new-profile.db"
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "test")
    monkeypatch.setenv("MEMORY_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "root-token")
    asyncio.run(upgrade())

    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            database_url=f"sqlite+aiosqlite:///{db_path}",
            auto_create_schema=True,
            service_token="root-token",
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
        )
    )
    headers = {"Authorization": "Bearer root-token"}
    with TestClient(app) as client:
        space = client.post(
            "/v1/spaces",
            json={"slug": "hackinterview", "name": "HackInterview"},
            headers=headers,
        ).json()["data"]
        profile = client.post(
            "/v1/profiles",
            json={"space_id": space["id"], "external_ref": "default", "name": "Default"},
            headers=headers,
        ).json()["data"]
        fact = client.post(
            "/v1/facts",
            json={
                "space_id": space["id"],
                "profile_id": profile["id"],
                "text": "Portable import should not overwrite the original profile.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "portable-fact"}],
            },
            headers=headers,
        ).json()["data"]

    export_path = tmp_path / "profile-export.json"
    exported = asyncio.run(
        export_profile_command(
            space="hackinterview",
            profile="default",
            out=str(export_path),
            redacted=False,
        )
    )
    imported = asyncio.run(
        import_profile_command(
            space="hackinterview",
            profile="default",
            file=str(export_path),
            dry_run=False,
            merge_strategy="create_new_profile",
            confirmed=True,
        )
    )

    async def load_rows() -> tuple[list[MemoryFactRow], list[dict[str, str]]]:
        async with AsyncSession(app.state.container.engine) as session:
            facts = list(
                (
                    await session.execute(
                        select(MemoryFactRow).order_by(
                            MemoryFactRow.profile_id,
                            MemoryFactRow.id,
                        )
                    )
                ).scalars()
            )
        with TestClient(app) as client:
            profiles = client.get(
                "/v1/profiles",
                params={"space_id": space["id"]},
                headers=headers,
            ).json()["data"]
        return facts, profiles

    facts, profiles = asyncio.run(load_rows())
    created_profile = imported["created_profile"]
    new_profile_facts = [row for row in facts if row.profile_id == created_profile["id"]]
    original_profile_facts = [row for row in facts if row.profile_id == profile["id"]]

    assert exported["status"] == "ok"
    assert imported["status"] == "ok"
    assert imported["merge_strategy"] == "create_new_profile"
    assert created_profile["external_ref"].startswith("default-import-")
    assert {item["external_ref"] for item in profiles} == {
        "default",
        created_profile["external_ref"],
    }
    assert [row.id for row in original_profile_facts] == [fact["id"]]
    assert len(new_profile_facts) == 1
    assert new_profile_facts[0].id != fact["id"]
    assert new_profile_facts[0].text == fact["text"]


def test_import_profile_supersede_matching_facts_keeps_history_and_reindexes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "supersede-import.db"
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "test")
    monkeypatch.setenv("MEMORY_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "root-token")
    asyncio.run(upgrade())

    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            database_url=f"sqlite+aiosqlite:///{db_path}",
            auto_create_schema=True,
            service_token="root-token",
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
        )
    )
    headers = {"Authorization": "Bearer root-token"}
    with TestClient(app) as client:
        space = client.post(
            "/v1/spaces",
            json={"slug": "hackinterview", "name": "HackInterview"},
            headers=headers,
        ).json()["data"]
        profile = client.post(
            "/v1/profiles",
            json={"space_id": space["id"], "external_ref": "default", "name": "Default"},
            headers=headers,
        ).json()["data"]
        original = client.post(
            "/v1/facts",
            json={
                "space_id": space["id"],
                "profile_id": profile["id"],
                "text": "Old imported fact value.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "original"}],
            },
            headers=headers,
        ).json()["data"]

    fixture = tmp_path / "supersede-profile.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "space": {"slug": "source-space"},
                "profile": {"external_ref": "source-profile"},
                "facts": [
                    {
                        "id": original["id"],
                        "kind": "note",
                        "text": "New imported fact value.",
                        "status": "active",
                        "confidence": "medium",
                        "trust_level": "medium",
                        "classification": "internal",
                        "version": 1,
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                    }
                ],
                "documents": [],
                "chunks": [],
                "source_refs": [
                    {
                        "fact_id": original["id"],
                        "fact_version": 1,
                        "source_type": "import",
                        "source_id": "supersede-fixture",
                        "quote_preview": "new value",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    imported = asyncio.run(
        import_profile_command(
            space="hackinterview",
            profile="default",
            file=str(fixture),
            dry_run=False,
            merge_strategy="supersede_matching_facts",
            confirmed=True,
        )
    )

    async def load_rows() -> tuple[list[MemoryFactRow], list[MemoryOutboxRow]]:
        async with AsyncSession(app.state.container.engine) as session:
            facts = list(
                (
                    await session.execute(
                        select(MemoryFactRow).order_by(MemoryFactRow.created_at, MemoryFactRow.id)
                    )
                ).scalars()
            )
            outbox = list(
                (
                    await session.execute(select(MemoryOutboxRow).order_by(MemoryOutboxRow.id))
                ).scalars()
            )
            return facts, outbox

    facts, outbox = asyncio.run(load_rows())
    original_row = next(row for row in facts if row.id == original["id"])
    imported_rows = [row for row in facts if row.id != original["id"]]
    event_pairs = {(row.event_type, row.aggregate_id) for row in outbox}

    assert imported["status"] == "ok"
    assert imported["merge_strategy"] == "supersede_matching_facts"
    assert original_row.status == "superseded"
    assert original_row.version == 2
    assert len(imported_rows) == 1
    assert imported_rows[0].status == "active"
    assert imported_rows[0].text == "New imported fact value."
    assert ("graph.delete_fact", original["id"]) in event_pairs
    assert ("graph.upsert_fact", imported_rows[0].id) in event_pairs
