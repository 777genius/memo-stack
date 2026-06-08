from __future__ import annotations

import asyncio
import json
from pathlib import Path

from memo_stack_mcp.application.obsidian import ObsidianMcpService
from memo_stack_mcp.config import MemoryMcpSettings


def test_obsidian_status_disabled_does_not_touch_vault(tmp_path: Path) -> None:
    missing_vault = tmp_path / "missing-vault"
    service = ObsidianMcpService(
        settings=MemoryMcpSettings(
            obsidian_enabled=False,
            obsidian_vault_path=str(missing_vault),
        )
    )

    payload = asyncio.run(service.status())

    assert payload["ok"] is True
    assert payload["data"]["status"] == "disabled"
    assert payload["data"]["enabled"] is False
    assert not missing_vault.exists()


def test_obsidian_setup_dry_run_then_apply_uses_v2_layout(tmp_path: Path) -> None:
    service = ObsidianMcpService(
        settings=MemoryMcpSettings(
            obsidian_enabled=True,
            obsidian_vault_path=str(tmp_path),
            default_space_slug="memo-stack",
            default_profile_external_ref="belief",
        )
    )

    dry_run = asyncio.run(service.setup(apply=False))
    expected_fact_dir = (
        tmp_path
        / "Memo Stack/spaces/memo-stack/profiles/belief/generated/facts"
    )

    assert dry_run["ok"] is True
    assert dry_run["data"]["dry_run"] is True
    assert dry_run["data"]["would_write"]
    assert not expected_fact_dir.exists()

    applied = asyncio.run(service.setup(apply=True))

    assert applied["ok"] is True
    assert applied["data"]["applied"] is True
    assert expected_fact_dir.exists()
    assert (tmp_path / "Memo Stack/README.md").exists()


def test_obsidian_setup_can_install_plugin_with_local_cli_path(tmp_path: Path) -> None:
    service = ObsidianMcpService(
        settings=MemoryMcpSettings(
            obsidian_enabled=True,
            obsidian_vault_path=str(tmp_path),
        )
    )

    applied = asyncio.run(
        service.setup(apply=True, install_plugin=True, enable_plugin=True)
    )
    settings_path = tmp_path / ".obsidian/plugins/memo-stack/data.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))

    assert applied["ok"] is True
    assert applied["data"]["plugin_installed"] is True
    assert applied["data"]["plugin_enabled"] is True
    assert settings["localCliPath"] == "memo-stack"
    assert settings["vaultPathOverride"] == str(tmp_path.resolve())


def test_obsidian_setup_supports_custom_config_dir(tmp_path: Path) -> None:
    service = ObsidianMcpService(
        settings=MemoryMcpSettings(
            obsidian_enabled=True,
            obsidian_vault_path=str(tmp_path),
            obsidian_config_dir=".obsidian-dev",
            default_space_slug="team",
            default_profile_external_ref="backend",
        )
    )

    applied = asyncio.run(
        service.setup(apply=True, install_plugin=True, enable_plugin=True)
    )
    settings_path = tmp_path / ".obsidian-dev/plugins/memo-stack/data.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))

    assert applied["ok"] is True
    assert applied["data"]["obsidian_config_dir"] == ".obsidian-dev"
    assert applied["data"]["settings_path"] == str(settings_path)
    assert (tmp_path / ".obsidian-dev/community-plugins.json").exists()
    assert not (tmp_path / ".obsidian/plugins/memo-stack").exists()
    assert settings["spaceSlug"] == "team"
    assert settings["profileExternalRef"] == "backend"


def test_obsidian_sync_apply_requires_separate_sync_gate(tmp_path: Path) -> None:
    service = ObsidianMcpService(
        settings=MemoryMcpSettings(
            obsidian_enabled=True,
            obsidian_sync_enabled=False,
            obsidian_vault_path=str(tmp_path),
        )
    )

    payload = asyncio.run(service.sync(apply=True))

    assert payload["ok"] is False
    assert payload["error"]["code"] == "memo_stack_mcp.obsidian.sync_disabled"
