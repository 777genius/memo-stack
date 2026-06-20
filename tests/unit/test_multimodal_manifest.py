import json
from datetime import UTC, datetime

from infinity_context_core.application.multimodal_manifest import (
    MULTIMODAL_MANIFEST_CONTRACT_SCHEMA_VERSION,
    MULTIMODAL_MANIFEST_SCHEMA_VERSION,
    multimodal_manifest_artifact_candidate,
    multimodal_manifest_payload,
    should_store_generic_multimodal_manifest,
)
from infinity_context_core.domain.assets import MemoryAsset, MemoryAssetId
from infinity_context_core.domain.entities import MemoryScopeId, SpaceId, ThreadId
from infinity_context_core.domain.extraction import AssetExtractionJob, AssetExtractionJobId
from infinity_context_core.ports.extraction import (
    ExtractedElement,
    ExtractionArtifactCandidate,
    ExtractionResult,
)

NOW = datetime(2026, 6, 18, tzinfo=UTC)


def test_multimodal_manifest_normalizes_document_image_audio_and_video_evidence() -> None:
    asset = _asset(content_type="video/mp4", filename="atlas-demo.mp4")
    job = _job(asset=asset)
    result = ExtractionResult(
        status="succeeded",
        normalized_content_type="video/mp4",
        title="Atlas demo",
        elements=(
            ExtractedElement(
                kind="heading",
                text="Project Atlas launch review",
                page_number=1,
                confidence=0.91,
            ),
            ExtractedElement(
                kind="ocr-region",
                text="Deploy button visible",
                bbox=(12.2, 33, 120.12345, 88.8),
                confidence=87,
            ),
            ExtractedElement(
                kind="transcript_segment",
                text="Alex says the launch checklist is ready.",
                time_start_ms=1200,
                time_end_ms=3400,
                confidence=0.78,
                metadata={"speaker": "Alex", "raw_private_note": {"ignored": True}},
            ),
            ExtractedElement(
                kind="keyframe",
                text="Frame shows staging dashboard.",
                time_start_ms=4000,
                time_end_ms=3000,
            ),
        ),
        artifacts=(
            ExtractionArtifactCandidate(
                artifact_type="keyframe",
                filename="frame-0001.jpg",
                content_type="image/jpeg",
                content=b"frame-bytes",
                metadata={"frame_index": 1},
            ),
        ),
        parser_name="test-parser",
        parser_version="1.2.3",
        model_version="vision-test",
        language="en",
        technical_metadata={
            "provider_request_id": "req_123",
            "duration_seconds": 4.2,
            "raw_provider_payload": "must-not-leak",
            "bad_float": float("nan"),
        },
        diagnostics={"provider_timeout": False, "secret_token": "must-not-leak"},
    )

    payload = multimodal_manifest_payload(asset=asset, job=job, result=result)

    assert payload["schema_version"] == MULTIMODAL_MANIFEST_SCHEMA_VERSION
    assert payload["contract"]["schema_version"] == MULTIMODAL_MANIFEST_CONTRACT_SCHEMA_VERSION
    assert payload["contract"]["provider_output_policy"] == "evidence_not_truth"
    assert payload["contract"]["raw_provider_payloads_in_public_api"] is False
    assert payload["contract"]["coordinate_fields"] == ["page_number", "bbox", "time_range"]
    assert "reversed time_range ends are dropped" in payload["contract"][
        "coordinate_validation_policy"
    ]
    assert payload["modalities"] == ["text", "document", "image", "audio", "video"]
    assert payload["features"] == {
        "modalities": ["text", "document", "image", "audio", "video"],
        "coordinate_fields_present": ["page_number", "bbox", "time_range"],
        "evidence_kinds": ["heading", "ocr_region", "transcript_segment", "keyframe"],
        "artifact_types": ["keyframe"],
        "has_text_preview": True,
        "has_page_refs": True,
        "has_bbox_refs": True,
        "has_time_ranges": True,
        "has_confidence": True,
        "has_artifacts": True,
        "has_extraction_metadata": True,
        "has_diagnostics": True,
        "has_language": True,
        "has_model_version": True,
    }
    assert payload["evidence_item_count"] == 4
    assert payload["evidence_items_truncated"] is False
    items = payload["evidence_items"]
    assert [item["modality"] for item in items] == ["document", "image", "audio", "video"]
    assert items[0]["page_number"] == 1
    assert items[1]["bbox"] == [12.2, 33.0, 120.1235, 88.8]
    assert items[1]["confidence"] == 0.87
    assert items[2]["time_range"] == {"start_ms": 1200, "end_ms": 3400}
    assert items[2]["metadata"] == {"speaker": "Alex"}
    assert items[3]["time_range"] == {"start_ms": 4000}
    assert payload["artifacts"][0]["artifact_type"] == "keyframe"
    assert payload["artifacts"][0]["byte_size"] == len(b"frame-bytes")
    extraction = payload["extraction"]
    assert extraction["technical_metadata"] == {
        "provider_request_id": "req_123",
        "duration_seconds": 4.2,
    }
    assert extraction["diagnostics"] == {"provider_timeout": False}
    serialized = json.dumps(payload, allow_nan=False)
    assert "frame-bytes" not in serialized
    assert "must-not-leak" not in serialized


