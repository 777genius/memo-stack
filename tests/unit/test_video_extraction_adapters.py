import asyncio
import json
from dataclasses import dataclass
from typing import Any

import pytest
from infinity_context_adapters.extraction import content as content_module
from infinity_context_adapters.extraction import transcription_engine as transcription_engine_module
from infinity_context_adapters.extraction.content import (
    MediaMetadataExtractionEngine,
    StandardExtractionRouter,
)
from infinity_context_adapters.extraction.media_tools import (
    MediaProbeResult,
    MediaStreamSummary,
    VideoKeyframe,
    _selected_keyframe_windows_ms,
)
from infinity_context_adapters.extraction.transcription.openai_adapter import (
    OpenAISpeechTranscriptionAdapter,
)
from infinity_context_adapters.extraction.transcription_engine import SpeechTranscriptionExtractionEngine
from infinity_context_adapters.extraction.video_evidence import VideoFrameEvidence
from infinity_context_core.ports.extraction import (
    ExtractedElement,
    ExtractionArtifactCandidate,
    ExtractionLimits,
    ExtractionRequest,
)


def test_speech_transcription_engine_binds_video_keyframe_timeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        transcription_engine_module,
        "extract_selected_video_keyframes",
        _fake_video_keyframes,
    )
    monkeypatch.setattr(
        transcription_engine_module,
        "analyze_video_keyframes",
        _fake_video_frame_evidence,
    )
    engine = SpeechTranscriptionExtractionEngine(
        transcription=OpenAISpeechTranscriptionAdapter(
            api_key=None,
            model="gpt-4o-mini-transcribe",
            client_factory=lambda: _FakeTranscriptionClient(),
        )
    )
    request = _request(
        parser_profile="media_api",
        enable_external_ai=True,
    )

    result = asyncio.run(engine.extract(request))

    assert result.status == "succeeded"
    assert result.parser_name == "speech_transcription"
    assert result.technical_metadata["keyframe_status"] == "extracted"
    assert result.technical_metadata["video_keyframe_count"] == 1
    assert result.technical_metadata["video_keyframe_ocr_extracted_count"] == 1
    assert {artifact.artifact_type for artifact in result.artifacts} == {
        "keyframe",
        "media_manifest",
        "transcript",
        "transcript_json",
        "video_frame_timeline",
    }
    assert [element.kind for element in result.elements] == [
        "transcript_segment",
        "transcript_segment",
        "video_keyframe",
    ]
    assert result.elements[-1].time_start_ms == 1250


def test_media_metadata_engine_emits_video_keyframe_timeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        content_module,
        "probe_media_with_ffprobe",
        lambda request: MediaProbeResult(
            status="succeeded",
            duration_seconds=8.0,
            stream_summaries=("video/h264 640x360", "audio/aac 48000Hz 2ch"),
            metadata={
                "probe_status": "succeeded",
                "video_width": 640,
                "video_height": 360,
                "audio_sample_rate": "48000",
                "audio_channels": 2,
            },
        ),
    )
    monkeypatch.setattr(content_module, "extract_selected_video_keyframes", _fake_video_keyframes)
    monkeypatch.setattr(content_module, "analyze_video_keyframes", _fake_video_frame_evidence)
    engine = MediaMetadataExtractionEngine()
    request = _request(parser_profile="standard_local")

    result = asyncio.run(engine.extract(request))

    assert result.status == "succeeded"
    assert result.parser_name == "media_metadata"
    assert result.technical_metadata["duration_seconds"] == 8.0
    assert result.technical_metadata["keyframe_status"] == "extracted"
    assert result.technical_metadata["video_keyframe_count"] == 1
    assert "Keyframes: 1 extracted" in (result.markdown or "")
    assert {artifact.artifact_type for artifact in result.artifacts} == {
        "keyframe",
        "media_manifest",
        "video_frame_timeline",
    }
    assert [element.kind for element in result.elements] == [
        "media_metadata",
        "video_keyframe",
    ]


def test_video_without_audio_skips_transcription_provider_and_keeps_keyframes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_called = False

    def client_factory() -> _FakeTranscriptionClient:
        nonlocal provider_called
        provider_called = True
        return _FakeTranscriptionClient()

    probe = MediaProbeResult(
        status="succeeded",
        duration_seconds=8.0,
        stream_summaries=("video/h264 640x360",),
        streams=(
            MediaStreamSummary(
                index=0,
                codec_type="video",
                codec_name="h264",
                width=640,
                height=360,
            ),
        ),
        metadata={
            "probe_status": "succeeded",
            "video_width": 640,
            "video_height": 360,
        },
    )
    monkeypatch.setattr(transcription_engine_module, "probe_media_with_ffprobe", lambda _: probe)
    monkeypatch.setattr(content_module, "probe_media_with_ffprobe", lambda _: probe)
    monkeypatch.setattr(content_module, "extract_selected_video_keyframes", _fake_video_keyframes)
    monkeypatch.setattr(content_module, "analyze_video_keyframes", _fake_video_frame_evidence)
    router = StandardExtractionRouter(
        engines=(
            SpeechTranscriptionExtractionEngine(
                transcription=OpenAISpeechTranscriptionAdapter(
                    api_key=None,
                    model="gpt-4o-mini-transcribe",
                    client_factory=client_factory,
                )
            ),
            MediaMetadataExtractionEngine(),
        )
    )
    request = _request(
        parser_profile="media_api",
        enable_external_ai=True,
    )

    result = asyncio.run(router.extract(request))

    assert provider_called is False
    assert result.status == "succeeded"
    assert result.parser_name == "media_metadata"
    assert result.diagnostics["speech_transcription_fallback"] is True
    assert result.technical_metadata["transcript_status"] == "not_applicable"
    assert (
        result.technical_metadata["transcript_error_code"]
        == "asset_extraction.transcription_no_audio_stream"
    )
    assert result.technical_metadata["keyframe_status"] == "extracted"
    assert {artifact.artifact_type for artifact in result.artifacts} == {
        "keyframe",
        "media_manifest",
        "video_frame_timeline",
    }


