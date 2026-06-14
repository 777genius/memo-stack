"""Extraction engine that turns speech transcription results into memory evidence."""

from __future__ import annotations

from dataclasses import replace

from memo_stack_core.ports.extraction import (
    ExtractedElement,
    ExtractionArtifactCandidate,
    ExtractionRequest,
    ExtractionResult,
)
from memo_stack_core.ports.transcription import (
    SpeechTranscriptionPort,
    SpeechTranscriptionRequest,
    SpeechTranscriptSegment,
)

from memo_stack_adapters.extraction.content import (
    _MEDIA_TYPES,
    ExtractionEngine,
    SupportDecision,
    _format_timestamp_ms,
    _limit_text,
    _unsupported,
)
from memo_stack_adapters.extraction.media_tools import probe_media_with_ffprobe

_API_TRANSCRIPTION_PROFILES = {
    "media_api",
    "standard_asr",
    "standard_full",
    "full",
}


class SpeechTranscriptionExtractionEngine(ExtractionEngine):
    name = "speech_transcription"
    version = "v1"

    def __init__(self, *, transcription: SpeechTranscriptionPort) -> None:
        self._transcription = transcription

    async def supports(self, request: ExtractionRequest) -> SupportDecision:
        if not _profile_wants_api_transcription(request.parser_profile):
            return SupportDecision(False, reason="parser_profile_not_media_api")
        if not _is_media_content_type(request.detected_content_type):
            return SupportDecision(False, reason="not_audio_or_video")
        return SupportDecision(True)

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        probe = probe_media_with_ffprobe(request)
        if probe.duration_seconds and probe.duration_seconds > request.limits.max_media_seconds:
            return _fallback_unsupported(
                request,
                code="asset_extraction.transcription_media_too_long",
                message="Media duration exceeds transcription limit",
                metadata={
                    "duration_seconds": probe.duration_seconds,
                    "max_media_seconds": request.limits.max_media_seconds,
                },
            )
        if not request.limits.enable_external_ai:
            return _fallback_unsupported(
                request,
                code="asset_extraction.transcription_external_ai_disabled",
                message="External AI speech transcription is disabled",
                metadata=probe.metadata,
            )

        result = await self._transcription.transcribe(
            SpeechTranscriptionRequest(
                job_id=request.job_id,
                asset_id=request.asset_id,
                filename=request.filename,
                content_type=request.detected_content_type,
                byte_size=request.byte_size,
                sha256_hex=request.sha256_hex,
                content=request.content,
                max_output_chars=request.limits.max_output_chars,
            )
        )
        if result.status != "succeeded":
            return _fallback_unsupported(
                request,
                code=result.safe_error_code or "asset_extraction.transcription_failed",
                message=result.safe_error_message or "Speech transcription failed",
                metadata={
                    "transcription_provider": result.provider_name,
                    "transcription_model": result.provider_model,
                    **result.diagnostics,
                    **probe.metadata,
                },
            )

        text = _limit_text(result.text, request.limits.max_output_chars)
        if not text.strip():
            return _fallback_unsupported(
                request,
                code="asset_extraction.transcription_empty_output",
                message="Speech transcription returned no searchable text",
                metadata={
                    "transcription_provider": result.provider_name,
                    "transcription_model": result.provider_model,
                    **probe.metadata,
                },
            )

        segments = result.segments or (
            SpeechTranscriptSegment(
                text=text,
                start_ms=0,
                end_ms=_duration_to_ms(result.duration_seconds or probe.duration_seconds),
            ),
        )
        elements = tuple(
            ExtractedElement(
                kind="transcript_segment",
                text=segment.text,
                time_start_ms=segment.start_ms,
                time_end_ms=segment.end_ms,
                confidence=segment.confidence,
                metadata={
                    "source": self.name,
                    "transcription_provider": result.provider_name,
                    "transcription_model": result.provider_model,
                    **({"speaker": segment.speaker} if segment.speaker else {}),
                    **segment.metadata,
                },
            )
            for segment in segments
            if segment.text.strip()
        )
        markdown = _limit_text(
            "\n".join(
                [
                    f"# {request.filename.strip() or 'Media transcript'}",
                    "## Transcript",
                    *_segment_lines(segments),
                ]
            ),
            request.limits.max_output_chars,
        )
        transcript_text = "\n".join(_segment_lines(segments))
        duration_seconds = result.duration_seconds or probe.duration_seconds
        return ExtractionResult(
            status="succeeded",
            normalized_content_type=request.detected_content_type,
            title=request.filename.strip() or "Media transcript",
            markdown=markdown,
            elements=elements,
            artifacts=(
                ExtractionArtifactCandidate(
                    artifact_type="transcript",
                    filename="transcript.txt",
                    content_type="text/plain",
                    content=transcript_text.encode("utf-8"),
                    metadata={
                        "parser": self.name,
                        "segment_count": len(elements),
                        "transcription_provider": result.provider_name,
                        "transcription_model": result.provider_model,
                    },
                ),
            ),
            technical_metadata={
                "byte_size": request.byte_size,
                "mime_detected": request.detected_content_type,
                "duration_seconds": duration_seconds,
                "segment_count": len(elements),
                "transcript_status": "extracted",
                "transcription_provider": result.provider_name,
                "transcription_model": result.provider_model,
                "transcription_provider_version": result.provider_version,
                "output_chars": len(markdown),
                **probe.metadata,
            },
            diagnostics={
                "engine": self.name,
                "provider_diagnostics": result.diagnostics,
            },
            language=result.language,
            parser_name=self.name,
            parser_version=self.version,
            model_version=result.provider_model,
        )


def _profile_wants_api_transcription(parser_profile: str) -> bool:
    normalized = parser_profile.strip().lower()
    return normalized in _API_TRANSCRIPTION_PROFILES or normalized.startswith(
        ("media_api:", "transcribe:", "openai_transcribe:")
    )


def _is_media_content_type(content_type: str) -> bool:
    return content_type in _MEDIA_TYPES or content_type.startswith(("audio/", "video/"))


def _segment_lines(segments: tuple[SpeechTranscriptSegment, ...]) -> list[str]:
    lines: list[str] = []
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        start = segment.start_ms
        end = segment.end_ms
        if start is None and end is None:
            lines.append(text)
            continue
        lines.append(
            f"{_format_timestamp_ms(start or 0)} --> "
            f"{_format_timestamp_ms(end if end is not None else start or 0)}\n{text}"
        )
    return lines


def _duration_to_ms(duration_seconds: float | None) -> int | None:
    if duration_seconds is None or duration_seconds <= 0:
        return None
    return int(round(duration_seconds * 1000))


def _fallback_unsupported(
    request: ExtractionRequest,
    *,
    code: str,
    message: str,
    metadata: dict[str, object] | None = None,
) -> ExtractionResult:
    result = _unsupported(
        request,
        parser_name=SpeechTranscriptionExtractionEngine.name,
        parser_version=SpeechTranscriptionExtractionEngine.version,
        code=code,
        message=message,
        metadata=metadata,
    )
    return replace(result, diagnostics={**result.diagnostics, "fallback_allowed": True})
