"""Optional Docling document extraction engine."""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
import tempfile
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from infinity_context_core.ports.extraction import (
    ExtractionArtifactCandidate,
    ExtractionRequest,
    ExtractionResult,
)

from infinity_context_adapters.extraction.content import (
    _IMAGE_TYPES,
    _PDF_TYPES,
    _STRUCTURED_DOCUMENT_TYPES,
    ExtractionEngine,
    SupportDecision,
    _limit_text,
    _safe_suffix,
    _unsupported,
)
from infinity_context_adapters.extraction.document_normalization import (
    normalize_docling_document,
)

_DOCLING_PROFILES = {"docling", "standard_docling", "standard_full", "full"}
_DOCLING_TEXT_TYPES = {"text/html", "text/markdown", "text/plain"}
_DOCLING_CONTENT_TYPES = (
    _PDF_TYPES | _STRUCTURED_DOCUMENT_TYPES | _IMAGE_TYPES | _DOCLING_TEXT_TYPES
)


class DoclingDocumentExtractionEngine(ExtractionEngine):
    name = "docling_document"

    def __init__(self, converter_factory: Callable[[], Any] | None = None) -> None:
        self._converter_factory = converter_factory

    async def supports(self, request: ExtractionRequest) -> SupportDecision:
        if not _profile_wants_docling(request.parser_profile):
            return SupportDecision(False, reason="parser_profile_not_docling")
        if request.detected_content_type not in _DOCLING_CONTENT_TYPES:
            return SupportDecision(False, reason="not_docling_document")
        if self._converter_factory is not None:
            return SupportDecision(True)
        if _load_docling_converter_factory() is not None:
            return SupportDecision(True)
        return SupportDecision(False, reason="docling_not_installed")

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._extract_sync, request),
                timeout=max(0.001, float(request.limits.parser_timeout_seconds)),
            )
        except TimeoutError:
            return _fallback_unsupported(
                request,
                code="asset_extraction.docling_timeout",
                message="Docling document conversion timed out",
                parser_version=_docling_version(),
                metadata={
                    "parser_timeout_seconds": request.limits.parser_timeout_seconds,
                },
            )

    def _extract_sync(self, request: ExtractionRequest) -> ExtractionResult:
        converter_factory = self._converter_factory or _load_docling_converter_factory()
        if converter_factory is None:
            return _fallback_unsupported(
                request,
                code="asset_extraction.docling_not_installed",
                message="Docling is not installed for this parser profile",
                parser_version=None,
            )

        try:
            with tempfile.NamedTemporaryFile(suffix=_safe_suffix(request.filename)) as source_file:
                source_file.write(request.content)
                source_file.flush()
                conversion = converter_factory().convert(
                    source_file.name,
                    max_num_pages=request.limits.max_pages,
                    max_file_size=request.limits.max_bytes,
                )
        except Exception:
            return _fallback_unsupported(
                request,
                code="asset_extraction.docling_conversion_failed",
                message="Docling document conversion failed",
                parser_version=_docling_version(),
            )

        document = getattr(conversion, "document", None)
        if document is None:
            return _fallback_unsupported(
                request,
                code="asset_extraction.docling_empty_document",
                message="Docling returned no document",
                parser_version=_docling_version(),
            )

        markdown = _document_markdown(document)
        if not markdown.strip():
            return _fallback_unsupported(
                request,
                code="asset_extraction.docling_empty_text",
                message="Docling returned no searchable text",
                parser_version=_docling_version(),
            )

        markdown = _limit_text(markdown, request.limits.max_output_chars)
        docling_metadata = _conversion_metadata(conversion)
        normalized = normalize_docling_document(
            document=document,
            markdown=markdown,
            max_tables=request.limits.max_tables,
            max_output_chars=request.limits.max_output_chars,
            parser_name=self.name,
        )
        artifacts = (
            _normalized_json_artifact(
                document=document,
                parser_name=self.name,
                parser_version=_docling_version(),
            ),
            *normalized.artifacts,
        )
        return ExtractionResult(
            status="succeeded",
            normalized_content_type=request.detected_content_type,
            title=request.filename.strip() or "Docling document",
            markdown=markdown,
            elements=normalized.elements,
            artifacts=tuple(item for item in artifacts if item is not None),
            technical_metadata={
                "byte_size": request.byte_size,
                "mime_detected": request.detected_content_type,
                "output_chars": len(markdown),
                "docling_status": _safe_text(getattr(conversion, "status", None)),
                **docling_metadata,
                **normalized.metadata,
            },
            diagnostics={"engine": self.name},
            parser_name=self.name,
            parser_version=_docling_version(),
        )


def _profile_wants_docling(parser_profile: str) -> bool:
    normalized = parser_profile.strip().lower()
    return normalized in _DOCLING_PROFILES or normalized.startswith("docling:")


def _load_docling_converter_factory() -> Callable[[], Any] | None:
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        return None
    return DocumentConverter


def _document_markdown(document: Any) -> str:
    export = getattr(document, "export_to_markdown", None)
    if callable(export):
        return str(export() or "").strip()
    export_text = getattr(document, "export_to_text", None)
    if callable(export_text):
        return str(export_text() or "").strip()
    return str(document or "").strip()


def _conversion_metadata(conversion: Any) -> dict[str, object]:
    metadata: dict[str, object] = {}
    for key in ("pages", "page_count", "num_pages"):
        value = getattr(conversion, key, None)
        if isinstance(value, int) and value >= 0:
            metadata["page_count"] = value
            break
    timings = getattr(conversion, "timings", None)
    if isinstance(timings, dict):
        metadata["docling_timing_count"] = len(timings)
    errors = getattr(conversion, "errors", None)
    if isinstance(errors, list):
        metadata["docling_error_count"] = len(errors)
    return metadata


def _normalized_json_artifact(
    *,
    document: Any,
    parser_name: str,
    parser_version: str | None,
) -> ExtractionArtifactCandidate | None:
    export = getattr(document, "export_to_dict", None)
    if not callable(export):
        return None
    try:
        payload = export(mode="json", by_alias=True, exclude_none=True, coord_precision=2)
    except TypeError:
        try:
            payload = export()
        except Exception:
            return None
    except Exception:
        return None
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return ExtractionArtifactCandidate(
        artifact_type="normalized_json",
        filename="docling-normalized.json",
        content_type="application/json",
        content=content,
        metadata={
            "parser": parser_name,
            **({"parser_version": parser_version} if parser_version else {}),
        },
    )


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
        parser_name=DoclingDocumentExtractionEngine.name,
        parser_version=parser_version,
        code=code,
        message=message,
        metadata=metadata,
    )
    return replace(result, diagnostics={**result.diagnostics, "fallback_allowed": True})


def _docling_version() -> str | None:
    try:
        return importlib.metadata.version("docling")
    except importlib.metadata.PackageNotFoundError:
        return None


def _safe_text(value: object) -> str | None:
    text = str(value).strip()
    return text or None
