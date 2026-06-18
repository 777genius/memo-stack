"""Mapping helpers for asset extraction results stored as memory evidence."""

from __future__ import annotations

import json

from infinity_context_core.application.context_link_candidate_policy import source_text_risk_metadata
from infinity_context_core.application.safe_payload import safe_metadata, safe_metadata_text
from infinity_context_core.domain.assets import MemoryAsset
from infinity_context_core.domain.extraction import AssetExtractionJob
from infinity_context_core.ports.extraction import ExtractedElement, ExtractionResult

ASSET_EXTRACTION_SOURCE_TYPE = "asset_extraction"
_MAX_SOURCE_REFS = 200
_MAX_RESULT_JSON_ELEMENTS = 100
_MAX_RESULT_JSON_ELEMENT_TEXT_CHARS = 4_000


def extracted_text(result: ExtractionResult) -> str:
    if result.markdown and result.markdown.strip():
        return result.markdown.strip()
    return "\n\n".join(element.text.strip() for element in result.elements if element.text.strip())


def asset_extraction_chunk_metadata(
    *,
    asset: MemoryAsset,
    job: AssetExtractionJob,
    result: ExtractionResult,
    extracted_text_value: str,
) -> dict[str, object]:
    refs = _extraction_source_refs(
        job=job,
        result=result,
        extracted_text_value=extracted_text_value,
    )
    total_ref_candidates = _source_ref_candidate_count(result)
    metadata: dict[str, object] = {
        "source_kind": ASSET_EXTRACTION_SOURCE_TYPE,
        "asset_id": str(asset.id),
        "asset_filename": asset.filename,
        "asset_content_type": asset.content_type,
        "extraction_job_id": str(job.id),
        "parser_profile": job.parser_profile,
        "parser_name": safe_metadata_text(result.parser_name),
        "normalized_content_type": safe_metadata_text(result.normalized_content_type),
        "source_ref_count": len(refs),
        "source_ref_count_total": total_ref_candidates,
        "source_refs_limit": _MAX_SOURCE_REFS,
        "source_refs_truncated": total_ref_candidates > len(refs),
        "source_refs": refs,
        **source_text_risk_metadata(extracted_text_value),
    }
    if result.parser_version:
        metadata["parser_version"] = safe_metadata_text(result.parser_version)
    if result.model_version:
        metadata["model_version"] = safe_metadata_text(result.model_version)
    if result.language:
        metadata["language"] = safe_metadata_text(result.language)
    return metadata


def result_json(result: ExtractionResult) -> str:
    serialized_elements, text_truncated_count = _result_json_elements(result)
    payload = {
        "status": result.status,
        "normalized_content_type": safe_metadata_text(result.normalized_content_type),
        "title": result.title,
        "language": safe_metadata_text(result.language) if result.language else None,
        "parser_name": safe_metadata_text(result.parser_name),
        "parser_version": safe_metadata_text(result.parser_version)
        if result.parser_version
        else None,
        "model_version": safe_metadata_text(result.model_version) if result.model_version else None,
        "technical_metadata": safe_metadata(result.technical_metadata),
        "diagnostics": safe_metadata(result.diagnostics),
        "element_count_total": len(result.elements),
        "element_count_serialized": len(serialized_elements),
        "elements_truncated": len(result.elements) > len(serialized_elements),
        "element_text_truncated_count": text_truncated_count,
        "elements": serialized_elements,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def artifact_storage_key(
    *,
    space_id: str,
    memory_scope_id: str,
    job_id: str,
    digest: str,
    filename: str,
) -> str:
    safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in filename)[:160]
    return f"{space_id}/{memory_scope_id}/extractions/{job_id}/{digest[:2]}/{digest}/{safe_name}"


def _result_json_elements(result: ExtractionResult) -> tuple[list[dict[str, object]], int]:
    items: list[dict[str, object]] = []
    text_truncated_count = 0
    for element in result.elements[:_MAX_RESULT_JSON_ELEMENTS]:
        safe_text = safe_metadata_text(
            element.text,
            limit=_MAX_RESULT_JSON_ELEMENT_TEXT_CHARS,
        )
        if len(element.text) > len(safe_text):
            text_truncated_count += 1
        items.append(
            {
                "kind": safe_metadata_text(element.kind, limit=120),
                "text": safe_text,
                "page_number": element.page_number,
                "time_start_ms": element.time_start_ms,
                "time_end_ms": element.time_end_ms,
                "bbox": element.bbox,
                "confidence": element.confidence,
                "metadata": safe_metadata(element.metadata),
            }
        )
    return items, text_truncated_count


def _extraction_source_refs(
    *,
    job: AssetExtractionJob,
    result: ExtractionResult,
    extracted_text_value: str,
) -> list[dict[str, object]]:
    refs: list[dict[str, object]] = []
    cursor = 0
    for index, element in enumerate(result.elements):
        text = element.text.strip()
        if not text:
            continue
        span = _find_element_span(extracted_text_value, text, cursor)
        if span is not None:
            cursor = span[1]
        refs.append(
            _element_source_ref(
                job=job,
                index=index,
                element=element,
                text=text,
                span=span,
            )
        )
        if len(refs) >= _MAX_SOURCE_REFS:
            break
    if refs:
        return refs
    return [
        {
            "source_type": ASSET_EXTRACTION_SOURCE_TYPE,
            "source_id": str(job.id),
            "asset_id": str(job.asset_id),
            "kind": "extracted_text",
            "char_start": 0,
            "char_end": len(extracted_text_value),
            "quote_preview": extracted_text_value[:240],
        }
    ]


def _source_ref_candidate_count(result: ExtractionResult) -> int:
    count = sum(1 for element in result.elements if element.text.strip())
    return count or 1


def _element_source_ref(
    *,
    job: AssetExtractionJob,
    index: int,
    element: ExtractedElement,
    text: str,
    span: tuple[int, int] | None,
) -> dict[str, object]:
    ref: dict[str, object] = {
        "source_type": ASSET_EXTRACTION_SOURCE_TYPE,
        "source_id": str(job.id),
        "asset_id": str(job.asset_id),
        "element_index": index,
        "kind": element.kind,
        "quote_preview": text[:240],
    }
    if span is not None:
        ref["char_start"] = span[0]
        ref["char_end"] = span[1]
    if element.page_number is not None:
        ref["page_number"] = element.page_number
    if element.time_start_ms is not None:
        ref["time_start_ms"] = element.time_start_ms
    if element.time_end_ms is not None:
        ref["time_end_ms"] = element.time_end_ms
    if element.bbox is not None:
        ref["bbox"] = [float(value) for value in element.bbox]
    if element.confidence is not None:
        ref["confidence"] = element.confidence
    provider_source = element.metadata.get("source")
    if isinstance(provider_source, str) and provider_source.strip():
        ref["provider_source"] = safe_metadata_text(provider_source.strip(), limit=120)
    return ref


def _find_element_span(
    extracted_text_value: str,
    element_text: str,
    cursor: int,
) -> tuple[int, int] | None:
    start = extracted_text_value.find(element_text, max(cursor, 0))
    if start < 0:
        start = extracted_text_value.find(element_text)
    if start < 0:
        return None
    return start, start + len(element_text)
