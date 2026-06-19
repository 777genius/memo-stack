import asyncio
import json
from dataclasses import replace
from typing import Any

from infinity_context_adapters.extraction.openai_vision import OpenAIImageVisionAdapter
from infinity_context_adapters.extraction.transcription.openai_adapter import (
    OPENAI_TRANSCRIPTION_SUPPORTED_FILE_SUFFIXES,
    OpenAISpeechTranscriptionAdapter,
)
from infinity_context_core.application.use_cases.asset_extraction_support import (
    is_permanent_error_code,
)
from infinity_context_core.ports.transcription import SpeechTranscriptionRequest
from infinity_context_core.ports.vision import ImageVisionRequest


class _ProviderError(Exception):
    def __init__(
        self,
        *,
        status_code: int | None = None,
        code: str = "",
        message: str = "provider failure with hidden details",
        body: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.body = body or {}


class _Transcriptions:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def create(self, **_kwargs: Any) -> object:
        raise self._exc


class _Audio:
    def __init__(self, exc: Exception) -> None:
        self.transcriptions = _Transcriptions(exc)


class _TranscriptionClient:
    def __init__(self, exc: Exception) -> None:
        self.audio = _Audio(exc)

    async def aclose(self) -> None:
        return None


class _Responses:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def create(self, **_kwargs: Any) -> object:
        raise self._exc


class _VisionClient:
    def __init__(self, exc: Exception) -> None:
        self.responses = _Responses(exc)

    async def aclose(self) -> None:
        return None


def test_openai_transcription_adapter_classifies_retryable_rate_limit() -> None:
    adapter = OpenAISpeechTranscriptionAdapter(
        api_key="test-key",
        model="gpt-4o-mini-transcribe",
        client_factory=lambda: _TranscriptionClient(
            _ProviderError(status_code=429, code="rate_limit_exceeded")
        ),
    )

    result = asyncio.run(adapter.transcribe(_speech_request()))

    assert result.status == "unsupported"
    assert result.safe_error_code == "asset_extraction.transcription.rate_limited"
    assert result.diagnostics["provider_retryable"] is True
    assert result.diagnostics["provider_error_type"] == "_ProviderError"
    assert "provider failure" not in repr(result.diagnostics)


def test_openai_transcription_adapter_classifies_permanent_invalid_api_key() -> None:
    raw_secret = "sk-proj-provider-secret-value1234567890"
    adapter = OpenAISpeechTranscriptionAdapter(
        api_key="test-key",
        model="gpt-4o-mini-transcribe",
        client_factory=lambda: _TranscriptionClient(
            _ProviderError(
                status_code=401,
                code="invalid_api_key",
                message=f"invalid Bearer {raw_secret}",
            )
        ),
    )

    result = asyncio.run(adapter.transcribe(_speech_request()))

    assert result.status == "unsupported"
    assert result.safe_error_code == "asset_extraction.transcription.invalid_api_key"
    assert result.diagnostics["provider_retryable"] is False
    assert is_permanent_error_code(result.safe_error_code)
    assert raw_secret not in json.dumps(result.diagnostics)


def test_openai_transcription_adapter_classifies_timeout_as_retryable_unavailable() -> None:
    adapter = OpenAISpeechTranscriptionAdapter(
        api_key="test-key",
        model="gpt-4o-mini-transcribe",
        client_factory=lambda: _TranscriptionClient(TimeoutError()),
    )

    result = asyncio.run(adapter.transcribe(_speech_request()))

    assert result.status == "unsupported"
    assert result.safe_error_code == "asset_extraction.transcription.provider_unavailable"
    assert result.diagnostics["provider_retryable"] is True
    assert result.diagnostics["request_timeout_seconds"] == 60.0


def test_openai_transcription_adapter_classifies_provider_quota_as_permanent() -> None:
    raw_secret = "sk-proj-quota-secret-value1234567890"
    adapter = OpenAISpeechTranscriptionAdapter(
        api_key="test-key",
        model="gpt-4o-mini-transcribe",
        client_factory=lambda: _TranscriptionClient(
            _ProviderError(
                status_code=429,
                message=f"quota exhausted for Bearer {raw_secret}",
                body={"error": {"code": "insufficient_quota", "type": "insufficient_quota"}},
            )
        ),
    )

    result = asyncio.run(adapter.transcribe(_speech_request()))

    assert result.status == "unsupported"
    assert result.safe_error_code == "asset_extraction.transcription.quota_exceeded"
    assert result.diagnostics["provider_retryable"] is False
    assert is_permanent_error_code(result.safe_error_code)
    assert raw_secret not in json.dumps(result.diagnostics)


def test_openai_transcription_adapter_accepts_documented_flac_and_ogg_types() -> None:
    adapter = OpenAISpeechTranscriptionAdapter(
        api_key="test-key",
        model="gpt-4o-mini-transcribe",
        client_factory=lambda: _TranscriptionClient(
            _ProviderError(status_code=503, code="unavailable")
        ),
    )

    for content_type in ("audio/flac", "audio/ogg"):
        result = asyncio.run(
            adapter.transcribe(replace(_speech_request(), content_type=content_type))
        )

        assert result.status == "unsupported"
        assert result.safe_error_code == "asset_extraction.transcription.provider_unavailable"

    assert ".flac" in OPENAI_TRANSCRIPTION_SUPPORTED_FILE_SUFFIXES
    assert ".ogg" in OPENAI_TRANSCRIPTION_SUPPORTED_FILE_SUFFIXES


def test_openai_vision_adapter_classifies_permanent_invalid_api_key() -> None:
    adapter = OpenAIImageVisionAdapter(
        api_key="test-key",
        model="gpt-4.1-mini",
        client_factory=lambda: _VisionClient(
            _ProviderError(status_code=401, code="invalid_api_key")
        ),
    )

    result = asyncio.run(adapter.analyze(_vision_request()))

    assert result.status == "unsupported"
    assert result.safe_error_code == "asset_extraction.vision.invalid_api_key"
    assert result.diagnostics["provider_retryable"] is False
    assert result.diagnostics["provider_error_type"] == "_ProviderError"
    assert is_permanent_error_code(result.safe_error_code)


def test_openai_vision_adapter_classifies_retryable_rate_limit() -> None:
    adapter = OpenAIImageVisionAdapter(
        api_key="test-key",
        model="gpt-4.1-mini",
        client_factory=lambda: _VisionClient(
            _ProviderError(status_code=429, code="rate_limit_exceeded")
        ),
    )

    result = asyncio.run(adapter.analyze(_vision_request()))

    assert result.status == "unsupported"
    assert result.safe_error_code == "asset_extraction.vision.rate_limited"
    assert result.diagnostics["provider_retryable"] is True
    assert result.diagnostics["provider_error_type"] == "_ProviderError"


def test_openai_vision_adapter_classifies_provider_quota_as_permanent() -> None:
    raw_secret = "sk-proj-vision-quota-secret-value1234567890"
    adapter = OpenAIImageVisionAdapter(
        api_key="test-key",
        model="gpt-4.1-mini",
        client_factory=lambda: _VisionClient(
            _ProviderError(
                status_code=429,
                code="insufficient_quota",
                message=f"vision quota Bearer {raw_secret}",
            )
        ),
    )

    result = asyncio.run(adapter.analyze(_vision_request()))

    assert result.status == "unsupported"
    assert result.safe_error_code == "asset_extraction.vision.quota_exceeded"
    assert result.diagnostics["provider_retryable"] is False
    assert is_permanent_error_code(result.safe_error_code)
    assert raw_secret not in json.dumps(result.diagnostics)


def test_openai_vision_adapter_classifies_timeout_as_retryable_unavailable() -> None:
    adapter = OpenAIImageVisionAdapter(
        api_key="test-key",
        model="gpt-4.1-mini",
        client_factory=lambda: _VisionClient(TimeoutError()),
    )

    result = asyncio.run(adapter.analyze(_vision_request()))

    assert result.status == "unsupported"
    assert result.safe_error_code == "asset_extraction.vision.provider_unavailable"
    assert result.diagnostics["provider_retryable"] is True
    assert result.diagnostics["request_timeout_seconds"] == 60.0


def _speech_request() -> SpeechTranscriptionRequest:
    return SpeechTranscriptionRequest(
        job_id="job_provider_error",
        asset_id="asset_provider_error",
        filename="voice.wav",
        content_type="audio/wav",
        byte_size=16,
        sha256_hex="a" * 64,
        content=b"fake audio bytes",
        max_output_chars=1000,
    )


def _vision_request() -> ImageVisionRequest:
    return ImageVisionRequest(
        job_id="job_provider_error",
        asset_id="asset_provider_error",
        filename="screenshot.png",
        content_type="image/png",
        byte_size=16,
        sha256_hex="b" * 64,
        content=b"fake image bytes",
        max_output_chars=1000,
    )
