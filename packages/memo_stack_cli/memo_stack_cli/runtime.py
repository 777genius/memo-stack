"""Local runtime adapters for Memo Stack CLI."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from memo_stack_cli.config import MemoStackCliConfig


@dataclass(frozen=True)
class RuntimeResult:
    ok: bool
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class RuntimePort(Protocol):
    def up(self, profile: str) -> RuntimeResult: ...

    def down(self) -> RuntimeResult: ...

    def logs(self, service: str | None, tail: int) -> RuntimeResult: ...


class DockerComposeRuntime:
    def __init__(self, *, config: MemoStackCliConfig) -> None:
        self._config = config

    def up(self, profile: str) -> RuntimeResult:
        if profile == "full":
            command = (
                "docker",
                "compose",
                "--profile",
                "full",
                "up",
                "-d",
                "memo_stack_server_full",
                "memo_stack_worker_full",
            )
        else:
            command = (
                "docker",
                "compose",
                "--profile",
                "lite",
                "up",
                "-d",
                "memo_stack_server",
                "memo_stack_worker",
            )
        return self._run(command)

    def down(self) -> RuntimeResult:
        return self._run(("docker", "compose", "--profile", "lite", "--profile", "full", "down"))

    def logs(self, service: str | None, tail: int) -> RuntimeResult:
        command = ["docker", "compose", "logs", f"--tail={max(1, tail)}"]
        if service:
            command.append(service)
        return self._run(tuple(command))

    def _run(self, command: tuple[str, ...]) -> RuntimeResult:
        if not self._compose_file().exists():
            return RuntimeResult(
                ok=False,
                command=command,
                returncode=127,
                stdout="",
                stderr=f"docker-compose.yml not found under {self._config.repo_dir}",
            )
        env = os.environ.copy()
        env.setdefault("MEMORY_SERVICE_TOKEN", self._config.service_token)
        env.setdefault("COMPOSE_PROJECT_NAME", self._config.compose_project_name)
        env_file = self._config.env_path
        if env_file.exists():
            env.setdefault("MEMO_STACK_ENV_FILE", str(env_file))
        process = subprocess.run(
            command,
            cwd=self._config.repo_dir,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        return RuntimeResult(
            ok=process.returncode == 0,
            command=command,
            returncode=process.returncode,
            stdout=process.stdout,
            stderr=process.stderr,
        )

    def _compose_file(self) -> Path:
        return self._config.repo_dir / "docker-compose.yml"


def docker_available() -> bool:
    return shutil.which("docker") is not None


def docker_compose_available() -> bool:
    if not docker_available():
        return False
    process = subprocess.run(
        ("docker", "compose", "version"),
        text=True,
        capture_output=True,
        check=False,
    )
    return process.returncode == 0
