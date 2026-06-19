"""Local media probing and video frame helpers for extraction adapters."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any

from infinity_context_core.ports.extraction import (
    ExtractionArtifactCandidate,
    ExtractionRequest,
)

_LOCAL_MEDIA_PROTOCOL_WHITELIST = "file"
_MEDIA_STDIN_POLICY = "closed"


@dataclass(frozen=True)
class MediaStreamSummary:
    index: int | None
    codec_type: str
    codec_name: str
    width: int | None = None
    height: int | None = None
    channels: int | None = None
    sample_rate: str | None = None
    duration_seconds: float | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "index": self.index,
            "codec_type": self.codec_type,
            "codec_name": self.codec_name,
            "width": self.width,
            "height": self.height,
            "channels": self.channels,
            "sample_rate": self.sample_rate,
            "duration_seconds": self.duration_seconds,
        }


@dataclass(frozen=True)
class MediaProbeResult:
    status: str
    duration_seconds: float | None = None
    stream_summaries: tuple[str, ...] = ()
    streams: tuple[MediaStreamSummary, ...] = ()
    metadata: dict[str, object] | None = None


@dataclass(frozen=True)
class VideoKeyframe:
    filename: str
    content: bytes
    content_type: str
    time_start_ms: int
    metadata: dict[str, object]
    time_end_ms: int | None = None

    def to_artifact(self) -> ExtractionArtifactCandidate:
        return ExtractionArtifactCandidate(
            artifact_type="keyframe",
            filename=self.filename,
            content_type=self.content_type,
            content=self.content,
            metadata={
                **self.metadata,
                "time_start_ms": self.time_start_ms,
                "time_end_ms": self.time_end_ms
                if self.time_end_ms is not None
                else self.time_start_ms,
            },
        )


def probe_media_with_ffprobe(request: ExtractionRequest) -> MediaProbeResult:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return MediaProbeResult(
            status="unavailable",
            metadata={
                "probe_status": "unavailable",
                **_media_subprocess_policy_metadata(request),
            },
        )
    suffix = _safe_suffix(request.filename)
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix) as media_file:
            media_file.write(request.content)
            media_file.flush()
            completed = _run_media_subprocess(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-protocol_whitelist",
                    _LOCAL_MEDIA_PROTOCOL_WHITELIST,
                    "-show_entries",
                    "format=duration:stream=index,codec_type,codec_name,width,height,channels,"
                    "sample_rate,duration",
                    "-of",
                    "json",
                    media_file.name,
                ],
                request=request,
            )
    except (OSError, subprocess.TimeoutExpired):
        return MediaProbeResult(
            status="failed",
            metadata={
                "probe_status": "failed",
                **_media_subprocess_policy_metadata(request),
            },
        )
    if completed.returncode != 0:
        return MediaProbeResult(
            status="failed",
            metadata={
                "probe_status": "failed",
                **_media_subprocess_policy_metadata(request),
            },
        )
    try:
        payload = json.loads(completed.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        return MediaProbeResult(
            status="failed",
            metadata={
                "probe_status": "failed",
                **_media_subprocess_policy_metadata(request),
            },
        )
    return _media_probe_from_payload(
        payload,
        metadata=_media_subprocess_policy_metadata(request),
    )


def extract_first_video_keyframe(
    request: ExtractionRequest,
) -> ExtractionArtifactCandidate | None:
    keyframes = extract_selected_video_keyframes(request, max_frames=1)
    return keyframes[0].to_artifact() if keyframes else None


def extract_selected_video_keyframes(
    request: ExtractionRequest,
    *,
    duration_seconds: float | None = None,
    max_frames: int = 3,
) -> tuple[VideoKeyframe, ...]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return ()
    timestamps = _selected_keyframe_seconds(duration_seconds, max_frames=max_frames)
    frames: list[VideoKeyframe] = []
    try:
        with tempfile.NamedTemporaryFile(suffix=_safe_suffix(request.filename)) as input_file:
            input_file.write(request.content)
            input_file.flush()
            windows = _selected_keyframe_windows_ms(
                timestamps,
                duration_seconds=duration_seconds,
            )
            for index, timestamp_seconds in enumerate(timestamps, start=1):
                time_start_ms, time_end_ms = windows[index - 1]
                frame = _extract_one_keyframe(
                    request=request,
                    input_path=input_file.name,
                    index=index,
                    timestamp_seconds=timestamp_seconds,
                    time_start_ms=time_start_ms,
                    time_end_ms=time_end_ms,
                )
                if frame is not None:
                    frames.append(frame)
    except (OSError, subprocess.TimeoutExpired):
        return tuple(frames)
    return tuple(frames)


def media_manifest_artifact(
    *,
    request: ExtractionRequest,
    probe: MediaProbeResult,
    parser_name: str,
) -> ExtractionArtifactCandidate:
    payload = {
        "schema_name": "infinity_context.media_manifest",
        "schema_version": 1,
        "parser": parser_name,
        "file": {
            "asset_id": request.asset_id,
            "filename": request.filename,
            "content_type": request.detected_content_type,
            "byte_size": request.byte_size,
            "sha256_hex": request.sha256_hex,
        },
        "probe": {
            "status": probe.status,
            "duration_seconds": probe.duration_seconds,
            "streams": [stream.to_payload() for stream in probe.streams],
            "stream_summaries": list(probe.stream_summaries),
            "metadata": probe.metadata or {},
        },
    }
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return ExtractionArtifactCandidate(
        artifact_type="media_manifest",
        filename="media-manifest.json",
        content_type="application/json",
        content=content,
        metadata={
            "parser": parser_name,
            "probe_status": probe.status,
            "duration_seconds": probe.duration_seconds,
            "stream_count": len(probe.streams),
        },
    )


def _extract_one_keyframe(
    *,
    request: ExtractionRequest,
    input_path: str,
    index: int,
    timestamp_seconds: float,
    time_start_ms: int,
    time_end_ms: int,
) -> VideoKeyframe | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    with tempfile.NamedTemporaryFile(suffix=".jpg") as output_file:
        completed = _run_media_subprocess(
            [
                ffmpeg,
                "-y",
                "-v",
                "error",
                "-protocol_whitelist",
                _LOCAL_MEDIA_PROTOCOL_WHITELIST,
                "-ss",
                _format_ffmpeg_seconds(timestamp_seconds),
                "-i",
                input_path,
                "-frames:v",
                "1",
                output_file.name,
            ],
            request=request,
        )
        if completed.returncode != 0:
            return None
        output_file.seek(0)
        content = output_file.read()
    if not content:
        return None
    selected_at_ms = int(round(timestamp_seconds * 1000))
    return VideoKeyframe(
        filename=f"keyframe-{index:04d}.jpg",
        content=content,
        content_type="image/jpeg",
        time_start_ms=time_start_ms,
        time_end_ms=time_end_ms,
        metadata={
            "selected_at_ms": selected_at_ms,
            "time_start_ms": time_start_ms,
            "time_end_ms": time_end_ms,
            "parser": "ffmpeg",
            "frame_index": index,
            "selection": "sampled_keyframe",
            **_media_subprocess_policy_metadata(request),
        },
    )


def _media_probe_from_payload(
    payload: dict[str, Any],
    *,
    metadata: dict[str, object] | None = None,
) -> MediaProbeResult:
    format_payload = payload.get("format") if isinstance(payload.get("format"), dict) else {}
    duration_seconds = _positive_float(format_payload.get("duration"))
    stream_summaries: list[str] = []
    streams: list[MediaStreamSummary] = []
    result_metadata: dict[str, object] = {
        "probe_status": "succeeded",
        **(metadata or {}),
    }
    for stream in payload.get("streams") or []:
        if not isinstance(stream, dict):
            continue
        codec_type = str(stream.get("codec_type") or "unknown")
        codec_name = str(stream.get("codec_name") or "unknown")
        width = _positive_int(stream.get("width"))
        height = _positive_int(stream.get("height"))
        channels = _positive_int(stream.get("channels"))
        sample_rate = _safe_text(stream.get("sample_rate"))
        streams.append(
            MediaStreamSummary(
                index=_positive_int(stream.get("index")),
                codec_type=codec_type,
                codec_name=codec_name,
                width=width,
                height=height,
                channels=channels,
                sample_rate=sample_rate,
                duration_seconds=_positive_float(stream.get("duration")),
            )
        )
        if codec_type == "video":
            summary = f"video/{codec_name}"
            if width and height:
                summary = f"{summary} {width}x{height}"
                result_metadata.setdefault("video_width", width)
                result_metadata.setdefault("video_height", height)
            stream_summaries.append(summary)
        elif codec_type == "audio":
            summary = f"audio/{codec_name}"
            if sample_rate:
                summary = f"{summary} {sample_rate}Hz"
                result_metadata.setdefault("audio_sample_rate", sample_rate)
            if channels:
                summary = f"{summary} {channels}ch"
                result_metadata.setdefault("audio_channels", channels)
            stream_summaries.append(summary)
        else:
            stream_summaries.append(f"{codec_type}/{codec_name}")
    return MediaProbeResult(
        status="succeeded",
        duration_seconds=duration_seconds,
        stream_summaries=tuple(stream_summaries),
        streams=tuple(streams),
        metadata=result_metadata,
    )


def _safe_suffix(filename: str) -> str:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if not extension:
        return ".bin"
    safe = "".join(ch for ch in extension if ch.isalnum())[:16]
    return f".{safe or 'bin'}"


def _subprocess_timeout_seconds(request: ExtractionRequest) -> int:
    return max(1, int(request.limits.subprocess_timeout_seconds))


def _run_media_subprocess(
    args: list[str],
    *,
    request: ExtractionRequest,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        timeout=_subprocess_timeout_seconds(request),
        stdin=subprocess.DEVNULL,
    )


def _media_subprocess_policy_metadata(request: ExtractionRequest) -> dict[str, object]:
    return {
        "protocol_whitelist": _LOCAL_MEDIA_PROTOCOL_WHITELIST,
        "stdin_policy": _MEDIA_STDIN_POLICY,
        "subprocess_timeout_seconds": _subprocess_timeout_seconds(request),
    }


def _selected_keyframe_seconds(
    duration_seconds: float | None,
    *,
    max_frames: int,
) -> tuple[float, ...]:
    max_frames = max(1, max_frames)
    if duration_seconds is None or duration_seconds <= 1 or max_frames == 1:
        return (0.0,)
    candidates = [0.0]
    if max_frames >= 2:
        candidates.append(max(0.0, duration_seconds / 2))
    if max_frames >= 3 and duration_seconds > 2:
        candidates.append(max(0.0, duration_seconds - 0.5))
    selected: list[float] = []
    for value in candidates:
        rounded = round(value, 3)
        if rounded not in selected:
            selected.append(rounded)
        if len(selected) >= max_frames:
            break
    return tuple(selected)


def _selected_keyframe_windows_ms(
    timestamps: tuple[float, ...],
    *,
    duration_seconds: float | None,
) -> tuple[tuple[int, int], ...]:
    if not timestamps:
        return ()
    if duration_seconds is None or duration_seconds <= 0:
        return tuple((_seconds_to_ms(value), _seconds_to_ms(value)) for value in timestamps)
    windows: list[tuple[int, int]] = []
    last_index = len(timestamps) - 1
    for index, timestamp in enumerate(timestamps):
        start_seconds = 0.0 if index == 0 else (timestamps[index - 1] + timestamp) / 2
        end_seconds = (
            duration_seconds if index == last_index else (timestamp + timestamps[index + 1]) / 2
        )
        start_ms = _seconds_to_ms(start_seconds)
        end_ms = max(start_ms, _seconds_to_ms(end_seconds))
        windows.append((start_ms, end_ms))
    return tuple(windows)


def _seconds_to_ms(value: float) -> int:
    return int(round(max(0.0, value) * 1000))


def _format_ffmpeg_seconds(value: float) -> str:
    return f"{max(0.0, value):.3f}"


def _positive_float(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _positive_int(value: object) -> int | None:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _safe_text(value: object) -> str | None:
    text = str(value).strip()
    return text or None
