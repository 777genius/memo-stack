"""Run a clean full-provider Memory Platform smoke test.

The script starts a fresh Docker Compose project with isolated Postgres,
Qdrant and Neo4j volumes, runs migrations and seed data, starts the local
FastAPI server, then verifies canonical facts, Graphiti projection, Qdrant
chunk recall, update and delete behavior. By default it also starts a real
stdio MCP client against the same isolated server and verifies the MCP path
over Graphiti, Qdrant and OpenAI embeddings.

Secrets are read from the process environment only. Nothing is written to .env.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TextIO

import httpx
from neo4j import GraphDatabase

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
SENSITIVE_ENV_KEYS = (
    "MEMORY_MCP_AUTH_TOKEN",
    "MEMORY_SERVICE_TOKEN",
    "MEMORY_OPENAI_API_KEY",
    "OPENAI_API_KEY",
    "MEMORY_CLEAN_SMOKE_TOKEN",
    "MEMORY_DATABASE_URL",
    "MEMORY_GRAPHITI_NEO4J_PASSWORD",
)
SENSITIVE_KEY_SUFFIXES = (
    "_TOKEN",
    "_KEY",
    "_SECRET",
    "_PASSWORD",
    "_CREDENTIAL",
    "_DATABASE_URL",
    "_DB_URL",
    "_DSN",
)
SENSITIVE_HEADER_KEYS = {
    "authorization",
    "idempotency-key",
}
SENSITIVE_KEY_NAMES = {
    "api_key",
    "apikey",
    "auth",
    "auth_token",
    "authorization",
    "credential",
    "credentials",
    "connection_string",
    "database_url",
    "db_url",
    "dsn",
    "idempotency_key",
    "idempotency-key",
    "passwd",
    "password",
    "secret",
    "token",
}
SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"Authorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{12,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{12,}\b"),
    re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password|passwd|credential)\s*[:=]\s*['\"]?"
        r"[A-Za-z0-9_./+=-]{8,}"
    ),
)
SAFE_MCP_INHERITED_ENV_KEYS = (
    "HOME",
    "LANG",
    "LC_ALL",
    "PATH",
    "PYTHONPATH",
    "REQUESTS_CA_BUNDLE",
    "SSL_CERT_FILE",
    "VIRTUAL_ENV",
)
DEFAULT_MCP_HTTP_TIMEOUT_SECONDS = "90"
DEFAULT_MCP_TOOL_TIMEOUT_SECONDS = 180.0


class CleanSmokeFailure(RuntimeError):
    """Raised when the full-provider smoke violates an expected invariant."""


class ServerHandle:
    def __init__(self, *, process: subprocess.Popen[str], output: TextIO) -> None:
        self.process = process
        self.output = output


def main() -> int:
    started = time.perf_counter()
    run_id = str(time.time_ns())
    project_name = os.getenv("MEMORY_CLEAN_SMOKE_PROJECT", f"memory-clean-{run_id[-8:]}")
    token = os.getenv("MEMORY_CLEAN_SMOKE_TOKEN", "clean-smoke-token")
    os.environ.setdefault("MEMORY_CLEAN_SMOKE_TOKEN", token)
    ports = _ports()
    compose_env = _compose_env(ports)
    server_env: dict[str, str] | None = None
    keep_stack = _bool(os.getenv("MEMORY_CLEAN_SMOKE_KEEP_STACK", "false"))
    skip_mcp = _bool(os.getenv("MEMORY_CLEAN_SMOKE_SKIP_MCP", "false"))
    server: ServerHandle | None = None

    try:
        server_env = _server_env(ports=ports, token=token, run_id=run_id)
        _compose(project_name, compose_env, "down", "-v", "--remove-orphans", check=False)
        _compose(
            project_name,
            compose_env,
            "--profile",
            "full",
            "up",
            "-d",
            "memory_postgres",
            "memory_qdrant",
            "memory_neo4j",
        )
        _wait_for_postgres(project_name, compose_env)
        _wait_for_http(f"http://127.0.0.1:{ports['qdrant']}/")
        _wait_for_neo4j(ports["neo4j_bolt"])

        _run_python(server_env, "-m", "memory_server.db", "upgrade")
        _run_python(server_env, "-m", "memory_server.admin", "seed-defaults")

        server = _start_server(server_env)
        base_url = f"http://127.0.0.1:{ports['server']}"
        _wait_for_http(f"{base_url}/v1/health", token=token)

        result = _run_lifecycle(base_url=base_url, token=token, env=server_env, run_id=run_id)
        if skip_mcp:
            result["mcp"] = {"skipped": True, "reason": "MEMORY_CLEAN_SMOKE_SKIP_MCP=true"}
        else:
            mcp_result = asyncio.run(
                _run_mcp_lifecycle(
                    base_url=base_url,
                    token=token,
                    env=server_env,
                    run_id=run_id,
                )
            )
            result["mcp"] = mcp_result
            result["checks"].update(mcp_result["checks"])
        result["project"] = project_name
        result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        print(
            json.dumps(
                _redact_payload(result, env=server_env),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        details: dict[str, Any] = {
            "ok": False,
            "error": exc.__class__.__name__,
            "message": _redact_text(str(exc), env=server_env),
            "project": project_name,
        }
        if server is not None:
            details["server_output_tail"] = _redact_text(_stop_server(server), env=server_env)
            server = None
        print(
            json.dumps(
                _redact_payload(details, env=server_env),
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    finally:
        if server is not None:
            _stop_server(server)
        if not keep_stack:
            _compose(project_name, compose_env, "down", "-v", "--remove-orphans", check=False)


def _ports() -> dict[str, int]:
    return {
        "postgres": _free_port(),
        "qdrant": _free_port(),
        "neo4j_http": _free_port(),
        "neo4j_bolt": _free_port(),
        "server": _free_port(),
    }


def _compose_env(ports: Mapping[str, int]) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "MEMORY_POSTGRES_PORT": str(ports["postgres"]),
            "MEMORY_QDRANT_PORT": str(ports["qdrant"]),
            "MEMORY_NEO4J_HTTP_PORT": str(ports["neo4j_http"]),
            "MEMORY_NEO4J_BOLT_PORT": str(ports["neo4j_bolt"]),
            "MEMORY_SERVER_PORT": str(ports["server"]),
        }
    )
    return env


def _server_env(*, ports: Mapping[str, int], token: str, run_id: str) -> dict[str, str]:
    openai_key = os.getenv("MEMORY_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not openai_key:
        raise CleanSmokeFailure("Set a Memory Platform OpenAI API key in the environment")

    env = os.environ.copy()
    env.update(
        {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY") or openai_key,
            "MEMORY_OPENAI_API_KEY": openai_key,
            "MEMORY_DEPLOY_PROFILE": "local",
            "MEMORY_DATABASE_URL": (
                f"postgresql+asyncpg://memory:memory@127.0.0.1:{ports['postgres']}/memory"
            ),
            "MEMORY_AUTO_CREATE_SCHEMA": "true",
            "MEMORY_HOST": "127.0.0.1",
            "MEMORY_PORT": str(ports["server"]),
            "MEMORY_SERVICE_TOKEN": token,
            "MEMORY_POLICY_MODE": "active_context",
            "MEMORY_QDRANT_ENABLED": "true",
            "MEMORY_QDRANT_URL": f"http://127.0.0.1:{ports['qdrant']}",
            "MEMORY_QDRANT_COLLECTION": f"memory_clean_smoke_{run_id}",
            "MEMORY_EMBEDDINGS_ENABLED": "true",
            "MEMORY_EMBEDDINGS_PROVIDER": "openai",
            "MEMORY_EMBEDDINGS_MODEL": os.getenv(
                "MEMORY_EMBEDDINGS_MODEL",
                "text-embedding-3-small",
            ),
            "MEMORY_EMBEDDINGS_DIMENSIONS": os.getenv("MEMORY_EMBEDDINGS_DIMENSIONS", "1536"),
            "MEMORY_GRAPHITI_ENABLED": "true",
            "MEMORY_GRAPHITI_NEO4J_URI": f"bolt://127.0.0.1:{ports['neo4j_bolt']}",
            "MEMORY_GRAPHITI_NEO4J_USER": "neo4j",
            "MEMORY_GRAPHITI_NEO4J_PASSWORD": "memorygraph",
            "MEMORY_GRAPHITI_BUILD_INDICES": "true",
            "MEMORY_PROVIDER_CIRCUIT_FAILURE_THRESHOLD": "2",
            "MEMORY_PROVIDER_CIRCUIT_RESET_AFTER_SECONDS": "30",
            "MEMORY_LEGACY_CLIENT_ENABLED": "false",
        }
    )
    return env


def _run_lifecycle(
    *,
    base_url: str,
    token: str,
    env: Mapping[str, str],
    run_id: str,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    marker = f"CLEAN_FULL_{run_id}"
    space_slug = "clean-full-smoke"
    profile_ref = "default"
    old_text = f"{marker}: Graphiti should project the initial canonical fact."
    new_text = f"{marker}: Graphiti and Qdrant should recall updated memory."
    doc_text = (
        f"{marker}: Qdrant vector recall should retrieve this document chunk. "
        "The architecture keeps Postgres canonical and providers derived."
    )

    fact = _request(
        base_url,
        headers,
        "POST",
        "/v1/facts",
        expected=201,
        json={
            "space_slug": space_slug,
            "profile_external_ref": profile_ref,
            "text": old_text,
            "kind": "architecture_decision",
            "classification": "internal",
            "source_refs": [{"source_type": "clean_smoke", "source_id": f"{marker}:fact"}],
        },
    )
    _worker_once(env)
    initial_context = _context(base_url, headers, space_slug, profile_ref, marker)
    initial_graph = _graph_episode(env, fact["id"])

    updated = _request(
        base_url,
        headers,
        "PATCH",
        f"/v1/facts/{fact['id']}",
        expected=200,
        json={
            "expected_version": fact["version"],
            "text": new_text,
            "reason": "clean full smoke update",
            "source_refs": [{"source_type": "clean_smoke", "source_id": f"{marker}:update"}],
        },
    )
    _worker_once(env)
    updated_context = _context(base_url, headers, space_slug, profile_ref, marker)
    updated_graph = _graph_episode(env, fact["id"])

    document = _request(
        base_url,
        headers,
        "POST",
        "/v1/documents",
        expected=201,
        json={
            "space_slug": space_slug,
            "profile_external_ref": profile_ref,
            "title": f"{marker} document",
            "text": doc_text,
            "source_type": "clean_smoke",
            "source_external_id": f"{marker}:document",
            "classification": "internal",
        },
    )
    _worker_once(env)
    doc_context = _context(
        base_url,
        headers,
        space_slug,
        profile_ref,
        "Qdrant vector recall Postgres canonical providers derived",
    )

    forgotten = _request(
        base_url,
        headers,
        "DELETE",
        f"/v1/facts/{fact['id']}",
        expected=200,
    )
    _worker_once(env)
    forgotten_context = _context(base_url, headers, space_slug, profile_ref, marker)
    forgotten_graph = _graph_episode(env, fact["id"])
    metrics = _request(base_url, headers, "GET", "/v1/diagnostics/metrics", expected=200)
    outbox = _request(base_url, headers, "GET", "/v1/diagnostics/outbox", expected=200)

    checks = {
        "initial_context_has_old_fact": old_text in initial_context["rendered_text"],
        "initial_graph_has_episode": initial_graph["count"] == 1,
        "initial_context_graph_hydrated": _context_diagnostic_int(
            initial_context,
            "graph_hydrated_count",
        )
        >= 1,
        "updated_context_has_new_fact": new_text in updated_context["rendered_text"],
        "updated_context_hides_old_fact": old_text not in updated_context["rendered_text"],
        "updated_graph_replaced_episode": updated_graph["count"] == 1
        and new_text in " ".join(updated_graph["contents"]),
        "updated_context_graph_hydrated": _context_diagnostic_int(
            updated_context,
            "graph_hydrated_count",
        )
        >= 1,
        "document_context_has_chunk": doc_text in doc_context["rendered_text"],
        "document_context_has_chunk_item": any(
            str(item.get("item_id", "")).startswith("chunk_") for item in doc_context["items"]
        ),
        "document_context_vector_hydrated": _context_diagnostic_int(
            doc_context,
            "vector_hydrated_count",
        )
        >= 1,
        "forgotten_fact_deleted": forgotten["status"] == "deleted",
        "forgotten_context_hides_new_fact": new_text not in forgotten_context["rendered_text"],
        "forgotten_graph_removed_episode": forgotten_graph["count"] == 0,
        "outbox_has_no_pending_or_dead": outbox["counts"].get("dead", 0) == 0
        and set(outbox["counts"]) <= {"done"},
        "providers_are_healthy": all(
            metrics["adapters"][name]["status"] == "ok"
            for name in ("qdrant", "graphiti", "embeddings")
        ),
        "context_provider_status_ok": doc_context["diagnostics"].get("vector_status") == "ok"
        and doc_context["diagnostics"].get("graph_status") == "ok",
    }
    if not all(checks.values()):
        raise CleanSmokeFailure(f"Clean full smoke checks failed: {checks}")

    return {
        "ok": True,
        "marker": marker,
        "fact_id": fact["id"],
        "updated_version": updated["version"],
        "document_id": document["id"],
        "checks": checks,
        "outbox_counts": outbox["counts"],
        "adapters": {
            name: metrics["adapters"][name]["status"]
            for name in ("qdrant", "graphiti", "embeddings", "cognee")
        },
        "context_diagnostics": doc_context["diagnostics"],
    }


async def _run_mcp_lifecycle(
    *,
    base_url: str,
    token: str,
    env: Mapping[str, str],
    run_id: str,
) -> dict[str, Any]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    headers = {"Authorization": f"Bearer {token}"}
    marker = f"CLEAN_FULL_MCP_{run_id}"
    space_slug = "clean-full-smoke"
    profile_ref = "default"
    old_text = f"{marker}: MCP should persist canonical facts before provider projections."
    new_text = f"{marker}: MCP should expose updated canonical facts after provider projections."
    doc_text = (
        f"{marker}: MCP Qdrant vector recall should retrieve this document chunk. "
        "Real-stack canary proves Graphiti, Qdrant and embeddings are wired."
    )
    mcp_env = _mcp_process_env(
        base_url=base_url,
        token=token,
        space_slug=space_slug,
        profile_ref=profile_ref,
    )
    params = StdioServerParameters(command=PYTHON, args=["-m", "memory_mcp"], env=mcp_env)

    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await _await_mcp(session.initialize(), "memory_mcp.initialize", env=mcp_env)
        tools = await _await_mcp(session.list_tools(), "memory_mcp.list_tools", env=mcp_env)
        tool_names = {tool.name for tool in tools.tools}
        required_tools = {
            "memory_status",
            "memory_search",
            "memory_remember_fact",
            "memory_update_fact",
            "memory_ingest_document",
            "memory_forget_fact",
        }
        if not required_tools.issubset(tool_names):
            raise CleanSmokeFailure(
                f"MCP clean full smoke missing tools: {sorted(required_tools - tool_names)}"
            )

        status_result = await _call_mcp_result(session, "memory_status", {}, env=mcp_env)
        _structured_mcp(status_result, "memory_status", env=mcp_env)
        remembered_result = await _call_mcp_result(
            session,
            "memory_remember_fact",
            {
                "text": old_text,
                "kind": "architecture_decision",
                "source_type": "manual",
                "source_id": f"{marker}:remember",
                "classification": "internal",
                "idempotency_key": f"{marker}:remember",
            },
            env=mcp_env,
        )
        remembered = _structured_mcp(remembered_result, "memory_remember_fact", env=mcp_env)
        fact = remembered["data"]
        fact_id = str(fact["id"])
        _worker_once(env)
        search_old_result = await _call_mcp_result(
            session,
            "memory_search",
            {"query": marker, "max_facts": 10, "max_chunks": 0},
            env=mcp_env,
        )
        search_old = _structured_mcp(search_old_result, "memory_search old", env=mcp_env)
        initial_graph = _graph_episode(env, fact_id)

        updated_result = await _call_mcp_result(
            session,
            "memory_update_fact",
            {
                "fact_id": fact_id,
                "expected_version": fact["version"],
                "text": new_text,
                "reason": "clean full MCP smoke update",
                "source_type": "manual",
                "source_id": f"{marker}:update",
            },
            env=mcp_env,
        )
        updated = _structured_mcp(updated_result, "memory_update_fact", env=mcp_env)
        _worker_once(env)
        search_new_result = await _call_mcp_result(
            session,
            "memory_search",
            {"query": marker, "max_facts": 10, "max_chunks": 0},
            env=mcp_env,
        )
        search_new = _structured_mcp(search_new_result, "memory_search updated", env=mcp_env)
        updated_graph = _graph_episode(env, fact_id)

        ingested_result = await _call_mcp_result(
            session,
            "memory_ingest_document",
            {
                "title": f"{marker} MCP real-stack document",
                "text": doc_text,
                "source_type": "document",
                "source_external_id": f"{marker}:document",
                "classification": "internal",
                "idempotency_key": f"{marker}:document",
            },
            env=mcp_env,
        )
        ingested = _structured_mcp(ingested_result, "memory_ingest_document", env=mcp_env)
        _worker_once(env)
        search_doc_result = await _call_mcp_result(
            session,
            "memory_search",
            {
                "query": "MCP Qdrant vector recall Graphiti embeddings wired",
                "max_facts": 0,
                "max_chunks": 10,
            },
            env=mcp_env,
        )
        search_doc = _structured_mcp(search_doc_result, "memory_search document", env=mcp_env)

        forgotten_result = await _call_mcp_result(
            session,
            "memory_forget_fact",
            {"fact_id": fact_id},
            env=mcp_env,
        )
        forgotten = _structured_mcp(forgotten_result, "memory_forget_fact", env=mcp_env)
        _worker_once(env)
        search_deleted_result = await _call_mcp_result(
            session,
            "memory_search",
            {"query": marker, "max_facts": 10, "max_chunks": 10},
            env=mcp_env,
        )
        search_deleted = _structured_mcp(
            search_deleted_result,
            "memory_search deleted",
            env=mcp_env,
        )
        forgotten_graph = _graph_episode(env, fact_id)
        final_status_result = await _call_mcp_result(session, "memory_status", {}, env=mcp_env)
        final_status = _structured_mcp(
            final_status_result,
            "memory_status final",
            env=mcp_env,
        )

    metrics = _request(base_url, headers, "GET", "/v1/diagnostics/metrics", expected=200)
    outbox = _request(base_url, headers, "GET", "/v1/diagnostics/outbox", expected=200)
    providers_ok = all(
        metrics["adapters"][name]["status"] == "ok"
        for name in ("qdrant", "graphiti", "embeddings")
    )
    status_adapters = final_status["data"]["capabilities"].get("adapters", {})
    status_providers_ok = all(
        status_adapters.get(name, {}).get("enabled") is True
        and status_adapters.get(name, {}).get("healthy") is True
        for name in ("qdrant", "graphiti", "embeddings")
    )
    search_doc_dump = _dump(search_doc)
    search_new_dump = _dump(search_new)
    search_deleted_dump = _dump(search_deleted)
    checks = {
        "mcp_status_projection_ready": bool(final_status["data"]["readiness"].get("read_ready"))
        and _required_mcp_adapters_ready(final_status, ("qdrant", "graphiti", "embeddings")),
        "mcp_search_has_graphiti_fact_after_worker": old_text in _dump(search_old)
        and initial_graph["count"] == 1
        and _search_diagnostic_status(search_old, "graph_status") == "ok"
        and _search_diagnostic_int(search_old, "graph_hydrated_count") >= 1,
        "mcp_search_has_qdrant_document_chunk_after_worker": marker in search_doc_dump
        and _search_has_chunk_item(search_doc)
        and ingested["data"].get("chunks", 0) >= 1
        and _search_diagnostic_status(search_doc, "vector_status") == "ok"
        and _search_diagnostic_int(search_doc, "vector_hydrated_count") >= 1,
        "mcp_search_hides_old_fact_after_update": new_text in search_new_dump
        and old_text not in search_new_dump
        and updated["data"]["version"] == 2
        and updated_graph["count"] == 1
        and new_text in " ".join(updated_graph["contents"])
        and _search_diagnostic_status(search_new, "graph_status") == "ok"
        and _search_diagnostic_int(search_new, "graph_hydrated_count") >= 1,
        "mcp_search_hides_deleted_fact": new_text not in search_deleted_dump
        and forgotten["data"]["status"] == "deleted"
        and forgotten_graph["count"] == 0,
        "mcp_text_fallback_does_not_leak_token": _mcp_text_has_no_secrets(
            status_result,
            remembered_result,
            search_old_result,
            updated_result,
            search_new_result,
            ingested_result,
            search_doc_result,
            forgotten_result,
            search_deleted_result,
            final_status_result,
            env=mcp_env,
        ),
        "mcp_outbox_has_no_pending_or_dead": outbox["counts"].get("dead", 0) == 0
        and set(outbox["counts"]) <= {"done"},
        "mcp_provider_diagnostics_ok": providers_ok
        and status_providers_ok
        and _required_mcp_adapters_ready(final_status, ("qdrant", "graphiti", "embeddings")),
    }
    if not all(checks.values()):
        raise CleanSmokeFailure(f"MCP clean full smoke checks failed: {checks}")

    return {
        "ok": True,
        "marker": marker,
        "fact_id": fact_id,
        "document_chunks": ingested["data"].get("chunks"),
        "checks": checks,
        "outbox_counts": outbox["counts"],
        "adapters": {
            name: metrics["adapters"][name]["status"]
            for name in ("qdrant", "graphiti", "embeddings")
        },
    }


def _request(
    base_url: str,
    headers: Mapping[str, str],
    method: str,
    path: str,
    *,
    expected: int,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with httpx.Client(base_url=base_url, headers=headers, timeout=90) as client:
        response = client.request(method, path, json=json)
    if response.status_code != expected:
        raise CleanSmokeFailure(
            f"{method} {path} expected {expected}, got {response.status_code}: {response.text}"
        )
    payload = response.json()
    data = payload.get("data")
    if not isinstance(data, dict):
        raise CleanSmokeFailure(f"{method} {path} returned non-object data")
    return data


def _context(
    base_url: str,
    headers: Mapping[str, str],
    space_slug: str,
    profile_ref: str,
    query: str,
) -> dict[str, Any]:
    return _request(
        base_url,
        headers,
        "POST",
        "/v1/context",
        expected=200,
        json={
            "space_slug": space_slug,
            "profile_external_ref": profile_ref,
            "query": query,
            "max_facts": 10,
            "max_chunks": 10,
            "token_budget": 1600,
        },
    )


def _context_diagnostic_int(context: Mapping[str, Any], key: str) -> int:
    diagnostics = context.get("diagnostics", {})
    if not isinstance(diagnostics, Mapping):
        return 0
    value = diagnostics.get(key)
    return value if isinstance(value, int) else 0


async def _call_mcp_result(
    session: Any,
    name: str,
    arguments: dict[str, Any],
    *,
    env: Mapping[str, str],
) -> Any:
    result = await _await_mcp(session.call_tool(name, arguments), name, env=env)
    if result.isError:
        raise CleanSmokeFailure(
            f"{name} returned MCP error: {_redact_text(str(result), env=env)}"
        )
    return result


async def _await_mcp(awaitable: Any, operation: str, *, env: Mapping[str, str]) -> Any:
    timeout = _mcp_tool_timeout_seconds()
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout)
    except TimeoutError as exc:
        raise CleanSmokeFailure(
            f"{operation} timed out after {timeout:g}s"
        ) from exc


def _structured_mcp(
    result: Any,
    operation: str,
    *,
    env: Mapping[str, str],
) -> dict[str, Any]:
    if result.structuredContent is not None:
        payload = result.structuredContent
    else:
        payload = json.loads(result.content[0].text)
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise CleanSmokeFailure(f"{operation} failed: {_redact_text(str(payload), env=env)}")
    return payload


def _mcp_text_has_no_secrets(*results: Any, env: Mapping[str, str]) -> bool:
    for result in results:
        for item in getattr(result, "content", []) or []:
            text = str(getattr(item, "text", "") or "")
            if _redact_text(text, env=env) != text:
                return False
    return True


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _search_has_chunk_item(search: Mapping[str, Any]) -> bool:
    data = search.get("data", {})
    if not isinstance(data, Mapping):
        return False
    items = data.get("items", [])
    if not isinstance(items, list):
        return False
    for item in items:
        if not isinstance(item, Mapping):
            continue
        if item.get("item_type") == "chunk" or str(item.get("item_id") or "").startswith("chunk_"):
            return True
        source_refs = item.get("source_refs", [])
        if isinstance(source_refs, list) and any(
            isinstance(ref, Mapping) and bool(ref.get("chunk_id")) for ref in source_refs
        ):
            return True
    return False


def _search_diagnostic_status(search: Mapping[str, Any], key: str) -> str:
    data = search.get("data", {})
    if not isinstance(data, Mapping):
        return ""
    diagnostics = data.get("diagnostics", {})
    if not isinstance(diagnostics, Mapping):
        return ""
    return str(diagnostics.get(key) or "")


def _search_diagnostic_int(search: Mapping[str, Any], key: str) -> int:
    data = search.get("data", {})
    if not isinstance(data, Mapping):
        return 0
    diagnostics = data.get("diagnostics", {})
    if not isinstance(diagnostics, Mapping):
        return 0
    value = diagnostics.get(key)
    return value if isinstance(value, int) else 0


def _required_mcp_adapters_ready(status: Mapping[str, Any], names: tuple[str, ...]) -> bool:
    data = status.get("data", {})
    if not isinstance(data, Mapping):
        return False
    capabilities = data.get("capabilities", {})
    if not isinstance(capabilities, Mapping):
        return False
    adapters = capabilities.get("adapters", {})
    if not isinstance(adapters, Mapping):
        return False
    for name in names:
        adapter = adapters.get(name)
        if not isinstance(adapter, Mapping):
            return False
        if adapter.get("enabled") is not True or adapter.get("healthy") is not True:
            return False
    return True


def _mcp_process_env(
    *,
    base_url: str,
    token: str,
    space_slug: str,
    profile_ref: str,
) -> dict[str, str]:
    env = {
        key: value
        for key in SAFE_MCP_INHERITED_ENV_KEYS
        if (value := os.getenv(key))
    }
    env["PYTHONPATH"] = _repo_pythonpath(env.get("PYTHONPATH"))
    env.update(
        {
            "MEMORY_MCP_API_URL": base_url,
            "MEMORY_MCP_AUTH_TOKEN": token,
            "MEMORY_MCP_DEFAULT_SPACE_SLUG": space_slug,
            "MEMORY_MCP_DEFAULT_PROFILE_EXTERNAL_REF": profile_ref,
            "MEMORY_MCP_AGENT_NAME": "clean-full-mcp-smoke-agent",
            "MEMORY_MCP_TRANSPORT": "stdio",
            "MEMORY_MCP_WRITE_MODE": "direct",
            "MEMORY_MCP_DELETE_MODE": "explicit",
            "MEMORY_MCP_INGEST_MODE": "allowed",
            "MEMORY_MCP_REQUEST_TIMEOUT_SECONDS": os.getenv(
                "MEMORY_MCP_REQUEST_TIMEOUT_SECONDS",
                DEFAULT_MCP_HTTP_TIMEOUT_SECONDS,
            ),
        }
    )
    return env


def _repo_pythonpath(existing: str | None) -> str:
    package_paths = [
        str(PROJECT_ROOT / "packages" / name)
        for name in (
            "memory_adapters",
            "memory_core",
            "memory_mcp",
            "memory_sdk",
            "memory_server",
        )
    ]
    if existing:
        package_paths.append(existing)
    return os.pathsep.join(package_paths)


def _mcp_tool_timeout_seconds() -> float:
    raw = os.getenv(
        "MEMORY_CLEAN_SMOKE_MCP_CALL_TIMEOUT_SECONDS",
        str(DEFAULT_MCP_TOOL_TIMEOUT_SECONDS),
    )
    try:
        timeout = float(raw)
    except ValueError as exc:
        raise CleanSmokeFailure(
            "MEMORY_CLEAN_SMOKE_MCP_CALL_TIMEOUT_SECONDS must be numeric"
        ) from exc
    if timeout <= 0:
        raise CleanSmokeFailure(
            "MEMORY_CLEAN_SMOKE_MCP_CALL_TIMEOUT_SECONDS must be positive"
        )
    return timeout


def _worker_once(env: Mapping[str, str]) -> None:
    _run_python(env, "-m", "memory_server.worker", "--once", "--limit", "20")


def _graph_episode(env: Mapping[str, str], fact_id: str) -> dict[str, Any]:
    driver = GraphDatabase.driver(
        env["MEMORY_GRAPHITI_NEO4J_URI"],
        auth=(env["MEMORY_GRAPHITI_NEO4J_USER"], env["MEMORY_GRAPHITI_NEO4J_PASSWORD"]),
    )
    try:
        records, _, _ = driver.execute_query(
            (
                "MATCH (e:Episodic {name: $name}) "
                "RETURN e.uuid AS uuid, e.content AS content ORDER BY e.created_at"
            ),
            name=f"fact:{fact_id}",
            database_="neo4j",
        )
    finally:
        driver.close()
    return {
        "count": len(records),
        "contents": [str(record.get("content") or "") for record in records],
    }


def _compose(project_name: str, env: Mapping[str, str], *args: str, check: bool = True) -> None:
    completed = subprocess.run(
        ["docker", "compose", "-p", project_name, *args],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=240,
    )
    if check and completed.returncode != 0:
        raise CleanSmokeFailure(
            "docker compose failed: " + completed.stdout[-2000:] + completed.stderr[-2000:]
        )


def _run_python(env: Mapping[str, str], *args: str) -> None:
    completed = subprocess.run(
        [PYTHON, *args],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=240,
    )
    if completed.returncode != 0:
        raise CleanSmokeFailure(
            f"python {' '.join(args)} failed: "
            + completed.stdout[-2000:]
            + completed.stderr[-2000:]
        )


def _start_server(env: Mapping[str, str]) -> ServerHandle:
    output = tempfile.TemporaryFile(mode="w+", encoding="utf-8")  # noqa: SIM115
    try:
        process = subprocess.Popen(
            [PYTHON, "-m", "memory_server.main"],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except Exception:
        output.close()
        raise
    return ServerHandle(process=process, output=output)


def _wait_for_postgres(project_name: str, env: Mapping[str, str]) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        completed = subprocess.run(
            [
                "docker",
                "compose",
                "-p",
                project_name,
                "exec",
                "-T",
                "memory_postgres",
                "pg_isready",
                "-U",
                "memory",
                "-d",
                "memory",
            ],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if completed.returncode == 0:
            return
        time.sleep(1)
    raise CleanSmokeFailure("Postgres did not become ready")


def _wait_for_http(url: str, *, token: str | None = None) -> None:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    deadline = time.monotonic() + 120
    last_error = ""
    while time.monotonic() < deadline:
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(url, headers=headers)
            if response.status_code < 500:
                return
            last_error = response.text[:500]
        except Exception as exc:
            last_error = str(exc)
        time.sleep(1)
    raise CleanSmokeFailure(f"HTTP endpoint did not become ready: {url}: {last_error}")


def _wait_for_neo4j(port: int) -> None:
    deadline = time.monotonic() + 120
    last_error = ""
    while time.monotonic() < deadline:
        driver = GraphDatabase.driver(
            f"bolt://127.0.0.1:{port}",
            auth=("neo4j", "memorygraph"),
        )
        try:
            driver.verify_connectivity()
            return
        except Exception as exc:
            last_error = str(exc)
        finally:
            driver.close()
        time.sleep(1)
    raise CleanSmokeFailure(f"Neo4j did not become ready: {last_error}")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _process_tail(server: ServerHandle) -> str:
    try:
        server.output.flush()
        server.output.seek(0)
        return server.output.read()[-2000:]
    except Exception:
        return ""


def _stop_server(server: ServerHandle) -> str:
    try:
        _terminate_process(server.process)
        return _process_tail(server)
    finally:
        server.output.close()


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}


def _redact_payload(value: Any, *, env: Mapping[str, str] | None = None) -> Any:
    if isinstance(value, str):
        return _redact_text(value, env=env)
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            redacted_key = _redact_key(key, env=env)
            if isinstance(key, str) and _is_sensitive_key_name(key):
                redacted_item: Any = "<redacted>"
            else:
                redacted_item = _redact_payload(item, env=env)
            redacted[_dedupe_key(redacted, redacted_key)] = redacted_item
        return redacted
    if isinstance(value, list):
        return [_redact_payload(item, env=env) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_payload(item, env=env) for item in value)
    return value


def _redact_text(text: str, *, env: Mapping[str, str] | None = None) -> str:
    redacted = text
    for value in _sensitive_values(env):
        redacted = redacted.replace(value, "<redacted>")
    for key in SENSITIVE_ENV_KEYS:
        redacted = redacted.replace(key, "<redacted-env>")
    for pattern in SENSITIVE_TEXT_PATTERNS:
        redacted = pattern.sub("<redacted>", redacted)
    return redacted


def _redact_key(key: Any, *, env: Mapping[str, str] | None = None) -> Any:
    if not isinstance(key, str):
        return key
    if _is_sensitive_key_name(key):
        return "<redacted-key>"
    redacted = _redact_text(key, env=env)
    return "<redacted-key>" if redacted != key else key


def _dedupe_key(mapping: Mapping[Any, Any], key: Any) -> Any:
    if key not in mapping:
        return key
    if not isinstance(key, str):
        return key
    index = 2
    while f"{key}-{index}" in mapping:
        index += 1
    return f"{key}-{index}"


def _is_sensitive_key_name(key: str) -> bool:
    normalized = key.strip()
    lowered = normalized.lower()
    if lowered in SENSITIVE_HEADER_KEYS or lowered in SENSITIVE_KEY_NAMES:
        return True
    upper = normalized.upper()
    return upper in SENSITIVE_ENV_KEYS or upper.endswith(SENSITIVE_KEY_SUFFIXES)


def _sensitive_values(env: Mapping[str, str] | None = None) -> list[str]:
    envs = [os.environ]
    if env is not None:
        envs.append(env)
    values = set()
    for item in envs:
        values.update(
            str(item.get(key) or "").strip()
            for key in SENSITIVE_ENV_KEYS
            if str(item.get(key) or "").strip()
        )
        values.update(
            str(value).strip()
            for key, value in item.items()
            if isinstance(key, str)
            and _is_sensitive_key_name(key)
            and len(str(value).strip()) >= 8
        )
    return sorted(values, key=len, reverse=True)


if __name__ == "__main__":
    raise SystemExit(main())
