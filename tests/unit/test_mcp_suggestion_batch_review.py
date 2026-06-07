from __future__ import annotations

import asyncio
from typing import Any

from memo_stack_mcp.application.service import MemoryToolService
from memo_stack_mcp.config import MemoryMcpSettings
from memo_stack_mcp.server import create_mcp_server


class BatchReviewGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def create_suggestions_batch(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("create_suggestions_batch", kwargs))
        return {
            "data": {
                "created": 2,
                "failed": 0,
                "stopped": False,
                "results": [
                    {
                        "index": 0,
                        "status": "created",
                        "suggestion": {"id": "sug_1", "status": "pending"},
                    },
                    {
                        "index": 1,
                        "status": "created",
                        "suggestion": {"id": "sug_2", "status": "pending"},
                    },
                ],
            }
        }

    async def review_suggestions_batch(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("review_suggestions_batch", kwargs))
        return {
            "data": {
                "applied": 2,
                "failed": 0,
                "stopped": False,
                "results": [
                    {
                        "suggestion_id": "sug_1",
                        "action": "approve",
                        "status": "applied",
                        "suggestion": {"id": "sug_1", "status": "approved"},
                        "fact": {"id": "fact_from_suggestion", "version": 1},
                    },
                    {
                        "suggestion_id": "sug_2",
                        "action": "reject",
                        "status": "applied",
                        "suggestion": {"id": "sug_2", "status": "rejected"},
                    },
                ],
            }
        }


def test_service_review_suggestions_batch_forwards_bounded_items() -> None:
    async def run() -> None:
        gateway = BatchReviewGateway()
        service = MemoryToolService(gateway=gateway, settings=MemoryMcpSettings())

        result = await service.review_suggestions_batch(
            items=[
                {
                    "suggestion_id": " sug_1 ",
                    "action": "approve",
                    "reason": "reviewed",
                    "force": True,
                },
                {"suggestion_id": "sug_2", "action": "reject"},
            ],
            continue_on_error=True,
        )

        assert result["ok"] is True
        assert result["data"]["applied"] == 2
        assert result["diagnostics"]["side_effects"] == ["reviewed_suggestions_batch"]
        assert gateway.calls == [
            (
                "review_suggestions_batch",
                {
                    "items": [
                        {
                            "suggestion_id": "sug_1",
                            "action": "approve",
                            "reason": "reviewed",
                            "force": True,
                        },
                        {
                            "suggestion_id": "sug_2",
                            "action": "reject",
                            "reason": None,
                            "force": False,
                        },
                    ],
                    "continue_on_error": True,
                },
            )
        ]

    asyncio.run(run())


def test_service_suggest_facts_batch_forwards_bounded_items() -> None:
    async def run() -> None:
        gateway = BatchReviewGateway()
        service = MemoryToolService(gateway=gateway, settings=MemoryMcpSettings())

        result = await service.suggest_facts_batch(
            items=[
                {
                    "candidate_text": "Batch MCP suggestion A.",
                    "kind": "architecture_decision",
                    "category": "Architecture",
                    "tags": ["RAG", "rag", "Cognee"],
                    "quote_preview": "Architecture note",
                },
                {"candidate_text": "Batch MCP suggestion B."},
            ],
            source_type="manual",
            source_id="mcp-batch",
            continue_on_error=True,
        )

        assert result["ok"] is True
        assert result["data"]["created"] == 2
        assert result["diagnostics"]["side_effects"] == ["created_suggestions_batch"]
        call_name, payload = gateway.calls[0]
        assert call_name == "create_suggestions_batch"
        assert payload["continue_on_error"] is True
        assert payload["items"][0]["category"] == "architecture"
        assert payload["items"][0]["tags"] == ["rag", "cognee"]
        assert payload["items"][0]["source_refs"][0].source_type == "manual"
        assert payload["items"][1]["safe_reason"] == "mcp_agent_suggestion_requires_review"

    asyncio.run(run())


def test_service_review_suggestions_batch_rejects_duplicate_targets() -> None:
    async def run() -> None:
        gateway = BatchReviewGateway()
        service = MemoryToolService(gateway=gateway, settings=MemoryMcpSettings())

        result = await service.review_suggestions_batch(
            items=[
                {"suggestion_id": "sug_1", "action": "reject"},
                {"suggestion_id": "sug_1", "action": "expire"},
            ]
        )

        assert result["ok"] is False
        assert result["error"]["code"] == "memo_stack_mcp.conflict.duplicate_batch_item"
        assert gateway.calls == []

    asyncio.run(run())


def test_mcp_review_suggestions_batch_tool_schema_is_bounded() -> None:
    async def run() -> None:
        server = create_mcp_server(
            service=MemoryToolService(gateway=BatchReviewGateway(), settings=MemoryMcpSettings())
        )
        tools = await server.list_tools()
        tool = next(item for item in tools if item.name == "memory_review_suggestions_batch")

        assert tool.inputSchema["properties"]["items"]["maxItems"] == 50
        assert "per-item" in tool.description
        assert tool.outputSchema["title"].endswith("Response")

    asyncio.run(run())


def test_mcp_suggest_facts_batch_tool_schema_is_bounded() -> None:
    async def run() -> None:
        server = create_mcp_server(
            service=MemoryToolService(gateway=BatchReviewGateway(), settings=MemoryMcpSettings())
        )
        tools = await server.list_tools()
        tool = next(item for item in tools if item.name == "memory_suggest_facts_batch")

        assert tool.inputSchema["properties"]["items"]["maxItems"] == 50
        assert "pending memory suggestions" in tool.description
        assert tool.outputSchema["title"].endswith("Response")

    asyncio.run(run())