def test_selected_keyframe_windows_cover_video_duration() -> None:
    assert _selected_keyframe_windows_ms(
        (0.0, 4.0, 7.5),
        duration_seconds=8.0,
    ) == ((0, 2000), (2000, 5750), (5750, 8000))
    assert _selected_keyframe_windows_ms(
        (1.25,),
        duration_seconds=None,
    ) == ((1250, 1250),)


def test_video_frame_evidence_preserves_frame_time_range() -> None:
    frame = VideoKeyframe(
        filename="keyframe-0001.png",
        content=_sample_png_bytes(),
        content_type="image/png",
        time_start_ms=1000,
        time_end_ms=2500,
        metadata={
            "selected_at_ms": 1250,
            "time_start_ms": 1000,
            "time_end_ms": 2500,
            "frame_index": 1,
            "selection": "sampled_keyframe",
        },
    )

    evidence = transcription_engine_module.analyze_video_keyframes(
        frames=(frame,),
        parser_name="test_video_parser",
        enable_ocr=False,
        ocr_timeout_seconds=1,
    )

    payload = json.loads(evidence.timeline_artifact.content.decode("utf-8"))
    assert payload["frames"][0]["selected_at_ms"] == 1250
    assert payload["frames"][0]["time_start_ms"] == 1000
    assert payload["frames"][0]["time_end_ms"] == 2500
    assert evidence.elements[0].time_start_ms == 1000
    assert evidence.elements[0].time_end_ms == 2500


def _request(
    *,
    parser_profile: str,
    enable_external_ai: bool = False,
) -> ExtractionRequest:
    content = b"\x00\x00\x00\x18ftypmp42fake video bytes"
    return ExtractionRequest(
        job_id="extract_1",
        asset_id="asset_1",
        filename="product-demo.mp4",
        declared_content_type="video/mp4",
        detected_content_type="video/mp4",
        byte_size=len(content),
        sha256_hex="0" * 64,
        content=content,
        parser_profile=parser_profile,
        limits=ExtractionLimits(
            max_bytes=10_000_000,
            enable_external_ai=enable_external_ai,
        ),
    )


def _fake_video_keyframes(
    request: ExtractionRequest,
    *,
    duration_seconds: float | None = None,
    max_frames: int = 3,
) -> tuple[VideoKeyframe, ...]:
    assert request.detected_content_type.startswith("video/")
    assert duration_seconds is None or duration_seconds > 0
    assert max_frames == 3
    return (
        VideoKeyframe(
            filename="keyframe-0001.jpg",
            content=b"fake jpeg bytes",
            content_type="image/jpeg",
            time_start_ms=1250,
            metadata={
                "time_start_ms": 1250,
                "frame_index": 1,
                "selection": "sampled_keyframe",
            },
        ),
    )


def _fake_video_frame_evidence(
    *,
    frames: tuple[VideoKeyframe, ...],
    parser_name: str,
    enable_ocr: bool,
    ocr_timeout_seconds: float,
) -> VideoFrameEvidence:
    assert len(frames) == 1
    assert enable_ocr is True
    assert ocr_timeout_seconds > 0
    frame = frames[0]
    return VideoFrameEvidence(
        elements=(
            ExtractedElement(
                kind="video_keyframe",
                text="Keyframe shows a memory capture review panel.",
                time_start_ms=frame.time_start_ms,
                time_end_ms=frame.time_start_ms,
                metadata={"source": parser_name, "frame_index": 1},
            ),
        ),
        timeline_artifact=ExtractionArtifactCandidate(
            artifact_type="video_frame_timeline",
            filename="video-frame-timeline.json",
            content_type="application/json",
            content=(
                b'{"frames":[{"ocr_status":"extracted","time_start_ms":1250}],'
                b'"schema_name":"infinity_context.video_frame_timeline"}'
            ),
            metadata={
                "parser": parser_name,
                "frame_count": 1,
                "ocr_extracted_frame_count": 1,
            },
        ),
        metadata={
            "video_keyframe_count": 1,
            "video_keyframe_ocr_extracted_count": 1,
        },
    )


@dataclass(frozen=True)
class _FakeTranscriptionResponse:
    text: str
    language: str = "en"
    duration: float = 4.0
    segments: list[dict[str, object]] | None = None
    words: list[dict[str, object]] | None = None


class _FakeVideoTranscriptions:
    async def create(self, **kwargs: Any) -> _FakeTranscriptionResponse:
        assert kwargs["model"] == "gpt-4o-mini-transcribe"
        assert kwargs["response_format"] == "json"
        assert kwargs["file"].name == "product-demo.mp4"
        return _FakeTranscriptionResponse(
            text=("Alex narrated the product demo while showing the memory review panel."),
            segments=[
                {
                    "start": 0.0,
                    "end": 2.0,
                    "text": "Alex narrated the product demo.",
                },
                {
                    "start": 2.0,
                    "end": 4.0,
                    "text": "The memory review panel is visible.",
                },
            ],
        )


class _FakeAudioClient:
    transcriptions = _FakeVideoTranscriptions()


class _FakeTranscriptionClient:
    audio = _FakeAudioClient()

    async def aclose(self) -> None:
        return None


def _sample_png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04"
        b"\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )
