import asyncio
from dataclasses import dataclass
from typing import Any

import pytest
from memo_stack_adapters.extraction import content as content_module
from memo_stack_adapters.extraction import transcription_engine as transcription_engine_module
from memo_stack_adapters.extraction.content import MediaMetadataExtractionEngine
from memo_stack_adapters.extraction.media_tools import MediaProbeResult, VideoKeyframe
from memo_stack_adapters.extraction.transcription.openai_adapter import (
    OpenAISpeechTranscriptionAdapter,
)
from memo_stack_adapters.extraction.transcription_engine import SpeechTranscriptionExtractionEngine
from memo_stack_adapters.extraction.video_evidence import VideoFrameEvidence
from memo_stack_core.ports.extraction import (
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
                b'"schema_name":"memo_stack.video_frame_timeline"}'
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
