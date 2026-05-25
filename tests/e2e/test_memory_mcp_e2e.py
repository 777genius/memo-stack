import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_PATHS = [
    PROJECT_ROOT / "packages" / "memory_core",
    PROJECT_ROOT / "packages" / "memory_server",
    PROJECT_ROOT / "packages" / "memory_adapters",
    PROJECT_ROOT / "packages" / "memory_sdk",
    PROJECT_ROOT / "packages" / "memory_mcp",
]


def test_memory_mcp_fact_lifecycle_and_document_recall_e2e(tmp_path: Path) -> None:
    port = _free_port()
    process = _start_memory_server(tmp_path, port)
    try:
        _wait_for_health(port, process)
        asyncio.run(_run_mcp_lifecycle(port))
    finally:
        _stop_process(process)


async def _run_mcp_lifecycle(port: int) -> None:
    marker = f"MCP_E2E_{int(time.time() * 1000)}"
    old_fact = f"{marker}: Memory Platform MCP should keep canonical facts active."
    new_fact = f"{marker}: Memory Platform MCP should keep updated canonical facts active."
    document_text = (
        f"{marker}: The document recall path should retrieve larger project notes. "
        "Graphiti is a graph adapter and Qdrant is a vector adapter."
    )
    env = _python_env(
        {
            "MEMORY_MCP_API_URL": f"http://127.0.0.1:{port}",
            "MEMORY_MCP_AUTH_TOKEN": "test-token",
            "MEMORY_MCP_DEFAULT_SPACE_SLUG": "mcp-e2e",
            "MEMORY_MCP_DEFAULT_PROFILE_EXTERNAL_REF": "default",
            "MEMORY_MCP_AGENT_NAME": "e2e-agent",
            "MEMORY_MCP_TRANSPORT": "stdio",
        }
    )
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "memory_mcp"],
        env=env,
    )

    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        listed = await session.list_tools()
        tool_names = {tool.name for tool in listed.tools}
        assert {
            "memory_status",
            "memory_search",
            "memory_remember_fact",
            "memory_update_fact",
            "memory_forget_fact",
            "memory_ingest_document",
        }.issubset(tool_names)

        status = await _call(session, "memory_status", {})
        assert status["ok"] is True
        assert status["data"]["default_scope"]["space_slug"] == "mcp-e2e"

        remembered = await _call(
            session,
            "memory_remember_fact",
            {
                "text": old_fact,
                "kind": "architecture_decision",
                "source_type": "manual",
                "source_id": f"{marker}:fact-source",
                "idempotency_key": f"{marker}:remember",
            },
        )
        assert remembered["ok"] is True
        fact = remembered["data"]
        fact_id = fact["id"]
        assert fact["version"] == 1

        search_old = await _call(
            session,
            "memory_search",
            {"query": marker, "max_facts": 5, "max_chunks": 0},
        )
        assert search_old["ok"] is True
        assert old_fact in _dump(search_old)

        updated = await _call(
            session,
            "memory_update_fact",
            {
                "fact_id": fact_id,
                "expected_version": 1,
                "text": new_fact,
                "reason": "E2E lifecycle update",
                "source_type": "manual",
                "source_id": f"{marker}:update-source",
            },
        )
        assert updated["ok"] is True
        assert updated["data"]["version"] == 2

        versions = await _call(session, "memory_list_fact_versions", {"fact_id": fact_id})
        assert versions["ok"] is True
        assert [version["version"] for version in versions["data"]] == [1, 2]

        search_new = await _call(
            session,
            "memory_search",
            {"query": marker, "max_facts": 5, "max_chunks": 0},
        )
        dumped_new = _dump(search_new)
        assert new_fact in dumped_new
        assert old_fact not in dumped_new

        ingested = await _call(
            session,
            "memory_ingest_document",
            {
                "title": f"{marker} architecture note",
                "text": document_text,
                "source_type": "document",
                "source_external_id": f"{marker}:doc",
                "idempotency_key": f"{marker}:doc-key",
            },
        )
        assert ingested["ok"] is True
        assert ingested["data"]["chunks"] >= 1

        search_doc = await _call(
            session,
            "memory_search",
            {
                "query": "Graphiti graph adapter Qdrant vector adapter",
                "max_facts": 0,
                "max_chunks": 5,
            },
        )
        assert search_doc["ok"] is True
        assert marker in _dump(search_doc)

        forgotten = await _call(session, "memory_forget_fact", {"fact_id": fact_id})
        assert forgotten["ok"] is True
        assert forgotten["data"]["status"] == "deleted"

        search_deleted = await _call(
            session,
            "memory_search",
            {"query": marker, "max_facts": 5, "max_chunks": 0},
        )
        assert new_fact not in _dump(search_deleted)


async def _call(
    session: ClientSession,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    result = await session.call_tool(name, arguments)
    assert result.isError is False
    if result.structuredContent is not None:
        return result.structuredContent
    return json.loads(result.content[0].text)


def _start_memory_server(tmp_path: Path, port: int) -> subprocess.Popen[str]:
    env = _python_env(
        {
            "MEMORY_DEPLOY_PROFILE": "test",
            "MEMORY_DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'memory.db'}",
            "MEMORY_AUTO_CREATE_SCHEMA": "true",
            "MEMORY_SERVICE_TOKEN": "test-token",
            "MEMORY_HOST": "127.0.0.1",
            "MEMORY_PORT": str(port),
            "MEMORY_QDRANT_ENABLED": "false",
            "MEMORY_GRAPHITI_ENABLED": "false",
            "MEMORY_EMBEDDINGS_ENABLED": "false",
        }
    )
    return subprocess.Popen(
        [sys.executable, "-m", "memory_server.main"],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _wait_for_health(port: int, process: subprocess.Popen[str]) -> None:
    deadline = time.time() + 20
    url = f"http://127.0.0.1:{port}/v1/health"
    last_error: Exception | None = None
    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise AssertionError(f"memory_server exited early:\n{output}")
        try:
            response = httpx.get(url, timeout=1)
            if response.status_code == 200:
                return
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(0.2)
    raise AssertionError(f"memory_server did not become healthy: {last_error}")


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _python_env(overrides: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    paths = [str(path) for path in PACKAGE_PATHS]
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    env.update(overrides)
    return env


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
