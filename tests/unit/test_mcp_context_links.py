from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from infinity_context_mcp.adapters.http_gateway import HttpMemoryGateway
from infinity_context_mcp.application.service import MemoryToolService
from infinity_context_mcp.config import MemoryMcpSettings
from infinity_context_mcp.server import create_mcp_server


class ContextLinkGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def suggest_context_links(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("suggest_context_links", kwargs))
        return {
            "data": {
                "candidates": [
                    {
                        "target_type": "fact",
                        "target_id": "fact_1",
                        "label": "Project Atlas",
                        "preview": "Alex Project Atlas review flow",
                        "score": 0.9,
                        "tier": "strong",
                        "reasons": ["matched terms"],
                        "suggestion_id": "cls_1" if kwargs["persist"] else None,
                        "status": "pending" if kwargs["persist"] else None,
                    }
                ],
                "diagnostics": {"persisted": kwargs["persist"]},
            }
        }

    async def list_context_links(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("list_context_links", kwargs))
        return {
            "data": [
                {
                    "id": "ctx_1",
                    "source_type": "capture",
                    "source_id": "cap_1",
                    "target_type": "fact",
                    "target_id": "fact_1",
                    "relation_type": "supports",
                    "confidence": "high",
                    "status": "active",
                    "reason": "reviewed",
                }
            ]
        }

    async def list_context_link_suggestions(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("list_context_link_suggestions", kwargs))
        return {
            "data": [
                {
                    "id": "cls_1",
                    "source_type": "capture",
                    "source_id": "cap_1",
                    "target_type": "fact",
                    "target_id": "fact_1",
                    "relation_type": "supports",
                    "confidence": "medium",
                    "status": "pending",
                    "score": 0.82,
                    "reason": "semantic overlap",
                }
            ]
        }

    async def review_context_link_suggestion(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("review_context_link_suggestion", kwargs))
        return {
            "data": {
                "suggestion": {"id": kwargs["suggestion_id"], "status": "approved"},
                "link": {
                    "id": "ctx_1",
                    "source_type": "capture",
                    "source_id": "cap_1",
                    "target_type": kwargs["target_type"] or "fact",
                    "target_id": kwargs["target_id"] or "fact_1",
                    "relation_type": kwargs["relation_type"] or "related_to",
                    "confidence": kwargs["confidence"] or "medium",
                    "reason": kwargs["link_reason"] or "semantic overlap",
                    "status": "active",
                },
                "duplicate_link": False,
            }
        }

    async def review_context_link_suggestions_batch(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("review_context_link_suggestions_batch", kwargs))
        return {
            "data": {
                "applied": 1,
                "failed": 1,
                "stopped": False,
                "results": [
                    {
                        "suggestion_id": "cls_1",
                        "action": "approve",
                        "status": "applied",
                        "suggestion": {"id": "cls_1", "status": "approved"},
                        "link": {"id": "ctx_1", "status": "active"},
                        "duplicate_link": False,
                    },
                    {
                        "suggestion_id": "cls_2",
                        "action": "reject",
                        "status": "failed",
                        "error_code": "not_found",
                        "error_message": "missing",
                    },
                ],
            }
        }


def test_service_suggests_context_links_with_persisted_review_queue() -> None:
    async def run() -> None:
        gateway = ContextLinkGateway()
        service = MemoryToolService(gateway=gateway, settings=MemoryMcpSettings())

        result = await service.suggest_context_links(
            space_slug="team",
            memory_scope_external_ref="scope",
            thread_external_ref="thread-1",
            source_type="capture",
            source_id="cap_1",
            text="Alex Project Atlas screenshot review flow",
            limit=100,
            persist=True,
        )

        assert result["ok"] is True
        assert result["data"]["candidates"][0]["suggestion_id"] == "cls_1"
        assert result["diagnostics"]["side_effects"] == ["created_context_link_suggestions"]
        assert result["diagnostics"]["warnings"] == ["limit_clamped_to_max"]
        call_name, payload = gateway.calls[0]
        assert call_name == "suggest_context_links"
        assert payload["scope"].space_slug == "team"
        assert payload["scope"].memory_scope_external_ref == "scope"
        assert payload["scope"].thread_external_ref == "thread-1"
        assert payload["source_type"] == "capture"
        assert payload["source_id"] == "cap_1"
        assert payload["limit"] == 30
        assert payload["persist"] is True

    asyncio.run(run())


def test_service_suggest_context_links_rejects_secret_text() -> None:
    async def run() -> None:
        gateway = ContextLinkGateway()
        service = MemoryToolService(gateway=gateway, settings=MemoryMcpSettings())

        result = await service.suggest_context_links(
            text="api key sk-test-secret-token should not be linked",
            persist=True,
        )

        assert result["ok"] is False
        assert result["error"]["code"] == "infinity_context_mcp.policy.secret_detected"
        assert gateway.calls == []

    asyncio.run(run())


def test_service_lists_context_links_with_bounded_status_filters() -> None:
    async def run() -> None:
        gateway = ContextLinkGateway()
        service = MemoryToolService(gateway=gateway, settings=MemoryMcpSettings())

        result = await service.list_context_links(
            space_slug="team",
            memory_scope_external_ref="scope",
            source_type="capture",
            source_id="cap_1",
            statuses=["active", "deleted", "active"],
            limit=500,
        )

        assert result["ok"] is True
        assert result["data"]["items"][0]["id"] == "ctx_1"
        assert result["diagnostics"]["warnings"] == ["limit_clamped_to_max"]
        call_name, payload = gateway.calls[0]
        assert call_name == "list_context_links"
        assert payload["scope"].space_slug == "team"
        assert payload["scope"].memory_scope_external_ref == "scope"
        assert payload["status"] is None
        assert payload["statuses"] == "active,deleted"
        assert payload["limit"] == 200

    asyncio.run(run())


