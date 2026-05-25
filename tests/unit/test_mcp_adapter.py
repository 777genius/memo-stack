import asyncio
import json
from typing import Any

import httpx
from memory_mcp.adapters.http_gateway import HttpMemoryGateway
from memory_mcp.application.service import MemoryToolService
from memory_mcp.config import MemoryMcpSettings, load_settings
from memory_mcp.domain.models import MemoryScope, SourceRef


class RecordingGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def health(self) -> dict[str, Any]:
        return {"status": "ok"}

    async def capabilities(self) -> dict[str, Any]:
        return {"policy_mode": "active_context"}

    async def build_context(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("build_context", kwargs))
        return {"data": {"rendered_text": "stored context", "items": []}}

    async def remember_fact(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("remember_fact", kwargs))
        return {
            "data": {
                "id": "fact_1",
                "version": 1,
                "text": kwargs["text"],
                "source_refs": [source.to_payload() for source in kwargs["source_refs"]],
            }
        }

    async def list_facts(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("list_facts", kwargs))
        return {"data": []}

    async def get_fact(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("get_fact", kwargs))
        return {"data": {"id": kwargs["fact_id"]}}

    async def list_fact_versions(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("list_fact_versions", kwargs))
        return {"data": []}

    async def update_fact(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("update_fact", kwargs))
        return {"data": {"id": kwargs["fact_id"], "version": kwargs["expected_version"] + 1}}

    async def forget_fact(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("forget_fact", kwargs))
        return {"data": {"id": kwargs["fact_id"], "status": "deleted"}}

    async def ingest_document(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("ingest_document", kwargs))
        return {"data": {"id": "doc_1"}}


def test_load_settings_uses_memory_service_token_fallback() -> None:
    settings = load_settings(
        {
            "MEMORY_SERVICE_TOKEN": "server-token",
            "MEMORY_MCP_API_URL": "http://memory.test/",
            "MEMORY_MCP_ALLOW_DELETES": "false",
        }
    )

    assert settings.auth_token == "server-token"
    assert settings.api_url == "http://memory.test"
    assert settings.allow_deletes is False


def test_service_remember_fact_uses_default_scope_and_stable_idempotency() -> None:
    async def run() -> None:
        gateway = RecordingGateway()
        service = MemoryToolService(
            gateway=gateway,
            settings=MemoryMcpSettings(
                default_space_slug="project-a",
                default_profile_external_ref="backend",
            ),
        )

        first = await service.remember_fact(
            text="Postgres is canonical truth.",
            kind="architecture_decision",
        )
        second = await service.remember_fact(
            text="Postgres is canonical truth.",
            kind="architecture_decision",
        )

        assert first["ok"] is True
        assert second["ok"] is True
        first_call = gateway.calls[0][1]
        second_call = gateway.calls[1][1]
        assert first_call["scope"] == MemoryScope("project-a", "backend", None)
        assert first_call["idempotency_key"] == second_call["idempotency_key"]
        assert first_call["source_refs"][0].source_type == "ai_response"

    asyncio.run(run())


def test_service_blocks_destructive_tools_when_disabled() -> None:
    async def run() -> None:
        service = MemoryToolService(
            gateway=RecordingGateway(),
            settings=MemoryMcpSettings(allow_deletes=False),
        )

        result = await service.forget_fact(fact_id="fact_1")

        assert result["ok"] is False
        assert result["error"]["code"] == "memory_mcp.deletes_disabled"

    asyncio.run(run())


def test_http_gateway_sends_auth_idempotency_and_external_scope() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization")
        seen["idempotency_key"] = request.headers.get("idempotency-key")
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(201, json={"data": {"id": "fact_1"}})

    async def run() -> None:
        gateway = HttpMemoryGateway(
            base_url="http://memory.test",
            auth_token="test-token",
            timeout_seconds=3,
            transport=httpx.MockTransport(handler),
        )

        response = await gateway.remember_fact(
            scope=MemoryScope("hackinterview", "default", "session-1"),
            text="Use Graphiti as graph adapter.",
            kind="architecture_decision",
            source_refs=[SourceRef(source_type="manual", source_id="note-1")],
            classification="internal",
            idempotency_key="fact-key-1",
        )

        assert response["data"]["id"] == "fact_1"

    asyncio.run(run())

    assert seen["authorization"] == "Bearer test-token"
    assert seen["idempotency_key"] == "fact-key-1"
    assert seen["url"] == "http://memory.test/v1/facts"
    assert seen["body"]["space_slug"] == "hackinterview"
    assert seen["body"]["profile_external_ref"] == "default"
    assert seen["body"]["thread_external_ref"] == "session-1"
