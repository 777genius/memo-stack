from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from memo_stack_server.config import CaptureMode, DeployProfile, Settings
from memo_stack_server.main import create_app
from memo_stack_server.worker import OutboxWorker


def test_extraction_artifact_public_contract_hides_storage_key(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        upload = client.post(
            "/v1/assets",
            params={
                "space_slug": "quick-capture",
                "memory_scope_external_ref": "frontend",
                "thread_external_ref": "public-contract",
                "filename": "artifact-contract.txt",
                "extract": "true",
            },
            content=b"Artifact public contract should not leak storage keys.",
            headers=_auth_headers({"Content-Type": "text/plain"}),
        )
        assert upload.status_code == 201, upload.text
        extraction_id = upload.json()["data"]["extraction"]["id"]

        processed = asyncio.run(OutboxWorker(client.app.state.container).run_once(limit=10))
        assert processed >= 1

        fetched = client.get(
            f"/v1/asset-extractions/{extraction_id}",
            headers=_auth_headers(),
        )
        assert fetched.status_code == 200, fetched.text
        artifacts = fetched.json()["data"]["artifacts"]
        assert artifacts
        artifact = next(item for item in artifacts if item["artifact_type"] == "markdown")

        assert "storage_key" not in artifact
        assert artifact["download_path"] == f"/v1/extraction-artifacts/{artifact['id']}/download"
        assert artifact["storage_backend"] == "local"

        downloaded = client.get(artifact["download_path"], headers=_auth_headers())
        assert downloaded.status_code == 200, downloaded.text
        assert b"Artifact public contract should not leak storage keys." in downloaded.content


def _make_client(tmp_path: Path, **overrides: Any) -> TestClient:
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


def _auth_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"Authorization": "Bearer test-token"}
    if extra:
        headers.update(extra)
    return headers
