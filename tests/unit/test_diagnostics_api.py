from pathlib import Path

from fastapi.testclient import TestClient
from memory_server.config import DeployProfile, Settings
from memory_server.main import create_app


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


def test_diagnostics_adapters_and_outbox_are_safe(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        document = client.post(
            "/v1/documents",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "title": "Diagnostics notes",
                "text": "Do not leak this raw diagnostic text through outbox diagnostics.",
                "source_type": "document",
                "source_external_id": "doc-diagnostics",
            },
            headers=auth_headers(),
        )
        adapters = client.get("/v1/diagnostics/adapters", headers=auth_headers())
        outbox = client.get(
            "/v1/diagnostics/outbox",
            params={"limit": 1},
            headers=auth_headers(),
        )

    assert document.status_code == 201
    assert adapters.status_code == 200
    assert adapters.json()["data"]["adapters"]["qdrant"]["enabled"] is False
    assert outbox.status_code == 200
    item = outbox.json()["data"]["items"][0]
    assert item["event_type"] == "vector.upsert_chunk"
    assert "payload_json" not in item
    assert "raw diagnostic text" not in str(item)


def test_diagnostics_profile_counts_are_scoped_and_non_content(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        client.post(
            "/v1/documents",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "title": "Profile diagnostics notes",
                "text": "PROFILE_DIAGNOSTIC_MARKER should not appear in diagnostics.",
                "source_type": "document",
                "source_external_id": "doc-profile-diagnostics",
            },
            headers=auth_headers(),
        )
        client.post(
            "/v1/facts",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "text": "PROFILE_DIAGNOSTIC_FACT should not appear in diagnostics.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "diag-fact"}],
            },
            headers=auth_headers(),
        )
        client.post(
            "/v1/suggestions",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "candidate_text": "PROFILE_DIAGNOSTIC_SUGGESTION",
                "safe_reason": "diagnostic count",
                "source_refs": [{"source_type": "manual", "source_id": "diag-suggestion"}],
            },
            headers=auth_headers(),
        )
        diagnostics = client.get(
            "/v1/diagnostics/profile/profile_default",
            headers=auth_headers(),
        )

    assert diagnostics.status_code == 200
    data = diagnostics.json()["data"]
    assert data["facts"]["active"] == 1
    assert data["documents"]["active"] == 1
    assert data["chunks"]["active"] == 1
    assert data["suggestions"]["pending"] == 1
    assert "PROFILE_DIAGNOSTIC" not in str(data)
