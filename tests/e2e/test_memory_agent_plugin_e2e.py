import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from memory_server_harness import run_memory_server

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "memory-agent-plugin"
CURSOR_WORKSPACE_PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "memory-agent-plugin-cursor-workspace"
NO_DEFAULT_THREAD_SENTINEL = "__MEMORY_PLATFORM_NO_DEFAULT_THREAD__"


def test_generated_plugin_package_manifests_reference_existing_artifacts() -> None:
    manifests = [
        PLUGIN_ROOT / ".codex-plugin" / "plugin.json",
        PLUGIN_ROOT / ".claude-plugin" / "plugin.json",
        PLUGIN_ROOT / ".cursor-plugin" / "plugin.json",
    ]
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["name"] == "memory-agent-plugin"
        mcp_path = PLUGIN_ROOT / manifest["mcpServers"]
        assert mcp_path.exists(), f"{manifest_path} references missing {mcp_path}"
        skills_relpath = manifest.get("skills")
        if skills_relpath is not None:
            skills_path = PLUGIN_ROOT / skills_relpath
            assert skills_path.exists(), f"{manifest_path} references missing {skills_path}"
            assert (skills_path / "memory" / "SKILL.md").exists()


def test_generated_plugin_inventory_matches_existing_outputs() -> None:
    assert _generated_outputs(PLUGIN_ROOT) == {
        ".claude-plugin/plugin.json",
        ".codex-plugin/plugin.json",
        ".cursor-plugin/plugin.json",
        ".mcp.json",
        ".opencode/skills/memory/SKILL.md",
        "GENERATED.md",
        "gemini-extension.json",
        "opencode.json",
        "skills/memory/SKILL.md",
    }
    assert _generated_outputs(CURSOR_WORKSPACE_PLUGIN_ROOT) == {
        ".cursor/mcp.json",
        "GENERATED.md",
    }


def test_generated_memory_agent_plugin_mcp_status_e2e(tmp_path: Path) -> None:
    with run_memory_server(tmp_path) as server:
        asyncio.run(
            _run_generated_plugin_status(
                plugin_root=PLUGIN_ROOT,
                config_relpath=".mcp.json",
                base_url=server.base_url,
                token=server.token,
                space_slug="plugin-e2e",
                agent_name="plugin-e2e-agent",
                workspace_root=PLUGIN_ROOT,
                cwd=PLUGIN_ROOT,
            )
        )


def test_generated_package_agent_mcp_surfaces_status_e2e(tmp_path: Path) -> None:
    generated_configs = [
        ("gemini-extension.json", "plugin-gemini-e2e", "plugin-gemini-agent"),
        ("opencode.json", "plugin-opencode-e2e", "plugin-opencode-agent"),
    ]
    with run_memory_server(tmp_path) as server:
        for config_relpath, space_slug, agent_name in generated_configs:
            asyncio.run(
                _run_generated_plugin_status(
                    plugin_root=PLUGIN_ROOT,
                    config_relpath=config_relpath,
                    base_url=server.base_url,
                    token=server.token,
                    space_slug=space_slug,
                    agent_name=agent_name,
                    workspace_root=PLUGIN_ROOT,
                    cwd=PLUGIN_ROOT,
                )
            )


def test_generated_cursor_workspace_plugin_mcp_status_e2e(tmp_path: Path) -> None:
    with run_memory_server(tmp_path) as server:
        asyncio.run(
            _run_generated_plugin_status(
                plugin_root=CURSOR_WORKSPACE_PLUGIN_ROOT,
                config_relpath=".cursor/mcp.json",
                base_url=server.base_url,
                token=server.token,
                space_slug="plugin-cursor-workspace-e2e",
                agent_name="plugin-cursor-workspace-e2e-agent",
                workspace_root=PROJECT_ROOT,
                cwd=PROJECT_ROOT,
            )
        )


