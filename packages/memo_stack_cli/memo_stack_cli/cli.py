"""Memo Stack local CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx
from memo_stack_sdk import MemoStackClient, MemoStackError, ReadScope

from memo_stack_cli import __version__
from memo_stack_cli.config import DEFAULT_API_URL, init_local_config, load_config
from memo_stack_cli.doctor import doctor_payload, run_doctor
from memo_stack_cli.mcp_config import SUPPORTED_AGENTS, render_mcp_config, write_mcp_config
from memo_stack_cli.runtime import DockerComposeRuntime


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    try:
        return int(args.handler(args))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except (MemoStackError, httpx.HTTPError, ValueError) as exc:
        print(f"memo-stack: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memo-stack")
    parser.add_argument("--version", action="version", version=f"memo-stack {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Initialize local Memo Stack config.")
    init_parser.add_argument(
        "--home",
        default=None,
        help="Install home. Defaults to ~/.memo-stack.",
    )
    init_parser.add_argument("--repo-dir", default=None, help="Memo Stack repo root.")
    init_parser.add_argument("--api-url", default=DEFAULT_API_URL)
    init_parser.add_argument("--force", action="store_true")
    init_parser.add_argument("--json", action="store_true")
    init_parser.set_defaults(handler=_cmd_init)

    up_parser = subparsers.add_parser("up", help="Start local Memo Stack.")
    profile = up_parser.add_mutually_exclusive_group()
    profile.add_argument("--lite", action="store_true", help="Start lite local stack.")
    profile.add_argument("--full", action="store_true", help="Start full provider stack.")
    up_parser.set_defaults(handler=_cmd_up)

    down_parser = subparsers.add_parser("down", help="Stop local Memo Stack.")
    down_parser.set_defaults(handler=_cmd_down)

    restart_parser = subparsers.add_parser("restart", help="Restart local Memo Stack.")
    profile = restart_parser.add_mutually_exclusive_group()
    profile.add_argument("--lite", action="store_true")
    profile.add_argument("--full", action="store_true")
    restart_parser.set_defaults(handler=_cmd_restart)

    status_parser = subparsers.add_parser("status", help="Check local Memo Stack status.")
    status_parser.add_argument("--json", action="store_true")
    status_parser.set_defaults(handler=_cmd_status)

    doctor_parser = subparsers.add_parser("doctor", help="Run local diagnostics.")
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.set_defaults(handler=_cmd_doctor)

    logs_parser = subparsers.add_parser("logs", help="Show docker compose logs.")
    logs_parser.add_argument("--service", default=None)
    logs_parser.add_argument("--tail", type=int, default=120)
    logs_parser.set_defaults(handler=_cmd_logs)

    mcp_parser = subparsers.add_parser("mcp-config", help="Print or write MCP config.")
    mcp_parser.add_argument("--agent", choices=sorted(SUPPORTED_AGENTS), required=True)
    mcp_parser.add_argument("--write", action="store_true")
    mcp_parser.add_argument("--include-token", action="store_true")
    mcp_parser.set_defaults(handler=_cmd_mcp_config)

    digest_parser = subparsers.add_parser("digest", help="Build a memory digest.")
    digest_parser.add_argument("topic")
    digest_parser.add_argument("--space", dest="space_slug", default=None)
    digest_parser.add_argument("--profile", dest="profile_external_ref", default=None)
    digest_parser.add_argument("--thread", dest="thread_external_ref", default=None)
    digest_parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    digest_parser.add_argument("--token-budget", type=int, default=2400)
    digest_parser.add_argument("--max-facts", type=int, default=20)
    digest_parser.add_argument("--max-chunks", type=int, default=20)
    digest_parser.add_argument("--max-suggestions", type=int, default=10)
    digest_parser.add_argument("--include-superseded", action="store_true")
    digest_parser.add_argument("--no-suggestions", action="store_true")
    digest_parser.add_argument("--no-related", action="store_true")
    digest_parser.set_defaults(handler=_cmd_digest)

    return parser


def _cmd_init(args: argparse.Namespace) -> int:
    repo_dir = Path(args.repo_dir).expanduser() if args.repo_dir else load_config().repo_dir
    config = init_local_config(
        home=Path(args.home).expanduser() if args.home else load_config().home,
        repo_dir=repo_dir,
        api_url=args.api_url,
        force=args.force,
    )
    payload = {
        "ok": True,
        "home": str(config.home),
        "repo_dir": str(config.repo_dir),
        "api_url": config.api_url,
        "env_path": str(config.env_path),
        "config_path": str(config.config_path),
        "token_configured": bool(config.service_token),
    }
    _print_payload(payload, as_json=args.json)
    return 0


def _cmd_up(args: argparse.Namespace) -> int:
    config = load_config()
    profile = "full" if args.full else "lite"
    result = DockerComposeRuntime(config=config).up(profile)
    _print_runtime_result(result)
    return 0 if result.ok else result.returncode or 1


def _cmd_down(_args: argparse.Namespace) -> int:
    result = DockerComposeRuntime(config=load_config()).down()
    _print_runtime_result(result)
    return 0 if result.ok else result.returncode or 1


def _cmd_restart(args: argparse.Namespace) -> int:
    config = load_config()
    runtime = DockerComposeRuntime(config=config)
    down = runtime.down()
    _print_runtime_result(down)
    if not down.ok:
        return down.returncode or 1
    profile = "full" if args.full else "lite"
    up = runtime.up(profile)
    _print_runtime_result(up)
    return 0 if up.ok else up.returncode or 1


def _cmd_status(args: argparse.Namespace) -> int:
    config = load_config()
    payload = _status_payload(config)
    _print_payload(payload, as_json=args.json)
    return 0 if payload["ok"] else 1


def _cmd_doctor(args: argparse.Namespace) -> int:
    config = load_config()
    payload = doctor_payload(config, run_doctor(config))
    _print_payload(payload, as_json=args.json)
    return 0 if payload["ok"] else 1


def _cmd_logs(args: argparse.Namespace) -> int:
    result = DockerComposeRuntime(config=load_config()).logs(args.service, args.tail)
    _print_runtime_result(result)
    return 0 if result.ok else result.returncode or 1


def _cmd_mcp_config(args: argparse.Namespace) -> int:
    config = load_config()
    if args.write:
        path = write_mcp_config(
            agent=args.agent,
            config=config,
            include_token=args.include_token,
        )
        print(str(path))
    else:
        print(
            render_mcp_config(
                agent=args.agent,
                config=config,
                include_token=args.include_token,
            )
        )
    return 0


def _cmd_digest(args: argparse.Namespace) -> int:
    config = load_config()
    client = MemoStackClient(base_url=config.api_url, token=config.service_token)
    payload = client.build_digest(
        topic=args.topic,
        read_scope=ReadScope(
            space_slug=args.space_slug or config.default_space_slug,
            profile_external_ref=args.profile_external_ref
            or config.default_profile_external_ref,
            thread_external_ref=args.thread_external_ref,
        ),
        token_budget=args.token_budget,
        max_facts=args.max_facts,
        max_chunks=args.max_chunks,
        max_suggestions=args.max_suggestions,
        include_pending_suggestions=not args.no_suggestions,
        include_superseded=args.include_superseded,
        include_related=not args.no_related,
        format=args.format,
    )
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(str(data.get("rendered_markdown") or ""))
    return 0


def _status_payload(config) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {config.service_token}"}
    payload: dict[str, Any] = {
        "ok": False,
        "api_url": config.api_url,
        "home": str(config.home),
        "repo_dir": str(config.repo_dir),
        "health": None,
        "capabilities": None,
    }
    try:
        with httpx.Client(base_url=config.api_url, timeout=3.0, headers=headers) as client:
            health = client.get("/v1/health")
            capabilities = client.get("/v1/capabilities")
            payload["health"] = _response_payload(health)
            payload["capabilities"] = _response_payload(capabilities)
            payload["ok"] = health.is_success and capabilities.is_success
    except httpx.HTTPError as exc:
        payload["error"] = exc.__class__.__name__
    return payload


def _response_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        payload = {"body": response.text[:500]}
    return {"status_code": response.status_code, "data": payload}


def _print_runtime_result(result) -> None:
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)


def _print_payload(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")
