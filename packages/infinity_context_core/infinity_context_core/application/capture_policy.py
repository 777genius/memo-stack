"""Deterministic capture admission, redaction and fingerprint helpers."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from infinity_context_core.application.sensitive_text import (
    redact_sensitive_text,
)


@dataclass(frozen=True)
class CaptureAdmissionResult:
    text: str
    accepted: bool
    redacted: bool
    reason: str


class CaptureAdmissionService:
    """Fast deterministic server-side admission guard."""

    def admit(self, text: str) -> CaptureAdmissionResult:
        stripped = text.strip()
        if not stripped:
            return CaptureAdmissionResult("", False, False, "empty_capture")
        redacted = redact_sensitive_text(stripped, marker="[redacted-secret]")
        did_redact = redacted != stripped
        if "[redacted-secret]" in redacted and len(redacted) <= len("[redacted-secret]") + 10:
            return CaptureAdmissionResult(redacted, False, True, "secret_rejected")
        return CaptureAdmissionResult(
            redacted,
            True,
            did_redact,
            "redacted" if did_redact else "accepted",
        )


def capture_payload_hash(*parts: object) -> str:
    raw = "\u241f".join("" if part is None else str(part) for part in parts)
    return sha256(raw.encode()).hexdigest()


def capture_idempotency_key(
    *,
    source_agent: str,
    source_kind: str,
    event_type: str,
    source_event_id: str | None,
    client_instance_id: str | None,
    text: str,
) -> str:
    if source_event_id:
        raw = (
            f"{source_agent}:{source_kind}:{event_type}:"
            f"{client_instance_id or ''}:{source_event_id}"
        )
    else:
        raw = f"{source_agent}:{source_kind}:{event_type}:{client_instance_id or ''}:{text}"
    return f"capture:{sha256(raw.encode('utf-8')).hexdigest()}"
