"""Run a clean full-provider Memory Platform smoke test.

The script starts a fresh Docker Compose project with isolated Postgres,
Qdrant and Neo4j volumes, runs migrations and seed data, starts the local
FastAPI server, then verifies canonical facts, Graphiti projection, Qdrant
chunk recall, update and delete behavior.

Secrets are read from the process environment only. Nothing is written to .env.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx
from neo4j import GraphDatabase

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


class CleanSmokeFailure(RuntimeError):
    """Raised when the full-provider smoke violates an expected invariant."""


def main() -> int:
    started = time.perf_counter()
    run_id = str(time.time_ns())
    project_name = os.getenv("MEMORY_CLEAN_SMOKE_PROJECT", f"memory-clean-{run_id[-8:]}")
    token = os.getenv("MEMORY_CLEAN_SMOKE_TOKEN", "clean-smoke-token")
    ports = _ports()
    compose_env = _compose_env(ports)
    server_env = _server_env(ports=ports, token=token, run_id=run_id)
    keep_stack = _bool(os.getenv("MEMORY_CLEAN_SMOKE_KEEP_STACK", "false"))
    server: subprocess.Popen[str] | None = None

    try:
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
        result["project"] = project_name
        result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        details: dict[str, Any] = {
            "ok": False,
            "error": exc.__class__.__name__,
            "message": str(exc),
            "project": project_name,
        }
        if server is not None:
            _stop_process(server)
            details["server_output_tail"] = _process_tail(server)
            server = None
        print(json.dumps(details, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1
    finally:
        if server is not None:
            _stop_process(server)
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
        raise CleanSmokeFailure("Set MEMORY_OPENAI_API_KEY or OPENAI_API_KEY")

    env = os.environ.copy()
    env.update(
        {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY") or openai_key,
            "MEMORY_OPENAI_API_KEY": openai_key,
            "MEMORY_DEPLOY_PROFILE": "local",
            "MEMORY_DATABASE_URL": (
                "postgresql+asyncpg://memory:memory"
                f"@127.0.0.1:{ports['postgres']}/memory"
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
            "MEMORY_LEGACY_HACKINTERVIEW_ENABLED": "false",
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
        "updated_context_has_new_fact": new_text in updated_context["rendered_text"],
        "updated_context_hides_old_fact": old_text not in updated_context["rendered_text"],
        "updated_graph_replaced_episode": updated_graph["count"] == 1
        and new_text in " ".join(updated_graph["contents"]),
        "document_context_has_chunk": doc_text in doc_context["rendered_text"],
        "document_context_has_chunk_item": any(
            str(item.get("item_id", "")).startswith("chunk_") for item in doc_context["items"]
        ),
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
            "docker compose failed: "
            + completed.stdout[-2000:]
            + completed.stderr[-2000:]
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


def _start_server(env: Mapping[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [PYTHON, "-m", "memory_server.main"],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


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


def _process_tail(process: subprocess.Popen[str]) -> str:
    if process.stdout is None:
        return ""
    try:
        return process.stdout.read()[-2000:]
    except Exception:
        return ""


def _stop_process(process: subprocess.Popen[str]) -> None:
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


if __name__ == "__main__":
    raise SystemExit(main())
