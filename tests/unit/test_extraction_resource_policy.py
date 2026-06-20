from infinity_context_core.application.extraction_resource_policy import (
    EXTRACTION_RESOURCE_LIMIT_CAPS,
    EXTRACTION_RESOURCE_POLICY_VERSION,
    EXTRACTION_RESULT_RESOURCE_POLICY_VERSION,
    assess_extraction_resource_limits,
    assess_extraction_result_resource_limits,
    extraction_limits_metadata,
    normalize_extraction_limits,
)
from infinity_context_core.ports.extraction import ExtractionLimits


def test_extraction_resource_policy_normalizes_untrusted_limits() -> None:
    raw = ExtractionLimits(
        max_bytes=10**12,
        max_pages=0,
        max_media_seconds=10**9,
        max_output_chars=-1,
        max_tables=-5,
        parser_timeout_seconds=0,
        subprocess_timeout_seconds=10**9,
        max_image_pixels=10**12,
        enable_ocr=True,
        enable_external_ai=False,
    )

    normalized = normalize_extraction_limits(raw)
    metadata = extraction_limits_metadata(raw)

    assert normalized.max_bytes == EXTRACTION_RESOURCE_LIMIT_CAPS["max_bytes"]
    assert normalized.max_pages == 1
    assert normalized.max_media_seconds == EXTRACTION_RESOURCE_LIMIT_CAPS["max_media_seconds"]
    assert normalized.max_output_chars == 1
    assert normalized.max_tables == 0
    assert normalized.parser_timeout_seconds == 0.001
    assert (
        normalized.subprocess_timeout_seconds
        == EXTRACTION_RESOURCE_LIMIT_CAPS["subprocess_timeout_seconds"]
    )
    assert normalized.max_image_pixels == EXTRACTION_RESOURCE_LIMIT_CAPS["max_image_pixels"]
    assert metadata["extraction_resource_policy_version"] == EXTRACTION_RESOURCE_POLICY_VERSION
    assert metadata["extraction_limits_normalized"] is True
    assert "max_bytes" in metadata["extraction_limits_clamped_fields"]
    assert "subprocess_timeout_seconds" in metadata["extraction_limits_clamped_fields"]


def test_extraction_resource_policy_blocks_oversized_assets_with_safe_metadata() -> None:
    limits = ExtractionLimits(max_bytes=10)

    decision = assess_extraction_resource_limits(
        asset_byte_size=11,
        limits=limits,
        byte_size_source="asset_metadata",
    )

    assert decision.allowed is False
    assert decision.code == "asset_extraction.file_too_large"
    assert decision.message == "Asset exceeds configured extraction size limit"
    assert decision.metadata["extraction_asset_byte_size"] == 11
    assert decision.metadata["extraction_max_bytes"] == 10
    assert decision.metadata["extraction_resource_limit_exceeded"] == "max_bytes"
    assert decision.metadata["extraction_asset_byte_size_source"] == "asset_metadata"


def test_extraction_resource_policy_allows_assets_within_limit() -> None:
    decision = assess_extraction_resource_limits(
        asset_byte_size=10,
        limits=ExtractionLimits(max_bytes=10),
    )

    assert decision.allowed is True
    assert decision.code is None
    assert decision.metadata["extraction_asset_byte_size"] == 10
    assert decision.metadata["extraction_limits_normalized"] is False


def test_extraction_result_resource_policy_blocks_media_duration_over_limit() -> None:
    decision = assess_extraction_result_resource_limits(
        result_metadata={"duration_seconds": 61.2},
        limits=ExtractionLimits(max_bytes=1_000, max_media_seconds=60),
    )

    assert decision.allowed is False
    assert decision.code == "asset_extraction.media_too_long"
    assert decision.message == "Media duration exceeds extraction resource limit"
    assert decision.metadata["extraction_result_resource_policy_version"] == (
        EXTRACTION_RESULT_RESOURCE_POLICY_VERSION
    )
    assert decision.metadata["extraction_resource_limit_exceeded"] == "max_media_seconds"
    assert decision.metadata["extraction_result_media_seconds"] == 61.2
    assert decision.metadata["extraction_max_media_seconds"] == 60


def test_extraction_result_resource_policy_blocks_image_pixels_over_limit() -> None:
    decision = assess_extraction_result_resource_limits(
        result_metadata={"image_width": 100, "image_height": 100},
        limits=ExtractionLimits(max_bytes=1_000, max_image_pixels=9_999),
    )

    assert decision.allowed is False
    assert decision.code == "asset_extraction.image_too_large"
    assert decision.metadata["extraction_resource_limit_exceeded"] == "max_image_pixels"
    assert decision.metadata["extraction_result_image_pixels"] == 10_000
    assert decision.metadata["extraction_max_image_pixels"] == 9_999


def test_extraction_result_resource_policy_marks_page_truncation_without_blocking() -> None:
    decision = assess_extraction_result_resource_limits(
        result_metadata={"page_count": 12, "pages_extracted": 5},
        limits=ExtractionLimits(max_bytes=1_000, max_pages=5),
    )

    assert decision.allowed is True
    assert decision.code is None
    assert decision.metadata["extraction_result_pages_truncated"] is True
    assert decision.metadata["extraction_resource_limits_applied"] == ["max_pages"]
    assert decision.metadata["extraction_result_page_count"] == 12
    assert decision.metadata["extraction_result_pages_processed"] == 5


def test_extraction_result_resource_policy_blocks_provider_page_limit_breach() -> None:
    decision = assess_extraction_result_resource_limits(
        result_metadata={"page_count": 12, "pages_extracted": 6},
        limits=ExtractionLimits(max_bytes=1_000, max_pages=5),
    )

    assert decision.allowed is False
    assert decision.code == "asset_extraction.page_limit_breach"
    assert decision.metadata["extraction_resource_limit_exceeded"] == "max_pages"
    assert decision.metadata["extraction_result_pages_processed"] == 6
