import asyncio
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from infinity_context_server.config import CaptureMode, DeployProfile, Settings
from infinity_context_server.main import create_app
from infinity_context_server.worker import OutboxWorker


def test_context_api_expands_approved_media_manifest_artifact_link(tmp_path: Path) -> None:
    marker = "LINKED_ARTIFACT_MARKER"
    with make_client(tmp_path) as client:
        upload = client.post(
            "/v1/assets",
            params={
                "space_slug": "linked-artifact-context",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "alex-review",
                "filename": "alex-review.pdf",
                "extract": "true",
            },
            content=sample_pdf_bytes(f"{marker} Alex last week approved the Atlas billing cutoff."),
            headers=auth_headers({"Content-Type": "application/pdf"}),
        )
        assert upload.status_code == 201, upload.text
        extraction_id = upload.json()["data"]["extraction"]["id"]

        processed = asyncio.run(OutboxWorker(client.app.state.container).run_once(limit=10))
        assert processed >= 1

        extraction = client.get(
            f"/v1/asset-extractions/{extraction_id}",
            headers=auth_headers(),
        )
        assert extraction.status_code == 200, extraction.text
        extraction_data = extraction.json()["data"]
        assert extraction_data["status"] == "succeeded"
        manifest_artifact = next(
            item
            for item in extraction_data["artifacts"]
            if item["artifact_type"] == "media_manifest"
        )

        anchor = client.post(
            "/v1/anchors",
            json={
                "space_slug": "linked-artifact-context",
                "memory_scope_external_ref": "default",
                "kind": "event",
                "label": "Alex review",
                "confidence": "high",
                "metadata": {
                    "anchor_family": "event",
                    "event_type": "meeting",
                    "event_participant_label": "Alex",
                    "event_participant_canonical_key": "alex",
                    "event_temporal_phrase": "last week",
                    "event_temporal_hint_code": "last_week",
                    "event_identity_terms": ["alex", "last_week:1:week"],
                },
            },
            headers=auth_headers(),
        )
        assert anchor.status_code == 200, anchor.text

        link = client.post(
            "/v1/context-links",
            json={
                "space_slug": "linked-artifact-context",
                "memory_scope_external_ref": "default",
                "source_type": "anchor",
                "source_id": anchor.json()["data"]["id"],
                "target_type": "extraction_artifact",
                "target_id": manifest_artifact["id"],
                "relation_type": "evidence_of",
                "confidence": "high",
                "reason": "anchor is grounded by the exact extracted manifest evidence",
            },
            headers=auth_headers(),
        )
        assert link.status_code == 200, link.text

        context = client.post(
            "/v1/context",
            json={
                "space_slug": "linked-artifact-context",
                "memory_scope_external_ref": "default",
                "query": "Alex last week",
                "token_budget": 1200,
                "max_facts": 0,
                "max_chunks": 0,
                "max_evidence_items": 6,
            },
            headers=auth_headers(),
        )
        assert context.status_code == 200, context.text
        data = context.json()["data"]

    assert marker in data["rendered_text"]
    linked_items = [
        item
        for item in data["items"]
        if item["diagnostics"].get("retrieval_source")
        == "approved_context_linked_extraction_artifacts"
    ]
    assert len(linked_items) == 1
    assert linked_items[0]["diagnostics"]["context_link_relation_type"] == "evidence_of"
    assert linked_items[0]["source_refs"][0]["page_number"] == 1
    assert linked_items[0]["citations"][0]["page_number"] == 1
    assert data["diagnostics"]["approved_context_linked_extraction_artifacts_used"] == 1
    assert (
        data["diagnostics"]["approved_context_linked_extraction_artifact_manifest_items_used"] == 1
    )


