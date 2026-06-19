import asyncio
import base64
import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from infinity_context_adapters.extraction.openai_vision import (
    OPENAI_VISION_MAX_PROVIDER_BINARY_BYTES,
    OpenAIImageVisionAdapter,
)
from infinity_context_adapters.extraction.transcription.openai_adapter import (
    OpenAISpeechTranscriptionAdapter,
    openai_transcription_request_contract,
)
from infinity_context_core.ports.transcription import SpeechTranscriptionRequest
from infinity_context_core.ports.vision import ImageVisionRequest

_IMAGE_BYTES = b"\x89PNG\r\n\x1a\nfake image bytes"
_AUDIO_BYTES = b"RIFF0000WAVEfake audio bytes"


def test_openai_transcription_request_contract_documents_model_shapes() -> None:
    assert openai_transcription_request_contract("gpt-4o-mini-transcribe") == {
        "chunking_strategy": None,
        "requires_chunking_strategy": False,
        "response_format": "json",
        "speaker_segments_supported": False,
        "supports_prompt": True,
        "supports_segment_timestamps": False,
        "timestamp_granularities": [],
    }
    assert openai_transcription_request_contract("whisper-1") == {
        "chunking_strategy": None,
        "requires_chunking_strategy": False,
        "response_format": "verbose_json",
        "speaker_segments_supported": False,
        "supports_prompt": True,
        "supports_segment_timestamps": True,
        "timestamp_granularities": ["segment"],
    }
    assert openai_transcription_request_contract("gpt-4o-transcribe-diarize") == {
        "chunking_strategy": "auto",
        "requires_chunking_strategy": True,
        "response_format": "diarized_json",
        "speaker_segments_supported": True,
        "supports_prompt": False,
        "supports_segment_timestamps": False,
        "timestamp_granularities": [],
    }


def test_openai_vision_adapter_sends_structured_responses_contract() -> None:
    responses = _RecordingVisionResponses(
        output_text=json.dumps(
            {
                "summary": "Screenshot shows MemoryScope review for Project Atlas.",
                "visible_text": ["Project Atlas", "Review suggestions"],
                "screenshot_ui_summary": "Review modal with suggested links.",
                "suggested_tags": ["atlas", "review"],
                "regions": [
                    {
                        "kind": "visible_text",
                        "text": "Project Atlas",
                        "bbox": [0.1, 0.2, 0.8, 0.4],
                        "confidence": 0.92,
                    }
                ],
            }
        )
    )
    client = _VisionClient(responses=responses)
    adapter = OpenAIImageVisionAdapter(
        api_key=None,
        model="gpt-4.1-mini",
        detail="low",
        client_factory=lambda: client,
        max_output_tokens=321,
        request_timeout_seconds=3,
    )

    result = asyncio.run(adapter.analyze(_vision_request()))

    assert result.status == "succeeded"
    assert result.payload_status == "parsed"
    assert result.provider_name == "openai_vision"
    assert result.provider_model == "gpt-4.1-mini"
    assert result.diagnostics == {
        "detail": "low",
        "payload_bounded": True,
        "request_timeout_seconds": 3.0,
    }
    assert result.payload["summary"] == "Screenshot shows MemoryScope review for Project Atlas."
    assert result.payload["visible_text"] == ["Project Atlas", "Review suggestions"]
    assert result.payload["regions"] == [
        {
            "kind": "visible_text",
            "text": "Project Atlas",
            "bbox": [0.1, 0.2, 0.8, 0.4],
            "confidence": 0.92,
        }
    ]
    assert client.closed is True

    call = responses.calls[0]
    assert call["model"] == "gpt-4.1-mini"
    assert call["max_output_tokens"] == 321
    assert call["store"] is False
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["strict"] is True
    assert call["text"]["format"]["schema"]["additionalProperties"] is False

    content = call["input"][0]["content"]
    assert content[0]["type"] == "input_text"
    assert "untrusted evidence" in content[0]["text"]
    assert content[1]["type"] == "input_image"
    assert content[1]["detail"] == "low"
    assert content[1]["image_url"].startswith("data:image/png;base64,")
    encoded = content[1]["image_url"].removeprefix("data:image/png;base64,")
    assert base64.b64decode(encoded) == _IMAGE_BYTES


def test_openai_vision_adapter_falls_back_to_bounded_text_payload_for_non_json() -> None:
    adapter = OpenAIImageVisionAdapter(
        api_key=None,
        model="gpt-4.1-mini",
        client_factory=lambda: _VisionClient(
            responses=_RecordingVisionResponses(
                output_text="Plain provider text about Alex and Project Atlas."
            )
        ),
    )

    result = asyncio.run(adapter.analyze(_vision_request()))

    assert result.status == "succeeded"
    assert result.payload_status == "fallback_text"
    assert result.payload["summary"] == "Plain provider text about Alex and Project Atlas."
    assert result.payload["visible_text"] == []
    assert result.payload["regions"] == []


