import asyncio
import shutil
import wave
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from memo_stack_server.config import CaptureMode, DeployProfile, Settings
from memo_stack_server.main import create_app
from memo_stack_server.worker import OutboxWorker


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


def sample_wav_bytes(seconds: int = 1) -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 8000 * seconds)
    return buffer.getvalue()


def test_media_api_without_external_ai_falls_back_to_local_media_metadata(
    tmp_path: Path,
) -> None:
    if not shutil.which("ffprobe"):
        pytest.skip("ffprobe is not available")

    with make_client(
        tmp_path,
        extraction_default_profile="media_api",
        extraction_external_ai_enabled=False,
        transcription_provider="openai",
    ) as client:
        upload = client.post(
            "/v1/assets",
            params={
                "space_slug": "quick-capture",
                "memory_scope_external_ref": "frontend",
                "thread_external_ref": "voice-notes",
                "filename": "voice-note.wav",
                "extract": "true",
                "estimated_media_seconds": 1,
            },
            content=sample_wav_bytes(),
            headers=auth_headers({"Content-Type": "audio/wav"}),
        )
        assert upload.status_code == 201, upload.text
        extraction_id = upload.json()["data"]["extraction"]["id"]

        processed = asyncio.run(OutboxWorker(client.app.state.container).run_once(limit=10))
        assert processed >= 1

        fetched = client.get(
            f"/v1/asset-extractions/{extraction_id}",
            headers=auth_headers(),
        )
        assert fetched.status_code == 200, fetched.text
        extracted = fetched.json()["data"]
        assert extracted["status"] == "succeeded"
        assert extracted["parser_profile"] == "media_api"
        assert extracted["parser_name"] == "media_metadata"
        assert extracted["safe_error_code"] is None
        assert extracted["metadata"]["degraded_fallback"] is True
        assert extracted["metadata"]["transcript_status"] == "disabled"
        assert (
            extracted["metadata"]["transcript_error_code"]
            == "asset_extraction.transcription_external_ai_disabled"
        )
        assert extracted["metadata"]["duration_seconds"] > 0
        assert extracted["progress"]["terminal"] is True
        assert extracted["execution"]["retry_after_at"] is None
        assert extracted["execution"]["retry_disposition"] is None
        assert {item["artifact_type"] for item in extracted["artifacts"]} == {
            "extracted_json",
            "markdown",
            "media_manifest",
        }
        assert extracted["usage"]["media_analysis_seconds_requested"] == 1
        assert extracted["usage"]["media_analysis_seconds_actual"] == 1
        assert extracted["usage"]["reconciled"] is True


def test_media_api_over_duration_limit_is_terminal_unsupported_and_reconciles_quota(
    tmp_path: Path,
) -> None:
    if not shutil.which("ffprobe"):
        pytest.skip("ffprobe is not available")

    with make_client(
        tmp_path,
        extraction_default_profile="media_api",
        extraction_external_ai_enabled=True,
        extraction_max_media_seconds=1,
        openai_api_key="not-used-because-duration-is-checked-before-provider-call",
        transcription_provider="openai",
    ) as client:
        upload = client.post(
            "/v1/assets",
            params={
                "space_slug": "quick-capture",
                "memory_scope_external_ref": "frontend",
                "thread_external_ref": "voice-notes",
                "filename": "too-long-voice-note.wav",
                "extract": "true",
                "estimated_media_seconds": 2,
            },
            content=sample_wav_bytes(seconds=2),
            headers=auth_headers({"Content-Type": "audio/wav"}),
        )
        assert upload.status_code == 201, upload.text
        extraction = upload.json()["data"]["extraction"]
        assert extraction["usage"]["media_analysis_seconds_requested"] == 2

        processed = asyncio.run(OutboxWorker(client.app.state.container).run_once(limit=10))
        assert processed >= 1

        fetched = client.get(
            f"/v1/asset-extractions/{extraction['id']}",
            headers=auth_headers(),
        )
        assert fetched.status_code == 200, fetched.text
        extracted = fetched.json()["data"]
        assert extracted["status"] == "unsupported"
        assert extracted["safe_error_code"] == "asset_extraction.media_too_long"
        assert extracted["result_document_ids"] == []
        assert extracted["artifacts"] == []
        assert extracted["progress"] == {
            "stage": "unsupported",
            "percent": 100,
            "message": "Asset type is unsupported",
            "terminal": True,
        }
        assert extracted["execution"]["retry_after_at"] is None
        assert extracted["execution"]["retry_disposition"] == "permanent"
        assert extracted["usage"]["media_analysis_seconds_requested"] == 2
        assert extracted["usage"]["media_analysis_seconds_actual"] == 0
        assert extracted["usage"]["media_analysis_seconds_delta"] == -2
        assert extracted["usage"]["media_analysis_seconds_final"] == 0
        assert extracted["usage"]["reconciled"] is True

        usage = client.get(
            "/v1/usage",
            params={"space_slug": "quick-capture"},
            headers=auth_headers(),
        )
        assert usage.status_code == 200, usage.text
        assert usage.json()["data"]["resources"][0]["used"] == 0