def test_context_api_expands_approved_asset_link_to_media_manifest_evidence(
    tmp_path: Path,
) -> None:
    marker = "LINKED_ASSET_MARKER"
    with make_client(tmp_path) as client:
        upload = client.post(
            "/v1/assets",
            params={
                "space_slug": "linked-asset-context",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "alex-review",
                "filename": "alex-review.pdf",
                "extract": "true",
            },
            content=sample_pdf_bytes(f"{marker} Alex last week approved the Atlas billing cutoff."),
            headers=auth_headers({"Content-Type": "application/pdf"}),
        )
        assert upload.status_code == 201, upload.text
        asset = upload.json()["data"]
        extraction_id = asset["extraction"]["id"]

        processed = asyncio.run(OutboxWorker(client.app.state.container).run_once(limit=10))
        assert processed >= 1

        extraction = client.get(
            f"/v1/asset-extractions/{extraction_id}",
            headers=auth_headers(),
        )
        assert extraction.status_code == 200, extraction.text
        extraction_data = extraction.json()["data"]
        assert extraction_data["status"] == "succeeded"
        assert any(
            item["artifact_type"] == "media_manifest" for item in extraction_data["artifacts"]
        )

        anchor = client.post(
            "/v1/anchors",
            json={
                "space_slug": "linked-asset-context",
                "memory_scope_external_ref": "default",
                "kind": "event",
                "label": "Alex review",
                "confidence": "high",
                "metadata": {
                    "anchor_family": "event",
                    "event_type": "meeting",
                    "event_participant_label": "Alex",
                    "event_participant_canonical_key": "alex",
                    "event_temporal_phrase": "last week",
                    "event_temporal_hint_code": "last_week",
                    "event_identity_terms": ["alex", "last_week:1:week"],
                },
            },
            headers=auth_headers(),
        )
        assert anchor.status_code == 200, anchor.text

        link = client.post(
            "/v1/context-links",
            json={
                "space_slug": "linked-asset-context",
                "memory_scope_external_ref": "default",
                "source_type": "anchor",
                "source_id": anchor.json()["data"]["id"],
                "target_type": "asset",
                "target_id": asset["id"],
                "relation_type": "evidence_of",
                "confidence": "high",
                "reason": "anchor is grounded by the uploaded asset extraction evidence",
            },
            headers=auth_headers(),
        )
        assert link.status_code == 200, link.text

        context = client.post(
            "/v1/context",
            json={
                "space_slug": "linked-asset-context",
                "memory_scope_external_ref": "default",
                "query": "Alex last week",
                "token_budget": 1200,
                "max_facts": 0,
                "max_chunks": 0,
                "max_evidence_items": 6,
            },
            headers=auth_headers(),
        )
        assert context.status_code == 200, context.text
        data = context.json()["data"]

    assert marker in data["rendered_text"]
    assert "Linked file alex-review.pdf" not in data["rendered_text"]
    linked_items = [
        item
        for item in data["items"]
        if "approved_context_linked_asset_manifest_evidence"
        in item["diagnostics"].get("retrieval_sources", ())
    ]
    assert len(linked_items) == 1
    assert linked_items[0]["item_type"] == "extraction_artifact"
    assert linked_items[0]["diagnostics"]["retrieval_source"] == "artifact_evidence"
    assert linked_items[0]["diagnostics"]["ranking_reason"] == (
        "hybrid match via artifact_evidence, approved_context_linked_asset_manifest_evidence"
    )
    assert linked_items[0]["diagnostics"]["context_link_relation_type"] == "evidence_of"
    assert linked_items[0]["diagnostics"]["asset_id"] == asset["id"]
    assert linked_items[0]["diagnostics"]["provenance"]["context_link_relation_type"] == (
        "evidence_of"
    )
    assert linked_items[0]["source_refs"][0]["page_number"] == 1
    assert linked_items[0]["citations"][0]["page_number"] == 1
    assert linked_items[0]["citations"][0]["ranking_reason"] == (
        "hybrid match via artifact_evidence, approved_context_linked_asset_manifest_evidence"
    )
    assert data["top_evidence"]
    top = data["top_evidence"][0]
    assert top["item_id"] == linked_items[0]["item_id"]
    assert top["citation"]["page_number"] == 1
    assert "page_citation" in top["reasons"]
    assert "quote_preview" in top["reasons"]
    assert data["diagnostics"]["top_evidence_returned"] >= 1
    assert data["diagnostics"]["top_evidence_cited_count"] >= 1
    assert data["diagnostics"]["approved_context_linked_assets_used"] == 1
    assert data["diagnostics"]["approved_context_linked_asset_manifest_jobs_considered"] == 1
    assert data["diagnostics"]["approved_context_linked_asset_manifest_artifacts_considered"] >= 1
    assert data["diagnostics"]["approved_context_linked_asset_manifest_items_used"] == 1


def make_client(tmp_path: Path, **overrides: Any) -> TestClient:
    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'memory.db'}",
            auto_create_schema=True,
            service_token="test-token",
            capture_mode=CaptureMode.SUGGEST,
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
            asset_storage_dir=str(tmp_path / "assets"),
            **overrides,
        )
    )
    return TestClient(app)


def auth_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"Authorization": "Bearer test-token"}
    if extra:
        headers.update(extra)
    return headers


def sample_pdf_bytes(text: str) -> bytes:
    stream = f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        + f"5 0 obj << /Length {len(stream)} >> stream\n".encode("ascii")
        + stream
        + b"\nendstream endobj\nxref\n0 6\n0000000000 65535 f \n"
        b"0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
        b"0000000241 00000 n \n0000000311 00000 n \n"
        b"trailer << /Root 1 0 R /Size 6 >>\nstartxref\n449\n%%EOF\n"
    )
