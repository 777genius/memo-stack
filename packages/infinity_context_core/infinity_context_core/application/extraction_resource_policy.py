"""Provider-neutral extraction resource limits."""

from __future__ import annotations

from dataclasses import dataclass

from infinity_context_core.ports.extraction import ExtractionLimits

EXTRACTION_RESOURCE_POLICY_VERSION = "asset-extraction-resource-policy-v1"

EXTRACTION_RESOURCE_LIMIT_CAPS = {
    "max_bytes": 500 * 1024 * 1024,
    "max_pages": 10_000,
    "max_media_seconds": 24 * 60 * 60,
    "max_output_chars": 10_000_000,
    "max_tables": 10_000,
    "parser_timeout_seconds": 24 * 60 * 60,
    "subprocess_timeout_seconds": 60 * 60,
    "max_image_pixels": 500_000_000,
}

_DEFAULT_MAX_BYTES = 25 * 1024 * 1024
_DEFAULT_MAX_PAGES = 100
_DEFAULT_MAX_MEDIA_SECONDS = 600
_DEFAULT_MAX_OUTPUT_CHARS = 500_000
_DEFAULT_MAX_TABLES = 100
_DEFAULT_PARSER_TIMEOUT_SECONDS = 300.0
_DEFAULT_SUBPROCESS_TIMEOUT_SECONDS = 60.0
_DEFAULT_MAX_IMAGE_PIXELS = 50_000_000


@dataclass(frozen=True)
class ExtractionResourceDecision:
    limits: ExtractionLimits
    allowed: bool
    code: str | None
    message: str | None
    metadata: dict[str, object]


def normalize_extraction_limits(limits: ExtractionLimits) -> ExtractionLimits:
    """Clamp externally supplied limits before they reach provider adapters."""

    return ExtractionLimits(
        max_bytes=_bounded_int(
            limits.max_bytes,
            minimum=1,
            maximum=EXTRACTION_RESOURCE_LIMIT_CAPS["max_bytes"],
            default=_DEFAULT_MAX_BYTES,
        ),
        max_pages=_bounded_int(
            limits.max_pages,
            minimum=1,
            maximum=EXTRACTION_RESOURCE_LIMIT_CAPS["max_pages"],
            default=_DEFAULT_MAX_PAGES,
        ),
        max_media_seconds=_bounded_int(
            limits.max_media_seconds,
            minimum=1,
            maximum=EXTRACTION_RESOURCE_LIMIT_CAPS["max_media_seconds"],
            default=_DEFAULT_MAX_MEDIA_SECONDS,
        ),
        max_output_chars=_bounded_int(
            limits.max_output_chars,
            minimum=1,
            maximum=EXTRACTION_RESOURCE_LIMIT_CAPS["max_output_chars"],
            default=_DEFAULT_MAX_OUTPUT_CHARS,
        ),
        max_tables=_bounded_int(
            limits.max_tables,
            minimum=0,
            maximum=EXTRACTION_RESOURCE_LIMIT_CAPS["max_tables"],
            default=_DEFAULT_MAX_TABLES,
        ),
        parser_timeout_seconds=_bounded_float(
            limits.parser_timeout_seconds,
            minimum=0.001,
            maximum=EXTRACTION_RESOURCE_LIMIT_CAPS["parser_timeout_seconds"],
            default=_DEFAULT_PARSER_TIMEOUT_SECONDS,
        ),
        subprocess_timeout_seconds=_bounded_float(
            limits.subprocess_timeout_seconds,
            minimum=0.001,
            maximum=EXTRACTION_RESOURCE_LIMIT_CAPS["subprocess_timeout_seconds"],
            default=_DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        ),
        max_image_pixels=_bounded_int(
            limits.max_image_pixels,
            minimum=1,
            maximum=EXTRACTION_RESOURCE_LIMIT_CAPS["max_image_pixels"],
            default=_DEFAULT_MAX_IMAGE_PIXELS,
        ),
        enable_ocr=bool(limits.enable_ocr),
        enable_external_ai=bool(limits.enable_external_ai),
    )


def extraction_limits_metadata(limits: ExtractionLimits) -> dict[str, object]:
    normalized = normalize_extraction_limits(limits)
    clamped_fields = _clamped_limit_fields(raw=limits, normalized=normalized)
    return {
        "extraction_resource_policy_version": EXTRACTION_RESOURCE_POLICY_VERSION,
        "extraction_limits_normalized": bool(clamped_fields),
        "extraction_limits_clamped_fields": clamped_fields,
        "extraction_max_bytes": normalized.max_bytes,
        "extraction_max_pages": normalized.max_pages,
        "extraction_max_media_seconds": normalized.max_media_seconds,
        "extraction_max_output_chars": normalized.max_output_chars,
        "extraction_max_tables": normalized.max_tables,
        "extraction_parser_timeout_seconds": normalized.parser_timeout_seconds,
        "extraction_subprocess_timeout_seconds": normalized.subprocess_timeout_seconds,
        "extraction_max_image_pixels": normalized.max_image_pixels,
        "extraction_ocr_enabled": normalized.enable_ocr,
        "extraction_external_ai_enabled": normalized.enable_external_ai,
    }


def assess_extraction_resource_limits(
    *,
    asset_byte_size: int,
    limits: ExtractionLimits,
    byte_size_source: str = "asset_metadata",
) -> ExtractionResourceDecision:
    normalized = normalize_extraction_limits(limits)
    safe_byte_size = max(0, _coerce_int(asset_byte_size, default=0))
    metadata = {
        **extraction_limits_metadata(normalized),
        "extraction_asset_byte_size": safe_byte_size,
        "extraction_asset_byte_size_source": byte_size_source[:80],
    }
    if safe_byte_size > normalized.max_bytes:
        return ExtractionResourceDecision(
            limits=normalized,
            allowed=False,
            code="asset_extraction.file_too_large",
            message="Asset exceeds configured extraction size limit",
            metadata={
                **metadata,
                "extraction_resource_limit_exceeded": "max_bytes",
            },
        )
    return ExtractionResourceDecision(
        limits=normalized,
        allowed=True,
        code=None,
        message=None,
        metadata=metadata,
    )


def _bounded_int(value: object, *, minimum: int, maximum: int, default: int) -> int:
    parsed = _coerce_int(value, default=default)
    return min(max(parsed, minimum), maximum)


def _bounded_float(value: object, *, minimum: float, maximum: float, default: float) -> float:
    parsed = _coerce_float(value, default=default)
    return min(max(parsed, minimum), maximum)


def _coerce_int(value: object, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except ValueError:
            return default
    return default


def _coerce_float(value: object, *, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def _clamped_limit_fields(
    *,
    raw: ExtractionLimits,
    normalized: ExtractionLimits,
) -> list[str]:
    fields = (
        "max_bytes",
        "max_pages",
        "max_media_seconds",
        "max_output_chars",
        "max_tables",
        "parser_timeout_seconds",
        "subprocess_timeout_seconds",
        "max_image_pixels",
        "enable_ocr",
        "enable_external_ai",
    )
    return [field for field in fields if getattr(raw, field) != getattr(normalized, field)]