def test_memory_agent_plugin_doctors_do_not_echo_token_e2e(tmp_path: Path) -> None:
    with run_memory_server(tmp_path) as server:
        for plugin_root in (PLUGIN_ROOT, CURSOR_WORKSPACE_PLUGIN_ROOT):
            env = os.environ.copy()
            env.update(
                {
                    "MEMORY_MCP_API_URL": server.base_url,
                    "MEMORY_MCP_AUTH_TOKEN": server.token,
                }
            )
            completed = subprocess.run(
                [str(plugin_root / "bin" / "memory-mcp-doctor")],
                cwd=plugin_root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = f"{completed.stdout}\n{completed.stderr}"
            assert "Memory Platform MCP plugin is ready" in output
            assert server.token not in output


def test_memory_agent_plugin_doctors_accept_service_token_fallback_e2e(tmp_path: Path) -> None:
    with run_memory_server(tmp_path) as server:
        for plugin_root in (PLUGIN_ROOT, CURSOR_WORKSPACE_PLUGIN_ROOT):
            env = os.environ.copy()
            env.pop("MEMORY_MCP_AUTH_TOKEN", None)
            env.update(
                {
                    "MEMORY_MCP_API_URL": server.base_url,
                    "MEMORY_SERVICE_TOKEN": server.token,
                }
            )
            completed = subprocess.run(
                [str(plugin_root / "bin" / "memory-mcp-doctor")],
                cwd=plugin_root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = f"{completed.stdout}\n{completed.stderr}"
            assert "Memory Platform MCP plugin is ready" in output
            assert server.token not in output


def test_memory_agent_plugin_doctors_redact_failed_url_diagnostics_e2e() -> None:
    secrets = {
        "doctor-user",
        "doctor-password",
        "port-secret",
        "query-secret",
        "fragment-secret",
        "doctor-secret-token",
    }
    for plugin_root in (PLUGIN_ROOT, CURSOR_WORKSPACE_PLUGIN_ROOT):
        env = os.environ.copy()
        env.update(
            {
                "MEMORY_MCP_API_URL": (
                    "http://doctor-user:doctor-password@127.0.0.1:port-secret"
                    "/memory?api_key=query-secret#fragment-secret"
                ),
                "MEMORY_MCP_AUTH_TOKEN": "doctor-secret-token",
            }
        )
        completed = subprocess.run(
            [str(plugin_root / "bin" / "memory-mcp-doctor")],
            cwd=plugin_root,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = f"{completed.stdout}\n{completed.stderr}"
        assert completed.returncode != 0
        assert "<redacted>" in output
        for secret in secrets:
            assert secret not in output


async def _run_generated_plugin_status(
    *,
    plugin_root: Path,
    config_relpath: str,
    base_url: str,
    token: str,
    space_slug: str,
    agent_name: str,
    workspace_root: Path,
    cwd: Path,
) -> None:
    command_template, args, server_env = _load_generated_mcp_server(
        plugin_root, config_relpath
    )
    command = _resolve_command(command_template, plugin_root, workspace_root)
    assert server_env["MEMORY_MCP_DEFAULT_THREAD_EXTERNAL_REF"] == NO_DEFAULT_THREAD_SENTINEL
    assert _command_exists(command, cwd)
    env = os.environ.copy()
    env.update(server_env)
    env.update(
        {
            "MEMORY_MCP_API_URL": base_url,
            "MEMORY_MCP_AUTH_TOKEN": token,
            "MEMORY_MCP_DEFAULT_SPACE_SLUG": space_slug,
            "MEMORY_MCP_DEFAULT_PROFILE_EXTERNAL_REF": "default",
            "MEMORY_MCP_AGENT_NAME": agent_name,
            "MEMORY_MCP_TRANSPORT": "stdio",
        }
    )
    params = StdioServerParameters(
        command=command,
        args=args,
        env=env,
        cwd=str(cwd),
    )

    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        tool_names = {tool.name for tool in tools.tools}
        assert "memory_status" in tool_names
        assert "memory_search" in tool_names
        result = await session.call_tool("memory_status", {})
        assert result.isError is False
        payload = _structured(result)
        assert payload["ok"] is True
        assert payload["data"]["default_scope"]["space_slug"] == space_slug
        assert payload["data"]["default_scope"]["profile_external_ref"] == "default"
        assert payload["data"]["default_scope"].get("thread_external_ref") is None
        dumped = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        assert token not in dumped
        assert NO_DEFAULT_THREAD_SENTINEL not in dumped


def _load_generated_mcp_server(
    plugin_root: Path, config_relpath: str
) -> tuple[str, list[str], dict[str, str]]:
    path = plugin_root / config_relpath
    assert path.exists(), f"Run plugin-kit-ai generate {plugin_root} first"
    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    if "mcp" in parsed:
        servers = parsed["mcp"]
        env_key = "environment"
    else:
        servers = parsed.get("mcpServers", parsed)
        env_key = "env"

    assert isinstance(servers, dict)
    assert "memory-platform" in servers
    server = servers["memory-platform"]
    assert isinstance(server, dict)
    command_value = server["command"]
    if isinstance(command_value, list):
        assert command_value
        command = str(command_value[0])
        args = [str(arg) for arg in command_value[1:]]
    else:
        command = str(command_value)
        args = [str(arg) for arg in server.get("args", [])]
    server_env = {str(key): str(value) for key, value in server.get(env_key, {}).items()}
    return command, args, server_env


def _resolve_command(command: str, plugin_root: Path, workspace_root: Path) -> str:
    return (
        command.replace("${package.root}", str(plugin_root))
        .replace("${workspaceFolder}", str(workspace_root))
        .replace("${extensionPath}", str(plugin_root))
    )


def _command_exists(command: str, cwd: Path) -> bool:
    command_path = Path(command)
    if command_path.is_absolute():
        return command_path.exists()
    return (cwd / command_path).exists()


def _generated_outputs(plugin_root: Path) -> set[str]:
    generated = plugin_root / "GENERATED.md"
    relpaths: set[str] = set()
    for line in generated.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("- `") or not stripped.endswith("`"):
            continue
        relpath = stripped[3:-1]
        if relpath in {"CLAUDE.md", "AGENTS.md"}:
            continue
        assert (plugin_root / relpath).exists(), f"{generated} lists missing {relpath}"
        relpaths.add(relpath)
    return relpaths


def _structured(result: Any) -> dict[str, Any]:
    if result.structuredContent is not None:
        return result.structuredContent
    return json.loads(result.content[0].text)
