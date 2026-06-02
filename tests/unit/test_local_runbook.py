import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_docker_compose_bootstraps_local_server_before_http() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "pg_isready -U memory -d memory" in compose
    assert "condition: service_healthy" in compose
    assert "python -m memory_server.db upgrade" in compose
    assert "python -m memory_server.admin seed-defaults" in compose
    assert "http://127.0.0.1:7788/v1/health" in compose


def test_makefile_has_one_command_stack_smoke_target() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert ".PHONY: memory-stack-smoke" in makefile
    assert "$(COMPOSE) --profile lite up -d memory_server memory_worker" in makefile
    assert "memory-test-quality: memory-lint memory-test-all memory-eval" in makefile
    assert "$(PYTHON) -m memory_server eval run --suite quality-golden" in makefile
    assert "$(PYTHON) -m pytest tests/e2e" in makefile
    assert "curl -fsS http://127.0.0.1:7788/v1/health" in makefile
    assert "$(MAKE) memory-smoke" in makefile


def test_makefile_has_clean_full_mcp_smoke_target() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert ".PHONY: memory-clean-full-mcp-smoke" in makefile
    assert "memory-clean-full-mcp-smoke:" in makefile
    assert "MEMORY_CLEAN_SMOKE_SKIP_MCP=false" in makefile
    assert "$(PYTHON) scripts/clean_full_smoke.py" in makefile


def test_makefile_has_memory_plugin_gate_target() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert ".PHONY: memory-plugin-test" in makefile
    assert (
        "memory-plugin-test: memory-plugin-check memory-plugin-validate memory-plugin-e2e"
        in makefile
    )
    assert "$(PYTHON) -m pytest tests/e2e/test_memory_agent_plugin_e2e.py -q" in makefile


def test_clean_full_smoke_uses_env_secrets_and_redacts_output(monkeypatch) -> None:
    script_path = ROOT / "scripts" / "clean_full_smoke.py"
    source = script_path.read_text(encoding="utf-8")
    assert "argparse" not in source
    assert "--auth-token" not in source
    assert "MEMORY_MCP_AUTH_TOKEN" in source
    assert "MEMORY_CLEAN_SMOKE_SKIP_MCP" in source

    module = _load_clean_full_smoke(script_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-unit-openai-secret")
    monkeypatch.setenv("MEMORY_MCP_AUTH_TOKEN", "unit-mcp-token")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "unit-service-token")
    payload = {
        "stdout": "sk-unit-openai-secret unit-mcp-token unit-service-token",
        "nested": ["unit-mcp-token"],
        "OPENAI_API_KEY": "Authorization: Bearer sk-proj-unit-secret-value",
        "Authorization": "Bearer plain-header-secret-value",
        "Idempotency-Key": "idempotency-secret-value",
        "CUSTOM_TOKEN": "custom-token-secret-value",
        "token": "short",
        "password": "tiny",
        "api_key": "plain",
        "generic": "token=generic-secret-value-12345",
    }

    rendered = json.dumps(module._redact_payload(payload), ensure_ascii=False)

    assert "sk-unit-openai-secret" not in rendered
    assert "unit-mcp-token" not in rendered
    assert "unit-service-token" not in rendered
    assert "OPENAI_API_KEY" not in rendered
    assert "sk-proj-unit-secret-value" not in rendered
    assert "Authorization" not in rendered
    assert "Idempotency-Key" not in rendered
    assert "CUSTOM_TOKEN" not in rendered
    assert "plain-header-secret-value" not in rendered
    assert "idempotency-secret-value" not in rendered
    assert "custom-token-secret-value" not in rendered
    assert '"token"' not in rendered
    assert '"password"' not in rendered
    assert '"api_key"' not in rendered
    assert '"short"' not in rendered
    assert '"tiny"' not in rendered
    assert '"plain"' not in rendered
    assert "generic-secret-value-12345" not in rendered
    assert "<redacted>" in rendered


