from pathlib import Path

from fastapi.testclient import TestClient
from memo_stack_core.memory_scope_snapshots import verify_snapshot_manifest_payload
from memo_stack_server.config import DeployProfile, Settings
from memo_stack_server.main import create_app


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


def test_memory_scope_snapshot_export_dry_run_and_confirmed_import(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        created = client.post(
            "/v1/facts",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "text": "SNAPSHOT_API_MARKER: memory_scope snapshots are portable.",
                "kind": "architecture_decision",
                "source_refs": [{"source_type": "manual", "source_id": "snapshot-api"}],
                "category": "architecture",
                "tags": ["snapshot"],
                "ttl_policy": "durable",
            },
            headers=auth_headers(),
        )
        target = client.post(
            "/v1/facts",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "text": "SNAPSHOT_RELATION_TARGET: relations survive memory_scope snapshots.",
                "kind": "architecture_decision",
                "source_refs": [{"source_type": "manual", "source_id": "snapshot-link"}],
                "category": "architecture",
                "tags": ["snapshot"],
                "ttl_policy": "durable",
            },
            headers=auth_headers(),
        )
        relation = client.post(
            f"/v1/facts/{created.json()['data']['id']}/relations",
            json={
                "target_fact_id": target.json()["data"]["id"],
                "relation_type": "supports",
                "reason": "Snapshot relation target supports the portable snapshot decision.",
            },
            headers=auth_headers(),
        )
        episode = client.post(
            "/v1/episodes",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "thread_external_ref": "snapshot-thread",
                "source_type": "system_audio",
                "source_external_id": "snapshot-episode",
                "text": "SNAPSHOT_EPISODE_MARKER: transcript survives memory_scope snapshots.",
                "speaker": "user",
                "trust_level": "high",
            },
            headers=auth_headers(),
        )
        exported = client.get(
            "/v1/export/memory_scope-snapshot",
            params={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "redacted": False,
            },
            headers=auth_headers(),
        )
        snapshot = exported.json()["data"]
        manifest = exported.json()["manifest"]
        dry_run = client.post(
            "/v1/export/memory_scope-snapshot/import",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "restore-base",
                "snapshot": snapshot,
                "manifest": manifest,
                "dry_run": True,
                "merge_strategy": "create_new_memory_scope",
            },
            headers=auth_headers(),
        )
        refused = client.post(
            "/v1/export/memory_scope-snapshot/import",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "restore-base",
                "snapshot": snapshot,
                "dry_run": False,
                "merge_strategy": "create_new_memory_scope",
                "confirmed": False,
            },
            headers=auth_headers(),
        )
        imported = client.post(
            "/v1/export/memory_scope-snapshot/import",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "restore-base",
                "snapshot": snapshot,
                "manifest": manifest,
                "dry_run": False,
                "merge_strategy": "create_new_memory_scope",
                "confirmed": True,
                "source_name": "unit-memory_scope-snapshot",
            },
            headers=auth_headers(),
        )
        created_memory_scope = imported.json()["data"]["created_memory_scope"]
        restored = client.get(
            "/v1/facts",
            params={
                "space_slug": "agents",
                "memory_scope_external_ref": created_memory_scope["external_ref"],
            },
            headers=auth_headers(),
        )
        restored_source = next(
            item
            for item in restored.json()["data"]
            if item["text"] == "SNAPSHOT_API_MARKER: memory_scope snapshots are portable."
        )
        restored_relations = client.get(
            f"/v1/facts/{restored_source['id']}/relations",
            headers=auth_headers(),
        )
        restored_browser = client.get(
            "/v1/memory-browser",
            params={
                "space_slug": "agents",
                "memory_scope_external_ref": created_memory_scope["external_ref"],
            },
            headers=auth_headers(),
        )

    assert created.status_code == 201
    assert target.status_code == 201
    assert relation.status_code == 201
    assert episode.status_code == 200
    assert exported.status_code == 200
    assert exported.json()["counts"]["facts"] == 2
    assert exported.json()["counts"]["episodes"] == 1
    assert exported.json()["counts"]["chunks"] == 1
    assert exported.json()["counts"]["relations"] == 1
    assert snapshot["schema_version"] == 3
    assert manifest["schema_version"] == "memo_stack.memory_scope_snapshot_manifest.v1"
    assert manifest["counts"]["episodes"] == 1
    assert manifest["counts"]["chunks"] == 1
    assert manifest["counts"]["relations"] == 1
    assert manifest["snapshot_sha256"]
    assert verify_snapshot_manifest_payload(snapshot=snapshot, manifest=manifest)["ok"] is True
    assert (
        snapshot["facts"][0]["text"] == "SNAPSHOT_API_MARKER: memory_scope snapshots are portable."
    )
    assert snapshot["facts"][0]["category"] == "architecture"
    assert snapshot["facts"][0]["tags"] == ["snapshot"]
    assert (
        snapshot["episodes"][0]["text"]
        == "SNAPSHOT_EPISODE_MARKER: transcript survives memory_scope snapshots."
    )
    assert snapshot["chunks"][0]["episode_id"] == snapshot["episodes"][0]["id"]
    assert snapshot["relations"][0]["relation_type"] == "supports"
    assert dry_run.status_code == 200
    assert dry_run.json()["data"]["dry_run"] is True
    assert dry_run.json()["data"]["would_create_memory_scope"] is True
    assert dry_run.json()["data"]["would_import"]["facts"] == 2
    assert dry_run.json()["data"]["would_import"]["episodes"] == 1
    assert dry_run.json()["data"]["would_import"]["chunks"] == 1
    assert dry_run.json()["data"]["would_import"]["relations"] == 1
    assert dry_run.json()["data"]["preview"]["would_create_memory_scope"] is True
    assert dry_run.json()["data"]["preview"]["would_import"]["facts"] == 2
    assert dry_run.json()["data"]["preview"]["would_import"]["episodes"] == 1
    assert dry_run.json()["data"]["preview"]["would_import"]["chunks"] == 1
    assert dry_run.json()["data"]["preview"]["would_import"]["relations"] == 1
    assert refused.status_code == 400
    assert imported.status_code == 200
    assert imported.json()["data"]["merge_strategy"] == "create_new_memory_scope"
    assert imported.json()["data"]["imported"]["episodes"] == 1
    assert imported.json()["data"]["imported"]["chunks"] == 1
    assert imported.json()["data"]["imported"]["relations"] == 1
    assert restored.status_code == 200
    assert restored_source["id"] != created.json()["data"]["id"]
    assert restored_relations.status_code == 200
    assert restored_browser.status_code == 200
    browser_data = restored_browser.json()["data"]
    assert len(browser_data["episodes"]) == 1
    assert len(browser_data["chunks"]) == 1
    assert (
        browser_data["episodes"][0]["text"]
        == "SNAPSHOT_EPISODE_MARKER: transcript survives memory_scope snapshots."
    )
    assert browser_data["chunks"][0]["episode_id"] == browser_data["episodes"][0]["id"]
    restored_relation = restored_relations.json()["data"]["items"][0]
    assert restored_relation["relation"]["relation_type"] == "supports"
    assert restored_relation["relation"]["source_fact_id"] == restored_source["id"]
    assert restored_relation["relation"]["target_fact_id"] != target.json()["data"]["id"]
    assert (
        restored_relation["related_fact"]["text"]
        == "SNAPSHOT_RELATION_TARGET: relations survive memory_scope snapshots."
    )


