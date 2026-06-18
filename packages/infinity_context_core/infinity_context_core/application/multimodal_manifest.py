"""Provider-neutral multimodal extraction manifest."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from hashlib import sha256

from infinity_context_core.application.safe_payload import safe_metadata_text
from infinity_context_core.domain.assets import MemoryAsset
from infinity_context_core.domain.extraction import AssetExtractionJob
from infinity_context_core.ports.extraction import (
    ExtractedElement,
    ExtractionArtifactCandidate,
    ExtractionResult,
)

MULTIMODAL_MANIFEST_SCHEMA_VERSION = "infinity_context.multimodal_manifest.v1"
MULTIMODAL_MANIFEST_CONTRACT_SCHEMA_VERSION = "infinity_context.multimodal_manifest_contract.v1"

_SOURCE_TYPE = "asset_extraction"
_MAX_EVIDENCE_ITEMS = 500
_MAX_ARTIFACT_ITEMS = 100
_MAX_TEXT_PREVIEW_CHARS = 600
_MODALITY_ORDER = ("text", "document", "image", "audio", "video")
_COORDINATE_FIELDS = ("page_number", "bbox", "time_range")
_FEATURE_FIELDS = (
    "modalities",
    "coordinate_fields_present",
    "evidence_kinds",
    "artifact_types",
    "has_text_preview",
    "has_page_refs",
    "has_bbox_refs",
    "has_time_ranges",
    "has_confidence",
    "has_artifacts",
    "has_extraction_metadata",
    "has_diagnostics",
    "has_language",
    "has_model_version",
)


def multimodal_manifest_artifact_candidate(
    *,
    asset: MemoryAsset,
    job: AssetExtractionJob,
    result: ExtractionResult,
) -> ExtractionArtifactCandidate:
    payload = multimodal_manifest_payload(asset=asset, job=job, result=result)
    content = json.dumps(payload, allow_nan=False, ensure_ascii=False, sort_keys=True).encode(
        "utf-8"
    )
    return ExtractionArtifactCandidate(
        artifact_type="media_manifest",
        filename="media_manifest.json",
        content_type="application/json",
        content=content,
        metadata={
            "schema_version": MULTIMODAL_MANIFEST_SCHEMA_VERSION,
            "parser": safe_metadata_text(result.parser_name),
            "evidence_item_count": payload["evidence_item_count"],
            "evidence_items_truncated": payload["evidence_items_truncated"],
        },
    )


def should_store_generic_multimodal_manifest(result: ExtractionResult) -> bool:
    if any(artifact.artifact_type == "media_manifest" for artifact in result.artifacts):
        return False
    if _content_type_modality(result.normalized_content_type) in {"image", "audio", "video"}:
        return bool(result.elements or result.artifacts)
    if _content_type_modality(result.normalized_content_type) == "document":
        return bool(result.elements)
    return any(
        element.page_number is not None
        or element.time_start_ms is not None
        or element.time_end_ms is not None
        or element.bbox is not None
        for element in result.elements
    )


def multimodal_manifest_payload(
    *,
    asset: MemoryAsset,
    job: AssetExtractionJob,
    result: ExtractionResult,
) -> dict[str, object]:
    evidence_items, text_truncated_count = _evidence_items(asset=asset, job=job, result=result)
    artifact_items = _artifact_items(result)
    modalities = _modalities(
        evidence_items=evidence_items,
        content_type=result.normalized_content_type,
    )
    return {
        "schema_version": MULTIMODAL_MANIFEST_SCHEMA_VERSION,
        "contract": multimodal_manifest_contract_payload(),
        "asset": {
            "id": str(asset.id),
            "filename": safe_metadata_text(asset.filename, limit=240),
            "content_type": safe_metadata_text(asset.content_type, limit=120),
            "normalized_content_type": safe_metadata_text(
                result.normalized_content_type,
                limit=120,
            ),
            "byte_size": asset.byte_size,
            "sha256_hex": asset.sha256_hex,
            "classification": safe_metadata_text(asset.classification, limit=80),
        },
        "extraction": {
            "job_id": str(job.id),
            "parser_profile": safe_metadata_text(job.parser_profile, limit=80),
            "parser_name": safe_metadata_text(result.parser_name, limit=120),
            "parser_version": safe_metadata_text(result.parser_version, limit=120)
            if result.parser_version
            else None,
            "model_version": safe_metadata_text(result.model_version, limit=120)
            if result.model_version
            else None,
            "language": safe_metadata_text(result.language, limit=80) if result.language else None,
            "status": safe_metadata_text(result.status, limit=80),
            "technical_metadata": _safe_manifest_metadata(result.technical_metadata),
            "diagnostics": _safe_manifest_metadata(result.diagnostics),
        },
        "modalities": modalities,
        "features": _feature_summary(
            evidence_items=evidence_items,
            artifact_items=artifact_items,
            result=result,
            modalities=modalities,
        ),
        "evidence_item_count": len(evidence_items),
        "evidence_item_count_total": len(result.elements),
        "evidence_item_limit": _MAX_EVIDENCE_ITEMS,
        "evidence_items_truncated": len(result.elements) > len(evidence_items),
        "evidence_text_preview_limit": _MAX_TEXT_PREVIEW_CHARS,
        "evidence_text_preview_truncated_count": text_truncated_count,
        "evidence_items": evidence_items,
        "artifact_count": len(artifact_items),
        "artifact_count_total": len(result.artifacts),
        "artifact_limit": _MAX_ARTIFACT_ITEMS,
        "artifacts_truncated": len(result.artifacts) > len(artifact_items),
        "artifacts": artifact_items,
    }


def multimodal_manifest_contract_payload() -> dict[str, object]:
    return {
        "schema_version": MULTIMODAL_MANIFEST_CONTRACT_SCHEMA_VERSION,
        "manifest_schema_version": MULTIMODAL_MANIFEST_SCHEMA_VERSION,
        "artifact_type": "media_manifest",
        "source_type": _SOURCE_TYPE,
        "evidence_item_fields": [
            "id",
            "source",
            "kind",
            "modality",
            "text_preview",
            "page_number",
            "bbox",
            "time_range",
            "confidence",
            "metadata",
        ],
        "coordinate_fields": list(_COORDINATE_FIELDS),
        "feature_fields": list(_FEATURE_FIELDS),
        "coordinates_are_optional_per_item": True,
        "provider_output_policy": "evidence_not_truth",
        "metadata_policy": (
            "bounded_scalar_metadata_without_sensitive_keys_or_raw_provider_payloads"
        ),
        "raw_provider_payloads_in_public_api": False,
        "raw_artifact_bytes_in_public_api": False,
        "artifact_integrity": {
            "hash_algorithm": "sha256",
            "byte_size_included": True,
        },
    }


def _evidence_items(
    *,
    asset: MemoryAsset,
    job: AssetExtractionJob,
    result: ExtractionResult,
) -> tuple[list[dict[str, object]], int]:
    items: list[dict[str, object]] = []
    text_truncated_count = 0
    for index, element in enumerate(result.elements[:_MAX_EVIDENCE_ITEMS]):
        text_preview = safe_metadata_text(element.text, limit=_MAX_TEXT_PREVIEW_CHARS)
        if len(element.text) > len(text_preview):
            text_truncated_count += 1
        item: dict[str, object] = {
            "id": f"element:{index}",
            "source": {
                "source_type": _SOURCE_TYPE,
                "source_id": str(job.id),
                "asset_id": str(asset.id),
                "element_index": index,
            },
            "kind": _safe_kind(element.kind),
            "modality": _element_modality(element, result.normalized_content_type),
            "text_preview": text_preview,
            "metadata": _safe_manifest_metadata(element.metadata),
        }
        if element.page_number is not None:
            item["page_number"] = max(1, int(element.page_number))
        bbox = _normalized_bbox(element.bbox)
        if bbox is not None:
            item["bbox"] = bbox
        time_range = _time_range(element)
        if time_range:
            item["time_range"] = time_range
        confidence = _normalized_confidence(element.confidence)
        if confidence is not None:
            item["confidence"] = confidence
        items.append(item)
    return items, text_truncated_count


def _artifact_items(result: ExtractionResult) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for index, artifact in enumerate(result.artifacts[:_MAX_ARTIFACT_ITEMS]):
        content = artifact.content
        items.append(
            {
                "id": f"artifact_candidate:{index}",
                "artifact_type": _safe_kind(artifact.artifact_type),
                "filename": safe_metadata_text(artifact.filename, limit=240),
                "content_type": safe_metadata_text(artifact.content_type, limit=120),
                "byte_size": len(content),
                "sha256_hex": sha256(content).hexdigest(),
                "metadata": _safe_manifest_metadata(artifact.metadata),
            }
        )
    return items


def _feature_summary(
    *,
    evidence_items: list[dict[str, object]],
    artifact_items: list[dict[str, object]],
    result: ExtractionResult,
    modalities: list[str],
) -> dict[str, object]:
    coordinate_fields = [
        field
        for field in _COORDINATE_FIELDS
        if any(field in item for item in evidence_items)
    ]
    artifact_types = _ordered_unique_safe_kinds(
        str(item.get("artifact_type") or "") for item in artifact_items
    )
    evidence_kinds = _ordered_unique_safe_kinds(
        str(item.get("kind") or "") for item in evidence_items
    )
    return {
        "modalities": modalities,
        "coordinate_fields_present": coordinate_fields,
        "evidence_kinds": evidence_kinds,
        "artifact_types": artifact_types,
        "has_text_preview": any(bool(item.get("text_preview")) for item in evidence_items),
        "has_page_refs": "page_number" in coordinate_fields,
        "has_bbox_refs": "bbox" in coordinate_fields,
        "has_time_ranges": "time_range" in coordinate_fields,
        "has_confidence": any("confidence" in item for item in evidence_items),
        "has_artifacts": bool(artifact_items),
        "has_extraction_metadata": bool(result.technical_metadata),
        "has_diagnostics": bool(result.diagnostics),
        "has_language": bool(result.language),
        "has_model_version": bool(result.model_version),
    }


def _ordered_unique_safe_kinds(values: Iterable[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        safe = _safe_kind(str(value))
        if safe == "unknown" or safe in seen:
            continue
        unique.append(safe)
        seen.add(safe)
        if len(unique) >= 40:
            break
    return unique


def _modalities(*, evidence_items: list[dict[str, object]], content_type: str) -> list[str]:
    present = {str(item["modality"]) for item in evidence_items}
    fallback = _content_type_modality(content_type)
    if fallback:
        present.add(fallback)
    if any(item.get("text_preview") for item in evidence_items):
        present.add("text")
    return [modality for modality in _MODALITY_ORDER if modality in present]


def _element_modality(element: ExtractedElement, content_type: str) -> str:
    kind = _safe_kind(element.kind)
    if kind in {"keyframe", "video_frame", "video_frame_timeline"}:
        return "video"
    if kind in {"transcript", "transcript_segment", "speech_segment", "word"}:
        return "audio"
    if element.time_start_ms is not None or element.time_end_ms is not None:
        return "video" if _content_type_modality(content_type) == "video" else "audio"
    if kind in {"ocr_region", "image_region", "vision_region"}:
        return "image"
    if element.bbox is not None and _content_type_modality(content_type) == "image":
        return "image"
    if element.page_number is not None or kind in {"table", "heading", "paragraph"}:
        return "document"
    return _content_type_modality(content_type) or "text"


def _content_type_modality(content_type: str) -> str | None:
    safe = content_type.strip().lower()
    if safe.startswith("image/"):
        return "image"
    if safe.startswith("audio/"):
        return "audio"
    if safe.startswith("video/"):
        return "video"
    if safe in {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/html",
    }:
        return "document"
    if safe.startswith("text/"):
        return "text"
    return None


def _time_range(element: ExtractedElement) -> dict[str, int] | None:
    start = element.time_start_ms
    end = element.time_end_ms
    if start is None and end is None:
        return None
    result: dict[str, int] = {}
    if start is not None:
        result["start_ms"] = max(0, int(start))
    if end is not None:
        result["end_ms"] = max(0, int(end))
    if "start_ms" in result and "end_ms" in result and result["end_ms"] < result["start_ms"]:
        result["end_ms"] = result["start_ms"]
    return result


def _normalized_bbox(value: tuple[float, float, float, float] | None) -> list[float] | None:
    if value is None or len(value) != 4:
        return None
    bbox: list[float] = []
    for raw in value:
        number = float(raw)
        if not math.isfinite(number):
            return None
        bbox.append(round(number, 4))
    return bbox


def _normalized_confidence(value: float | None) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    if number > 1 and number <= 100:
        number = number / 100
    return round(min(max(number, 0.0), 1.0), 4)


def _safe_kind(value: str) -> str:
    safe = safe_metadata_text(value, limit=80).strip().lower().replace("-", "_")
    return "_".join(part for part in safe.split() if part) or "unknown"


def _safe_manifest_metadata(metadata: dict[str, object]) -> dict[str, object]:
    safe: dict[str, object] = {}
    for raw_key, raw_value in list(metadata.items())[:40]:
        key = safe_metadata_text(str(raw_key), limit=80).strip()
        if not key or _sensitive_manifest_metadata_key(key):
            continue
        if isinstance(raw_value, str):
            safe[key] = safe_metadata_text(raw_value, limit=240)
        elif raw_value is None or isinstance(raw_value, (bool, int)) or (
            isinstance(raw_value, float) and math.isfinite(raw_value)
        ):
            safe[key] = raw_value
    return safe


def _sensitive_manifest_metadata_key(key: str) -> bool:
    lowered = key.lower()
    return any(
        marker in lowered
        for marker in (
            "api_key",
            "apikey",
            "auth",
            "authorization",
            "credential",
            "password",
            "passwd",
            "private",
            "raw",
            "secret",
            "token",
        )
    )
