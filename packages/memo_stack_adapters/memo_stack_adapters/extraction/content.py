"""Provider-neutral content extraction adapters."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from io import BytesIO

from memo_stack_core.ports.extraction import (
    ContentExtractionPort,
    ExtractedElement,
    ExtractionArtifactCandidate,
    ExtractionRequest,
    ExtractionResult,
    FileTypeDetectionRequest,
    FileTypeDetectionResult,
    FileTypeDetectorPort,
)

from memo_stack_adapters.extraction.media_tools import (
    extract_first_video_keyframe,
    probe_media_with_ffprobe,
)

_TEXT_TYPES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "text/html",
    "application/json",
}
_TEXT_HEURISTIC_TYPES = {"application/octet-stream"}
_PDF_TYPES = {"application/pdf"}
_STRUCTURED_DOCUMENT_TYPES = {
    "application/msword",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/epub+zip",
    "message/rfc822",
}
_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/tiff",
}
_TIMED_TEXT_TYPES = {
    "application/x-subrip",
    "text/vtt",
}
_AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "audio/flac",
    "audio/webm",
    "audio/ogg",
}
_VIDEO_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/x-matroska",
}
_MEDIA_TYPES = _AUDIO_TYPES | _VIDEO_TYPES
_SUBTITLE_TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*"
    r"(?P<end>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})"
)


class SimpleFileTypeDetector(FileTypeDetectorPort):
    async def detect(self, request: FileTypeDetectionRequest) -> FileTypeDetectionResult:
        declared = _normalize_content_type(request.declared_content_type)
        extension = _extension(request.filename)
        detected = _choose_detected_content_type(
            magic_type=_magic_content_type(request.content),
            extension_type=_extension_content_type(extension),
            declared_type=declared,
        )
        return FileTypeDetectionResult(
            content_type=detected or "application/octet-stream",
            extension=extension,
            confidence="high" if detected != declared else "medium",
            diagnostics={"declared_content_type": declared},
        )


@dataclass(frozen=True)
class SupportDecision:
    supported: bool
    reason: str | None = None


class ExtractionEngine:
    name = "base"

    async def supports(self, request: ExtractionRequest) -> SupportDecision:
        raise NotImplementedError

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        raise NotImplementedError


class StandardExtractionRouter(ContentExtractionPort):
    def __init__(self, engines: tuple[ExtractionEngine, ...]) -> None:
        self._engines = engines

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        diagnostics: dict[str, object] = {"parser_profile": request.parser_profile}
        fallback_result: ExtractionResult | None = None
        for engine in self._engines:
            decision = await engine.supports(request)
            diagnostics[f"{engine.name}_support"] = decision.supported
            if decision.reason:
                diagnostics[f"{engine.name}_reason"] = decision.reason
            if not decision.supported:
                continue
            result = await engine.extract(request)
            if _result_allows_fallback(result):
                fallback_result = _merge_diagnostics(result, diagnostics)
                diagnostics[f"{engine.name}_fallback"] = True
                continue
            return _merge_diagnostics(result, diagnostics)
        if fallback_result is not None:
            return fallback_result
        return ExtractionResult(
            status="unsupported",
            normalized_content_type=request.detected_content_type,
            title=request.filename,
            technical_metadata={
                "byte_size": request.byte_size,
                "mime_detected": request.detected_content_type,
            },
            diagnostics=diagnostics,
            parser_name="standard-router",
            parser_version="v1",
            safe_error_code="asset_extraction.unsupported_content_type",
            safe_error_message="No extraction engine supports this asset type",
        )


class SimpleTextExtractionEngine(ExtractionEngine):
    name = "simple_text"
    version = "v1"

    async def supports(self, request: ExtractionRequest) -> SupportDecision:
        if request.detected_content_type in _TEXT_TYPES:
            return SupportDecision(True)
        if (
            request.detected_content_type in _TEXT_HEURISTIC_TYPES
            and _looks_like_utf8_text(request.content)
        ):
            return SupportDecision(True, reason="utf8_text_heuristic")
        return SupportDecision(False, reason="not_text")

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        text = _decode_text(request.content)
        if request.detected_content_type == "application/json":
            text = _json_to_text(text)
        text = _limit_text(text, request.limits.max_output_chars)
        title = request.filename.strip() or "asset"
        return ExtractionResult(
            status="succeeded",
            normalized_content_type=request.detected_content_type,
            title=title,
            markdown=text,
            elements=(
                ExtractedElement(
                    kind="text",
                    text=text,
                    metadata={"source": "simple_text"},
                ),
            ),
            technical_metadata={
                "byte_size": request.byte_size,
                "mime_detected": request.detected_content_type,
                "output_chars": len(text),
            },
            diagnostics={"engine": self.name},
            parser_name=self.name,
            parser_version=self.version,
        )


class PdfTextExtractionEngine(ExtractionEngine):
    name = "pypdf_text"
    version = "v1"

    async def supports(self, request: ExtractionRequest) -> SupportDecision:
        if request.detected_content_type in _PDF_TYPES:
            return SupportDecision(True)
        return SupportDecision(False, reason="not_pdf")

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        return await asyncio.to_thread(self._extract_sync, request)

    def _extract_sync(self, request: ExtractionRequest) -> ExtractionResult:
        try:
            from pypdf import PdfReader
        except ImportError:
            return _unsupported(
                request,
                parser_name=self.name,
                parser_version=self.version,
                code="asset_extraction.pdf_dependency_missing",
                message="PDF text extraction dependency is not installed",
            )

        try:
            reader = PdfReader(BytesIO(request.content), strict=False)
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:
                    return _unsupported(
                        request,
                        parser_name=self.name,
                        parser_version=self.version,
                        code="asset_extraction.pdf_encrypted",
                        message="Encrypted PDF cannot be extracted locally",
                    )
            page_count = len(reader.pages)
            pages_to_extract = min(page_count, request.limits.max_pages)
            elements: list[ExtractedElement] = []
            markdown_parts = [f"# {request.filename.strip() or 'PDF document'}"]
            for index in range(pages_to_extract):
                raw_text = reader.pages[index].extract_text() or ""
                page_text = _limit_text(raw_text, request.limits.max_output_chars).strip()
                if not page_text:
                    continue
                page_number = index + 1
                markdown_parts.extend((f"## Page {page_number}", page_text))
                elements.append(
                    ExtractedElement(
                        kind="page_text",
                        text=page_text,
                        page_number=page_number,
                        metadata={"source": self.name},
                    )
                )
        except Exception:
            return _unsupported(
                request,
                parser_name=self.name,
                parser_version=self.version,
                code="asset_extraction.pdf_parse_failed",
                message="PDF text extraction failed",
            )

        markdown = _limit_text("\n\n".join(markdown_parts), request.limits.max_output_chars)
        if not elements:
            return _unsupported(
                request,
                parser_name=self.name,
                parser_version=self.version,
                code="asset_extraction.pdf_no_text",
                message="PDF has no locally extractable text",
                metadata={
                    "byte_size": request.byte_size,
                    "mime_detected": request.detected_content_type,
                    "page_count": page_count,
                    "pages_extracted": pages_to_extract,
                    "ocr_required": True,
                },
            )

        return ExtractionResult(
            status="succeeded",
            normalized_content_type="application/pdf",
            title=request.filename.strip() or "PDF document",
            markdown=markdown,
            elements=tuple(elements),
            technical_metadata={
                "byte_size": request.byte_size,
                "mime_detected": request.detected_content_type,
                "page_count": page_count,
                "pages_extracted": pages_to_extract,
                "truncated_pages": page_count > pages_to_extract,
                "output_chars": len(markdown),
            },
            diagnostics={"engine": self.name},
            parser_name=self.name,
            parser_version=self.version,
        )


class ImageMetadataExtractionEngine(ExtractionEngine):
    name = "image_metadata"
    version = "v1"

    async def supports(self, request: ExtractionRequest) -> SupportDecision:
        if request.detected_content_type in _IMAGE_TYPES:
            return SupportDecision(True)
        return SupportDecision(False, reason="not_image")

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        return await asyncio.to_thread(self._extract_sync, request)

    def _extract_sync(self, request: ExtractionRequest) -> ExtractionResult:
        try:
            from PIL import Image
        except ImportError:
            return _unsupported(
                request,
                parser_name=self.name,
                parser_version=self.version,
                code="asset_extraction.image_dependency_missing",
                message="Image metadata dependency is not installed",
            )

        try:
            with Image.open(BytesIO(request.content)) as image:
                image.load()
                width, height = image.size
                image_format = image.format
                mode = image.mode
        except Exception:
            return _unsupported(
                request,
                parser_name=self.name,
                parser_version=self.version,
                code="asset_extraction.image_parse_failed",
                message="Image could not be read locally",
            )

        ocr_text = ""
        ocr_status = "disabled"
        if request.limits.enable_ocr:
            ocr_text, ocr_status = _run_tesseract_ocr(
                content=request.content,
                extension=_extension(request.filename),
            )

        lines = [
            f"# {request.filename.strip() or 'Image asset'}",
            "Image asset evidence",
            f"- Content type: {request.detected_content_type}",
            f"- Dimensions: {width}x{height}",
            f"- Format: {image_format or 'unknown'}",
            f"- OCR status: {ocr_status}",
        ]
        elements = [
            ExtractedElement(
                kind="image_metadata",
                text=(
                    f"Image asset {request.filename} "
                    f"({request.detected_content_type}, {width}x{height})"
                ),
                metadata={
                    "source": self.name,
                    "width": width,
                    "height": height,
                    "format": image_format,
                    "ocr_status": ocr_status,
                },
            )
        ]
        if ocr_text.strip():
            limited_ocr_text = _limit_text(ocr_text, request.limits.max_output_chars)
            lines.extend(("## OCR Text", limited_ocr_text))
            elements.append(
                ExtractedElement(
                    kind="ocr_text",
                    text=limited_ocr_text,
                    confidence=None,
                    metadata={"source": "tesseract_cli"},
                )
            )

        markdown = _limit_text("\n".join(lines), request.limits.max_output_chars)
        return ExtractionResult(
            status="succeeded",
            normalized_content_type=request.detected_content_type,
            title=request.filename.strip() or "Image asset",
            markdown=markdown,
            elements=tuple(elements),
            technical_metadata={
                "byte_size": request.byte_size,
                "mime_detected": request.detected_content_type,
                "image_width": width,
                "image_height": height,
                "image_format": image_format,
                "image_mode": mode,
                "ocr_status": ocr_status,
                "output_chars": len(markdown),
            },
            diagnostics={"engine": self.name},
            parser_name=self.name,
            parser_version=self.version,
        )


class TimedTextTranscriptExtractionEngine(ExtractionEngine):
    name = "timed_text_transcript"
    version = "v1"

    async def supports(self, request: ExtractionRequest) -> SupportDecision:
        if request.detected_content_type in _TIMED_TEXT_TYPES:
            return SupportDecision(True)
        return SupportDecision(False, reason="not_timed_text")

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        text = _decode_text(request.content)
        segments = _parse_timed_text_segments(text)
        if not segments:
            return _unsupported(
                request,
                parser_name=self.name,
                parser_version=self.version,
                code="asset_extraction.transcript_parse_failed",
                message="Timed transcript contains no readable segments",
            )

        lines = [f"# {request.filename.strip() or 'Transcript'}", "## Transcript"]
        elements: list[ExtractedElement] = []
        for segment in segments:
            start_ms, end_ms, segment_text = segment
            if not segment_text:
                continue
            lines.append(
                f"[{_format_timestamp_ms(start_ms)} - {_format_timestamp_ms(end_ms)}] "
                f"{segment_text}"
            )
            elements.append(
                ExtractedElement(
                    kind="transcript_segment",
                    text=segment_text,
                    time_start_ms=start_ms,
                    time_end_ms=end_ms,
                    metadata={"source": self.name},
                )
            )

        markdown = _limit_text("\n".join(lines), request.limits.max_output_chars)
        transcript_text = "\n".join(
            f"{_format_timestamp_ms(item[0])} --> {_format_timestamp_ms(item[1])}\n{item[2]}"
            for item in segments
        )
        return ExtractionResult(
            status="succeeded",
            normalized_content_type=request.detected_content_type,
            title=request.filename.strip() or "Transcript",
            markdown=markdown,
            elements=tuple(elements),
            artifacts=(
                ExtractionArtifactCandidate(
                    artifact_type="transcript",
                    filename="transcript.txt",
                    content_type="text/plain",
                    content=transcript_text.encode("utf-8"),
                    metadata={"parser": self.name, "segment_count": len(elements)},
                ),
            ),
            technical_metadata={
                "byte_size": request.byte_size,
                "mime_detected": request.detected_content_type,
                "segment_count": len(elements),
                "duration_ms": max((segment[1] for segment in segments), default=0),
                "output_chars": len(markdown),
            },
            diagnostics={"engine": self.name},
            parser_name=self.name,
            parser_version=self.version,
        )


class MediaMetadataExtractionEngine(ExtractionEngine):
    name = "media_metadata"
    version = "v1"

    async def supports(self, request: ExtractionRequest) -> SupportDecision:
        if request.detected_content_type in _MEDIA_TYPES:
            return SupportDecision(True)
        if request.detected_content_type.startswith(("audio/", "video/")):
            return SupportDecision(True, reason="media_prefix")
        return SupportDecision(False, reason="not_media")

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        return await asyncio.to_thread(self._extract_sync, request)

    def _extract_sync(self, request: ExtractionRequest) -> ExtractionResult:
        probe = probe_media_with_ffprobe(request)
        if probe.status == "unavailable":
            return _unsupported(
                request,
                parser_name=self.name,
                parser_version=self.version,
                code="asset_extraction.media_probe_unavailable",
                message="Local media probing is not available",
                metadata={
                    "byte_size": request.byte_size,
                    "mime_detected": request.detected_content_type,
                },
            )
        if probe.status == "failed":
            return _unsupported(
                request,
                parser_name=self.name,
                parser_version=self.version,
                code="asset_extraction.media_probe_failed",
                message="Media file could not be probed locally",
                metadata={
                    "byte_size": request.byte_size,
                    "mime_detected": request.detected_content_type,
                },
            )
        if probe.duration_seconds and probe.duration_seconds > request.limits.max_media_seconds:
            return _unsupported(
                request,
                parser_name=self.name,
                parser_version=self.version,
                code="asset_extraction.media_too_long",
                message="Media duration exceeds local extraction limit",
                metadata={
                    "byte_size": request.byte_size,
                    "mime_detected": request.detected_content_type,
                    "duration_seconds": probe.duration_seconds,
                    "max_media_seconds": request.limits.max_media_seconds,
                },
            )

        keyframe = None
        if request.detected_content_type.startswith("video/"):
            keyframe = extract_first_video_keyframe(request)

        lines = [
            f"# {request.filename.strip() or 'Media asset'}",
            "Media asset evidence",
            f"- Content type: {request.detected_content_type}",
            f"- Duration: {_format_duration_seconds(probe.duration_seconds)}",
            f"- Streams: {', '.join(probe.stream_summaries) or 'unknown'}",
            "- Transcript status: not configured in local extractor",
        ]
        if keyframe is not None:
            lines.append("- Keyframe status: extracted")
        markdown = _limit_text("\n".join(lines), request.limits.max_output_chars)
        artifacts = (keyframe,) if keyframe is not None else ()
        return ExtractionResult(
            status="succeeded",
            normalized_content_type=request.detected_content_type,
            title=request.filename.strip() or "Media asset",
            markdown=markdown,
            elements=(
                ExtractedElement(
                    kind="media_metadata",
                    text=(
                        f"Media asset {request.filename} "
                        f"({request.detected_content_type}, "
                        f"{_format_duration_seconds(probe.duration_seconds)})"
                    ),
                    metadata={"source": self.name, **probe.metadata},
                ),
            ),
            artifacts=artifacts,
            technical_metadata={
                "byte_size": request.byte_size,
                "mime_detected": request.detected_content_type,
                "duration_seconds": probe.duration_seconds,
                "stream_count": len(probe.stream_summaries),
                "transcript_status": "not_configured",
                "keyframe_status": "extracted" if keyframe is not None else "not_applicable",
                "output_chars": len(markdown),
                **probe.metadata,
            },
            diagnostics={"engine": self.name},
            parser_name=self.name,
            parser_version=self.version,
        )


def _normalize_content_type(value: str) -> str:
    return (value or "application/octet-stream").split(";")[0].strip().lower()


def _extension(filename: str) -> str | None:
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return suffix or None


def _choose_detected_content_type(
    *,
    magic_type: str | None,
    extension_type: str | None,
    declared_type: str,
) -> str:
    if extension_type and _extension_should_override_magic(
        magic_type=magic_type,
        extension_type=extension_type,
    ):
        return extension_type
    if _declared_should_override_magic(
        magic_type=magic_type,
        declared_type=declared_type,
    ):
        return declared_type
    return magic_type or extension_type or declared_type


def _declared_should_override_magic(
    *,
    magic_type: str | None,
    declared_type: str,
) -> bool:
    if magic_type != "text/plain":
        return False
    known_declared_types = (
        _TIMED_TEXT_TYPES
        | _TEXT_TYPES
        | _PDF_TYPES
        | _STRUCTURED_DOCUMENT_TYPES
        | _IMAGE_TYPES
        | _MEDIA_TYPES
    )
    return declared_type in known_declared_types


def _extension_should_override_magic(
    *,
    magic_type: str | None,
    extension_type: str,
) -> bool:
    if magic_type is None:
        return True
    if (
        magic_type == "text/plain"
        and extension_type
        in _TIMED_TEXT_TYPES
        | _TEXT_TYPES
        | _PDF_TYPES
        | _STRUCTURED_DOCUMENT_TYPES
        | _IMAGE_TYPES
        | _MEDIA_TYPES
    ):
        return True
    if magic_type == "application/zip" and extension_type in _STRUCTURED_DOCUMENT_TYPES:
        return True
    return magic_type == "video/mp4" and extension_type == "audio/mp4"


def _extension_content_type(extension: str | None) -> str | None:
    return {
        "txt": "text/plain",
        "md": "text/markdown",
        "markdown": "text/markdown",
        "csv": "text/csv",
        "html": "text/html",
        "htm": "text/html",
        "json": "application/json",
        "pdf": "application/pdf",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "ppt": "application/vnd.ms-powerpoint",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "xls": "application/vnd.ms-excel",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "epub": "application/epub+zip",
        "eml": "message/rfc822",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
        "bmp": "image/bmp",
        "tif": "image/tiff",
        "tiff": "image/tiff",
        "srt": "application/x-subrip",
        "vtt": "text/vtt",
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
        "wav": "audio/wav",
        "flac": "audio/flac",
        "ogg": "audio/ogg",
        "oga": "audio/ogg",
        "mp4": "video/mp4",
        "m4v": "video/mp4",
        "mov": "video/quicktime",
        "webm": "video/webm",
        "mkv": "video/x-matroska",
    }.get(extension or "")


def _magic_content_type(content: bytes) -> str | None:
    prefix = content[:16]
    if prefix.startswith(b"%PDF"):
        return "application/pdf"
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if prefix.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if prefix.startswith(b"GIF87a") or prefix.startswith(b"GIF89a"):
        return "image/gif"
    if content[:12].startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    if content[:12].startswith(b"RIFF") and content[8:12] == b"WAVE":
        return "audio/wav"
    if prefix.startswith(b"ID3") or prefix[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}:
        return "audio/mpeg"
    if len(content) >= 12 and content[4:8] == b"ftyp":
        return "video/mp4"
    if prefix.startswith(b"PK\x03\x04"):
        return "application/zip"
    if _looks_like_utf8_text(content):
        return "text/plain"
    return None


def _looks_like_utf8_text(content: bytes) -> bool:
    if not content:
        return False
    try:
        text = content[:4096].decode("utf-8")
    except UnicodeDecodeError:
        return False
    if "\x00" in text:
        return False
    printable = sum(1 for ch in text if ch.isprintable() or ch.isspace())
    return printable / max(1, len(text)) > 0.92


def _decode_text(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("utf-8", errors="replace")


def _json_to_text(text: str) -> str:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _limit_text(text: str, max_chars: int) -> str:
    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped
    return stripped[:max_chars].rstrip()


def _merge_diagnostics(
    result: ExtractionResult,
    diagnostics: dict[str, object],
) -> ExtractionResult:
    merged = {**diagnostics, **result.diagnostics}
    return ExtractionResult(
        status=result.status,
        normalized_content_type=result.normalized_content_type,
        title=result.title,
        elements=result.elements,
        markdown=result.markdown,
        artifacts=result.artifacts,
        technical_metadata=result.technical_metadata,
        diagnostics=merged,
        language=result.language,
        parser_name=result.parser_name,
        parser_version=result.parser_version,
        model_version=result.model_version,
        safe_error_code=result.safe_error_code,
        safe_error_message=result.safe_error_message,
    )


def _result_allows_fallback(result: ExtractionResult) -> bool:
    return result.status == "unsupported" and result.diagnostics.get("fallback_allowed") is True


def _unsupported(
    request: ExtractionRequest,
    *,
    parser_name: str,
    parser_version: str | None,
    code: str,
    message: str,
    metadata: dict[str, object] | None = None,
) -> ExtractionResult:
    return ExtractionResult(
        status="unsupported",
        normalized_content_type=request.detected_content_type,
        title=request.filename,
        technical_metadata={
            "byte_size": request.byte_size,
            "mime_detected": request.detected_content_type,
            **(metadata or {}),
        },
        diagnostics={"engine": parser_name},
        parser_name=parser_name,
        parser_version=parser_version,
        safe_error_code=code,
        safe_error_message=message,
    )


def _run_tesseract_ocr(*, content: bytes, extension: str | None) -> tuple[str, str]:
    tesseract = shutil.which("tesseract")
    if not tesseract:
        return "", "unavailable"
    suffix = f".{extension}" if extension else ".img"
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix) as image_file:
            image_file.write(content)
            image_file.flush()
            completed = subprocess.run(
                [tesseract, image_file.name, "stdout"],
                check=False,
                capture_output=True,
                timeout=20,
            )
    except (OSError, subprocess.TimeoutExpired):
        return "", "failed"
    if completed.returncode != 0:
        return "", "failed"
    text = completed.stdout.decode("utf-8", errors="replace").strip()
    return text, "extracted" if text else "no_text"


def _parse_timed_text_segments(text: str) -> list[tuple[int, int, str]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", normalized)
    segments: list[tuple[int, int, str]] = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        if lines[0].upper().startswith("WEBVTT"):
            continue
        timestamp_index = next(
            (index for index, line in enumerate(lines) if _SUBTITLE_TIMESTAMP_RE.search(line)),
            None,
        )
        if timestamp_index is None:
            continue
        match = _SUBTITLE_TIMESTAMP_RE.search(lines[timestamp_index])
        if match is None:
            continue
        caption_lines = lines[timestamp_index + 1 :]
        segment_text = _clean_caption_text(" ".join(caption_lines))
        if not segment_text:
            continue
        segments.append(
            (
                _timestamp_to_ms(match.group("start")),
                _timestamp_to_ms(match.group("end")),
                segment_text,
            )
        )
    return segments


def _clean_caption_text(text: str) -> str:
    without_tags = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", without_tags).strip()


def _timestamp_to_ms(value: str) -> int:
    parts = value.replace(",", ".").split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return int(round(((hours * 60 + minutes) * 60 + seconds) * 1000))


def _format_timestamp_ms(value: int) -> str:
    milliseconds = value % 1000
    total_seconds = value // 1000
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"


def _safe_suffix(filename: str) -> str:
    extension = _extension(filename)
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


def _format_duration_seconds(value: float | None) -> str:
    if value is None:
        return "unknown"
    return f"{value:.2f}s"
