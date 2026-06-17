import asyncio

from memo_stack_adapters.extraction.openai_vision import OpenAIVisionImageExtractionEngine
from memo_stack_core.ports.extraction import ExtractionLimits, ExtractionRequest
from memo_stack_core.ports.vision import ImageVisionRequest, ImageVisionResult


def test_vision_engine_accepts_provider_neutral_image_vision_port() -> None:
    engine = OpenAIVisionImageExtractionEngine(
        api_key=None,
        model="unused-openai-model",
        detail="low",
        vision=_FakeImageVisionPort(),
    )

    result = asyncio.run(engine.extract(_request()))

    assert result.status == "succeeded"
    assert result.model_version == "custom-vision-model"
    assert result.technical_metadata["vision_provider"] == "custom_vision"
    assert result.technical_metadata["vision_provider_version"] == "test-port"
    assert "Custom provider saw a memory review screenshot" in (result.markdown or "")


class _FakeImageVisionPort:
    async def analyze(self, request: ImageVisionRequest) -> ImageVisionResult:
        assert request.content_type == "image/png"
        assert request.filename == "memory-screenshot.png"
        return ImageVisionResult(
            status="succeeded",
            payload={
                "schema_name": "memo_stack.vision_image_evidence",
                "schema_version": "1.0",
                "summary": "Custom provider saw a memory review screenshot.",
                "visible_text": ["Review links"],
                "screenshot_ui_summary": "A memory review panel is visible.",
                "suggested_tags": ["review", "memory"],
                "regions": [
                    {
                        "kind": "visible_text",
                        "text": "Review links",
                        "bbox": [0, 0, 1, 1],
                        "confidence": 0.9,
                    }
                ],
            },
            payload_status="parsed",
            provider_name="custom_vision",
            provider_model="custom-vision-model",
            provider_version="test-port",
        )


def _request() -> ExtractionRequest:
    content = _sample_png_bytes()
    return ExtractionRequest(
        job_id="extract_vision",
        asset_id="asset_vision",
        filename="memory-screenshot.png",
        declared_content_type="image/png",
        detected_content_type="image/png",
        byte_size=len(content),
        sha256_hex="0" * 64,
        content=content,
        parser_profile="standard_vision",
        limits=ExtractionLimits(
            max_bytes=10_000_000,
            max_image_pixels=10,
            enable_external_ai=True,
        ),
    )


def _sample_png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04"
        b"\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )
