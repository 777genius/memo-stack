"""Provider-neutral image understanding ports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ImageVisionRequest:
    job_id: str
    asset_id: str
    filename: str
    content_type: str
    byte_size: int
    sha256_hex: str
    content: bytes
    max_output_chars: int


@dataclass(frozen=True)
class ImageVisionResult:
    status: str
    payload: dict[str, object] = field(default_factory=dict)
    payload_status: str = "empty"
    provider_name: str = "unknown"
    provider_model: str | None = None
    provider_version: str | None = None
    diagnostics: dict[str, object] = field(default_factory=dict)
    safe_error_code: str | None = None
    safe_error_message: str | None = None


class ImageVisionPort(Protocol):
    async def analyze(self, request: ImageVisionRequest) -> ImageVisionResult:
        """Analyze an image through a provider-neutral boundary."""
