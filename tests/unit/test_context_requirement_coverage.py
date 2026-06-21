from infinity_context_core.application.context_query_intent import build_query_anchor_intent
from infinity_context_core.application.context_requirement_coverage import (
    context_requirement_coverage,
    sanitize_context_requirement_coverage,
)
from infinity_context_core.application.dto import ContextItem
from infinity_context_core.domain.entities import SourceRef


def test_context_requirement_coverage_satisfies_anchor_and_multimodal_request() -> None:
    query = "созвон с алексом про атлас час назад, дай цитату и таймкод"
    intent = build_query_anchor_intent(query)
    items = (
        ContextItem(
            item_id="anchor_event_call",
            item_type="anchor",
            text="event: Call with Alex about Atlas hour ago.",
            score=0.94,
            source_refs=(),
            diagnostics={"anchor_kind": "event", "memory_scope_id": "scope"},
        ),
        ContextItem(
            item_id="artifact_audio_segment",
            item_type="extraction_artifact",
            text="Transcript: Alex approved Atlas rollout.",
            score=0.91,
            source_refs=(
                SourceRef(
                    source_type="extraction_artifact",
                    source_id="artifact_audio",
                    chunk_id="segment_1",
                    quote_preview="Alex approved Atlas rollout.",
                    time_start_ms=1200,
                    time_end_ms=6400,
                ),
            ),
            diagnostics={
                "evidence_kind": "transcript_segment",
                "evidence_modality": "audio",
                "memory_scope_id": "scope",
            },
        ),
    )

    coverage = context_requirement_coverage(
        query=query,
        query_anchor_intent=intent,
        items=items,
    )

    assert coverage["status"] == "satisfied"
    assert set(coverage["requested_anchor_kinds"]) >= {"person", "project", "event"}
    assert set(coverage["covered_anchor_kinds"]) >= {"event", "person", "project"}
    assert coverage["requested_modalities"] == ["audio"]
    assert coverage["covered_modalities"] == ["audio"]
    assert set(coverage["requested_evidence_features"]) == {"citation", "time_range"}
    assert set(coverage["covered_evidence_features"]) >= {"citation", "time_range"}
    assert coverage["missing_total"] == 0
    assert coverage["coverage_ratio"] == 1.0


def test_context_requirement_coverage_reports_missing_visual_region() -> None:
    query = "покажи что было на скриншоте про Atlas, нужна область на экране"
    intent = build_query_anchor_intent(query)
    items = (
        ContextItem(
            item_id="fact_atlas",
            item_type="fact",
            text="Atlas billing was approved, but no screenshot evidence is attached.",
            score=0.88,
            source_refs=(SourceRef(source_type="manual", source_id="fact_atlas"),),
            diagnostics={"memory_scope_id": "scope"},
        ),
    )

    coverage = context_requirement_coverage(
        query=query,
        query_anchor_intent=intent,
        items=items,
    )

    assert coverage["status"] == "missing"
    assert "image" in coverage["missing_modalities"]
    assert "visual_region" in coverage["missing_evidence_features"]
    assert coverage["missing_total"] > 0
    assert coverage["coverage_ratio"] == 0.0


def test_context_requirement_coverage_supports_document_page_citations() -> None:
    query = "find the page in the PDF document where Atlas renewal is mentioned"
    intent = build_query_anchor_intent(query)
    items = (
        ContextItem(
            item_id="doc_chunk_7",
            item_type="chunk",
            text="Atlas renewal appears in section 7.",
            score=0.9,
            source_refs=(
                SourceRef(
                    source_type="document",
                    source_id="doc_atlas_pdf",
                    chunk_id="chunk_7",
                    page_number=7,
                    quote_preview="Atlas renewal appears in section 7.",
                ),
            ),
            diagnostics={"memory_scope_id": "scope"},
        ),
    )

    coverage = context_requirement_coverage(
        query=query,
        query_anchor_intent=intent,
        items=items,
    )

    assert coverage["status"] == "satisfied"
    assert coverage["requested_modalities"] == ["document"]
    assert coverage["covered_modalities"] == ["document"]
    assert set(coverage["requested_evidence_features"]) >= {"citation", "page_or_char"}
    assert set(coverage["covered_evidence_features"]) >= {"citation", "page_or_char"}


