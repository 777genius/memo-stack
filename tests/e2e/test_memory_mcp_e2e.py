import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from memory_server_harness import python_env, run_memory_server


def test_memory_mcp_fact_lifecycle_and_document_recall_e2e(tmp_path: Path) -> None:
    with run_memory_server(tmp_path) as server:
        asyncio.run(_run_mcp_lifecycle(server.base_url, server.token))


async def _run_mcp_lifecycle(base_url: str, token: str) -> None:
    marker = f"MCP_E2E_{int(time.time() * 1000)}"
    old_fact = f"{marker}: Memory Platform MCP should keep canonical facts active."
    new_fact = f"{marker}: Memory Platform MCP should keep updated canonical facts active."
    document_text = (
        f"{marker}: The document recall path should retrieve larger project notes. "
        "Graphiti is a graph adapter and Qdrant is a vector adapter."
    )
    env = python_env(
        {
            "MEMORY_MCP_API_URL": base_url,
            "MEMORY_MCP_AUTH_TOKEN": token,
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
            "memory_suggest_fact",
            "memory_list_suggestions",
            "memory_approve_suggestion",
            "memory_reject_suggestion",
            "memory_expire_suggestion",
        }.issubset(tool_names)
        assert "memory_forget_by_query" not in tool_names

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

        suggested_text = f"{marker}: Pending MCP suggestions must stay out of context."
        suggested = await _call(
            session,
            "memory_suggest_fact",
            {
                "candidate_text": suggested_text,
                "kind": "constraint",
                "source_type": "manual",
                "source_id": f"{marker}:suggestion-source",
            },
        )
        assert suggested["ok"] is True
        assert suggested["data"]["status"] == "pending"

        suggestions = await _call(session, "memory_list_suggestions", {"status": "pending"})
        assert suggestions["ok"] is True
        assert suggested_text in _dump(suggestions)

        search_suggested = await _call(
            session,
            "memory_search",
            {"query": suggested_text, "max_facts": 5, "max_chunks": 0},
        )
        assert suggested_text not in _dump(search_suggested)

        approved_suggestion = await _call(
            session,
            "memory_approve_suggestion",
            {
                "suggestion_id": suggested["data"]["id"],
                "reason": "E2E reviewed suggestion",
            },
        )
        assert approved_suggestion["ok"] is True
        assert approved_suggestion["data"]["fact"]["version"] == 1
        search_approved_suggestion = await _call(
            session,
            "memory_search",
            {"query": suggested_text, "max_facts": 5, "max_chunks": 0},
        )
        assert suggested_text in _dump(search_approved_suggestion)

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


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
