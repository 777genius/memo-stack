#!/usr/bin/env python3
"""Verify the one-command local MCP and visual-memory first-use path."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from infinity_context_core.application.sensitive_text import redact_sensitive_text
from infinity_context_core.reporting import with_report_provenance

try:
    from scripts.clean_full_smoke_redaction import has_unredacted_secret_marker, redact_payload
except ModuleNotFoundError:
    from clean_full_smoke_redaction import has_unredacted_secret_marker, redact_payload


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUITE = "infinity-context-local-experience-proof"
DEFAULT_REPORT_OUT = ".e2e-artifacts/local-experience-proof.json"
DEFAULT_VISUAL_SMOKE_REPORT = ".e2e-artifacts/local-mcp-visual-memory-smoke.json"
DEFAULT_PROOF_HOME = PROJECT_ROOT / ".tmp" / "local-experience-proof-home"
MIN_MCP_TOOL_COUNT = 40


def main() -> int:
    args = _parse_args()
    started = time.perf_counter()
    env = _proof_env(args)
    components: dict[str, Any] = {}

    components["install_script_syntax"] = _run_plain_check(
        ["bash", "-n", str(PROJECT_ROOT / "scripts" / "install.sh")],
        env=env,
        timeout_seconds=args.command_timeout_seconds,
    )
    components["quickstart_no_start"] = _summarize_quickstart(
        _run_json_command(
            [
                args.python,
                "-m",
                "infinity_context_cli",
                "quickstart",
                "--home",
                str(args.home),
                "--repo-dir",
                str(args.repo_dir),
                "--api-url",
                args.api_url,
                "--agent",
                args.agent,
                "--no-start",
                "--force",
                "--json",
            ],
            env=env,
            timeout_seconds=args.command_timeout_seconds,
        ),
        expect_ready=False,
    )
    components["quickstart_live"] = _summarize_quickstart(
        _run_json_command(
            [
                args.python,
                "-m",
                "infinity_context_cli",
                "quickstart",
                "--home",
                str(args.home),
                "--repo-dir",
                str(args.repo_dir),
                "--api-url",
                args.api_url,
                "--agent",
                args.agent,
                "--force",
                "--json",
            ],
            env=env,
            timeout_seconds=args.command_timeout_seconds,
        ),
        expect_ready=True,
    )
    components["doctor"] = _summarize_doctor(
        _run_json_command(
            [args.python, "-m", "infinity_context_cli", "doctor", "--json"],
            env=env,
            timeout_seconds=args.command_timeout_seconds,
        )
    )
    components["local_visual_smoke"] = _summarize_local_visual_smoke(
        _run_json_command(
            [
                args.python,
                str(PROJECT_ROOT / "scripts" / "local_mcp_visual_memory_smoke.py"),
                "--api-url",
                args.api_url,
                "--report-out",
                args.visual_smoke_report,
            ],
            env=env,
            timeout_seconds=args.visual_smoke_timeout_seconds,
        )
    )

    failures = _failed_required_components(components)
    report = _build_report(
        api_url=args.api_url,
        agent=args.agent,
        components=components,
        failures=failures,
        started=started,
    )
    _write_report(report, args.report_out, env=env)
    return 0 if report["ok"] else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--home", type=Path, default=DEFAULT_PROOF_HOME)
    parser.add_argument("--repo-dir", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--api-url", default=os.getenv("MEMORY_API_URL", "http://127.0.0.1:7788"))
    parser.add_argument("--agent", default="codex")
    parser.add_argument("--report-out", default=DEFAULT_REPORT_OUT)
    parser.add_argument("--visual-smoke-report", default=DEFAULT_VISUAL_SMOKE_REPORT)
    parser.add_argument("--command-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--visual-smoke-timeout-seconds", type=float, default=60.0)
    return parser.parse_args()


def _proof_env(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    env["INFINITY_CONTEXT_HOME"] = str(args.home.expanduser())
    env["INFINITY_CONTEXT_REPO_ROOT"] = str(args.repo_dir.expanduser())
    env["MEMORY_API_URL"] = args.api_url.rstrip("/")
    port = _api_port(args.api_url)
    if port is not None:
        env.setdefault("MEMORY_SERVER_PORT", str(port))
    return env


def _api_port(api_url: str) -> int | None:
    parsed = urlparse(api_url)
    if parsed.port is not None:
        return parsed.port
    if parsed.scheme == "http":
        return 80
    if parsed.scheme == "https":
        return 443
    return None


def _run_plain_check(
    command: list[str],
    *,
    env: dict[str, str],
    timeout_seconds: float,
) -> dict[str, Any]:
    result = _run_command(command, env=env, timeout_seconds=timeout_seconds)
    return {
        "status": "succeeded" if result["returncode"] == 0 else "failed",
        "ok": result["returncode"] == 0,
        "returncode": result["returncode"],
        "command": _command_label(command),
        "error_tail": result.get("stderr_tail") if result["returncode"] != 0 else "",
    }


def _run_json_command(
    command: list[str],
    *,
    env: dict[str, str],
    timeout_seconds: float,
) -> dict[str, Any]:
    result = _run_command(command, env=env, timeout_seconds=timeout_seconds)
    payload, parse_error = _parse_json_from_output(str(result.get("stdout") or ""))
    return {
        "status": "succeeded" if result["returncode"] == 0 and payload is not None else "failed",
        "ok": result["returncode"] == 0 and payload is not None,
        "returncode": result["returncode"],
        "command": _command_label(command),
        "payload": payload,
        "parse_error": parse_error,
        "stdout_tail": result.get("stdout_tail") if payload is None else "",
        "stderr_tail": result.get("stderr_tail") if result["returncode"] != 0 else "",
    }


def _run_command(
    command: list[str],
    *,
    env: dict[str, str],
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "command timed out",
            "stdout_tail": _tail(exc.stdout or ""),
            "stderr_tail": _tail(exc.stderr or "command timed out"),
        }
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }


def _parse_json_from_output(output: str) -> tuple[dict[str, Any] | None, str | None]:
    for index, char in enumerate(output):
        if char != "{":
            continue
        try:
            parsed = json.loads(output[index:])
        except json.JSONDecodeError as exc:
            last_error = str(exc)
            continue
        if isinstance(parsed, dict):
            return parsed, None
        return None, "json payload is not an object"
    return None, locals().get("last_error", "json object not found")


def _summarize_quickstart(result: dict[str, Any], *, expect_ready: bool) -> dict[str, Any]:
    payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
    experience = payload.get("local_experience") if isinstance(payload, dict) else {}
    if not isinstance(experience, dict):
        experience = {}
    readiness = experience.get("readiness") if isinstance(experience.get("readiness"), dict) else {}
    first_capture = (
        experience.get("first_capture") if isinstance(experience.get("first_capture"), dict) else {}
    )
    expected_status = "ready" if expect_ready else "configured_not_started"
    checks = {
        "command_ok": result.get("ok") is True,
        "payload_ok": payload.get("ok") is True,
        "status_expected": experience.get("status") == expected_status,
        "mcp_ready": experience.get("mcp_ready") is True,
        "token_not_included": payload.get("token_included") is False,
        "runtime_ready_matches": (
            experience.get("visual_memory_ready") is True
            if expect_ready
            else experience.get("visual_memory_ready") is False
        ),
        "score_expected": (
            readiness.get("score") == 10.0 if expect_ready else readiness.get("score") == 4.0
        ),
        "capture_surface_documented": bool(first_capture.get("supports")),
        "review_ready_when_live": (
            first_capture.get("review_supported") is True if expect_ready else True
        ),
    }
    return {
        "status": "succeeded" if all(checks.values()) else "failed",
        "ok": all(checks.values()),
        "checks": checks,
        "local_experience_status": experience.get("status"),
        "readiness_score": readiness.get("score"),
        "first_capture_supports": list(_as_list(first_capture.get("supports"))),
        "active_modalities": list(_as_list(first_capture.get("active_modalities"))),
        "visual_memory_ready": experience.get("visual_memory_ready") is True,
        "mcp_ready": experience.get("mcp_ready") is True,
        "ready_agents": list(_as_list(experience.get("ready_agents"))),
        "command": result.get("command"),
        "returncode": result.get("returncode"),
        "parse_error": result.get("parse_error"),
    }


def _summarize_doctor(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
    experience = payload.get("local_experience") if isinstance(payload, dict) else {}
    if not isinstance(experience, dict):
        experience = {}
    readiness = experience.get("readiness") if isinstance(experience.get("readiness"), dict) else {}
    checks = {
        "command_ok": result.get("ok") is True,
        "payload_ok": payload.get("ok") is True,
        "status_ready": experience.get("status") == "ready",
        "visual_memory_ready": experience.get("visual_memory_ready") is True,
        "mcp_ready": experience.get("mcp_ready") is True,
        "score_ready": readiness.get("score") == 10.0,
    }
    return {
        "status": "succeeded" if all(checks.values()) else "failed",
        "ok": all(checks.values()),
        "checks": checks,
        "local_experience_status": experience.get("status"),
        "readiness_score": readiness.get("score"),
        "next_actions": list(_as_list(experience.get("next_actions"))),
        "command": result.get("command"),
        "returncode": result.get("returncode"),
        "parse_error": result.get("parse_error"),
    }


def _summarize_local_visual_smoke(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
    checks_payload = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    generated_mcp = (
        checks_payload.get("generated_mcp")
        if isinstance(checks_payload.get("generated_mcp"), dict)
        else {}
    )
    mcp_session = (
        checks_payload.get("mcp_session")
        if isinstance(checks_payload.get("mcp_session"), dict)
        else {}
    )
    ui = checks_payload.get("ui") if isinstance(checks_payload.get("ui"), dict) else {}
    visual_memory = (
        checks_payload.get("visual_memory")
        if isinstance(checks_payload.get("visual_memory"), dict)
        else {}
    )
    mcp_digest = (
        checks_payload.get("mcp_digest")
        if isinstance(checks_payload.get("mcp_digest"), dict)
        else {}
    )
    mcp_digest_checks = (
        mcp_digest.get("checks") if isinstance(mcp_digest.get("checks"), dict) else {}
    )
    checks = {
        "command_ok": result.get("ok") is True,
        "payload_ok": payload.get("ok") is True,
        "mcp_tool_count": int(mcp_session.get("tool_count") or 0) >= MIN_MCP_TOOL_COUNT,
        "raw_token_absent": generated_mcp.get("raw_token_absent") is True,
        "token_not_included": generated_mcp.get("token_included") is False,
        "first_memory_guidance": ui.get("first_memory_guidance") is True,
        "visual_memory_visible": visual_memory.get("browser_capture_visible") is True,
        "pending_review_created": int(visual_memory.get("pending_suggestions") or 0) >= 1,
        "mcp_digest_ready": mcp_digest.get("ok") is True,
        "mcp_digest_evidence_only": mcp_digest_checks.get("evidence_only") is True,
        "mcp_digest_pending_review": (
            mcp_digest_checks.get("pending_suggestion_visible") is True
        ),
        "mcp_digest_token_safe": mcp_digest_checks.get("raw_token_absent") is True,
    }
    return {
        "status": "succeeded" if all(checks.values()) else "failed",
        "ok": all(checks.values()),
        "checks": checks,
        "mcp_tool_count": mcp_session.get("tool_count"),
        "ui_url": payload.get("ui_url"),
        "review_url": payload.get("review_url"),
        "capture_id": visual_memory.get("capture_id"),
        "pending_suggestions": visual_memory.get("pending_suggestions"),
        "digest_id": mcp_digest.get("digest_id"),
        "digest_pending_suggestion_items": mcp_digest.get("pending_suggestion_items"),
        "command": result.get("command"),
        "returncode": result.get("returncode"),
        "parse_error": result.get("parse_error"),
    }


def _build_report(
    *,
    api_url: str,
    agent: str,
    components: dict[str, Any],
    failures: list[str],
    started: float,
) -> dict[str, object]:
    report = {
        "suite": SUITE,
        "schema_version": 1,
        "ok": not failures,
        "api_url": api_url.rstrip("/"),
        "ui_url": f"{api_url.rstrip('/')}/ui/",
        "agent": agent,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "components": components,
        "failures": failures,
        "redaction_applied": True,
    }
    return with_report_provenance(
        report,
        generated_by="scripts/local_experience_proof.py",
        suite=SUITE,
        project="infinity-context",
        cwd=PROJECT_ROOT,
    )


def _failed_required_components(components: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for name in (
        "install_script_syntax",
        "quickstart_no_start",
        "quickstart_live",
        "doctor",
        "local_visual_smoke",
    ):
        component = components.get(name)
        if not isinstance(component, dict) or component.get("ok") is not True:
            failures.append(name)
    return failures


def _write_report(report: dict[str, object], report_out: str, *, env: dict[str, str]) -> None:
    redacted = redact_payload(report, env=env)
    serialized = json.dumps(redacted, ensure_ascii=False, sort_keys=True)
    if has_unredacted_secret_marker(serialized):
        raise RuntimeError("Refusing to write local experience proof with unredacted secrets")
    if report_out:
        path = Path(report_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


def _tail(value: str, *, limit: int = 1200) -> str:
    return redact_sensitive_text(value)[-limit:]


def _command_label(command: list[str]) -> list[str]:
    return [Path(item).name if index == 0 else item for index, item in enumerate(command)]


def _as_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


if __name__ == "__main__":
    raise SystemExit(main())
