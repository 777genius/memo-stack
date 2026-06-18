import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from infinity_context_adapters.postgres.models import MemoryContextLinkSuggestionRow
from infinity_context_core.memory_scope_snapshots import verify_snapshot_manifest_payload
from infinity_context_server.config import CaptureMode, DeployProfile, Settings
from infinity_context_server.main import create_app
from infinity_context_server.worker import OutboxWorker
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
            capture_mode=CaptureMode.SUGGEST,
            asset_storage_dir=str(tmp_path / "assets"),
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
        anchor = client.post(
            "/v1/anchors",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "kind": "person",
                "label": "Alex Snapshot",
                "aliases": ["Alex"],
                "description": "Person anchor linked from a snapshot capture.",
                "metadata": {"source": "snapshot-api-test"},
            },
            headers=auth_headers(),
        )
        asset = client.post(
            "/v1/assets",
            params={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "thread_external_ref": "snapshot-thread",
                "filename": "snapshot-evidence.txt",
                "extract": "true",
            },
            content=b"snapshot asset bytes",
            headers={**auth_headers(), "Content-Type": "text/plain"},
        )
        processed = asyncio.run(OutboxWorker(client.app.state.container).run_once(limit=20))
        extraction_id = asset.json()["data"]["extraction"]["id"]
        extraction = client.get(
            f"/v1/asset-extractions/{extraction_id}",
            headers=auth_headers(),
        )
        markdown_artifact = next(
            item
            for item in extraction.json()["data"]["artifacts"]
            if item["artifact_type"] == "markdown"
        )
        capture = client.post(
            "/v1/captures",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "thread_external_ref": "snapshot-thread",
                "source_agent": "memo-frontend",
                "source_kind": "manual",
                "event_type": "SnapshotCapture",
                "actor_role": "user",
                "text": "SNAPSHOT_CAPTURE_MARKER: quick capture survives snapshots.",
                "source_authority": "user_statement",
                "evidence_refs": [
                    {"source_type": "fact", "source_id": created.json()["data"]["id"]},
                    {"source_type": "episode", "source_id": episode.json()["data"]["episode_id"]},
                    {"source_type": "anchor", "source_id": anchor.json()["data"]["id"]},
                    {"source_type": "asset", "source_id": asset.json()["data"]["id"]},
                ],
                "idempotency_key": "snapshot-capture",
                "consolidate": False,
            },
            headers=auth_headers(),
        )
        link_suggestions = client.post(
            "/v1/link-suggestions",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "thread_external_ref": "snapshot-thread",
                "text": "snapshot thread memory",
                "source_type": "capture",
                "source_id": capture.json()["data"]["id"],
                "limit": 10,
                "persist": False,
            },
            headers=auth_headers(),
        )
        thread_candidate = next(
            item
            for item in link_suggestions.json()["data"]["candidates"]
            if item["target_type"] == "thread"
        )

        async def persist_thread_suggestion() -> None:
            now = datetime.now(UTC)
            async with AsyncSession(client.app.state.container.engine) as session:
                session.add(
                    MemoryContextLinkSuggestionRow(
                        id="ctxlinksug_snapshot_thread",
                        space_id=created.json()["data"]["space_id"],
                        memory_scope_id=created.json()["data"]["memory_scope_id"],
                        source_type="capture",
                        source_id=capture.json()["data"]["id"],
                        target_type="thread",
                        target_id=thread_candidate["target_id"],
                        relation_type="related_to",
                        confidence="high",
                        reason="Snapshot capture belongs to the saved source thread.",
                        score=92.0,
                        status="pending",
                        metadata_json={
                            "external_ref": "snapshot-thread",
                            "reason_codes": ["same_thread"],
                        },
                        created_at=now,
                        updated_at=now,
                        reviewed_at=None,
                        review_reason=None,
                    )
                )
                await session.commit()

        asyncio.run(persist_thread_suggestion())
        context_link = client.post(
            "/v1/context-links",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "source_type": "capture",
                "source_id": capture.json()["data"]["id"],
                "target_type": "anchor",
                "target_id": anchor.json()["data"]["id"],
                "relation_type": "mentions",
                "confidence": "high",
                "reason": "Capture text mentions the person anchor.",
                "metadata": {"source": "snapshot-api-test"},
            },
            headers=auth_headers(),
        )
        asset_context_link = client.post(
            "/v1/context-links",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "source_type": "capture",
                "source_id": capture.json()["data"]["id"],
                "target_type": "asset",
                "target_id": asset.json()["data"]["id"],
                "relation_type": "mentions",
                "confidence": "high",
                "reason": "Capture text is backed by the uploaded file.",
                "metadata": {"source": "snapshot-api-test"},
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
        restored_browser_data = restored_browser.json()["data"]
        restored_asset_download = client.get(
            f"/v1/assets/{restored_browser_data['assets'][0]['id']}/download",
            headers=auth_headers(),
        )
        restored_extraction = client.get(
            f"/v1/asset-extractions/{restored_browser_data['extraction_jobs'][0]['id']}",
            headers=auth_headers(),
        )
        restored_markdown_artifact = next(
            item
            for item in restored_extraction.json()["data"]["artifacts"]
            if item["artifact_type"] == "markdown"
        )
        restored_artifact_download = client.get(
            f"/v1/extraction-artifacts/{restored_markdown_artifact['id']}/download",
            headers=auth_headers(),
        )
        restored_suggestion_id = restored_browser_data["context_link_suggestions"][0]["id"]
        reviewed_restored_suggestion = client.post(
            f"/v1/context-link-suggestions/{restored_suggestion_id}/review",
            json={"action": "approve", "reason": "restored suggestion review"},
            headers=auth_headers(),
        )

    assert created.status_code == 201
    assert target.status_code == 201
    assert relation.status_code == 201
    assert episode.status_code == 200
    assert anchor.status_code == 200
    assert asset.status_code == 201
    assert processed >= 1
    assert extraction.status_code == 200
    assert extraction.json()["data"]["status"] == "succeeded"
    assert capture.status_code == 201
    assert link_suggestions.status_code == 200
    assert thread_candidate["metadata"]["external_ref"] == "snapshot-thread"
    assert context_link.status_code == 200
    assert asset_context_link.status_code == 200
    assert exported.status_code == 200
    assert exported.json()["counts"]["threads"] == 1
    assert exported.json()["counts"]["facts"] == 2
    assert exported.json()["counts"]["episodes"] == 1
    assert exported.json()["counts"]["documents"] == 1
    assert exported.json()["counts"]["chunks"] == 2
    assert exported.json()["counts"]["assets"] == 1
    assert exported.json()["counts"]["asset_blobs"] == 1
    assert exported.json()["counts"]["asset_extraction_jobs"] == 1
    assert exported.json()["counts"]["extraction_artifacts"] == 2
    assert exported.json()["counts"]["extraction_artifact_blobs"] == 2
    assert exported.json()["counts"]["captures"] == 1
    assert exported.json()["counts"]["anchors"] == 1
    assert exported.json()["counts"]["context_links"] == 2
    assert exported.json()["counts"]["context_link_suggestions"] == 1
    assert exported.json()["counts"]["relations"] == 1
    assert snapshot["schema_version"] == 9
    assert manifest["schema_version"] == "infinity_context.memory_scope_snapshot_manifest.v1"
    assert manifest["counts"]["threads"] == 1
    assert manifest["counts"]["episodes"] == 1
    assert manifest["counts"]["documents"] == 1
    assert manifest["counts"]["chunks"] == 2
    assert manifest["counts"]["assets"] == 1
    assert manifest["counts"]["asset_blobs"] == 1
    assert manifest["counts"]["asset_extraction_jobs"] == 1
    assert manifest["counts"]["extraction_artifacts"] == 2
    assert manifest["counts"]["extraction_artifact_blobs"] == 2
    assert manifest["counts"]["captures"] == 1
    assert manifest["counts"]["anchors"] == 1
    assert manifest["counts"]["context_links"] == 2
    assert manifest["counts"]["context_link_suggestions"] == 1
    assert manifest["counts"]["relations"] == 1
    assert manifest["snapshot_sha256"]
    assert verify_snapshot_manifest_payload(snapshot=snapshot, manifest=manifest)["ok"] is True
    assert snapshot["threads"][0]["external_ref"] == "snapshot-thread"
    assert snapshot["episodes"][0]["thread_id"] == snapshot["threads"][0]["id"]
    assert snapshot["documents"][0]["thread_id"] == snapshot["threads"][0]["id"]
    assert snapshot["assets"][0]["thread_id"] == snapshot["threads"][0]["id"]
    assert snapshot["asset_extraction_jobs"][0]["thread_id"] == snapshot["threads"][0]["id"]
    assert snapshot["captures"][0]["thread_id"] == snapshot["threads"][0]["id"]
    assert (
        snapshot["facts"][0]["text"] == "SNAPSHOT_API_MARKER: memory_scope snapshots are portable."
    )
    assert snapshot["facts"][0]["category"] == "architecture"
    assert snapshot["facts"][0]["tags"] == ["snapshot"]
    assert (
        snapshot["episodes"][0]["text"]
        == "SNAPSHOT_EPISODE_MARKER: transcript survives memory_scope snapshots."
    )
    assert (
        snapshot["captures"][0]["text_redacted"]
        == "SNAPSHOT_CAPTURE_MARKER: quick capture survives snapshots."
    )
    assert {chunk["source_type"] for chunk in snapshot["chunks"]} == {
        "asset_extraction",
        "system_audio",
    }
    assert any(chunk["episode_id"] == snapshot["episodes"][0]["id"] for chunk in snapshot["chunks"])
    assert snapshot["assets"][0]["filename"] == "snapshot-evidence.txt"
    assert snapshot["asset_blobs"][0]["asset_id"] == snapshot["assets"][0]["id"]
    assert snapshot["asset_extraction_jobs"][0]["id"] == extraction_id
    assert snapshot["asset_extraction_jobs"][0]["asset_id"] == snapshot["assets"][0]["id"]
    assert {item["artifact_id"] for item in snapshot["extraction_artifact_blobs"]} == {
        item["id"] for item in snapshot["extraction_artifacts"]
    }
    assert snapshot["anchors"][0]["label"] == "Alex Snapshot"
    assert {item["target_type"] for item in snapshot["context_links"]} == {"anchor", "asset"}
    assert snapshot["context_link_suggestions"][0]["status"] == "pending"
    assert snapshot["context_link_suggestions"][0]["target_type"] == "thread"
    assert snapshot["context_link_suggestions"][0]["target_id"] == snapshot["threads"][0]["id"]
    assert snapshot["relations"][0]["relation_type"] == "supports"
    assert dry_run.status_code == 200
    assert dry_run.json()["data"]["dry_run"] is True
    assert dry_run.json()["data"]["would_create_memory_scope"] is True
    assert dry_run.json()["data"]["would_import"]["threads"] == 1
    assert dry_run.json()["data"]["would_import"]["facts"] == 2
    assert dry_run.json()["data"]["would_import"]["episodes"] == 1
    assert dry_run.json()["data"]["would_import"]["documents"] == 1
    assert dry_run.json()["data"]["would_import"]["chunks"] == 2
    assert dry_run.json()["data"]["would_import"]["assets"] == 1
    assert dry_run.json()["data"]["would_import"]["asset_extraction_jobs"] == 1
    assert dry_run.json()["data"]["would_import"]["extraction_artifacts"] == 2
    assert dry_run.json()["data"]["would_import"]["captures"] == 1
    assert dry_run.json()["data"]["would_import"]["anchors"] == 1
    assert dry_run.json()["data"]["would_import"]["context_links"] == 2
    assert dry_run.json()["data"]["would_import"]["context_link_suggestions"] == 1
    assert dry_run.json()["data"]["would_import"]["relations"] == 1
    assert dry_run.json()["data"]["preview"]["would_create_memory_scope"] is True
    assert dry_run.json()["data"]["preview"]["would_import"]["threads"] == 1
    assert dry_run.json()["data"]["preview"]["would_import"]["facts"] == 2
    assert dry_run.json()["data"]["preview"]["would_import"]["episodes"] == 1
    assert dry_run.json()["data"]["preview"]["would_import"]["documents"] == 1
    assert dry_run.json()["data"]["preview"]["would_import"]["chunks"] == 2
    assert dry_run.json()["data"]["preview"]["would_import"]["assets"] == 1
    assert dry_run.json()["data"]["preview"]["would_import"]["asset_extraction_jobs"] == 1
    assert dry_run.json()["data"]["preview"]["would_import"]["extraction_artifacts"] == 2
    assert dry_run.json()["data"]["preview"]["would_import"]["captures"] == 1
    assert dry_run.json()["data"]["preview"]["would_import"]["anchors"] == 1
    assert dry_run.json()["data"]["preview"]["would_import"]["context_links"] == 2
    assert dry_run.json()["data"]["preview"]["would_import"]["context_link_suggestions"] == 1
    assert dry_run.json()["data"]["preview"]["would_import"]["relations"] == 1
    assert refused.status_code == 400
    assert imported.status_code == 200
    assert imported.json()["data"]["merge_strategy"] == "create_new_memory_scope"
    assert imported.json()["data"]["imported"]["threads"] == 1
    assert imported.json()["data"]["imported"]["episodes"] == 1
    assert imported.json()["data"]["imported"]["documents"] == 1
    assert imported.json()["data"]["imported"]["chunks"] == 2
    assert imported.json()["data"]["imported"]["assets"] == 1
    assert imported.json()["data"]["imported"]["asset_extraction_jobs"] == 1
    assert imported.json()["data"]["imported"]["extraction_artifacts"] == 2
    assert imported.json()["data"]["imported"]["captures"] == 1
    assert imported.json()["data"]["imported"]["anchors"] == 1
    assert imported.json()["data"]["imported"]["context_links"] == 2
    assert imported.json()["data"]["imported"]["context_link_suggestions"] == 1
    assert imported.json()["data"]["imported"]["relations"] == 1
    assert restored.status_code == 200
    assert restored_source["id"] != created.json()["data"]["id"]
    assert restored_relations.status_code == 200
    assert restored_browser.status_code == 200
    browser_data = restored_browser_data
    assert len(browser_data["threads"]) == 1
    assert len(browser_data["episodes"]) == 1
    assert len(browser_data["documents"]) == 1
    assert len(browser_data["chunks"]) == 2
    assert len(browser_data["assets"]) == 1
    assert len(browser_data["extraction_jobs"]) == 1
    assert len(browser_data["captures"]) == 1
    assert len(browser_data["anchors"]) == 1
    assert len(browser_data["context_links"]) == 2
    assert len(browser_data["context_link_suggestions"]) == 1
    assert (
        browser_data["episodes"][0]["text"]
        == "SNAPSHOT_EPISODE_MARKER: transcript survives memory_scope snapshots."
    )
    restored_extraction_chunk = next(
        item for item in browser_data["chunks"] if item["source_type"] == "asset_extraction"
    )
    restored_episode_chunk = next(
        item for item in browser_data["chunks"] if item["source_type"] == "system_audio"
    )
    assert restored_episode_chunk["episode_id"] == browser_data["episodes"][0]["id"]
    restored_capture = browser_data["captures"][0]
    restored_asset = browser_data["assets"][0]
    restored_extraction_job = browser_data["extraction_jobs"][0]
    restored_anchor = browser_data["anchors"][0]
    restored_thread = browser_data["threads"][0]
    restored_context_link = next(
        item for item in browser_data["context_links"] if item["target_type"] == "anchor"
    )
    restored_asset_context_link = next(
        item for item in browser_data["context_links"] if item["target_type"] == "asset"
    )
    restored_context_link_suggestion = browser_data["context_link_suggestions"][0]
    assert restored_capture["id"] != capture.json()["data"]["id"]
    assert restored_asset["id"] != asset.json()["data"]["id"]
    assert restored_extraction_job["id"] != extraction_id
    assert restored_anchor["id"] != anchor.json()["data"]["id"]
    assert restored_thread["id"] != snapshot["threads"][0]["id"]
    assert restored_thread["external_ref"] == "snapshot-thread"
    assert browser_data["episodes"][0]["thread_id"] == restored_thread["id"]
    assert browser_data["documents"][0]["thread_id"] == restored_thread["id"]
    assert restored_asset["thread_id"] == restored_thread["id"]
    assert restored_extraction_job["thread_id"] == restored_thread["id"]
    assert restored_capture["thread_id"] == restored_thread["id"]
    assert restored_context_link["id"] != context_link.json()["data"]["id"]
    assert restored_asset_context_link["id"] != asset_context_link.json()["data"]["id"]
    assert restored_context_link_suggestion["id"] != "ctxlinksug_snapshot_thread"
    assert restored_capture["text_preview"] == (
        "SNAPSHOT_CAPTURE_MARKER: quick capture survives snapshots."
    )
    assert restored_capture["evidence_refs"][0]["source_id"] == restored_source["id"]
    assert restored_capture["evidence_refs"][1]["source_id"] == browser_data["episodes"][0]["id"]
    assert restored_capture["evidence_refs"][2]["source_id"] == restored_anchor["id"]
    assert restored_capture["evidence_refs"][3]["source_id"] == restored_asset["id"]
    assert restored_extraction_job["asset_id"] == restored_asset["id"]
    assert restored_extraction_job["result_document_ids"] == [browser_data["documents"][0]["id"]]
    assert restored_extraction_chunk["source_external_id"] == restored_extraction_job["id"]
    assert restored_extraction_chunk["metadata"]["asset_id"] == restored_asset["id"]
    assert (
        restored_extraction_chunk["metadata"]["extraction_job_id"] == restored_extraction_job["id"]
    )
    assert restored_extraction_chunk["source_refs"][0]["source_id"] == restored_extraction_job["id"]
    assert restored_extraction_chunk["source_refs"][0]["asset_id"] == restored_asset["id"]
    assert restored_context_link["source_id"] == restored_capture["id"]
    assert restored_context_link["target_id"] == restored_anchor["id"]
    assert restored_asset_context_link["source_id"] == restored_capture["id"]
    assert restored_asset_context_link["target_id"] == restored_asset["id"]
    assert restored_context_link_suggestion["source_id"] == restored_capture["id"]
    assert restored_context_link_suggestion["target_id"] == restored_thread["id"]
    assert restored_context_link_suggestion["target_type"] == "thread"
    assert restored_context_link_suggestion["status"] == "pending"
    assert restored_asset_download.status_code == 200
    assert restored_asset_download.content == b"snapshot asset bytes"
    assert restored_extraction.status_code == 200
    assert restored_markdown_artifact["id"] != markdown_artifact["id"]
    assert restored_markdown_artifact["asset_id"] == restored_asset["id"]
    assert restored_markdown_artifact["job_id"] == restored_extraction_job["id"]
    assert restored_artifact_download.status_code == 200
    assert restored_artifact_download.content == b"snapshot asset bytes"
    assert reviewed_restored_suggestion.status_code == 200
    assert reviewed_restored_suggestion.json()["data"]["suggestion"]["status"] == "approved"
    assert reviewed_restored_suggestion.json()["data"]["link"]["target_type"] == "thread"
    assert reviewed_restored_suggestion.json()["data"]["link"]["target_id"] == restored_thread["id"]
    assert reviewed_restored_suggestion.json()["data"]["duplicate_link"] is False
    restored_relation = restored_relations.json()["data"]["items"][0]
    assert restored_relation["relation"]["relation_type"] == "supports"
    assert restored_relation["relation"]["source_fact_id"] == restored_source["id"]
    assert restored_relation["relation"]["target_fact_id"] != target.json()["data"]["id"]
    assert (
        restored_relation["related_fact"]["text"]
        == "SNAPSHOT_RELATION_TARGET: relations survive memory_scope snapshots."
    )


def test_memory_scope_snapshot_import_accepts_legacy_anchor_relation_payload(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        source = client.post(
            "/v1/facts",
            json={
                "space_slug": "legacy-snapshots",
                "memory_scope_external_ref": "source-memory_scope",
                "text": "LEGACY_SNAPSHOT_SOURCE: anchor and relation defaults survive.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "legacy-source"}],
            },
            headers=auth_headers(),
        )
        target = client.post(
            "/v1/facts",
            json={
                "space_slug": "legacy-snapshots",
                "memory_scope_external_ref": "source-memory_scope",
                "text": "LEGACY_SNAPSHOT_TARGET: relation target survives.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "legacy-target"}],
            },
            headers=auth_headers(),
        )
        relation = client.post(
            f"/v1/facts/{source.json()['data']['id']}/relations",
            json={
                "target_fact_id": target.json()["data"]["id"],
                "relation_type": "supports",
                "reason": "Legacy snapshot relation did not have temporal fields.",
            },
            headers=auth_headers(),
        )
        anchor = client.post(
            "/v1/anchors",
            json={
                "space_slug": "legacy-snapshots",
                "memory_scope_external_ref": "source-memory_scope",
                "kind": "organization",
                "label": "Legacy OpenAI",
                "aliases": ["Open AI"],
                "description": "Legacy snapshot anchor without lifecycle fields.",
            },
            headers=auth_headers(),
        )
        exported = client.get(
            "/v1/export/memory_scope-snapshot",
            params={
                "space_slug": "legacy-snapshots",
                "memory_scope_external_ref": "source-memory_scope",
            },
            headers=auth_headers(),
        )
        snapshot = exported.json()["data"]
        snapshot["schema_version"] = 8
        for item in snapshot["anchors"]:
            item.pop("confidence", None)
            item.pop("evidence_refs", None)
            item.pop("observed_at", None)
            item.pop("valid_from", None)
            item.pop("valid_to", None)
        for item in snapshot["relations"]:
            item.pop("observed_at", None)
            item.pop("valid_from", None)
            item.pop("valid_to", None)

        imported = client.post(
            "/v1/export/memory_scope-snapshot/import",
            json={
                "space_slug": "legacy-snapshots-imported",
                "memory_scope_external_ref": "target-memory_scope",
                "snapshot": snapshot,
                "merge_strategy": "create_new_memory_scope",
                "dry_run": False,
                "confirmed": True,
            },
            headers=auth_headers(),
        )
        imported_memory_scope = imported.json()["data"]["created_memory_scope"]
        browser = client.get(
            "/v1/memory-browser",
            params={
                "space_slug": "legacy-snapshots-imported",
                "memory_scope_external_ref": imported_memory_scope["external_ref"],
                "limit": 20,
            },
            headers=auth_headers(),
        )
        restored_source = next(
            item
            for item in browser.json()["data"]["facts"]
            if item["text"] == "LEGACY_SNAPSHOT_SOURCE: anchor and relation defaults survive."
        )
        restored_relations = client.get(
            f"/v1/facts/{restored_source['id']}/relations",
            headers=auth_headers(),
        )

    assert source.status_code == 201
    assert target.status_code == 201
    assert relation.status_code == 201
    assert anchor.status_code == 200
    assert exported.status_code == 200
    assert imported.status_code == 200, imported.text
    assert imported.json()["data"]["status"] == "ok"
    assert imported.json()["data"]["merge_strategy"] == "create_new_memory_scope"
    assert imported.json()["data"]["imported"]["anchors"] == 1
    assert imported.json()["data"]["imported"]["relations"] == 1

    assert browser.status_code == 200
    data = browser.json()["data"]
    restored_anchor = data["anchors"][0]
    assert restored_anchor["id"] != anchor.json()["data"]["id"]
    assert restored_anchor["confidence"] == "medium"
    assert restored_anchor["evidence_refs"] == []
    assert restored_anchor["observed_at"] == restored_anchor["created_at"]
    assert restored_anchor["valid_from"] is None
    assert restored_anchor["valid_to"] is None

    assert restored_relations.status_code == 200
    restored_relation = restored_relations.json()["data"]["items"][0]["relation"]
    assert restored_relation["id"] != relation.json()["data"]["id"]
    assert restored_relation["relation_type"] == "supports"
    assert restored_relation["source_fact_id"] == restored_source["id"]
    assert restored_relation["target_fact_id"] != target.json()["data"]["id"]
    assert restored_relation["observed_at"] == restored_relation["created_at"]
    assert restored_relation["valid_from"] is None
    assert restored_relation["valid_to"] is None


def test_memory_scope_snapshot_import_dry_run_returns_conflict_preview(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        fact = client.post(
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
        client.post(
            "/v1/captures",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "source_agent": "memo-frontend",
                "source_kind": "manual",
                "event_type": "SnapshotConflictCapture",
                "actor_role": "user",
                "text": "SNAPSHOT_API_CAPTURE_CONFLICT: conflict preview includes captures.",
                "source_authority": "user_statement",
                "evidence_refs": [{"source_type": "fact", "source_id": fact.json()["data"]["id"]}],
                "idempotency_key": "snapshot-conflict-capture",
                "consolidate": False,
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
    assert data["conflict_count"] == 2
    assert preview["conflict_count"] == 2
    assert preview["conflicts"]["facts"] == [exported.json()["data"]["facts"][0]["id"]]
    assert preview["conflicts"]["captures"] == [exported.json()["data"]["captures"][0]["id"]]
    assert preview_data["preview"] == preview
    assert preview["would_import"]["facts"] == 1
    assert preview["would_import"]["captures"] == 0
    assert "conflicts_block_import" in preview["warnings"]


def test_memory_scope_snapshot_preview_returns_legacy_default_diagnostics(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        response = client.post(
            "/v1/export/memory_scope-snapshot/preview",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "restore-base",
                "snapshot": {
                    "schema_version": 7,
                    "facts": [{"id": "fact_source"}, {"id": "fact_target"}],
                    "anchors": [
                        {
                            "id": "anchor_legacy_alex",
                            "kind": "person",
                            "normalized_key": "alex",
                            "label": "Alex api-key should not leak",
                        }
                    ],
                    "relations": [
                        {
                            "id": "relation_legacy_supports",
                            "source_fact_id": "fact_source",
                            "target_fact_id": "fact_target",
                            "relation_type": "supports",
                        }
                    ],
                },
                "merge_strategy": "skip_existing",
            },
            headers=auth_headers(),
        )

    assert response.status_code == 200, response.text
    preview = response.json()["data"]["preview"]
    assert preview["diagnostics"] == {
        "migration_defaults_applied": {
            "anchor_confidence": 1,
            "anchor_evidence_refs": 1,
            "anchor_observed_at": 1,
            "anchor_valid_from": 1,
            "anchor_valid_to": 1,
            "relation_observed_at": 1,
            "relation_valid_from": 1,
            "relation_valid_to": 1,
        },
        "migration_defaults_applied_count": 8,
    }
    assert "migration_defaults_applied.anchor_confidence" in preview["warnings"]
    assert "api-key" not in repr(preview["diagnostics"])
    assert "api-key" not in repr(preview["warnings"])


def test_memory_scope_snapshot_import_remaps_reviewed_context_link_audit(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        original_fact = _create_fact(
            client,
            text="SNAPSHOT_REVIEW_ORIGINAL: original suggestion target.",
            source_id="snapshot-review-original",
        )
        override_fact = _create_fact(
            client,
            text="SNAPSHOT_REVIEW_OVERRIDE: reviewer override target.",
            source_id="snapshot-review-override",
        )
        corrected_fact = _create_fact(
            client,
            text="SNAPSHOT_REVIEW_CORRECTED: reviewer corrected target.",
            source_id="snapshot-review-corrected",
        )
        approved_capture = _create_review_capture(
            client,
            source_event_id="snapshot-review-approved-capture",
            text="Snapshot review capture should first suggest original target.",
        )
        rejected_capture = _create_review_capture(
            client,
            source_event_id="snapshot-review-rejected-capture",
            text="Snapshot review rejected capture should stay rejected after import.",
        )
        approved_candidate = _persist_fact_link_suggestion(
            client,
            source_id=approved_capture.json()["data"]["id"],
            target_id=original_fact.json()["data"]["id"],
            text="Snapshot review original target",
        )
        rejected_candidate = _persist_fact_link_suggestion(
            client,
            source_id=rejected_capture.json()["data"]["id"],
            target_id=original_fact.json()["data"]["id"],
            text="Snapshot review original target rejected",
        )
        approved = client.post(
            f"/v1/context-link-suggestions/{approved_candidate['suggestion_id']}/review",
            json={
                "action": "approve",
                "reason": "approved with reviewer override",
                "target_type": "fact",
                "target_id": override_fact.json()["data"]["id"],
                "relation_type": "supports",
                "confidence": "high",
                "link_reason": "reviewer selected override target",
            },
            headers=auth_headers(),
        )
        rejected = client.post(
            f"/v1/context-link-suggestions/{rejected_candidate['suggestion_id']}/review",
            json={"action": "reject", "reason": "not the right restored context"},
            headers=auth_headers(),
        )
        approved_link_id = approved.json()["data"]["link"]["id"]
        corrected_link = client.patch(
            f"/v1/context-links/{approved_link_id}",
            json={
                "target_type": "fact",
                "target_id": corrected_fact.json()["data"]["id"],
                "relation_type": "supports",
                "confidence": "medium",
                "reason": "manual correction after approval",
                "metadata": {"last_edit_source": "snapshot-review-test"},
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
                "memory_scope_external_ref": "restore-base",
                "snapshot": exported.json()["data"],
                "manifest": exported.json()["manifest"],
                "dry_run": False,
                "merge_strategy": "create_new_memory_scope",
                "confirmed": True,
                "source_name": "review-history-snapshot",
            },
            headers=auth_headers(),
        )
        created_memory_scope = imported.json()["data"]["created_memory_scope"]
        restored_facts = client.get(
            "/v1/facts",
            params={
                "space_slug": "agents",
                "memory_scope_external_ref": created_memory_scope["external_ref"],
            },
            headers=auth_headers(),
        )
        restored_suggestions = client.get(
            "/v1/context-link-suggestions",
            params={
                "space_slug": "agents",
                "memory_scope_external_ref": created_memory_scope["external_ref"],
                "statuses": "approved,rejected",
                "limit": "20",
            },
            headers=auth_headers(),
        )
        restored_links = client.get(
            "/v1/context-links",
            params={
                "space_slug": "agents",
                "memory_scope_external_ref": created_memory_scope["external_ref"],
                "status": "active",
                "limit": "20",
            },
            headers=auth_headers(),
        )

    assert original_fact.status_code == 201
    assert override_fact.status_code == 201
    assert corrected_fact.status_code == 201
    assert approved.status_code == 200, approved.text
    assert rejected.status_code == 200, rejected.text
    assert corrected_link.status_code == 200, corrected_link.text
    assert exported.status_code == 200
    assert exported.json()["counts"]["context_link_suggestions"] >= 2
    assert exported.json()["counts"]["context_links"] == 1
    assert imported.status_code == 200, imported.text
    assert imported.json()["data"]["imported"]["context_link_suggestions"] >= 2
    assert imported.json()["data"]["imported"]["context_links"] == 1
    assert restored_facts.status_code == 200
    fact_by_text = {item["text"]: item for item in restored_facts.json()["data"]}
    restored_original = fact_by_text["SNAPSHOT_REVIEW_ORIGINAL: original suggestion target."]
    restored_override = fact_by_text["SNAPSHOT_REVIEW_OVERRIDE: reviewer override target."]
    restored_corrected = fact_by_text["SNAPSHOT_REVIEW_CORRECTED: reviewer corrected target."]
    assert restored_suggestions.status_code == 200
    suggestions_by_status = {item["status"]: item for item in restored_suggestions.json()["data"]}
    restored_approved_suggestion = suggestions_by_status["approved"]
    restored_rejected_suggestion = suggestions_by_status["rejected"]
    assert restored_approved_suggestion["review_reason"] == "approved with reviewer override"
    assert restored_approved_suggestion["reviewed_at"]
    assert restored_approved_suggestion["target_id"] == restored_original["id"]
    assert restored_approved_suggestion["metadata"]["approved_override"] is True
    assert restored_approved_suggestion["metadata"]["original_target_id"] == restored_original["id"]
    assert restored_approved_suggestion["metadata"]["approved_target_id"] == restored_override["id"]
    approved_review_event = restored_approved_suggestion["metadata"]["review_events"][-1]
    assert approved_review_event["suggestion_id"] == restored_approved_suggestion["id"]
    assert approved_review_event["source_id"] == restored_approved_suggestion["source_id"]
    assert approved_review_event["target_id"] == restored_original["id"]
    assert approved_review_event["approved_override"] is True
    assert approved_review_event["original_target_id"] == restored_original["id"]
    assert approved_review_event["approved_target_id"] == restored_override["id"]
    assert approved_review_event["approved_relation_type"] == "supports"
    assert approved_review_event["action"] == "approve"
    assert approved_review_event["new_status"] == "approved"
    assert restored_rejected_suggestion["review_reason"] == "not the right restored context"
    assert restored_rejected_suggestion["reviewed_at"]
    rejected_review_event = restored_rejected_suggestion["metadata"]["review_events"][-1]
    assert rejected_review_event["suggestion_id"] == restored_rejected_suggestion["id"]
    assert rejected_review_event["source_id"] == restored_rejected_suggestion["source_id"]
    assert rejected_review_event["target_id"] == restored_rejected_suggestion["target_id"]
    assert rejected_review_event["action"] == "reject"
    assert rejected_review_event["new_status"] == "rejected"
    assert restored_links.status_code == 200
    restored_link = restored_links.json()["data"][0]
    assert restored_link["target_id"] == restored_corrected["id"]
    assert (
        restored_link["metadata"]["approved_from_suggestion_id"]
        == restored_approved_suggestion["id"]
    )
    assert restored_link["metadata"]["original_target_id"] == restored_original["id"]
    assert restored_link["metadata"]["approved_target_id"] == restored_override["id"]
    edit_event = restored_link["metadata"]["edit_events"][-1]
    assert edit_event["previous"]["target_id"] == restored_override["id"]
    assert edit_event["next"]["target_id"] == restored_corrected["id"]


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


def test_memory_scope_snapshot_import_rejects_manifest_count_mismatch(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        client.post(
            "/v1/facts",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "source-memory_scope",
                "text": "SNAPSHOT_API_COUNT_MARKER: manifest catches summary drift.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "snapshot-count"}],
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
        manifest = exported.json()["manifest"]
        manifest["counts"]["facts"] = 99
        imported = client.post(
            "/v1/export/memory_scope-snapshot/import",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "restore-base",
                "snapshot": exported.json()["data"],
                "manifest": manifest,
                "dry_run": True,
            },
            headers=auth_headers(),
        )
        previewed = client.post(
            "/v1/export/memory_scope-snapshot/preview",
            json={
                "space_slug": "agents",
                "memory_scope_external_ref": "restore-base",
                "snapshot": exported.json()["data"],
                "manifest": manifest,
            },
            headers=auth_headers(),
        )

    assert imported.status_code == 400
    assert previewed.status_code == 400
    assert "manifest verification failed" in imported.text
    assert "snapshot_sha256_mismatch" not in imported.text
    assert "count_mismatch:facts" in imported.text
    assert "count_mismatch:facts" in previewed.text


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


def _create_fact(client: TestClient, *, text: str, source_id: str) -> Any:
    return client.post(
        "/v1/facts",
        json={
            "space_slug": "agents",
            "memory_scope_external_ref": "source-memory_scope",
            "thread_external_ref": "snapshot-review",
            "text": text,
            "kind": "note",
            "source_refs": [{"source_type": "manual", "source_id": source_id}],
            "tags": ["snapshot", "review"],
        },
        headers={**auth_headers(), "Idempotency-Key": source_id},
    )


def _create_review_capture(
    client: TestClient,
    *,
    source_event_id: str,
    text: str,
) -> Any:
    return client.post(
        "/v1/captures",
        json={
            "space_slug": "agents",
            "memory_scope_external_ref": "source-memory_scope",
            "thread_external_ref": "snapshot-review",
            "source_agent": "memo-frontend",
            "source_kind": "manual",
            "event_type": "SnapshotReviewCapture",
            "actor_role": "user",
            "source_event_id": source_event_id,
            "text": text,
            "source_authority": "user_statement",
            "consolidate": False,
        },
        headers=auth_headers(),
    )


def _persist_fact_link_suggestion(
    client: TestClient,
    *,
    source_id: str,
    target_id: str,
    text: str,
) -> dict[str, Any]:
    response = client.post(
        "/v1/link-suggestions",
        json={
            "space_slug": "agents",
            "memory_scope_external_ref": "source-memory_scope",
            "thread_external_ref": "snapshot-review",
            "source_type": "capture",
            "source_id": source_id,
            "text": text,
            "persist": True,
            "limit": 10,
        },
        headers=auth_headers(),
    )
    assert response.status_code == 200, response.text
    return next(
        item
        for item in response.json()["data"]["candidates"]
        if item["target_type"] == "fact" and item["target_id"] == target_id
    )
