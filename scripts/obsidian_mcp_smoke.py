"""Non-UI MCP smoke for Obsidian vault setup tools."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args(argv)

    temp_dir = Path(tempfile.mkdtemp(prefix="memo-stack-obsidian-mcp-"))
    try:
        payload = asyncio.run(_run(temp_dir))
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    finally:
        if not args.keep:
            shutil.rmtree(temp_dir, ignore_errors=True)


async def _run(temp_dir: Path) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    missing_vault = temp_dir / "missing-vault"
    missing_home = temp_dir / "missing-home"
    local_home = temp_dir / "memo-home"
    prepare_home = temp_dir / "prepare-home"
    prepare_vault = temp_dir / "PrepareVault"
    vault = temp_dir / "Vault"
    vault.mkdir()
    prepare_vault.mkdir()

    disabled = await _with_session(
        repo_root=repo_root,
        env={
            "MEMORY_MCP_OBSIDIAN_ENABLED": "false",
            "MEMORY_MCP_OBSIDIAN_VAULT": str(missing_vault),
        },
        callback=lambda session: _call(session, "memory_obsidian_status", {}),
    )
    _assert(disabled["ok"] is True, "disabled status should return ok")
    _assert(
        disabled["data"]["status"] == "disabled",
        "disabled status should report disabled",
    )
    _assert(not missing_vault.exists(), "disabled status must not touch the vault")

    local_disabled = await _with_session(
        repo_root=repo_root,
        env={
            "MEMORY_MCP_LOCAL_RUNTIME_ENABLED": "false",
            "MEMORY_MCP_LOCAL_RUNTIME_HOME": str(missing_home),
        },
        callback=lambda session: _call(session, "memory_local_runtime_status", {}),
    )
    _assert(local_disabled["ok"] is True, "local runtime disabled status should return ok")
    _assert(
        local_disabled["data"]["status"] == "disabled",
        "local runtime disabled status should report disabled",
    )
    _assert(not missing_home.exists(), "local runtime disabled status must not touch home")

    local_env = {
        "MEMORY_MCP_LOCAL_RUNTIME_ENABLED": "true",
        "MEMORY_MCP_LOCAL_RUNTIME_START_ENABLED": "false",
        "MEMORY_MCP_LOCAL_RUNTIME_HOME": str(local_home),
        "MEMORY_MCP_LOCAL_RUNTIME_REPO_DIR": str(repo_root),
    }
    local_init_dry_run = await _with_session(
        repo_root=repo_root,
        env=local_env,
        callback=lambda session: _call(session, "memory_local_runtime_init", {"apply": False}),
    )
    _assert(local_init_dry_run["ok"] is True, "local runtime init dry-run should succeed")
    _assert(
        local_init_dry_run["data"]["dry_run"] is True,
        "local runtime init should be dry-run by default",
    )
    _assert(not (local_home / "config.toml").exists(), "local runtime dry-run must not write")

    local_init_applied = await _with_session(
        repo_root=repo_root,
        env=local_env,
        callback=lambda session: _call(session, "memory_local_runtime_init", {"apply": True}),
    )
    _assert(local_init_applied["ok"] is True, "local runtime init apply should succeed")
    _assert((local_home / "config.toml").exists(), "local runtime init should write config")
    _assert((local_home / ".env").exists(), "local runtime init should write env")
    _assert(
        "MEMORY_SERVICE_TOKEN" not in json.dumps(local_init_applied, sort_keys=True),
        "local runtime init response must not expose token names",
    )

    local_start_dry_run = await _with_session(
        repo_root=repo_root,
        env=local_env,
        callback=lambda session: _call(
            session,
            "memory_local_runtime_start",
            {"profile": "lite", "apply": False},
        ),
    )
    _assert(
        local_start_dry_run["data"]["status"] == "start_planned",
        "local runtime start dry-run should only plan",
    )

    local_start_blocked = await _with_session(
        repo_root=repo_root,
        env=local_env,
        callback=lambda session: _call_error(
            session,
            "memory_local_runtime_start",
            {"profile": "lite", "apply": True},
        ),
    )
    _assert(
        local_start_blocked["error"]["code"]
        == "memo_stack_mcp.local_runtime.start_disabled",
        "local runtime start should require the start env gate",
    )

    prepare_env = {
        "MEMORY_MCP_API_URL": "http://127.0.0.1:9",
        "MEMORY_MCP_LOCAL_RUNTIME_ENABLED": "true",
        "MEMORY_MCP_LOCAL_RUNTIME_START_ENABLED": "false",
        "MEMORY_MCP_LOCAL_RUNTIME_HOME": str(prepare_home),
        "MEMORY_MCP_LOCAL_RUNTIME_REPO_DIR": str(repo_root),
        "MEMORY_MCP_OBSIDIAN_ENABLED": "true",
        "MEMORY_MCP_OBSIDIAN_SYNC_ENABLED": "false",
        "MEMORY_MCP_OBSIDIAN_VAULT": str(prepare_vault),
        "MEMORY_MCP_OBSIDIAN_ROOT_FOLDER": "Memo Stack",
        "MEMORY_MCP_OBSIDIAN_LAYOUT": "v2",
        "MEMORY_MCP_DEFAULT_SPACE_SLUG": "prepare-smoke",
        "MEMORY_MCP_DEFAULT_PROFILE_EXTERNAL_REF": "default",
    }
    prepare_dry_run = await _with_session(
        repo_root=repo_root,
        env=prepare_env,
        callback=lambda session: _call(session, "memory_obsidian_prepare", {"apply": False}),
    )
    prepare_facts = (
        prepare_vault
        / "Memo Stack/spaces/prepare-smoke/profiles/default/generated/facts"
    )
    _assert(prepare_dry_run["ok"] is True, "prepare dry-run should succeed")
    _assert(
        prepare_dry_run["data"]["status"] == "prepare_planned",
        "prepare dry-run should be planned",
    )
    _assert(not (prepare_home / "config.toml").exists(), "prepare dry-run must not write config")
    _assert(not prepare_facts.exists(), "prepare dry-run must not write vault folders")

    prepare_applied = await _with_session(
        repo_root=repo_root,
        env=prepare_env,
        callback=lambda session: _call(session, "memory_obsidian_prepare", {"apply": True}),
    )
    _assert(prepare_applied["ok"] is True, "prepare apply should succeed")
    _assert(
        prepare_applied["data"]["status"] == "prepared_backend_not_ready",
        "prepare apply should stop before preview when backend is not ready",
    )
    _assert((prepare_home / "config.toml").exists(), "prepare apply should write config")
    _assert(prepare_facts.exists(), "prepare apply should write V2 facts dir")
    _assert(
        (prepare_vault / ".obsidian/plugins/memo-stack/main.js").exists(),
        "prepare apply should install plugin bundle",
    )
    _assert(
        "local_runtime_started" not in prepare_applied["diagnostics"]["side_effects"],
        "prepare apply must not start local runtime",
    )
    _assert(
        "obsidian_sync" not in prepare_applied["diagnostics"]["side_effects"],
        "prepare apply must not run mutating sync",
    )

    common_env = {
        "MEMORY_MCP_OBSIDIAN_ENABLED": "true",
        "MEMORY_MCP_OBSIDIAN_SYNC_ENABLED": "false",
        "MEMORY_MCP_OBSIDIAN_VAULT": str(vault),
        "MEMORY_MCP_OBSIDIAN_ROOT_FOLDER": "Memo Stack",
        "MEMORY_MCP_OBSIDIAN_LAYOUT": "v2",
        "MEMORY_MCP_DEFAULT_SPACE_SLUG": "mcp-smoke",
        "MEMORY_MCP_DEFAULT_PROFILE_EXTERNAL_REF": "default",
    }
    dry_run = await _with_session(
        repo_root=repo_root,
        env=common_env,
        callback=lambda session: _call(
            session,
            "memory_obsidian_setup",
            {"apply": False, "install_plugin": True, "enable_plugin": True},
        ),
    )
    expected_facts = vault / "Memo Stack/spaces/mcp-smoke/profiles/default/generated/facts"
    _assert(dry_run["ok"] is True, "dry-run setup should succeed")
    _assert(dry_run["data"]["dry_run"] is True, "dry-run setup should remain dry")
    _assert(dry_run["data"]["would_install_plugin"] is True, "dry-run should plan plugin install")
    _assert(not expected_facts.exists(), "dry-run setup must not write scoped folders")

    applied = await _with_session(
        repo_root=repo_root,
        env=common_env,
        callback=lambda session: _call(
            session,
            "memory_obsidian_setup",
            {"apply": True, "install_plugin": True, "enable_plugin": True},
        ),
    )
    _assert(applied["ok"] is True, "applied setup should succeed")
    _assert(applied["data"]["plugin_installed"] is True, "plugin should be installed")
    _assert(applied["data"]["plugin_enabled"] is True, "plugin should be enabled")
    _assert(expected_facts.exists(), "applied setup should write V2 facts dir")
    _assert((vault / "Memo Stack/README.md").exists(), "applied setup should write README")
    _assert(
        (vault / ".obsidian/plugins/memo-stack/main.js").exists(),
        "applied setup should install plugin bundle",
    )
    plugin_settings = json.loads(
        (vault / ".obsidian/plugins/memo-stack/data.json").read_text(encoding="utf-8")
    )
    _assert(plugin_settings["localCliPath"] == "memo-stack", "plugin settings need local CLI")

    status = await _with_session(
        repo_root=repo_root,
        env=common_env,
        callback=lambda session: _call(session, "memory_obsidian_status", {}),
    )
    _assert(status["ok"] is True, "enabled status should return ok")
    _assert(status["data"]["status"] in {"ready", "needs_attention"}, "status should be computed")

    sync_disabled = await _with_session(
        repo_root=repo_root,
        env=common_env,
        callback=lambda session: _call_error(
            session,
            "memory_obsidian_sync",
            {"apply": True, "apply_import": True},
        ),
    )
    _assert(
        sync_disabled["error"]["code"] == "memo_stack_mcp.obsidian.sync_disabled",
        "mutating sync should require the sync env gate",
    )

    return {
        "ok": True,
        "vault": str(vault),
        "disabled_status": disabled["data"]["status"],
        "setup_status": applied["data"]["status"],
        "status_after_setup": status["data"]["status"],
        "sync_disabled_code": sync_disabled["error"]["code"],
        "local_runtime_init_status": local_init_applied["data"]["status"],
        "local_runtime_start_disabled_code": local_start_blocked["error"]["code"],
        "prepare_status": prepare_applied["data"]["status"],
        "facts_dir": str(expected_facts),
    }


async def _with_session(
    *,
    repo_root: Path,
    env: dict[str, str],
    callback,
) -> dict[str, Any]:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "memo_stack_mcp"],
        env=_python_env(repo_root, env),
        cwd=str(repo_root),
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        tool_names = {tool.name for tool in tools.tools}
        expected = {
            "memory_local_runtime_status",
            "memory_local_runtime_init",
            "memory_local_runtime_doctor",
            "memory_local_runtime_start",
            "memory_obsidian_prepare",
            "memory_obsidian_status",
            "memory_obsidian_setup",
            "memory_obsidian_preview",
            "memory_obsidian_sync",
        }
        missing = expected - tool_names
        _assert(not missing, f"missing MCP Obsidian tools: {sorted(missing)}")
        return await callback(session)


async def _call(
    session: ClientSession,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    result = await session.call_tool(name, arguments)
    _assert(result.isError is False, f"{name} returned MCP error")
    return _structured(result)


async def _call_error(
    session: ClientSession,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    result = await session.call_tool(name, arguments)
    _assert(result.isError is True, f"{name} should return MCP error")
    return _structured(result)


def _structured(result: Any) -> dict[str, Any]:
    if result.structuredContent is not None:
        return dict(result.structuredContent)
    return json.loads(result.content[0].text)


def _python_env(repo_root: Path, extra: dict[str, str]) -> dict[str, str]:
    package_paths = [
        "packages/memo_stack_core",
        "packages/memo_stack_adapters",
        "packages/memo_stack_server",
        "packages/memo_stack_sdk",
        "packages/memo_stack_cli",
        "packages/memo_stack_obsidian",
        "packages/memo_stack_mcp",
    ]
    return {
        **os.environ,
        **extra,
        "MEMORY_MCP_TRANSPORT": "stdio",
        "PYTHONPATH": os.pathsep.join(str(repo_root / path) for path in package_paths),
    }


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    raise SystemExit(main())
