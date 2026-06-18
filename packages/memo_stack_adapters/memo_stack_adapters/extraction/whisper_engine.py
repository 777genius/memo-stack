"""Optional faster-whisper ASR extraction engine for audio and video assets."""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
import tempfile
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from memo_stack_core.ports.extraction import (
    ExtractedElement,
    ExtractionArtifactCandidate,
    ExtractionRequest,
    ExtractionResult,
)

from memo_stack_adapters.extraction.content import (
    _MEDIA_TYPES,
    ExtractionEngine,
    SupportDecision,
    _format_timestamp_ms,
    _limit_text,
    _safe_suffix,
    _unsupported,
)
from memo_stack_adapters.extraction.media_tools import (
    media_manifest_artifact,
    probe_media_with_ffprobe,
)

_ASR_PROFILES = {
    "asr",
    "faster_whisper",
    "local_asr",
    "media_local_asr",
}


class FasterWhisperTranscriptionEngine(ExtractionEngine):
    name = "faster_whisper_transcript"

    def __init__(
        self,
        *,
        model_name: str = "base",
        device: str = "auto",
        compute_type: str = "default",
        model_factory: Callable[[str, str, str], Any] | None = None,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._compute_type = compute_type
        self._model_factory = model_factory

    async def supports(self, request: ExtractionRequest) -> SupportDecision:
        if not _profile_wants_asr(request.parser_profile):
            return SupportDecision(False, reason="parser_profile_not_asr")
        if not _is_media_content_type(request.detected_content_type):
            return SupportDecision(False, reason="not_audio_or_video")
        if self._model_factory is not None:
            return SupportDecision(True)
        if _load_whisper_model_factory() is not None:
            return SupportDecision(True)
        return SupportDecision(False, reason="faster_whisper_not_installed")

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._extract_sync, request),
                timeout=max(0.001, float(request.limits.parser_timeout_seconds)),
            )
        except TimeoutError:
            return _fallback_unsupported(
                request,
                code="asset_extraction.asr_timeout",
                message="Local ASR transcription timed out",
                parser_version=_faster_whisper_version(),
                metadata={
                    "parser_timeout_seconds": request.limits.parser_timeout_seconds,
                },
            )

    def _extract_sync(self, request: ExtractionRequest) -> ExtractionResult:
        probe = probe_media_with_ffprobe(request)
        if probe.duration_seconds and probe.duration_seconds > request.limits.max_media_seconds:
            return _fallback_unsupported(
                request,
                code="asset_extraction.asr_media_too_long",
                message="Media duration exceeds local ASR limit",
                parser_version=_faster_whisper_version(),
                metadata={
                    "duration_seconds": probe.duration_seconds,
                    "max_media_seconds": request.limits.max_media_seconds,
                },
            )

        model_factory = self._model_factory or _load_whisper_model_factory()
        if model_factory is None:
            return _fallback_unsupported(
                request,
                code="asset_extraction.asr_dependency_missing",
                message="faster-whisper is not installed for this parser profile",
                parser_version=None,
            )

        model_name = _model_name_for_profile(request.parser_profile, self._model_name)
        try:
            with tempfile.NamedTemporaryFile(suffix=_safe_suffix(request.filename)) as media_file:
                media_file.write(request.content)
                media_file.flush()
                model = model_factory(model_name, self._device, self._compute_type)
                segments, info = model.transcribe(media_file.name)
                segment_items = tuple(_segment_item(segment) for segment in segments)
        except Exception:
            return _fallback_unsupported(
                request,
                code="asset_extraction.asr_transcription_failed",
                message="Local ASR transcription failed",
                parser_version=_faster_whisper_version(),
                metadata={"asr_model": model_name},
            )

        segment_items = tuple(item for item in segment_items if item.text)
        if not segment_items:
            return _fallback_unsupported(
                request,
                code="asset_extraction.asr_no_speech",
                message="Local ASR returned no speech segments",
                parser_version=_faster_whisper_version(),
                metadata={"asr_model": model_name},
            )

        lines = [f"# {request.filename.strip() or 'Media transcript'}", "## Transcript"]
        elements: list[ExtractedElement] = []
        for item in segment_items:
            lines.append(
                f"[{_format_timestamp_ms(item.start_ms)} - "
                f"{_format_timestamp_ms(item.end_ms)}] {item.text}"
            )
            elements.append(
                ExtractedElement(
                    kind="transcript_segment",
                    text=item.text,
                    time_start_ms=item.start_ms,
                    time_end_ms=item.end_ms,
                    confidence=item.confidence,
                    metadata={"source": self.name, "asr_model": model_name},
                )
            )

        markdown = _limit_text("\n".join(lines), request.limits.max_output_chars)
        transcript_text = "\n".join(
            f"{_format_timestamp_ms(item.start_ms)} --> "
            f"{_format_timestamp_ms(item.end_ms)}\n{item.text}"
            for item in segment_items
        )
        transcript_features = _local_transcript_feature_metadata(segment_items)
        duration_seconds = (
            _positive_float(getattr(info, "duration", None)) or probe.duration_seconds
        )
        language = _safe_text(getattr(info, "language", None))
        metadata = {
            "byte_size": request.byte_size,
            "mime_detected": request.detected_content_type,
            "duration_seconds": duration_seconds,
            "segment_count": len(elements),
            "transcript_status": "extracted",
            "asr_model": model_name,
            "asr_device": self._device,
            "asr_compute_type": self._compute_type,
            "language_probability": _positive_float(getattr(info, "language_probability", None)),
            "output_chars": len(markdown),
            **transcript_features,
            **(probe.metadata or {}),
        }
        transcript_json = json.dumps(
            {
                "schema_name": "memo_stack.transcript",
                "schema_version": 1,
                "asset_id": request.asset_id,
                "filename": request.filename,
                "content_type": request.detected_content_type,
                "duration_seconds": duration_seconds,
                "language": language,
                "provider": {
                    "name": self.name,
                    "model": model_name,
                    "version": _faster_whisper_version(),
                },
                "features": transcript_features,
                "text": "\n".join(item.text for item in segment_items),
                "segments": [
                    {
                        "text": item.text,
                        "start_ms": item.start_ms,
                        "end_ms": item.end_ms,
                        "confidence": item.confidence,
                        "speaker": None,
                        "metadata": {"source": self.name, "asr_model": model_name},
                    }
                    for item in segment_items
                ],
                "words": [],
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
        return ExtractionResult(
            status="succeeded",
            normalized_content_type=request.detected_content_type,
            title=request.filename.strip() or "Media transcript",
            markdown=markdown,
            elements=tuple(elements),
            artifacts=(
                media_manifest_artifact(
                    request=request,
                    probe=probe,
                    parser_name=self.name,
                ),
                ExtractionArtifactCandidate(
                    artifact_type="transcript",
                    filename="transcript.txt",
                    content_type="text/plain",
                    content=transcript_text.encode("utf-8"),
                    metadata={
                        "parser": self.name,
                        "segment_count": len(elements),
                        "asr_model": model_name,
                        **transcript_features,
                    },
                ),
                ExtractionArtifactCandidate(
                    artifact_type="transcript_json",
                    filename="transcript.json",
                    content_type="application/json",
                    content=transcript_json,
                    metadata={
                        "parser": self.name,
                        "segment_count": len(elements),
                        "word_count": 0,
                        "asr_model": model_name,
                        **transcript_features,
                    },
                ),
            ),
            technical_metadata=metadata,
            diagnostics={"engine": self.name},
            language=language,
            parser_name=self.name,
            parser_version=_faster_whisper_version(),
            model_version=model_name,
        )


def _profile_wants_asr(parser_profile: str) -> bool:
    normalized = parser_profile.strip().lower()
    return normalized in _ASR_PROFILES or normalized.startswith(
        ("asr:", "faster_whisper:", "media_local_asr:")
    )


def _model_name_for_profile(parser_profile: str, default: str) -> str:
    normalized = parser_profile.strip()
    if ":" not in normalized:
        return default
    prefix, value = normalized.split(":", 1)
    if prefix.lower() in {"asr", "faster_whisper", "media_local_asr"} and value.strip():
        return value.strip()
    return default


def _is_media_content_type(content_type: str) -> bool:
    return content_type in _MEDIA_TYPES or content_type.startswith(("audio/", "video/"))


def _load_whisper_model_factory() -> Callable[[str, str, str], Any] | None:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None

    def build_model(model_name: str, device: str, compute_type: str) -> Any:
        return WhisperModel(model_name, device=device, compute_type=compute_type)

    return build_model


class _SegmentItem:
    def __init__(
        self,
        *,
        start_ms: int,
        end_ms: int,
        text: str,
        confidence: float | None,
    ) -> None:
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.text = text
        self.confidence = confidence


def _segment_item(segment: object) -> _SegmentItem:
    start_seconds = _positive_float(getattr(segment, "start", None)) or 0
    end_seconds = _positive_float(getattr(segment, "end", None)) or start_seconds
    return _SegmentItem(
        start_ms=int(round(start_seconds * 1000)),
        end_ms=int(round(end_seconds * 1000)),
        text=_safe_text(getattr(segment, "text", None)) or "",
        confidence=_segment_confidence(segment),
    )


def _local_transcript_feature_metadata(
    segment_items: tuple[_SegmentItem, ...],
) -> dict[str, object]:
    features: list[str] = []
    if segment_items:
        features.append("segments")
    if any(item.start_ms is not None or item.end_ms is not None for item in segment_items):
        features.append("time_ranges")
    return {
        "transcript_features": features,
        "transcript_feature_names": ",".join(features),
        "has_time_ranges": "time_ranges" in features,
        "has_speaker_labels": False,
        "has_word_timestamps": False,
    }


def _segment_confidence(segment: object) -> float | None:
    avg_logprob = _number(getattr(segment, "avg_logprob", None))
    if avg_logprob is not None:
        return max(0.0, min(1.0, 1.0 + avg_logprob))
    no_speech_prob = _number(getattr(segment, "no_speech_prob", None))
    if no_speech_prob is not None:
        return max(0.0, min(1.0, 1.0 - no_speech_prob))
    return None


def _fallback_unsupported(
    request: ExtractionRequest,
    *,
    code: str,
    message: str,
    parser_version: str | None,
    metadata: dict[str, object] | None = None,
) -> ExtractionResult:
    result = _unsupported(
        request,
        parser_name=FasterWhisperTranscriptionEngine.name,
        parser_version=parser_version,
        code=code,
        message=message,
        metadata=metadata,
    )
    return replace(result, diagnostics={**result.diagnostics, "fallback_allowed": True})


def _faster_whisper_version() -> str | None:
    try:
        return importlib.metadata.version("faster-whisper")
    except importlib.metadata.PackageNotFoundError:
        return None


def _positive_float(value: object) -> float | None:
    number = _number(value)
    if number is None or number <= 0:
        return None
    return number


def _number(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _safe_text(value: object) -> str | None:
    text = str(value).strip()
    return text or None