def test_openai_vision_adapter_rejects_large_provider_payload_without_provider_call() -> None:
    provider_called = False

    def client_factory() -> _VisionClient:
        nonlocal provider_called
        provider_called = True
        return _VisionClient(responses=_RecordingVisionResponses(output_text="{}"))

    adapter = OpenAIImageVisionAdapter(
        api_key=None,
        model="gpt-4.1-mini",
        client_factory=client_factory,
    )

    result = asyncio.run(
        adapter.analyze(
            _vision_request(byte_size=OPENAI_VISION_MAX_PROVIDER_BINARY_BYTES + 1)
        )
    )

    assert provider_called is False
    assert result.status == "unsupported"
    assert result.safe_error_code == "asset_extraction.vision_provider_payload_too_large"
    assert result.diagnostics["provider_retryable"] is False
    assert (
        result.diagnostics["max_provider_binary_upload_bytes"]
        == OPENAI_VISION_MAX_PROVIDER_BINARY_BYTES
    )


def test_openai_vision_adapter_returns_safe_diagnostics_for_provider_errors() -> None:
    secret = "sk-proj-vision-secret-value-1234567890"
    adapter = OpenAIImageVisionAdapter(
        api_key="test-key",
        model="gpt-4.1-mini",
        client_factory=lambda: _VisionClient(
            responses=_FailingVisionResponses(
                _ProviderError(
                    status_code=401,
                    code="invalid_api_key",
                    message=f"invalid Authorization Bearer {secret}",
                )
            )
        ),
    )

    result = asyncio.run(adapter.analyze(_vision_request()))

    assert result.status == "unsupported"
    assert result.safe_error_code == "asset_extraction.vision.invalid_api_key"
    assert result.safe_error_message == "OpenAI image understanding failed"
    assert result.diagnostics["provider_retryable"] is False
    assert secret not in json.dumps(result.diagnostics)
    assert secret not in (result.safe_error_message or "")


def test_openai_transcription_adapter_sends_audio_contract_and_parses_timecodes() -> None:
    transcriptions = _RecordingAudioTranscriptions(
        response=_TranscriptionResponse(
            text="Alex confirmed the Project Atlas launch scope.",
            language="en",
            duration=4.5,
            segments=[
                {
                    "id": "seg_1",
                    "start": 0.0,
                    "end": 2.25,
                    "text": "Alex confirmed the Project Atlas launch scope.",
                    "avg_logprob": -0.3,
                },
                {"start": 2.25, "end": 4.5, "text": "Memory should link to the call."},
            ],
            words=[
                {"word": "Alex", "start": 0.0, "end": 0.4},
                {"word": "Atlas", "start": 1.5, "end": 1.9},
            ],
            usage={"input_tokens": 11, "output_tokens": 7},
        )
    )
    client = _TranscriptionClient(transcriptions=transcriptions)
    adapter = OpenAISpeechTranscriptionAdapter(
        api_key=None,
        model="gpt-4o-mini-transcribe",
        client_factory=lambda: client,
        prompt="Prefer project and people names.",
        request_timeout_seconds=4,
    )

    result = asyncio.run(
        adapter.transcribe(
            _speech_request(filename="meeting", content_type="audio/mpeg")
        )
    )

    assert result.status == "succeeded"
    assert result.text == "Alex confirmed the Project Atlas launch scope."
    assert result.language == "en"
    assert result.duration_seconds == 4.5
    assert result.provider_name == "openai_transcription"
    assert result.provider_model == "gpt-4o-mini-transcribe"
    assert result.diagnostics == {
        "request_timeout_seconds": 4.0,
        "response_format": "json",
        "usage": {"input_tokens": 11, "output_tokens": 7},
    }
    assert result.segments[0].start_ms == 0
    assert result.segments[0].end_ms == 2250
    assert result.segments[0].confidence == 0.97
    assert result.segments[0].metadata["id"] == "seg_1"
    assert result.words[1].word == "Atlas"
    assert result.words[1].start_ms == 1500
    assert client.closed is True

    call = transcriptions.calls[0]
    assert call["model"] == "gpt-4o-mini-transcribe"
    assert call["response_format"] == "json"
    assert call["prompt"] == "Prefer project and people names."
    assert call["file"].name == "meeting.mp3"
    assert call["file"].read() == _AUDIO_BYTES
    assert "timestamp_granularities" not in call
    assert "chunking_strategy" not in call