def test_clean_full_smoke_redacts_explicit_canary_env_without_process_env() -> None:
    module = _load_clean_full_smoke(ROOT / "scripts" / "clean_full_smoke.py")

    rendered = json.dumps(
        module._redact_payload(
            {
                "message": (
                    "token=explicit-service-token "
                    "postgresql+asyncpg://memory:secret-db-pass@127.0.0.1/memory "
                    "neo4j password memorygraph"
                )
            },
            env={
                "MEMORY_SERVICE_TOKEN": "explicit-service-token",
                "MEMORY_DATABASE_URL": (
                    "postgresql+asyncpg://memory:secret-db-pass@127.0.0.1/memory"
                ),
                "MEMORY_GRAPHITI_NEO4J_PASSWORD": "memorygraph",
            },
        ),
        ensure_ascii=False,
    )

    assert "explicit-service-token" not in rendered
    assert "secret-db-pass" not in rendered
    assert "memorygraph" not in rendered
    assert "<redacted>" in rendered


def test_clean_full_smoke_mcp_text_secret_check_catches_generic_tokens() -> None:
    module = _load_clean_full_smoke(ROOT / "scripts" / "clean_full_smoke.py")

    class Content:
        text = "Authorization: Bearer sk-proj-generic-fallback-token-value"

    class Result:
        content = [Content()]

    assert not module._mcp_text_has_no_secrets(Result(), env={})


def test_clean_full_smoke_keeps_mcp_import_lazy_for_api_only_mode() -> None:
    source = (ROOT / "scripts" / "clean_full_smoke.py").read_text(encoding="utf-8")
    before_mcp_lifecycle = source.split("async def _run_mcp_lifecycle", maxsplit=1)[0]

    assert "from mcp import" not in before_mcp_lifecycle
    assert "from mcp.client.stdio import" not in before_mcp_lifecycle


def test_clean_full_smoke_server_logs_do_not_use_unread_pipe() -> None:
    source = (ROOT / "scripts" / "clean_full_smoke.py").read_text(encoding="utf-8")

    assert "stdout=subprocess.PIPE" not in source
    assert "tempfile.TemporaryFile" in source
    assert "server_output_tail" in source


def test_clean_full_smoke_accepts_real_context_chunk_shape() -> None:
    module = _load_clean_full_smoke(ROOT / "scripts" / "clean_full_smoke.py")

    assert module._search_has_chunk_item(
        {"data": {"items": [{"item_id": "mem_123", "item_type": "chunk", "source_refs": []}]}}
    )
    assert module._search_has_chunk_item(
        {
            "data": {
                "items": [
                    {
                        "item_id": "mem_123",
                        "item_type": "fact",
                        "source_refs": [{"chunk_id": "chunk-canonical-id"}],
                    }
                ]
            }
        }
    )
    assert not module._search_has_chunk_item(
        {"data": {"items": [{"item_id": "fact_123", "item_type": "fact", "source_refs": []}]}}
    )
    assert (
        module._search_diagnostic_status(
            {
                "data": {
                    "diagnostics": {
                        "vector_status": "ok",
                        "graph_status": "skipped",
                        "vector_hydrated_count": 1,
                    }
                }
            },
            "vector_status",
        )
        == "ok"
    )
    assert (
        module._search_diagnostic_int(
            {"data": {"diagnostics": {"vector_hydrated_count": 1}}},
            "vector_hydrated_count",
        )
        == 1
    )
    assert module._context_diagnostic_int(
        {"diagnostics": {"graph_hydrated_count": 2}},
        "graph_hydrated_count",
    ) == 2


