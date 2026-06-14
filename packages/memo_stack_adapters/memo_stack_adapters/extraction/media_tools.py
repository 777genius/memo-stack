"""Local media probing helpers for extraction adapters."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any

from memo_stack_core.ports.extraction import (
    ExtractionArtifactCandidate,
    ExtractionRequest,
)


@dataclass(frozen=True)
class MediaProbeResult:
    status: str
    duration_seconds: float | None = None
    stream_summaries: tuple[str, ...] = ()
    metadata: dict[str, object] | None = None


def probe_media_with_ffprobe(request: ExtractionRequest) -> MediaProbeResult:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return MediaProbeResult(status="unavailable", metadata={"probe_status": "unavailable"})
    suffix = _safe_suffix(request.filename)
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix) as media_file:
            media_file.write(request.content)
            media_file.flush()
            completed = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration:stream=index,codec_type,codec_name,width,height,channels,"
                    "sample_rate,duration",
                    "-of",
                    "json",
                    media_file.name,
                ],
                check=False,
                capture_output=True,
                timeout=20,
            )
    except (OSError, subprocess.TimeoutExpired):
        return MediaProbeResult(status="failed", metadata={"probe_status": "failed"})
    if completed.returncode != 0:
        return MediaProbeResult(status="failed", metadata={"probe_status": "failed"})
    try:
        payload = json.loads(completed.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        return MediaProbeResult(status="failed", metadata={"probe_status": "failed"})
    return _media_probe_from_payload(payload)


def extract_first_video_keyframe(
    request: ExtractionRequest,
) -> ExtractionArtifactCandidate | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    try:
        with (
            tempfile.NamedTemporaryFile(suffix=_safe_suffix(request.filename)) as input_file,
            tempfile.NamedTemporaryFile(suffix=".jpg") as output_file,
        ):
            input_file.write(request.content)
            input_file.flush()
            completed = subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-v",
                    "error",
                    "-ss",
                    "0",
                    "-i",
                    input_file.name,
                    "-frames:v",
                    "1",
                    output_file.name,
                ],
                check=False,
                capture_output=True,
                timeout=30,
            )
            if completed.returncode != 0:
                return None
            output_file.seek(0)
            content = output_file.read()
    except (OSError, subprocess.TimeoutExpired):
        return None
    if not content:
        return None
    return ExtractionArtifactCandidate(
        artifact_type="keyframe",
        filename="keyframe-0001.jpg",
        content_type="image/jpeg",
        content=content,
        metadata={"time_start_ms": 0, "parser": "ffmpeg"},
    )


def _media_probe_from_payload(payload: dict[str, Any]) -> MediaProbeResult:
    format_payload = payload.get("format") if isinstance(payload.get("format"), dict) else {}
    duration_seconds = _positive_float(format_payload.get("duration"))
    stream_summaries: list[str] = []
    metadata: dict[str, object] = {"probe_status": "succeeded"}
    for stream in payload.get("streams") or []:
        if not isinstance(stream, dict):
            continue
        codec_type = str(stream.get("codec_type") or "unknown")
        codec_name = str(stream.get("codec_name") or "unknown")
        if codec_type == "video":
            width = stream.get("width")
            height = stream.get("height")
            summary = f"video/{codec_name}"
            if width and height:
                summary = f"{summary} {width}x{height}"
                metadata.setdefault("video_width", width)
                metadata.setdefault("video_height", height)
            stream_summaries.append(summary)
        elif codec_type == "audio":
            summary = f"audio/{codec_name}"
            sample_rate = stream.get("sample_rate")
            channels = stream.get("channels")
            if sample_rate:
                summary = f"{summary} {sample_rate}Hz"
                metadata.setdefault("audio_sample_rate", sample_rate)
            if channels:
                summary = f"{summary} {channels}ch"
                metadata.setdefault("audio_channels", channels)
            stream_summaries.append(summary)
        else:
            stream_summaries.append(f"{codec_type}/{codec_name}")
    return MediaProbeResult(
        status="succeeded",
        duration_seconds=duration_seconds,
        stream_summaries=tuple(stream_summaries),
        metadata=metadata,
    )


def _safe_suffix(filename: str) -> str:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if not extension:
        return ".bin"
    safe = "".join(ch for ch in extension if ch.isalnum())[:16]
    return f".{safe or 'bin'}"


def _positive_float(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number
