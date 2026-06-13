import subprocess
import sys
import time
from pathlib import Path

import httpx
from memo_stack_server_harness import run_memo_stack_server


def test_asset_extraction_http_worker_e2e(tmp_path: Path) -> None:
    with (
        run_memo_stack_server(
            tmp_path,
            database_name="asset-extraction-e2e.db",
            extra_env={"MEMORY_ASSET_STORAGE_DIR": str(tmp_path / "assets")},
        ) as server,
        httpx.Client(
            base_url=server.base_url,
            headers={"Authorization": f"Bearer {server.token}"},
            timeout=5,
        ) as client,
    ):
        marker = f"ASSET_EXTRACTION_E2E_{time.time_ns()}"
        text = (
            f"{marker}: screenshot notes should become searchable extracted "
            "evidence tied to the uploaded asset."
        )
        upload = client.post(
            "/v1/assets",
            params={
                "space_slug": "asset-extraction-e2e",
                "memory_scope_external_ref": "frontend",
                "thread_external_ref": "quick-capture",
                "filename": "capture-note.txt",
                "extract": "true",
            },
            content=text.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
        )
        assert upload.status_code == 201, upload.text
        extraction_id = upload.json()["data"]["extraction"]["id"]

        worker = subprocess.run(
            [
                sys.executable,
                "-m",
                "memo_stack_server.worker",
                "--once",
                "--limit",
                "10",
            ],
            env=server.env,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        assert worker.returncode == 0, worker.stdout + worker.stderr

        extracted = client.get(f"/v1/asset-extractions/{extraction_id}")
        assert extracted.status_code == 200, extracted.text
        extraction = extracted.json()["data"]
        assert extraction["status"] == "succeeded"
        assert extraction["parser_name"] == "simple_text"
        assert len(extraction["result_document_ids"]) == 1
        assert {item["artifact_type"] for item in extraction["artifacts"]} == {
            "extracted_json",
            "markdown",
        }
        markdown_artifact = next(
            item for item in extraction["artifacts"] if item["artifact_type"] == "markdown"
        )

        chunks = client.get(f"/v1/documents/{extraction['result_document_ids'][0]}/chunks")
        assert chunks.status_code == 200, chunks.text
        chunk_text = " ".join(item["text"] for item in chunks.json()["data"])
        assert marker in chunk_text
        assert "searchable extracted evidence" in chunk_text

        scope_list = client.get(
            "/v1/asset-extractions",
            params={
                "space_slug": "asset-extraction-e2e",
                "memory_scope_external_ref": "frontend",
                "thread_external_ref": "quick-capture",
            },
        )
        assert scope_list.status_code == 200, scope_list.text
        assert scope_list.json()["data"][0]["id"] == extraction_id

        artifact_download = client.get(
            f"/v1/extraction-artifacts/{markdown_artifact['id']}/download"
        )
        assert artifact_download.status_code == 200, artifact_download.text
        assert marker.encode("utf-8") in artifact_download.content