def test_memory_scope_snapshot_import_dry_run_returns_conflict_preview(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        client.post(
            "/v1/facts",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "text": "SNAPSHOT_API_CONFLICT_MARKER: conflict preview is explicit.",
                "kind": "architecture_decision",
                "source_refs": [{"source_type": "manual", "source_id": "snapshot-conflict"}],
            },
            headers=auth_headers(),
        )
        exported = client.get(
            "/v1/export/memory_scope-snapshot",
            params={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "redacted": False,
            },
            headers=auth_headers(),
        )
        imported = client.post(
            "/v1/export/memory_scope-snapshot/import",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "snapshot": exported.json()["data"],
                "manifest": exported.json()["manifest"],
                "dry_run": True,
                "merge_strategy": "fail_on_conflict",
            },
            headers=auth_headers(),
        )
        preview_response = client.post(
            "/v1/export/memory_scope-snapshot/preview",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "snapshot": exported.json()["data"],
                "manifest": exported.json()["manifest"],
                "merge_strategy": "fail_on_conflict",
            },
            headers=auth_headers(),
        )

    data = imported.json()["data"]
    preview_data = preview_response.json()["data"]
    preview = data["preview"]
    assert imported.status_code == 200
    assert preview_response.status_code == 200
    assert data["status"] == "conflict"
    assert preview_data["status"] == "conflict"
    assert data["conflict_count"] == 1
    assert preview["conflict_count"] == 1
    assert preview["conflicts"]["facts"] == [exported.json()["data"]["facts"][0]["id"]]
    assert preview_data["preview"] == preview
    assert preview["would_import"]["facts"] == 1
    assert "conflicts_block_import" in preview["warnings"]


def test_memory_scope_snapshot_import_rejects_manifest_mismatch(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        client.post(
            "/v1/facts",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "text": "SNAPSHOT_API_TAMPER_MARKER: manifest catches edits.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "snapshot-tamper"}],
            },
            headers=auth_headers(),
        )
        exported = client.get(
            "/v1/export/memory_scope-snapshot",
            params={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "redacted": False,
            },
            headers=auth_headers(),
        )
        snapshot = exported.json()["data"]
        snapshot["facts"][0]["text"] = "tampered"
        imported = client.post(
            "/v1/export/memory_scope-snapshot/import",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "restore-base",
                "snapshot": snapshot,
                "manifest": exported.json()["manifest"],
                "dry_run": True,
            },
            headers=auth_headers(),
        )
        previewed = client.post(
            "/v1/export/memory_scope-snapshot/preview",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "restore-base",
                "snapshot": snapshot,
                "manifest": exported.json()["manifest"],
            },
            headers=auth_headers(),
        )

    assert imported.status_code == 400
    assert previewed.status_code == 400
    assert "manifest verification failed" in imported.text
    assert "manifest verification failed" in previewed.text
    assert "snapshot_sha256_mismatch" in imported.text


def test_memory_scope_snapshot_import_refuses_redacted_memory(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        client.post(
            "/v1/facts",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "text": "Redacted snapshots are export-only.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "snapshot-redacted"}],
            },
            headers=auth_headers(),
        )
        exported = client.get(
            "/v1/export/memory_scope-snapshot",
            params={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "redacted": True,
            },
            headers=auth_headers(),
        )
        imported = client.post(
            "/v1/export/memory_scope-snapshot/import",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "restore-base",
                "snapshot": exported.json()["data"],
                "dry_run": False,
                "merge_strategy": "create_new_memory_scope",
                "confirmed": True,
            },
            headers=auth_headers(),
        )

    assert exported.status_code == 200
    assert exported.json()["data"]["redacted"] is True
    assert exported.json()["data"]["facts"][0]["text"] is None
    assert imported.status_code == 200
    assert imported.json()["data"]["status"] == "refused"
    assert imported.json()["data"]["reason"] == "redacted_memory_scope_export_cannot_be_imported"
