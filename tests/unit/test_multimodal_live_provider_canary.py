from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts" / "multimodal_live_provider_canary.py"
PACKAGE_PATHS = (
    "packages/memo_stack_core",
    "packages/memo_stack_server",
    "packages/memo_stack_adapters",
    "packages/memo_stack_sdk",
    "packages/memo_stack_mcp",
    "packages/memo_stack_cli",
)


def test_multimodal_live_provider_canary_reports_missing_key_without_secret_leak(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "provider-canary.json"
    sentinel = "sk-test-secret-that-must-not-leak"
    env = _test_env_without_openai_keys()
    env["MEMORY_AGENT_BENCH_OPENAI_API_KEY"] = sentinel

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--report-out",
            str(report_path),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 2
    stdout_report = json.loads(result.stdout)
    file_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert stdout_report == file_report
    assert file_report["ok"] is False
    assert file_report["suite"] == "memo-stack-multimodal-live-provider-canary"
    assert file_report["required_env"] == ["MEMORY_OPENAI_API_KEY or OPENAI_API_KEY"]
    assert file_report["secrets_redacted"] is True
    assert isinstance(file_report["generated_at"], str)
    assert file_report["git"]["commit"]
    assert file_report["git"]["short_commit"]
    assert isinstance(file_report["git"]["dirty"], bool)
    assert file_report["provider_key_present"] is False
    assert file_report["provider_contract"]["transcription"] == {
        "docs_url": "https://developers.openai.com/api/docs/guides/speech-to-text",
        "endpoint": "/v1/audio/transcriptions",
        "max_upload_bytes": 26214400,
        "model": "gpt-4o-mini-transcribe",
        "supported_file_types": [
            ".m4a",
            ".mp3",
            ".mp4",
            ".mpeg",
            ".mpga",
            ".wav",
            ".webm",
        ],
    }
    assert file_report["provider_contract"]["vision"] == {
        "detail": "low",
        "detail_levels": ["low", "high", "auto"],
        "docs_url": "https://developers.openai.com/api/docs/guides/images-vision",
        "endpoint_family": "responses",
        "max_images_per_request": 1500,
        "max_provider_binary_upload_bytes": 402650094,
        "max_provider_payload_bytes": 536870912,
        "model": "gpt-4.1-mini",
        "supported_file_types": [".gif", ".jpeg", ".jpg", ".png", ".webp"],
    }
    assert file_report["components"]["provider_key"] == {
        "message": (
            "Set MEMORY_OPENAI_API_KEY or OPENAI_API_KEY before running the live provider canary"
        ),
        "operator_action": "configure_provider_credential",
        "reason": "provider_credential_missing",
        "status": "degraded",
        "user_retryable": False,
    }
    assert file_report["components"]["vision"] == {
        "operator_action": "configure_provider_credential",
        "reason": "provider_credential_missing",
        "status": "skipped",
        "user_retryable": False,
    }
    assert file_report["components"]["transcription"] == {
        "operator_action": "configure_provider_credential",
        "reason": "provider_credential_missing",
        "status": "skipped",
        "user_retryable": False,
    }
    combined_output = result.stdout + result.stderr + report_path.read_text(encoding="utf-8")
    assert sentinel not in combined_output
    assert "MEMORY_AGENT_BENCH_OPENAI_API_KEY" not in combined_output


def test_multimodal_live_provider_canary_has_local_fixtures_and_redaction() -> None:
    module = _load_canary_module()

    assert module._content_type_for_path(Path("fixture.wav")) == "audio/wav"
    assert module._content_type_for_path(Path("fixture.mp3")) == "audio/mpeg"
    assert module._content_type_for_path(Path("fixture.bin")) == ("application/octet-stream")
    assert module._sample_png_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    safe = module._safe_diagnostics(
        {
            "api_key": "sk-test-secret",
            "access_token": "secret-token",
            "authorization": "Bearer secret",
            "request_timeout_seconds": 10,
            "usage": {"input_tokens": 1, "output_tokens": 2},
        }
    )

    assert "api_key" not in safe
    assert "access_token" not in safe
    assert "authorization" not in safe
    assert safe["request_timeout_seconds"] == 10
    assert safe["usage"] == {"input_tokens": 1, "output_tokens": 2}


def test_multimodal_live_provider_canary_default_report_matches_goal_audit(
    monkeypatch,
) -> None:
    module = _load_canary_module()
    monkeypatch.delenv("MEMORY_MULTIMODAL_PROVIDER_CANARY_REPORT_OUT", raising=False)

    args = module._parse_args([])

    assert args.report_out == ".e2e-artifacts/multimodal-live-provider-canary.json"


def test_multimodal_live_provider_canary_reports_model_specific_vision_details() -> None:
    module = _load_canary_module()
    args = module._parse_args(["--vision-model", "gpt-5.5"])

    report = module._base_report(args, has_provider_key=False)

    assert report["provider_contract"]["vision"]["detail_levels"] == [
        "low",
        "high",
        "original",
        "auto",
    ]


def test_multimodal_live_provider_canary_preflights_audio_fixture_contract(
    tmp_path: Path,
) -> None:
    module = _load_canary_module()
    valid = tmp_path / "fixture.wav"
    valid.write_bytes(b"RIFF" + b"\0" * 32)
    unsupported = tmp_path / "fixture.ogg"
    unsupported.write_bytes(b"OggS")
    huge = tmp_path / "fixture.mp3"
    with huge.open("wb") as handle:
        handle.truncate(module.OPENAI_AUDIO_MAX_UPLOAD_BYTES + 1)

    assert module._audio_fixture_contract_check(valid) == {"status": "succeeded"}
    assert module._audio_fixture_contract_check(unsupported) == {
        "filename_suffix": ".ogg",
        "message": "Audio fixture type is not supported by OpenAI transcription upload",
        "operator_action": "replace_audio_fixture",
        "reason": "audio_fixture_unsupported_type",
        "status": "degraded",
        "supported_file_types": [
            ".m4a",
            ".mp3",
            ".mp4",
            ".mpeg",
            ".mpga",
            ".wav",
            ".webm",
        ],
        "user_retryable": False,
    }
    too_large = module._audio_fixture_contract_check(huge)
    assert too_large["status"] == "degraded"
    assert too_large["reason"] == "audio_fixture_too_large"
    assert too_large["operator_action"] == "replace_audio_fixture"
    assert too_large["max_upload_bytes"] == 26214400


def test_multimodal_live_provider_canary_requires_strong_synthetic_transcript() -> None:
    module = _load_canary_module()

    weak = module._transcript_check("memo", audio_path=None)
    strong = module._transcript_check(
        "Memo Stack live transcription canary",
        audio_path=None,
    )
    explicit_fixture = module._transcript_check("user supplied fixture", audio_path="voice.wav")

    assert weak == {
        "message": "Synthetic speech transcript missed expected canary terms",
        "missing_terms": ["canary", "stack"],
        "operator_action": "inspect_provider_canary",
        "reason": "synthetic_transcript_mismatch",
        "status": "failed",
        "user_retryable": False,
    }
    assert strong == {"status": "succeeded"}
    assert explicit_fixture == {"status": "succeeded"}


def test_multimodal_live_provider_canary_rejects_empty_vision_evidence(
    monkeypatch,
) -> None:
    module = _load_canary_module()

    class EmptyVisionAdapter:
        def __init__(self, **_: object) -> None:
            pass

        async def analyze(self, request: object) -> SimpleNamespace:
            return SimpleNamespace(
                status="succeeded",
                payload={"summary": "", "visible_text": []},
                payload_status="parsed",
                provider_name="fake_vision",
                provider_model="fake-model",
                provider_version="fake-version",
                diagnostics={"request_timeout_seconds": 1},
            )

    monkeypatch.setattr(module, "OpenAIImageVisionAdapter", EmptyVisionAdapter)

    result = asyncio.run(
        module._run_vision(
            api_key="sk-test-provider-key",
            args=module._parse_args(["--timeout-seconds", "1"]),
        )
    )

    assert result == {
        "diagnostics": {"request_timeout_seconds": 1},
        "message": "Provider returned no visible text or image summary",
        "operator_action": "inspect_provider_canary",
        "payload_status": "parsed",
        "provider_model": "fake-model",
        "provider_name": "fake_vision",
        "provider_version": "fake-version",
        "reason": "vision_empty_evidence",
        "status": "failed",
        "summary_chars": 0,
        "user_retryable": False,
        "visible_text_count": 0,
    }


def _test_env_without_openai_keys() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("MEMORY_OPENAI_API_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    env["PYTHONPATH"] = _pythonpath(env)
    return env


def _pythonpath(env: dict[str, str]) -> str:
    parts = [str(ROOT / path) for path in PACKAGE_PATHS]
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    return os.pathsep.join(parts)


def _load_canary_module():
    for path in reversed(PACKAGE_PATHS):
        sys.path.insert(0, str(ROOT / path))
    spec = importlib.util.spec_from_file_location(
        "multimodal_live_provider_canary_for_test",
        SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