def test_context_requirement_coverage_infers_video_from_frame_timeline_source() -> None:
    query = "покажи таймкод в видео где Atlas launch approved"
    intent = build_query_anchor_intent(query)
    items = (
        ContextItem(
            item_id="artifact_video_timeline",
            item_type="extraction_artifact",
            text="Video frame timeline: Atlas launch approved at 00:42.",
            score=0.91,
            source_refs=(
                SourceRef(
                    source_type="extraction_artifact",
                    source_id="video_frame_timeline_artifact",
                    chunk_id="keyframe-0001",
                    quote_preview="Atlas launch approved at 00:42.",
                    time_start_ms=42_000,
                    time_end_ms=49_000,
                ),
            ),
            diagnostics={},
        ),
        ContextItem(
            item_id="anchor_launch_event",
            item_type="anchor",
            text="event: Atlas launch approved in the video.",
            score=0.89,
            source_refs=(),
            diagnostics={"anchor_kind": "event", "memory_scope_id": "scope"},
        ),
    )

    coverage = context_requirement_coverage(
        query=query,
        query_anchor_intent=intent,
        items=items,
    )

    assert coverage["status"] == "satisfied"
    assert coverage["requested_modalities"] == ["video"]
    assert coverage["covered_modalities"] == ["video"]
    assert "audio" not in coverage["covered_modalities"]
    assert set(coverage["covered_evidence_features"]) >= {"citation", "time_range"}


def test_context_requirement_coverage_does_not_treat_unknown_timestamp_as_audio() -> None:
    query = "найди аудио где Atlas renewal approved"
    intent = build_query_anchor_intent(query)
    items = (
        ContextItem(
            item_id="generic_timed_artifact",
            item_type="extraction_artifact",
            text="Atlas renewal approved.",
            score=0.9,
            source_refs=(
                SourceRef(
                    source_type="extraction_artifact",
                    source_id="generic_artifact",
                    chunk_id="segment-1",
                    quote_preview="Atlas renewal approved.",
                    time_start_ms=1200,
                    time_end_ms=6400,
                ),
            ),
            diagnostics={},
        ),
    )

    coverage = context_requirement_coverage(
        query=query,
        query_anchor_intent=intent,
        items=items,
    )

    assert coverage["status"] == "partial"
    assert coverage["requested_modalities"] == ["audio"]
    assert coverage["missing_modalities"] == ["audio"]
    assert "time_range" in coverage["covered_evidence_features"]


def test_context_requirement_coverage_does_not_request_audio_for_invoice_voice_substring() -> None:
    query = "where on screen is Project Atlas screenshot invoice owner Alex"
    intent = build_query_anchor_intent(query)
    items = (
        ContextItem(
            item_id="artifact_invoice_screenshot",
            item_type="extraction_artifact",
            text="Project Atlas screenshot invoice owner Alex",
            score=0.91,
            source_refs=(
                SourceRef(
                    source_type="extraction_artifact",
                    source_id="artifact_invoice_screenshot",
                    chunk_id="ocr-owner",
                    quote_preview="Project Atlas screenshot invoice owner Alex",
                    bbox=(12.0, 32.0, 300.0, 88.0),
                ),
            ),
            diagnostics={
                "evidence_kind": "ocr_region",
                "evidence_modality": "image",
            },
        ),
    )

    coverage = context_requirement_coverage(
        query=query,
        query_anchor_intent=intent,
        items=items,
    )

    assert coverage["status"] == "satisfied"
    assert coverage["requested_modalities"] == ["image"]
    assert "audio" not in coverage["requested_modalities"]


def test_context_requirement_coverage_still_requests_audio_for_voice_word() -> None:
    query = "find the voice recording where Alex approved Atlas"
    intent = build_query_anchor_intent(query)

    coverage = context_requirement_coverage(
        query=query,
        query_anchor_intent=intent,
        items=(),
    )

    assert coverage["status"] == "missing"
    assert coverage["requested_modalities"] == ["audio"]
    assert coverage["missing_modalities"] == ["audio"]


def test_sanitize_context_requirement_coverage_bounds_and_redacts_payload() -> None:
    secret = "sk-proj-contextcoverage-secret1234567890"

    sanitized = sanitize_context_requirement_coverage(
        {
            "schema_version": "evil",
            "status": "satisfied",
            "requested_total": 3,
            "covered_total": 99,
            "missing_total": 99,
            "coverage_ratio": 99,
            "requested_modalities": ["image", secret, *[f"extra_{index}" for index in range(20)]],
            "covered_modalities": ["image"],
            "missing_modalities": [secret],
            "item_count": 2,
        }
    )

    assert sanitized["schema_version"] == "context-requirement-coverage-v1"
    assert sanitized["status"] == "satisfied"
    assert sanitized["covered_total"] == 3
    assert sanitized["missing_total"] == 0
    assert sanitized["coverage_ratio"] == 1.0
    assert secret not in str(sanitized)
    assert "[redacted]" not in str(sanitized)
    assert len(sanitized["requested_modalities"]) <= 12