def test_service_reviews_context_link_suggestions_batch_with_item_failures() -> None:
    async def run() -> None:
        gateway = ContextLinkGateway()
        service = MemoryToolService(gateway=gateway, settings=MemoryMcpSettings())

        result = await service.review_context_link_suggestions_batch(
            items=[
                {
                    "suggestion_id": " cls_1 ",
                    "action": "approve",
                    "target_type": "fact",
                    "target_id": "fact_1",
                    "relation_type": "supports",
                    "confidence": "high",
                    "link_reason": "user selected exact target",
                },
                {"suggestion_id": "cls_2", "action": "reject", "reason": "wrong target"},
            ],
            continue_on_error=True,
        )

        assert result["ok"] is True
        assert result["diagnostics"]["degraded"] is True
        assert result["diagnostics"]["side_effects"] == [
            "reviewed_context_link_suggestions_batch"
        ]
        call_name, payload = gateway.calls[0]
        assert call_name == "review_context_link_suggestions_batch"
        assert payload["continue_on_error"] is True
        assert payload["items"][0] == {
            "suggestion_id": "cls_1",
            "action": "approve",
            "reason": None,
            "target_type": "fact",
            "target_id": "fact_1",
            "relation_type": "supports",
            "confidence": "high",
            "link_reason": "user selected exact target",
        }

    asyncio.run(run())


def test_service_rejects_duplicate_context_link_batch_items() -> None:
    async def run() -> None:
        gateway = ContextLinkGateway()
        service = MemoryToolService(gateway=gateway, settings=MemoryMcpSettings())

        result = await service.review_context_link_suggestions_batch(
            items=[
                {"suggestion_id": "cls_1", "action": "approve"},
                {"suggestion_id": " cls_1 ", "action": "reject"},
            ]
        )

        assert result["ok"] is False
        assert result["error"]["code"] == "infinity_context_mcp.conflict.duplicate_batch_item"
        assert gateway.calls == []

    asyncio.run(run())


def test_mcp_context_link_tool_schema_is_bounded_and_typed() -> None:
    async def run() -> None:
        server = create_mcp_server(
            service=MemoryToolService(gateway=ContextLinkGateway(), settings=MemoryMcpSettings())
        )
        tools = await server.list_tools()

        suggest = next(tool for tool in tools if tool.name == "memory_suggest_context_links")
        list_links = next(tool for tool in tools if tool.name == "memory_list_context_links")
        list_suggestions = next(
            tool for tool in tools if tool.name == "memory_list_context_link_suggestions"
        )
        review = next(
            tool for tool in tools if tool.name == "memory_review_context_link_suggestion"
        )
        batch = next(
            tool
            for tool in tools
            if tool.name == "memory_review_context_link_suggestions_batch"
        )

        assert suggest.annotations.readOnlyHint is False
        assert suggest.inputSchema["properties"]["limit"]["maximum"] == 30
        assert "pending link suggestions" in suggest.description
        assert list_links.annotations.readOnlyHint is True
        assert list_suggestions.annotations.readOnlyHint is True
        assert review.annotations.readOnlyHint is False
        assert batch.inputSchema["properties"]["items"]["maxItems"] == 50
        assert set(review.inputSchema["properties"]["action"]["enum"]) == {
            "approve",
            "reject",
            "expire",
        }
        assert "ContextLink" in batch.outputSchema["title"]

    asyncio.run(run())


def test_http_gateway_context_link_review_contract() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        item: dict[str, Any] = {"method": request.method, "url": str(request.url)}
        if request.content:
            item["body"] = json.loads(request.content.decode("utf-8"))
        seen.append(item)
        return httpx.Response(200, json={"data": []})

    async def run() -> None:
        gateway = HttpMemoryGateway(
            base_url="http://memory.test",
            auth_token="token",
            timeout_seconds=3,
            transport=httpx.MockTransport(handler),
        )
        await gateway.list_context_link_suggestions(
            scope=type("Scope", (), {"space_slug": "team", "memory_scope_external_ref": "scope"})(),
            source_type="capture",
            source_id="cap_1",
            status=None,
            statuses="approved,rejected",
            limit=20,
        )
        await gateway.suggest_context_links(
            scope=type(
                "Scope",
                (),
                {
                    "space_slug": "team",
                    "memory_scope_external_ref": "scope",
                    "thread_external_ref": "thread",
                },
            )(),
            text="Alex screenshot",
            source_type="capture",
            source_id="cap_1",
            limit=5,
            persist=True,
        )
        await gateway.review_context_link_suggestions_batch(
            items=[{"suggestion_id": "cls_1", "action": "reject"}],
            continue_on_error=True,
        )

    asyncio.run(run())

    assert seen[0]["method"] == "GET"
    assert seen[0]["url"] == (
        "http://memory.test/v1/context-link-suggestions?"
        "space_slug=team&memory_scope_external_ref=scope&source_type=capture&"
        "source_id=cap_1&statuses=approved%2Crejected&limit=20"
    )
    assert seen[1] == {
        "method": "POST",
        "url": "http://memory.test/v1/link-suggestions",
        "body": {
            "space_slug": "team",
            "memory_scope_external_ref": "scope",
            "thread_external_ref": "thread",
            "text": "Alex screenshot",
            "source_type": "capture",
            "source_id": "cap_1",
            "limit": 5,
            "persist": True,
        },
    }
    assert seen[2] == {
        "method": "POST",
        "url": "http://memory.test/v1/context-link-suggestions/review-batch",
        "body": {
            "items": [{"suggestion_id": "cls_1", "action": "reject"}],
            "continue_on_error": True,
        },
    }
