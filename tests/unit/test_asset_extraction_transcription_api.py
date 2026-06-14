import asyncio
import json
import wave
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from memo_stack_adapters.extraction.transcription.openai_adapter import (
    OpenAISpeechTranscriptionAdapter,
)
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


class _FakeTranscriptionResponse:
    text = "Alex discussed memory scopes from a voice note."
    language = "en"
    duration = 1.0
    segments = [
        {
            "start": 0.0,
            "end": 1.0,
            "text": "Alex discussed memory scopes from a voice note.",
        }
    ]


class _FakeAudioTranscriptions:
    async def create(self, **kwargs: Any) -> _FakeTranscriptionResponse:
        assert kwargs["model"] == "gpt-4o-mini-transcribe"
        assert kwargs["response_format"] == "json"
        assert kwargs["file"].name == "voice-note.wav"
        return _FakeTranscriptionResponse()


class _FakeAudioClient:
    transcriptions = _FakeAudioTranscriptions()


class _FakeTranscriptionClient:
    audio = _FakeAudioClient()

    async def aclose(self) -> None:
        return None


def test_audio_asset_extraction_uses_api_first_transcription(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        OpenAISpeechTranscriptionAdapter,
        "_client",
        lambda self: _FakeTranscriptionClient(),
    )
    with make_client(
        tmp_path,
        extraction_external_ai_enabled=True,
        extraction_default_profile="media_api",
        openai_api_key="test-key",
        transcription_provider="openai",
        transcription_openai_model="gpt-4o-mini-transcribe",
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
        assert extracted["parser_name"] == "speech_transcription"
        assert extracted["model_version"] == "gpt-4o-mini-transcribe"
        assert extracted["metadata"]["transcript_status"] == "extracted"
        assert extracted["metadata"]["transcription_provider"] == "openai_transcription"
        assert extracted["usage"]["media_analysis_seconds_actual"] == 1
        assert {item["artifact_type"] for item in extracted["artifacts"]} == {
            "extracted_json",
            "markdown",
            "media_manifest",
            "transcript",
            "transcript_json",
        }
        transcript_json_artifact = next(
            item for item in extracted["artifacts"] if item["artifact_type"] == "transcript_json"
        )
        transcript_download = client.get(
            f"/v1/extraction-artifacts/{transcript_json_artifact['id']}/download",
            headers=auth_headers(),
        )
        assert transcript_download.status_code == 200, transcript_download.text
        transcript_payload = json.loads(transcript_download.content.decode("utf-8"))
        assert transcript_payload["schema_name"] == "memo_stack.transcript"
        assert transcript_payload["segments"][0]["start_ms"] == 0
        assert transcript_payload["segments"][0]["end_ms"] == 1000

        chunks = client.get(
            f"/v1/documents/{extracted['result_document_ids'][0]}/chunks",
            headers=auth_headers(),
        )
        assert chunks.status_code == 200, chunks.text
        first_chunk = chunks.json()["data"][0]
        assert "Alex discussed memory scopes" in first_chunk["text"]
        source_refs = first_chunk["source_refs"]
        assert source_refs[0]["source_type"] == "asset_extraction"
        assert source_refs[0]["asset_id"] == upload.json()["data"]["id"]
        assert source_refs[0]["time_start_ms"] == 0
        assert source_refs[0]["time_end_ms"] == 1000
