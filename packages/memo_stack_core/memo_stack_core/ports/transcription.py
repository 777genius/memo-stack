"""Provider-neutral speech transcription ports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class SpeechTranscriptionRequest:
    job_id: str
    asset_id: str
    filename: str
    content_type: str
    byte_size: int
    sha256_hex: str
    content: bytes
    max_output_chars: int
    prompt: str | None = None


@dataclass(frozen=True)
class SpeechTranscriptSegment:
    text: str
    start_ms: int | None = None
    end_ms: int | None = None
    confidence: float | None = None
    speaker: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SpeechTranscriptionResult:
    status: str
    text: str = ""
    segments: tuple[SpeechTranscriptSegment, ...] = ()
    language: str | None = None
    duration_seconds: float | None = None
    provider_name: str = "unknown"
    provider_model: str | None = None
    provider_version: str | None = None
    diagnostics: dict[str, object] = field(default_factory=dict)
    safe_error_code: str | None = None
    safe_error_message: str | None = None


class SpeechTranscriptionPort(Protocol):
    async def transcribe(
        self,
        request: SpeechTranscriptionRequest,
    ) -> SpeechTranscriptionResult:
        """Transcribe an audio or video asset through a provider-neutral boundary."""
