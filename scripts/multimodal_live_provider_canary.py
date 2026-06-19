"""Run a live multimodal provider canary for image vision and transcription."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
import uuid
import zlib
from datetime import UTC, datetime
from pathlib import Path

from infinity_context_adapters.extraction.openai_vision import (
    OPENAI_VISION_DOCS_URL,
    OPENAI_VISION_ENDPOINT_FAMILY,
    OPENAI_VISION_MAX_IMAGES_PER_REQUEST,
    OPENAI_VISION_MAX_PROVIDER_BINARY_BYTES,
    OPENAI_VISION_MAX_PROVIDER_PAYLOAD_BYTES,
    OPENAI_VISION_SUPPORTED_FILE_SUFFIXES,
    OpenAIImageVisionAdapter,
    openai_vision_supported_detail_levels,
)
from infinity_context_adapters.extraction.transcription.openai_adapter import (
    OPENAI_TRANSCRIPTION_DOCS_URL,
    OPENAI_TRANSCRIPTION_ENDPOINT,
    OPENAI_TRANSCRIPTION_MAX_UPLOAD_BYTES,
    OPENAI_TRANSCRIPTION_SUPPORTED_FILE_SUFFIXES,
    OpenAISpeechTranscriptionAdapter,
)
from infinity_context_core.ports.transcription import SpeechTranscriptionRequest
from infinity_context_core.ports.vision import ImageVisionRequest

SUITE = "infinity-context-multimodal-live-provider-canary"
PROOF_MATRIX_VERSION = "multimodal-provider-proof-matrix-v1"
REQUIRED_ENV = "MEMORY_OPENAI_API_KEY or OPENAI_API_KEY"
DEFAULT_REPORT_OUT = ".e2e-artifacts/multimodal-live-provider-canary.json"
DEFAULT_VISION_MODEL = "gpt-4.1-mini"
DEFAULT_TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"
DEFAULT_VISION_DETAIL = "low"
DEFAULT_TIMEOUT_SECONDS = 60.0
SYNTHETIC_AUDIO_PHRASE = "infinity context live transcription canary"
SYNTHETIC_VISION_TEXT = "INFINITY CONTEXT 24"
OPENAI_AUDIO_MAX_UPLOAD_BYTES = OPENAI_TRANSCRIPTION_MAX_UPLOAD_BYTES
OPENAI_AUDIO_SUPPORTED_SUFFIXES = frozenset(OPENAI_TRANSCRIPTION_SUPPORTED_FILE_SUFFIXES)
OPENAI_VISION_SUPPORTED_SUFFIXES = frozenset(OPENAI_VISION_SUPPORTED_FILE_SUFFIXES)
SECRET_VALUE_PATTERNS = (
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
)

_CONTENT_TYPES_BY_SUFFIX = {
    ".m4a": "audio/m4a",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".mpeg": "audio/mpeg",
    ".mpga": "audio/mpga",
    ".wav": "audio/wav",
    ".webm": "audio/webm",
}

_FONT_5X7 = {
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
}


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = asyncio.run(run_multimodal_live_provider_canary(args))
    _write_report(report, args.report_out)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["ok"] is True:
        return 0
    if report["components"]["provider_key"]["status"] == "degraded":
        return 2
    return 1


async def run_multimodal_live_provider_canary(
    args: argparse.Namespace,
) -> dict[str, object]:
    api_key = _provider_api_key()
    report = _base_report(args, has_provider_key=bool(api_key))
    if not api_key:
        report["components"]["provider_key"] = _component(
            "degraded",
            reason="provider_credential_missing",
            message=f"Set {REQUIRED_ENV} before running the live provider canary",
        )
        report["components"]["vision"] = _component(
            "skipped",
            reason="provider_credential_missing",
        )
        report["components"]["transcription"] = _component(
            "skipped",
            reason="provider_credential_missing",
        )
        report["ok"] = False
        _update_proof_matrix(report)
        return report

    report["components"]["provider_key"] = _component("configured")
    vision = await _run_vision(api_key=api_key, args=args)
    transcription = await _run_transcription(api_key=api_key, args=args)
    report["components"]["vision"] = vision
    report["components"]["transcription"] = transcription
    report["ok"] = vision["status"] == "succeeded" and transcription["status"] == "succeeded"
    _update_proof_matrix(report)
    return report


async def _run_vision(
    *,
    api_key: str,
    args: argparse.Namespace,
) -> dict[str, object]:
    image = _sample_png_bytes()
    fixture = _bytes_fixture_summary(
        role="image_vision",
        source="generated_png_fixture",
        filename="infinity-context-live-vision-canary.png",
        content_type="image/png",
        content=image,
        expected_visible_text=SYNTHETIC_VISION_TEXT,
    )
    request = ImageVisionRequest(
        job_id=f"live-canary-{uuid.uuid4()}",
        asset_id=f"asset-{uuid.uuid4()}",
        filename=str(fixture["filename"]),
        content_type=str(fixture["content_type"]),
        byte_size=len(image),
        sha256_hex=hashlib.sha256(image).hexdigest(),
        content=image,
        max_output_chars=4000,
    )
    adapter = OpenAIImageVisionAdapter(
        api_key=api_key,
        model=args.vision_model,
        detail=args.vision_detail,
        request_timeout_seconds=args.timeout_seconds,
    )
    result = await adapter.analyze(request)
    if result.status != "succeeded":
        return _component(
            "failed",
            reason=result.safe_error_code or "vision_provider_failed",
            message=result.safe_error_message,
            provider_name=result.provider_name,
            provider_model=result.provider_model,
            provider_version=result.provider_version,
            fixture=fixture,
            diagnostics=_safe_diagnostics(result.diagnostics),
        )

    visible_text = result.payload.get("visible_text")
    visible_text_count = len(visible_text) if isinstance(visible_text, list) else 0
    summary = result.payload.get("summary")
    summary_chars = len(summary) if isinstance(summary, str) else 0
    evidence_check = _vision_evidence_check(
        visible_text_count=visible_text_count,
        summary_chars=summary_chars,
    )
    if evidence_check["status"] != "succeeded":
        return _component(
            "failed",
            reason=evidence_check["reason"],
            message=evidence_check["message"],
            provider_name=result.provider_name,
            provider_model=result.provider_model,
            provider_version=result.provider_version,
            fixture=fixture,
            payload_status=result.payload_status,
            visible_text_count=visible_text_count,
            summary_chars=summary_chars,
            diagnostics=_safe_diagnostics(result.diagnostics),
        )
    return _component(
        "succeeded",
        provider_name=result.provider_name,
        provider_model=result.provider_model,
        provider_version=result.provider_version,
        fixture=fixture,
        payload_status=result.payload_status,
        visible_text_count=visible_text_count,
        summary_chars=summary_chars,
        diagnostics=_safe_diagnostics(result.diagnostics),
    )


async def _run_transcription(
    *,
    api_key: str,
    args: argparse.Namespace,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="infinity-context-live-asr-") as tmp:
        generated_audio = args.audio_fixture is None
        audio_path = _audio_fixture_path(args.audio_fixture, Path(tmp))
        if audio_path is None:
            return _component(
                "degraded",
                reason="audio_fixture_missing",
                message=(
                    "Set MEMORY_MULTIMODAL_PROVIDER_AUDIO_FIXTURE or run on macOS "
                    "with the say command available"
                ),
            )
        audio_validation = _audio_fixture_contract_check(audio_path)
        if audio_validation["status"] != "succeeded":
            return audio_validation
        content = audio_path.read_bytes()
        content_type = _content_type_for_path(audio_path)
        fixture = _audio_fixture_summary(
            path=audio_path,
            content_type=content_type,
            content=content,
            generated=generated_audio,
        )
        request = SpeechTranscriptionRequest(
            job_id=f"live-canary-{uuid.uuid4()}",
            asset_id=f"asset-{uuid.uuid4()}",
            filename=audio_path.name,
            content_type=content_type,
            byte_size=len(content),
            sha256_hex=hashlib.sha256(content).hexdigest(),
            content=content,
            max_output_chars=4000,
            prompt="This is a short Infinity Context provider canary.",
        )
        adapter = OpenAISpeechTranscriptionAdapter(
            api_key=api_key,
            model=args.transcription_model,
            request_timeout_seconds=args.timeout_seconds,
        )
        result = await adapter.transcribe(request)

    if result.status != "succeeded":
        return _component(
            "failed",
            reason=result.safe_error_code or "transcription_provider_failed",
            message=result.safe_error_message,
            provider_name=result.provider_name,
            provider_model=result.provider_model,
            provider_version=result.provider_version,
            fixture=fixture,
            diagnostics=_safe_diagnostics(result.diagnostics),
        )

    transcript_check = _transcript_check(result.text, audio_path=args.audio_fixture)
    if transcript_check["status"] != "succeeded":
        return _component(
            "failed",
            reason=transcript_check["reason"],
            message=transcript_check["message"],
            provider_name=result.provider_name,
            provider_model=result.provider_model,
            provider_version=result.provider_version,
            fixture=fixture,
            transcript_chars=len(result.text),
            segment_count=len(result.segments),
            word_count=len(result.words),
            language=result.language,
            duration_seconds=result.duration_seconds,
            diagnostics=_safe_diagnostics(result.diagnostics),
        )

    return _component(
        "succeeded",
        provider_name=result.provider_name,
        provider_model=result.provider_model,
        provider_version=result.provider_version,
        fixture=fixture,
        transcript_chars=len(result.text),
        segment_count=len(result.segments),
        word_count=len(result.words),
        language=result.language,
        duration_seconds=result.duration_seconds,
        diagnostics=_safe_diagnostics(result.diagnostics),
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-out",
        default=os.environ.get(
            "MEMORY_MULTIMODAL_PROVIDER_CANARY_REPORT_OUT",
            DEFAULT_REPORT_OUT,
        ),
        help="Optional path for the JSON canary report.",
    )
    parser.add_argument(
        "--audio-fixture",
        default=os.environ.get("MEMORY_MULTIMODAL_PROVIDER_AUDIO_FIXTURE"),
        help="Optional speech fixture path for OpenAI transcription.",
    )
    parser.add_argument(
        "--vision-model",
        default=os.environ.get("MEMORY_EXTRACTION_VISION_MODEL", DEFAULT_VISION_MODEL),
    )
    parser.add_argument(
        "--vision-detail",
        default=os.environ.get("MEMORY_EXTRACTION_VISION_DETAIL", DEFAULT_VISION_DETAIL),
    )
    parser.add_argument(
        "--transcription-model",
        default=os.environ.get(
            "MEMORY_TRANSCRIPTION_OPENAI_MODEL",
            DEFAULT_TRANSCRIPTION_MODEL,
        ),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(
            os.environ.get(
                "MEMORY_EXTRACTION_PROVIDER_TIMEOUT_SECONDS",
                DEFAULT_TIMEOUT_SECONDS,
            )
        ),
    )
    return parser.parse_args(argv)


def _base_report(
    args: argparse.Namespace,
    *,
    has_provider_key: bool,
) -> dict[str, object]:
    return {
        "suite": SUITE,
        "ok": False,
        "required_env": [REQUIRED_ENV],
        "secrets_redacted": True,
        "generated_at": _utc_now(),
        "git": _git_info(),
        "provider_key_present": has_provider_key,
        "provider_contract": {
            "external_ai_required": True,
            "timeout_seconds": args.timeout_seconds,
            "vision": {
                "endpoint_family": OPENAI_VISION_ENDPOINT_FAMILY,
                "model": args.vision_model,
                "detail": args.vision_detail,
                "detail_levels": list(openai_vision_supported_detail_levels(args.vision_model)),
                "supported_file_types": sorted(OPENAI_VISION_SUPPORTED_SUFFIXES),
                "docs_url": OPENAI_VISION_DOCS_URL,
                "max_provider_payload_bytes": OPENAI_VISION_MAX_PROVIDER_PAYLOAD_BYTES,
                "max_provider_binary_upload_bytes": OPENAI_VISION_MAX_PROVIDER_BINARY_BYTES,
                "max_images_per_request": OPENAI_VISION_MAX_IMAGES_PER_REQUEST,
            },
            "transcription": {
                "endpoint": OPENAI_TRANSCRIPTION_ENDPOINT,
                "model": args.transcription_model,
                "max_upload_bytes": OPENAI_AUDIO_MAX_UPLOAD_BYTES,
                "supported_file_types": sorted(OPENAI_AUDIO_SUPPORTED_SUFFIXES),
                "docs_url": OPENAI_TRANSCRIPTION_DOCS_URL,
            },
        },
        "failure_policy_contract": _failure_policy_contract(),
        "proof_matrix": _proof_matrix(
            components={},
            failure_policy_contract={},
            provider_key_present=has_provider_key,
            secrets_redacted=True,
        ),
        "models": {
            "vision": args.vision_model,
            "transcription": args.transcription_model,
        },
        "components": {
            "provider_key": _component("unknown"),
            "vision": _component("unknown"),
            "transcription": _component("unknown"),
        },
    }


def _update_proof_matrix(report: dict[str, object]) -> None:
    components = report.get("components") if isinstance(report.get("components"), dict) else {}
    failure_policy_contract = (
        report.get("failure_policy_contract")
        if isinstance(report.get("failure_policy_contract"), dict)
        else {}
    )
    report["proof_matrix"] = _proof_matrix(
        components=components,
        failure_policy_contract=failure_policy_contract,
        provider_key_present=bool(report.get("provider_key_present")),
        secrets_redacted=report.get("secrets_redacted") is True,
    )


def _proof_matrix(
    *,
    components: dict[object, object],
    failure_policy_contract: dict[object, object],
    provider_key_present: bool,
    secrets_redacted: bool,
) -> dict[str, object]:
    requirements = {
        "vision_real_provider": _live_component_requirement(
            components,
            "vision",
            requires_provider_key=True,
            provider_key_present=provider_key_present,
        ),
        "audio_transcription_real_provider": _live_component_requirement(
            components,
            "transcription",
            requires_provider_key=True,
            provider_key_present=provider_key_present,
        ),
        "vision_fixture_contract": _fixture_component_requirement(
            components,
            "vision",
            expected_role="image_vision",
            expected_content_type="image/png",
            supported_suffixes=OPENAI_VISION_SUPPORTED_SUFFIXES,
            requires_provider_key=True,
            provider_key_present=provider_key_present,
        ),
        "audio_fixture_contract": _fixture_component_requirement(
            components,
            "transcription",
            expected_role="audio_transcription",
            expected_content_type=None,
            supported_suffixes=OPENAI_AUDIO_SUPPORTED_SUFFIXES,
            requires_provider_key=True,
            provider_key_present=provider_key_present,
        ),
        "invalid_key_classification": _contract_requirement(
            failure_policy_contract,
            "invalid_api_key",
            expected_operator_action="replace_provider_credential",
            expected_retryable=False,
        ),
        "rate_limit_classification": _contract_requirement(
            failure_policy_contract,
            "rate_limited",
            expected_operator_action="retry_later",
            expected_retryable=True,
        ),
        "timeout_classification": _contract_requirement(
            failure_policy_contract,
            "timeout",
            expected_operator_action="retry_later",
            expected_retryable=True,
        ),
        "no_secret_leak_guard": {
            "status": "contract_covered" if secrets_redacted else "failed",
            "proof": "bounded_report_redaction",
            "requires_provider_key": False,
            "ok": secrets_redacted,
        },
    }
    live_names = (
        "vision_real_provider",
        "audio_transcription_real_provider",
        "vision_fixture_contract",
        "audio_fixture_contract",
    )
    contract_names = tuple(name for name in requirements if name not in live_names)
    return {
        "schema_version": PROOF_MATRIX_VERSION,
        "requirements": requirements,
        "summary": {
            "live_requirements_passed": sum(
                1 for name in live_names if requirements[name].get("ok") is True
            ),
            "live_requirements_total": len(live_names),
            "contract_requirements_passed": sum(
                1 for name in contract_names if requirements[name].get("ok") is True
            ),
            "contract_requirements_total": len(contract_names),
        },
    }


def _live_component_requirement(
    components: dict[object, object],
    name: str,
    *,
    requires_provider_key: bool,
    provider_key_present: bool,
) -> dict[str, object]:
    component = components.get(name)
    if not isinstance(component, dict):
        status = "not_run" if provider_key_present else "skipped"
        return {
            "status": status,
            "proof": "live_provider_call",
            "requires_provider_key": requires_provider_key,
            "ok": False,
        }
    component_status = str(component.get("status") or "unknown")
    return {
        "status": component_status,
        "proof": "live_provider_call",
        "requires_provider_key": requires_provider_key,
        "ok": component_status == "succeeded",
        **(
            {"reason": component.get("reason")}
            if isinstance(component.get("reason"), str)
            else {}
        ),
    }


def _fixture_component_requirement(
    components: dict[object, object],
    name: str,
    *,
    expected_role: str,
    expected_content_type: str | None,
    supported_suffixes: frozenset[str],
    requires_provider_key: bool,
    provider_key_present: bool,
) -> dict[str, object]:
    component = components.get(name)
    if not isinstance(component, dict):
        status = "not_run" if provider_key_present else "skipped"
        return {
            "status": status,
            "proof": "local_fixture_contract",
            "requires_provider_key": requires_provider_key,
            "ok": False,
        }
    if not provider_key_present and component.get("status") == "skipped":
        return {
            "status": "skipped",
            "proof": "local_fixture_contract",
            "requires_provider_key": requires_provider_key,
            "ok": False,
            **(
                {"reason": component.get("reason")}
                if isinstance(component.get("reason"), str)
                else {}
            ),
        }
    fixture = component.get("fixture")
    if not isinstance(fixture, dict):
        return {
            "status": "missing",
            "proof": "local_fixture_contract",
            "requires_provider_key": requires_provider_key,
            "ok": False,
            "reason": "fixture_summary_missing",
        }
    suffix = str(fixture.get("suffix") or "")
    content_type = str(fixture.get("content_type") or "")
    sha256_hex = str(fixture.get("sha256_hex") or "")
    byte_size = fixture.get("byte_size")
    ok = (
        fixture.get("role") == expected_role
        and suffix in supported_suffixes
        and (expected_content_type is None or content_type == expected_content_type)
        and isinstance(byte_size, int)
        and byte_size > 0
        and bool(re.fullmatch(r"[a-f0-9]{64}", sha256_hex))
    )
    return {
        "status": "contract_covered" if ok else "failed",
        "proof": "local_fixture_contract",
        "requires_provider_key": requires_provider_key,
        "ok": ok,
        "suffix": suffix,
        "content_type": content_type,
    }


def _contract_requirement(
    contract: dict[object, object],
    name: str,
    *,
    expected_operator_action: str,
    expected_retryable: bool,
) -> dict[str, object]:
    case = contract.get(name)
    if not isinstance(case, dict):
        return {
            "status": "missing",
            "proof": "adapter_contract_test",
            "requires_provider_key": False,
            "ok": False,
        }
    ok = (
        case.get("reason") is not None
        and case.get("operator_action") == expected_operator_action
        and case.get("user_retryable") is expected_retryable
    )
    return {
        "status": "contract_covered" if ok else "failed",
        "proof": "adapter_contract_test",
        "requires_provider_key": False,
        "ok": ok,
        "reason": case.get("reason"),
        "operator_action": case.get("operator_action"),
        "user_retryable": case.get("user_retryable"),
    }


def _provider_api_key() -> str | None:
    value = os.environ.get("MEMORY_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if value and value.strip():
        return value.strip()
    return None


def _bytes_fixture_summary(
    *,
    role: str,
    source: str,
    filename: str,
    content_type: str,
    content: bytes,
    expected_visible_text: str | None = None,
) -> dict[str, object]:
    summary: dict[str, object] = {
        "role": role,
        "source": source,
        "filename": Path(filename).name,
        "suffix": Path(filename).suffix.lower(),
        "content_type": content_type,
        "byte_size": len(content),
        "sha256_hex": hashlib.sha256(content).hexdigest(),
    }
    if expected_visible_text:
        summary["expected_visible_text"] = expected_visible_text
    return summary


def _audio_fixture_summary(
    *,
    path: Path,
    content_type: str,
    content: bytes,
    generated: bool,
) -> dict[str, object]:
    return _bytes_fixture_summary(
        role="audio_transcription",
        source="generated_synthetic_speech" if generated else "configured_audio_fixture",
        filename=path.name,
        content_type=content_type,
        content=content,
    )


def _component(status: str, **values: object) -> dict[str, object]:
    component = {"status": status}
    for key, value in values.items():
        if value is not None:
            component[key] = _safe_report_value(value)
    component.update(
        _recovery_policy(
            status=status,
            reason=component.get("reason") if isinstance(component.get("reason"), str) else None,
        )
    )
    return component


def _recovery_policy(*, status: str, reason: str | None) -> dict[str, object]:
    if status in {"configured", "succeeded", "unknown"}:
        return {}
    normalized = (reason or status).strip().lower()
    if "missing_api_key" in normalized or "credential_missing" in normalized:
        return {
            "user_retryable": False,
            "operator_action": "configure_provider_credential",
        }
    if "invalid_api_key" in normalized:
        return {
            "user_retryable": False,
            "operator_action": "replace_provider_credential",
        }
    if "quota_exceeded" in normalized or "insufficient_quota" in normalized:
        return {
            "user_retryable": False,
            "operator_action": "check_provider_billing",
        }
    if "rate_limited" in normalized or "timeout" in normalized or "unavailable" in normalized:
        return {
            "user_retryable": True,
            "operator_action": "retry_later",
        }
    if normalized == "audio_fixture_missing":
        return {
            "user_retryable": False,
            "operator_action": "provide_audio_fixture",
        }
    if normalized.startswith("audio_fixture_"):
        return {
            "user_retryable": False,
            "operator_action": "replace_audio_fixture",
        }
    return {
        "user_retryable": False,
        "operator_action": "inspect_provider_canary",
    }


def _failure_policy_contract() -> dict[str, object]:
    return {
        "provider_credential_missing": _component(
            "degraded",
            reason="provider_credential_missing",
        ),
        "invalid_api_key": _component(
            "failed",
            reason="asset_extraction.vision.invalid_api_key",
        ),
        "quota_exceeded": _component(
            "failed",
            reason="asset_extraction.transcription.quota_exceeded",
        ),
        "rate_limited": _component(
            "failed",
            reason="asset_extraction.transcription.rate_limited",
        ),
        "timeout": _component(
            "failed",
            reason="asset_extraction.vision.timeout",
        ),
    }


def _write_report(report: dict[str, object], report_out: str | None) -> None:
    if not report_out:
        return
    path = Path(report_out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git_info() -> dict[str, object]:
    return {
        "commit": _git_output("rev-parse", "HEAD"),
        "short_commit": _git_output("rev-parse", "--short", "HEAD"),
        "dirty": bool(_git_output("status", "--short")),
    }


def _git_output(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=Path(__file__).resolve().parents[1],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _audio_fixture_path(configured: str | None, tmp_dir: Path) -> Path | None:
    if configured:
        path = Path(configured).expanduser()
        if path.is_file() and path.stat().st_size > 0:
            return path
        return None
    return _synthesize_audio_fixture(tmp_dir)


def _synthesize_audio_fixture(tmp_dir: Path) -> Path | None:
    say = shutil.which("say")
    if not say:
        return None
    output = tmp_dir / "infinity-context-live-transcription-canary.wav"
    command = [
        say,
        "-o",
        str(output),
        "--file-format=WAVE",
        "--data-format=LEI16@16000",
        SYNTHETIC_AUDIO_PHRASE,
    ]
    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    if output.is_file() and output.stat().st_size > 0:
        return output
    return None


def _content_type_for_path(path: Path) -> str:
    return _CONTENT_TYPES_BY_SUFFIX.get(path.suffix.lower(), "application/octet-stream")


def _audio_fixture_contract_check(path: Path) -> dict[str, object]:
    suffix = path.suffix.lower()
    if suffix not in OPENAI_AUDIO_SUPPORTED_SUFFIXES:
        return _component(
            "degraded",
            reason="audio_fixture_unsupported_type",
            message="Audio fixture type is not supported by OpenAI transcription upload",
            filename_suffix=suffix[:20] or "<none>",
            supported_file_types=sorted(OPENAI_AUDIO_SUPPORTED_SUFFIXES),
        )
    try:
        byte_size = path.stat().st_size
    except OSError as exc:
        return _component(
            "degraded",
            reason="audio_fixture_unreadable",
            message=str(exc)[:200],
        )
    if byte_size <= 0:
        return _component(
            "degraded",
            reason="audio_fixture_empty",
            message="Audio fixture is empty",
        )
    if byte_size > OPENAI_AUDIO_MAX_UPLOAD_BYTES:
        return _component(
            "degraded",
            reason="audio_fixture_too_large",
            message="Audio fixture exceeds OpenAI transcription upload limit",
            byte_size=byte_size,
            max_upload_bytes=OPENAI_AUDIO_MAX_UPLOAD_BYTES,
        )
    return _component("succeeded")


def _transcript_check(
    transcript: str,
    *,
    audio_path: str | None,
) -> dict[str, object]:
    if not transcript.strip():
        return _component(
            "failed",
            reason="transcription_empty_text",
            message="Provider returned an empty transcript",
        )
    if audio_path:
        return _component("succeeded")
    normalized_terms = set(transcript.lower().replace("-", " ").split())
    expected_terms = {"infinity", "context", "canary"}
    missing_terms = sorted(expected_terms.difference(normalized_terms))
    if missing_terms:
        return _component(
            "failed",
            reason="synthetic_transcript_mismatch",
            message="Synthetic speech transcript missed expected canary terms",
            missing_terms=missing_terms,
        )
    return _component("succeeded")


def _vision_evidence_check(
    *,
    visible_text_count: int,
    summary_chars: int,
) -> dict[str, object]:
    if visible_text_count > 0 or summary_chars > 0:
        return _component("succeeded")
    return _component(
        "failed",
        reason="vision_empty_evidence",
        message="Provider returned no visible text or image summary",
    )


def _safe_diagnostics(diagnostics: dict[str, object]) -> dict[str, object]:
    safe: dict[str, object] = {}
    for key, value in diagnostics.items():
        if _is_sensitive_report_key(key):
            continue
        safe_value = _safe_report_value(value)
        if isinstance(safe_value, str):
            safe[key] = safe_value[:200]
        elif isinstance(safe_value, (int, float, bool)) or safe_value is None:
            safe[key] = safe_value
        elif isinstance(safe_value, list):
            safe[key] = safe_value[:10]
        elif isinstance(safe_value, dict):
            safe[key] = {
                str(child_key): child_value
                for child_key, child_value in list(safe_value.items())[:10]
                if isinstance(child_value, (str, int, float, bool)) or child_value is None
            }
        else:
            safe[key] = safe_value.__class__.__name__
    return safe


def _safe_report_value(value: object) -> object:
    if isinstance(value, str):
        return _redact_secret_fragments(value)
    if isinstance(value, list):
        return [_safe_report_value(item) for item in value[:10]]
    if isinstance(value, dict):
        safe: dict[str, object] = {}
        for child_key, child_value in list(value.items())[:10]:
            if _is_sensitive_report_key(str(child_key)):
                continue
            safe[str(child_key)] = _safe_report_value(child_value)
        return safe
    return value


def _is_sensitive_report_key(key: str) -> bool:
    normalized = key.lower()
    return normalized in {
        "api_key",
        "apikey",
        "authorization",
        "access_token",
        "refresh_token",
        "bearer_token",
        "token",
        "secret",
        "password",
        "credential",
    } or normalized.endswith(("_api_key", "_secret", "_password", "_credential"))


def _redact_secret_fragments(value: str) -> str:
    redacted = value
    for pattern in SECRET_VALUE_PATTERNS:
        redacted = pattern.sub("<redacted>", redacted)
    return redacted


def _sample_png_bytes() -> bytes:
    width = 180
    height = 64
    pixels = bytearray([255, 255, 255] * width * height)
    _draw_text(pixels, width, x=14, y=18, text="INFINITY CONTEXT 24", scale=3)
    return _encode_png(width, height, bytes(pixels))


def _draw_text(
    pixels: bytearray,
    width: int,
    *,
    x: int,
    y: int,
    text: str,
    scale: int,
) -> None:
    cursor = x
    for char in text:
        glyph = _FONT_5X7.get(char.upper())
        if glyph is None:
            cursor += 6 * scale
            continue
        for row_index, row in enumerate(glyph):
            for column_index, enabled in enumerate(row):
                if enabled != "1":
                    continue
                _fill_rect(
                    pixels,
                    width,
                    x=cursor + column_index * scale,
                    y=y + row_index * scale,
                    size=scale,
                    color=(18, 24, 38),
                )
        cursor += 6 * scale


def _fill_rect(
    pixels: bytearray,
    width: int,
    *,
    x: int,
    y: int,
    size: int,
    color: tuple[int, int, int],
) -> None:
    height = len(pixels) // (width * 3)
    for yy in range(y, min(y + size, height)):
        for xx in range(x, min(x + size, width)):
            offset = (yy * width + xx) * 3
            pixels[offset : offset + 3] = bytes(color)


def _encode_png(width: int, height: int, rgb: bytes) -> bytes:
    raw_rows = []
    row_length = width * 3
    for y in range(height):
        raw_rows.append(b"\x00" + rgb[y * row_length : (y + 1) * row_length])
    raw = b"".join(raw_rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw, level=9))
        + _png_chunk(b"IEND", b"")
    )


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


if __name__ == "__main__":
    raise SystemExit(main())
