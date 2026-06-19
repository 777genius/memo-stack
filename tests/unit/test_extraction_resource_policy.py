from infinity_context_core.application.extraction_resource_policy import (
    EXTRACTION_RESOURCE_LIMIT_CAPS,
    EXTRACTION_RESOURCE_POLICY_VERSION,
    assess_extraction_resource_limits,
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