def test_multimodal_manifest_drops_invalid_coordinate_values() -> None:
    asset = _asset(content_type="video/mp4", filename="bad-coordinates.mp4")
    job = _job(asset=asset)
    result = ExtractionResult(
        status="succeeded",
        normalized_content_type="video/mp4",
        title="Bad coordinates",
        elements=(
            ExtractedElement(
                kind="ocr_region",
                text="Negative bbox should not be published.",
                page_number=0,
                bbox=(-1.0, 4.0, 120.0, 44.0),
            ),
            ExtractedElement(
                kind="ocr_region",
                text="Degenerate bbox should not be published.",
                bbox=(10.0, 10.0, 8.0, 20.0),
            ),
            ExtractedElement(
                kind="transcript_segment",
                text="Negative time should not be published.",
                time_start_ms=-10,
                time_end_ms=-1,
            ),
            ExtractedElement(
                kind="keyframe",
                text="Reversed end should be dropped but valid start remains.",
                time_start_ms=5000,
                time_end_ms=4000,
            ),
        ),
        parser_name="test-parser",
    )

    payload = multimodal_manifest_payload(asset=asset, job=job, result=result)

    items = payload["evidence_items"]
    assert "page_number" not in items[0]
    assert "bbox" not in items[0]
    assert "bbox" not in items[1]
    assert "time_range" not in items[2]
    assert items[3]["time_range"] == {"start_ms": 5000}
    assert payload["features"]["coordinate_fields_present"] == ["time_range"]
    assert payload["features"]["has_bbox_refs"] is False
    assert payload["features"]["has_time_ranges"] is True


def test_multimodal_manifest_bounds_evidence_and_text_previews() -> None:
    asset = _asset(content_type="application/pdf", filename="large.pdf")
    job = _job(asset=asset)
    long_text = "A" * 800
    elements = tuple(
        ExtractedElement(kind="paragraph", text=long_text, page_number=index + 1)
        for index in range(520)
    )
    result = ExtractionResult(
        status="succeeded",
        normalized_content_type="application/pdf",
        title="Large document",
        elements=elements,
        parser_name="test-parser",
    )

    payload = multimodal_manifest_payload(asset=asset, job=job, result=result)

    assert payload["modalities"] == ["text", "document"]
    assert payload["evidence_item_count"] == 500
    assert payload["evidence_item_count_total"] == 520
    assert payload["evidence_item_limit"] == 500
    assert payload["evidence_items_truncated"] is True
    assert payload["evidence_text_preview_truncated_count"] == 500
    assert len(payload["evidence_items"][0]["text_preview"]) == 600
    assert payload["evidence_items"][-1]["source"]["element_index"] == 499


def test_multimodal_manifest_artifact_candidate_uses_media_manifest_type() -> None:
    asset = _asset(content_type="audio/wav", filename="call.wav")
    job = _job(asset=asset)
    result = ExtractionResult(
        status="succeeded",
        normalized_content_type="audio/wav",
        title="Call",
        elements=(
            ExtractedElement(
                kind="speech_segment",
                text="Alex confirmed the payment status.",
                time_start_ms=0,
                time_end_ms=1500,
            ),
        ),
        parser_name="audio-parser",
    )

    candidate = multimodal_manifest_artifact_candidate(asset=asset, job=job, result=result)
    payload = json.loads(candidate.content.decode("utf-8"))

    assert candidate.artifact_type == "media_manifest"
    assert candidate.filename == "media_manifest.json"
    assert candidate.content_type == "application/json"
    assert candidate.metadata["schema_version"] == MULTIMODAL_MANIFEST_SCHEMA_VERSION
    assert candidate.metadata["evidence_item_count"] == 1
    assert payload["contract"]["schema_version"] == MULTIMODAL_MANIFEST_CONTRACT_SCHEMA_VERSION
    assert payload["modalities"] == ["text", "audio"]
    assert payload["features"]["coordinate_fields_present"] == ["time_range"]
    assert payload["evidence_items"][0]["modality"] == "audio"


def test_generic_multimodal_manifest_is_skipped_for_text_only_and_provider_manifest() -> None:
    text_result = ExtractionResult(
        status="succeeded",
        normalized_content_type="text/plain",
        title="Plain note",
        elements=(ExtractedElement(kind="paragraph", text="plain text"),),
        parser_name="text-parser",
    )
    media_result = ExtractionResult(
        status="succeeded",
        normalized_content_type="audio/wav",
        title="Call",
        elements=(ExtractedElement(kind="speech_segment", text="hello", time_start_ms=0),),
        artifacts=(
            ExtractionArtifactCandidate(
                artifact_type="media_manifest",
                filename="provider-media.json",
                content_type="application/json",
                content=b"{}",
            ),
        ),
        parser_name="media-parser",
    )
    pdf_result = ExtractionResult(
        status="succeeded",
        normalized_content_type="application/pdf",
        title="PDF",
        elements=(ExtractedElement(kind="paragraph", text="page text", page_number=1),),
        parser_name="pdf-parser",
    )

    assert should_store_generic_multimodal_manifest(text_result) is False
    assert should_store_generic_multimodal_manifest(media_result) is False
    assert should_store_generic_multimodal_manifest(pdf_result) is True


def _asset(*, content_type: str, filename: str) -> MemoryAsset:
    return MemoryAsset.create(
        asset_id=MemoryAssetId("asset-1"),
        space_id=SpaceId("space-1"),
        memory_scope_id=MemoryScopeId("scope-1"),
        thread_id=ThreadId("thread-1"),
        filename=filename,
        content_type=content_type,
        byte_size=1024,
        sha256_hex="a" * 64,
        storage_backend="local",
        storage_key=f"assets/{filename}",
        now=NOW,
    )


def _job(*, asset: MemoryAsset) -> AssetExtractionJob:
    return AssetExtractionJob.create(
        job_id=AssetExtractionJobId("extract-1"),
        asset_id=asset.id,
        space_id=asset.space_id,
        memory_scope_id=asset.memory_scope_id,
        thread_id=asset.thread_id,
        parser_profile="standard_local",
        parser_config_hash="f" * 64,
        source_sha256_hex=asset.sha256_hex,
        now=NOW,
    )
