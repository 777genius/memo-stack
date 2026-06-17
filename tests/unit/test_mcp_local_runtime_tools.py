from __future__ import annotations

import asyncio
import json
from pathlib import Path

from memo_stack_cli.runtime import RuntimeResult
from memo_stack_mcp.application import local_runtime
from memo_stack_mcp.application.local_runtime import LocalRuntimeMcpService
from memo_stack_mcp.config import MemoryMcpSettings


def test_local_runtime_status_disabled_does_not_touch_home(tmp_path: Path) -> None:
    missing_home = tmp_path / "missing-home"
    service = LocalRuntimeMcpService(
        settings=MemoryMcpSettings(
            local_runtime_enabled=False,
            local_runtime_home=str(missing_home),
        )
    )

    payload = asyncio.run(service.status())

    assert payload["ok"] is True
    assert payload["data"]["status"] == "disabled"
    assert payload["data"]["enabled"] is False
    assert not missing_home.exists()


def test_local_runtime_init_dry_run_then_apply_writes_config_without_token_leak(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    service = LocalRuntimeMcpService(
        settings=MemoryMcpSettings(
            local_runtime_enabled=True,
            local_runtime_home=str(home),
            local_runtime_repo_dir=str(repo),
        )
    )

    dry_run = asyncio.run(service.init(apply=False))

    assert dry_run["ok"] is True
    assert dry_run["data"]["dry_run"] is True
    assert dry_run["data"]["would_write"]
    assert not (home / "config.toml").exists()
    assert not (home / ".env").exists()

    applied = asyncio.run(service.init(apply=True))
    serialized = json.dumps(applied, sort_keys=True)

    assert applied["ok"] is True
    assert applied["data"]["applied"] is True
    assert applied["data"]["token_configured"] is True
    assert (home / "config.toml").exists()
    assert (home / ".env").exists()
    assert "mst_" not in serialized
    assert "MEMORY_SERVICE_TOKEN" not in serialized


def test_local_runtime_start_dry_run_is_plan_only(tmp_path: Path) -> None:
    service = LocalRuntimeMcpService(
        settings=MemoryMcpSettings(
            local_runtime_enabled=True,
            local_runtime_home=str(tmp_path / "home"),
        )
    )

    payload = asyncio.run(service.start(compose_profile="lite", apply=False))

    assert payload["ok"] is True
    assert payload["data"]["dry_run"] is True
    assert payload["data"]["status"] == "start_planned"
    assert payload["data"]["command"] == [
        "docker",
        "compose",
        "--profile",
        "lite",
        "up",
        "-d",
        "memo_stack_server",
        "memo_stack_worker",
        "memo_stack_extraction_worker",
    ]
    assert not (tmp_path / "home").exists()


def test_local_runtime_start_apply_requires_separate_start_gate(tmp_path: Path) -> None:
    service = LocalRuntimeMcpService(
        settings=MemoryMcpSettings(
            local_runtime_enabled=True,
            local_runtime_start_enabled=False,
            local_runtime_home=str(tmp_path / "home"),
        )
    )

    payload = asyncio.run(service.start(compose_profile="lite", apply=True))

    assert payload["ok"] is False
    assert payload["error"]["code"] == "memo_stack_mcp.local_runtime.start_disabled"


def test_local_runtime_start_redacts_provider_tokens_in_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")

    class FakeRuntime:
        def __init__(self, *, config) -> None:
            self.config = config

        def up(self, compose_profile: str) -> RuntimeResult:
            assert compose_profile == "lite"
            return RuntimeResult(
                ok=False,
                command=("docker", "compose", "up"),
                returncode=1,
                stdout=(
                    f"service token {self.config.service_token} "
                    "ghp_abcdefghijklmnopqrstuvwxyz "
                    "AKIAIOSFODNN7EXAMPLE"
                ),
                stderr="token=plain-provider-token-value password=hunter2-secret-value",
            )

    monkeypatch.setattr(local_runtime, "DockerComposeRuntime", FakeRuntime)
    service = LocalRuntimeMcpService(
        settings=MemoryMcpSettings(
            local_runtime_enabled=True,
            local_runtime_start_enabled=True,
            local_runtime_home=str(home),
            local_runtime_repo_dir=str(repo),
        )
    )

    asyncio.run(service.init(apply=True))
    payload = asyncio.run(service.start(compose_profile="lite", apply=True))
    rendered = json.dumps(payload, sort_keys=True)

    assert payload["ok"] is True
    assert payload["data"]["status"] == "start_failed"
    assert "ghp_abcdefghijklmnopqrstuvwxyz" not in rendered
    assert "AKIAIOSFODNN7EXAMPLE" not in rendered
    assert "plain-provider-token-value" not in rendered
    assert "hunter2-secret-value" not in rendered
    assert "[redacted]" in rendered
