from __future__ import annotations

import asyncio
import json
from pathlib import Path

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