def test_clean_full_smoke_mcp_env_does_not_inherit_provider_secrets(monkeypatch) -> None:
    module = _load_clean_full_smoke(ROOT / "scripts" / "clean_full_smoke.py")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-unit-openai-secret")
    monkeypatch.setenv("MEMORY_OPENAI_API_KEY", "sk-unit-memory-openai-secret")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "unit-service-token")
    monkeypatch.setenv("MEMORY_GRAPHITI_NEO4J_PASSWORD", "unit-neo4j-password")
    monkeypatch.setenv("PYTHONPATH", "existing-pythonpath")

    env = module._mcp_process_env(
        base_url="http://127.0.0.1:7788",
        token="unit-mcp-token",
        space_slug="unit-space",
        profile_ref="unit-profile",
    )

    assert env["MEMORY_MCP_API_URL"] == "http://127.0.0.1:7788"
    assert env["MEMORY_MCP_AUTH_TOKEN"] == "unit-mcp-token"
    assert env["MEMORY_MCP_REQUEST_TIMEOUT_SECONDS"] == "90"
    assert "packages/memory_mcp" in env["PYTHONPATH"]
    assert "existing-pythonpath" in env["PYTHONPATH"]
    assert "OPENAI_API_KEY" not in env
    assert "MEMORY_OPENAI_API_KEY" not in env
    assert "MEMORY_SERVICE_TOKEN" not in env
    assert "MEMORY_GRAPHITI_NEO4J_PASSWORD" not in env


def test_clean_full_smoke_required_mcp_adapters_ignore_optional_disabled() -> None:
    module = _load_clean_full_smoke(ROOT / "scripts" / "clean_full_smoke.py")

    status = {
        "data": {
            "capabilities": {
                "adapters": {
                    "qdrant": {"enabled": True, "healthy": True},
                    "graphiti": {"enabled": True, "healthy": True},
                    "embeddings": {"enabled": True, "healthy": True},
                    "cognee": {"enabled": False, "healthy": False},
                }
            }
        }
    }

    assert module._required_mcp_adapters_ready(
        status,
        ("qdrant", "graphiti", "embeddings"),
    )
    assert not module._required_mcp_adapters_ready(
        status,
        ("qdrant", "graphiti", "embeddings", "cognee"),
    )


def test_clean_full_smoke_missing_key_message_does_not_name_sensitive_envs(monkeypatch) -> None:
    module = _load_clean_full_smoke(ROOT / "scripts" / "clean_full_smoke.py")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("MEMORY_OPENAI_API_KEY", raising=False)

    try:
        module._server_env(
            ports={"postgres": 1, "qdrant": 2, "neo4j_bolt": 3, "server": 4},
            token="t",
            run_id="r",
        )
    except module.CleanSmokeFailure as exc:
        message = str(exc)
    else:
        raise AssertionError("expected missing key failure")

    assert "OPENAI_API_KEY" not in message
    assert "MEMORY_OPENAI_API_KEY" not in message


def test_real_stack_mcp_canary_docs_are_env_based() -> None:
    docs = "\n".join(
        [
            (ROOT / "docs" / "README.md").read_text(encoding="utf-8"),
            (ROOT / "docs" / "mcp-adapter.md").read_text(encoding="utf-8"),
            (ROOT / "docs" / "mcp-memory-foundation-plan.md").read_text(encoding="utf-8"),
        ]
    )

    assert "memory-clean-full-mcp-smoke" in docs
    assert "MEMORY_CLEAN_SMOKE_SKIP_MCP=true" in docs
    assert "--auth-token" not in docs
    assert "local-token" not in docs
    assert "local-dev-token" not in docs
    assert re.search(r"\bsk-[A-Za-z0-9]", docs) is None
    assert re.search(r"=<[A-Za-z0-9_-]+>", docs) is None
    assert re.search(
        r'"[A-Z0-9_]*(TOKEN|KEY|SECRET|PASSWORD|DATABASE_URL|DB_URL|DSN)[A-Z0-9_]*"'
        r'\s*:\s*"<[^"]+>"',
        docs,
    ) is None


def _load_clean_full_smoke(path: Path):
    spec = importlib.util.spec_from_file_location("clean_full_smoke_for_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