def test_openai_transcription_adapter_uses_diarize_contract_without_prompt() -> None:
    transcriptions = _RecordingAudioTranscriptions(
        response=_TranscriptionResponse(
            text="Agent: Memory scope is ready.",
            segments=[
                {
                    "type": "transcript.text.segment",
                    "speaker": "agent",
                    "start": 0.0,
                    "end": 1.5,
                    "text": "Memory scope is ready.",
                }
            ],
        )
    )
    adapter = OpenAISpeechTranscriptionAdapter(
        api_key=None,
        model="gpt-4o-transcribe-diarize",
        client_factory=lambda: _TranscriptionClient(transcriptions=transcriptions),
        prompt="Must not be sent with diarize model.",
    )

    result = asyncio.run(adapter.transcribe(_speech_request(filename="call.mp3")))

    assert result.status == "succeeded"
    assert result.diagnostics["response_format"] == "diarized_json"
    assert result.diagnostics["chunking_strategy"] == "auto"
    assert result.segments[0].speaker == "agent"
    call = transcriptions.calls[0]
    assert call["response_format"] == "diarized_json"
    assert call["chunking_strategy"] == "auto"
    assert "prompt" not in call


def test_openai_transcription_adapter_returns_safe_diagnostics_for_provider_errors() -> None:
    secret = "sk-proj-transcription-secret-value-1234567890"
    adapter = OpenAISpeechTranscriptionAdapter(
        api_key="test-key",
        model="gpt-4o-mini-transcribe",
        client_factory=lambda: _TranscriptionClient(
            transcriptions=_FailingAudioTranscriptions(
                _ProviderError(
                    status_code=429,
                    code="rate_limit_exceeded",
                    message=f"rate limit for Bearer {secret}",
                )
            )
        ),
    )

    result = asyncio.run(adapter.transcribe(_speech_request()))

    assert result.status == "unsupported"
    assert result.safe_error_code == "asset_extraction.transcription.rate_limited"
    assert result.safe_error_message == "OpenAI speech transcription failed"
    assert result.diagnostics["provider_retryable"] is True
    assert secret not in json.dumps(result.diagnostics)
    assert secret not in (result.safe_error_message or "")


def test_openai_transcription_adapter_handles_empty_output_as_degraded_contract() -> None:
    adapter = OpenAISpeechTranscriptionAdapter(
        api_key=None,
        model="gpt-4o-mini-transcribe",
        client_factory=lambda: _TranscriptionClient(
            transcriptions=_RecordingAudioTranscriptions(
                response=_TranscriptionResponse(text="   ")
            )
        ),
    )

    result = asyncio.run(adapter.transcribe(_speech_request()))

    assert result.status == "unsupported"
    assert result.safe_error_code == "asset_extraction.transcription_empty_output"
    assert result.safe_error_message == "OpenAI speech transcription returned no text"


class _RecordingVisionResponses:
    def __init__(self, *, output_text: str) -> None:
        self.output_text = output_text
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=self.output_text)


class _FailingVisionResponses:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    async def create(self, **_kwargs: Any) -> object:
        raise self.exc


class _VisionClient:
    def __init__(self, *, responses: object) -> None:
        self.responses = responses
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


@dataclass(frozen=True)
class _TranscriptionResponse:
    text: str
    language: str | None = None
    duration: float | None = None
    segments: list[dict[str, object]] | None = None
    words: list[dict[str, object]] | None = None
    usage: dict[str, object] | None = None


class _RecordingAudioTranscriptions:
    def __init__(self, *, response: _TranscriptionResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _TranscriptionResponse:
        self.calls.append(kwargs)
        return self.response


class _FailingAudioTranscriptions:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    async def create(self, **_kwargs: Any) -> object:
        raise self.exc


class _AudioClient:
    def __init__(self, *, transcriptions: object) -> None:
        self.transcriptions = transcriptions


class _TranscriptionClient:
    def __init__(self, *, transcriptions: object) -> None:
        self.audio = _AudioClient(transcriptions=transcriptions)
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class _ProviderError(Exception):
    def __init__(
        self,
        *,
        status_code: int | None,
        code: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def _vision_request(*, byte_size: int | None = None) -> ImageVisionRequest:
    return ImageVisionRequest(
        job_id="extract_vision_contract",
        asset_id="asset_vision_contract",
        filename="screenshot.png",
        content_type="image/png",
        byte_size=byte_size if byte_size is not None else len(_IMAGE_BYTES),
        sha256_hex="a" * 64,
        content=_IMAGE_BYTES,
        max_output_chars=4000,
    )


def _speech_request(
    *,
    filename: str = "voice-note.wav",
    content_type: str = "audio/wav",
) -> SpeechTranscriptionRequest:
    return SpeechTranscriptionRequest(
        job_id="extract_transcription_contract",
        asset_id="asset_transcription_contract",
        filename=filename,
        content_type=content_type,
        byte_size=len(_AUDIO_BYTES),
        sha256_hex="b" * 64,
        content=_AUDIO_BYTES,
        max_output_chars=4000,
    )
