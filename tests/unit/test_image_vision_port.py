import asyncio
import json

from infinity_context_adapters.extraction.openai_vision import (
    OPENAI_VISION_MAX_PROVIDER_BINARY_BYTES,
    OpenAIImageVisionAdapter,
    OpenAIVisionImageExtractionEngine,
)
from infinity_context_core.ports.extraction import ExtractionLimits, ExtractionRequest
from infinity_context_core.ports.vision import ImageVisionRequest, ImageVisionResult

_VISION_SECRET = "sk-proj-vision-secret-value1234567890"


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
    rendered_diagnostics = json.dumps(result.diagnostics, ensure_ascii=False)
    assert _VISION_SECRET not in rendered_diagnostics
    assert "api_key" not in result.diagnostics

    vision_json = next(
        artifact for artifact in result.artifacts if artifact.artifact_type == "vision_json"
    )
    rendered_artifact = vision_json.content.decode("utf-8")
    assert _VISION_SECRET not in rendered_artifact
    payload = json.loads(rendered_artifact)
    assert "raw_provider_payload" not in payload


def test_openai_vision_adapter_rejects_oversized_data_url_before_provider_call() -> None:
    def client_factory() -> object:
        raise AssertionError("oversized image must not call OpenAI")

    adapter = OpenAIImageVisionAdapter(
        api_key=None,
        model="gpt-4.1-mini",
        detail="low",
        client_factory=client_factory,
    )

    result = asyncio.run(
        adapter.analyze(
            ImageVisionRequest(
                job_id="extract_large_vision",
                asset_id="asset_large_vision",
                filename="large.png",
                content_type="image/png",
                byte_size=OPENAI_VISION_MAX_PROVIDER_BINARY_BYTES + 1,
                sha256_hex="0" * 64,
                content=b"small-placeholder",
                max_output_chars=1000,
            )
        )
    )

    assert result.status == "unsupported"
    assert result.safe_error_code == "asset_extraction.vision_provider_payload_too_large"
    assert result.diagnostics["provider_retryable"] is False
    assert (
        result.diagnostics["max_provider_binary_upload_bytes"]
        == OPENAI_VISION_MAX_PROVIDER_BINARY_BYTES
    )


class _FakeImageVisionPort:
    async def analyze(self, request: ImageVisionRequest) -> ImageVisionResult:
        assert request.content_type == "image/png"
        assert request.filename == "memory-screenshot.png"
        return ImageVisionResult(
            status="succeeded",
            payload={
                "schema_name": "infinity_context.vision_image_evidence",
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
                "raw_provider_payload": {
                    "api_key": _VISION_SECRET,
                    "debug": f"Bearer {_VISION_SECRET}",
                },
            },
            payload_status="parsed",
            provider_name="custom_vision",
            provider_model="custom-vision-model",
            provider_version="test-port",
            diagnostics={
                "api_key": _VISION_SECRET,
                "debug": f"Bearer {_VISION_SECRET}",
            },
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
