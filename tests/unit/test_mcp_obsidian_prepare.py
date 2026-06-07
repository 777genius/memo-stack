from __future__ import annotations

import asyncio
import json
from pathlib import Path

from memo_stack_mcp.application.local_runtime import LocalRuntimeMcpService
from memo_stack_mcp.application.obsidian import ObsidianMcpService
from memo_stack_mcp.application.prepare import ObsidianPrepareMcpService
from memo_stack_mcp.config import MemoryMcpSettings


def test_obsidian_prepare_dry_run_does_not_write(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    vault = tmp_path / "vault"
    repo.mkdir()
    vault.mkdir()
    (repo / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    service = _service(
        MemoryMcpSettings(
            api_url="http://127.0.0.1:9",
            local_runtime_enabled=True,
            local_runtime_home=str(home),
            local_runtime_repo_dir=str(repo),
            obsidian_enabled=True,
            obsidian_vault_path=str(vault),
            default_space_slug="memo-stack",
            default_profile_external_ref="belief",
        )
    )

    payload = asyncio.run(service.prepare(apply=False))

    assert payload["ok"] is True
    assert payload["data"]["status"] == "prepare_planned"
    assert payload["data"]["dry_run"] is True
    assert payload["data"]["local_runtime"]["would_write"]
    assert payload["data"]["obsidian_setup"]["would_install_plugin"] is True
    assert not (home / "config.toml").exists()
    assert not (vault / "Memo Stack").exists()
    assert not (vault / ".obsidian/plugins/memo-stack").exists()


def test_obsidian_prepare_apply_stops_before_preview_when_backend_not_ready(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    vault = tmp_path / "vault"
    repo.mkdir()
    vault.mkdir()
    (repo / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    service = _service(
        MemoryMcpSettings(
            api_url="http://127.0.0.1:9",
            local_runtime_enabled=True,
            local_runtime_home=str(home),
            local_runtime_repo_dir=str(repo),
            obsidian_enabled=True,
            obsidian_vault_path=str(vault),
            default_space_slug="memo-stack",
            default_profile_external_ref="belief",
        )
    )

    payload = asyncio.run(service.prepare(apply=True))
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["ok"] is True
    assert payload["data"]["status"] == "prepared_backend_not_ready"
    assert payload["data"]["applied"] is True
    assert payload["data"].get("obsidian_preview") is None
    assert (home / "config.toml").exists()
    assert (home / ".env").exists()
    assert (
        vault / "Memo Stack/spaces/memo-stack/profiles/belief/generated/facts"
    ).exists()
    assert (vault / ".obsidian/plugins/memo-stack/main.js").exists()
    assert "local_runtime_started" not in payload["diagnostics"]["side_effects"]
    assert "obsidian_sync" not in payload["diagnostics"]["side_effects"]
    assert "MEMORY_SERVICE_TOKEN" not in serialized
    assert "mst_" not in serialized


def test_obsidian_prepare_requires_local_runtime_gate(tmp_path: Path) -> None:
    home = tmp_path / "home"
    vault = tmp_path / "vault"
    vault.mkdir()
    service = _service(
        MemoryMcpSettings(
            local_runtime_enabled=False,
            local_runtime_home=str(home),
            obsidian_enabled=True,
            obsidian_vault_path=str(vault),
        )
    )

    payload = asyncio.run(service.prepare(apply=True))

    assert payload["ok"] is False
    assert payload["data"]["status"] == "local_runtime_init_failed"
    assert payload["error"]["code"] == "memo_stack_mcp.local_runtime.disabled"
    assert not home.exists()
    assert not (vault / "Memo Stack").exists()


def _service(settings: MemoryMcpSettings) -> ObsidianPrepareMcpService:
    return ObsidianPrepareMcpService(
        local_runtime=LocalRuntimeMcpService(settings=settings),
        obsidian=ObsidianMcpService(settings=settings),
    )
