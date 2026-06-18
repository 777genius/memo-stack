#!/usr/bin/env python3
"""Run the Flutter Marionette memory flow against a local server and worker."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def main() -> int:
    args = _parse_args()
    root = Path(__file__).resolve().parents[1]
    frontend_dir = (root / args.frontend_dir).resolve()
    python_bin = _resolve_python(args.python, root=root)
    flutter_bin = _resolve_flutter(args.flutter)
    dart_bin = _resolve_dart(flutter_bin)
    run_id = str(int(time.time() * 1000))
    scope_ref = args.scope_ref or f"marionette-local-proof-{run_id}"

    tmp_ctx = tempfile.TemporaryDirectory(prefix="memo-stack-marionette.")
    tmp_root = Path(tmp_ctx.name)
    processes: list[subprocess.Popen[bytes]] = []
    try:
        server_env = _server_env(
            tmp_root=tmp_root,
            host=args.host,
            port=args.port,
            service_token=args.service_token,
        )
        server = _start(
            [str(python_bin), "-m", "memo_stack_server.main"],
            cwd=root,
            env=server_env,
        )
        processes.append(server)
        _wait_for_health(
            f"http://{args.host}:{args.port}/healthz",
            server,
            timeout_seconds=args.server_startup_timeout,
        )

        worker = _start(
            [
                str(python_bin),
                "-m",
                "memo_stack_server.worker",
                "--loop",
                "--role",
                "all",
                "--sleep-seconds",
                "1",
                "--limit",
                "10",
            ],
            cwd=root,
            env=server_env,
        )
        processes.append(worker)

        marionette_env = os.environ.copy()
        marionette_env.update(
            {
                "FLUTTER_BIN": str(flutter_bin),
                "MEMO_STACK_BACKEND_HOST": args.host,
                "MEMO_STACK_BACKEND_PORT": str(args.port),
                "MEMO_STACK_SERVICE_TOKEN": args.service_token,
                "MEMO_STACK_SPACE_SLUG": args.space_slug,
                "MEMO_STACK_MEMORY_SCOPE_EXTERNAL_REF": scope_ref,
                "MEMO_STACK_E2E_STARTUP_TIMEOUT": str(args.flutter_startup_timeout),
                "MEMO_STACK_E2E_CALL_TIMEOUT": str(args.call_timeout),
                "MEMO_STACK_E2E_DEVICE": args.device,
                "MEMO_STACK_E2E_RUN_ID": run_id,
            }
        )
        result = subprocess.run(
            [str(dart_bin), "run", "tool/marionette_anchor_lifecycle_e2e.dart"],
            cwd=frontend_dir,
            env=marionette_env,
            check=False,
        )
        return int(result.returncode)
    finally:
        _stop_processes(reversed(processes))
        if args.keep_temp:
            print(f"kept temp dir: {tmp_root}", file=sys.stderr)
        else:
            tmp_ctx.cleanup()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Memo Stack frontend Marionette E2E with local server and worker."
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--flutter", default=os.environ.get("FLUTTER", "flutter"))
    parser.add_argument("--frontend-dir", default="frontend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=17789)
    parser.add_argument("--service-token", default="local-dev-token")
    parser.add_argument("--space-slug", default="marionette-local-proof")
    parser.add_argument("--scope-ref")
    parser.add_argument("--device", default="macos")
    parser.add_argument("--server-startup-timeout", type=int, default=90)
    parser.add_argument("--flutter-startup-timeout", type=int, default=180)
    parser.add_argument("--call-timeout", type=int, default=45)
    parser.add_argument("--keep-temp", action="store_true")
    return parser.parse_args()


def _server_env(
    *,
    tmp_root: Path,
    host: str,
    port: int,
    service_token: str,
) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "MEMORY_DEPLOY_PROFILE": "test",
            "MEMORY_DATABASE_URL": f"sqlite+aiosqlite:///{tmp_root / 'memory.db'}",
            "MEMORY_AUTO_CREATE_SCHEMA": "true",
            "MEMORY_HOST": host,
            "MEMORY_PORT": str(port),
            "MEMORY_SERVICE_TOKEN": service_token,
            "MEMORY_CAPTURE_MODE": "suggest",
            "MEMORY_QDRANT_ENABLED": "false",
            "MEMORY_GRAPHITI_ENABLED": "false",
            "MEMORY_EMBEDDINGS_ENABLED": "false",
            "MEMORY_ASSET_STORAGE_DIR": str(tmp_root / "assets"),
        }
    )
    return env


def _resolve_flutter(value: str) -> Path:
    candidates = [
        value,
        str(Path.home() / "dev/flutter/bin/flutter"),
        str(Path.home() / "dev/projects/flutter/bin/flutter"),
    ]
    for candidate in candidates:
        resolved = shutil.which(candidate) if os.path.sep not in candidate else candidate
        if resolved and Path(resolved).exists():
            return Path(resolved).resolve()
    return Path(value)


def _resolve_python(value: str, *, root: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path


def _resolve_dart(flutter_bin: Path) -> Path:
    adjacent = flutter_bin.parent / "dart"
    if adjacent.exists():
        return adjacent.resolve()
    dart = shutil.which("dart")
    if dart:
        return Path(dart).resolve()
    return Path("dart")


def _start(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.Popen[bytes]:
    print(f"starting: {' '.join(command)}", file=sys.stderr)
    return subprocess.Popen(command, cwd=cwd, env=env)


def _wait_for_health(url: str, process: subprocess.Popen[bytes], *, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: str | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"server exited before health check: {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if 200 <= int(response.status) < 300:
                    return
        except (OSError, urllib.error.URLError) as exc:
            last_error = str(exc)
        time.sleep(1)
    raise TimeoutError(f"server health check timed out: {url}; last_error={last_error}")


def _stop_processes(processes) -> None:
    for process in processes:
        if process.poll() is not None:
            continue
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
