from __future__ import annotations

import asyncio
from pathlib import Path

from infinity_context_mcp.adapters.http_gateway import HttpMemoryGateway
from infinity_context_mcp.application.service import MemoryToolService
from infinity_context_mcp.config import MemoryMcpSettings
from infinity_context_sdk import InfinityContextClient
from infinity_context_server_harness import run_infinity_context_server


def test_context_link_review_mcp_service_e2e(tmp_path: Path) -> None:
    with run_infinity_context_server(
        tmp_path,
        database_name="context-link-mcp-review.db",
        extra_env={"MEMORY_CAPTURE_MODE": "suggest"},
    ) as server:
        client = InfinityContextClient(base_url=server.base_url, token=server.token)
        fact = client.remember_fact(
            space_slug="context-link-mcp-e2e",
            memory_scope_external_ref="default",
            thread_external_ref="review",
            text="Alex linked the Project Atlas screenshot to the memory browser review flow.",
            kind="note",
            source_refs=[{"source_type": "manual", "source_id": "mcp-link-target"}],
            tags=["alex", "atlas", "review"],
            idempotency_key="context-link-mcp-target",
        )
        document = client.ingest_document(
            space_slug="context-link-mcp-e2e",
            memory_scope_external_ref="default",
            thread_external_ref="review",
            title="Project Atlas screenshot review notes",
            text="Alex Project Atlas screenshot review flow should appear as a document.",
            source_type="document",
            source_external_id="context-link-mcp-document",
            idempotency_key="context-link-mcp-document",
        )
        client.remember_fact(
            space_slug="context-link-mcp-e2e",
            memory_scope_external_ref="default",
            thread_external_ref="review",
            text="Project Atlas has a separate roadmap note not tied to this screenshot.",
            kind="note",
            source_refs=[{"source_type": "manual", "source_id": "mcp-link-other"}],
            tags=["atlas", "roadmap"],
            idempotency_key="context-link-mcp-other",
        )
        capture = client.create_capture(
            space_slug="context-link-mcp-e2e",
            memory_scope_external_ref="default",
            thread_external_ref="review",
            source_agent="memo-frontend",
            source_kind="manual",
            event_type="QuickCapture",
            actor_role="user",
            source_event_id="context-link-mcp-capture",
            text="Save Alex Project Atlas screenshot for memory browser review flow.",
            source_authority="user_statement",
        )
        result = asyncio.run(
            _review_links_with_mcp_service(
                base_url=server.base_url,
                token=server.token,
                source_id=capture["data"]["id"],
                target_fact_id=fact["data"]["id"],
            )
        )

    assert result["suggested"]["diagnostics"]["side_effects"] == [
        "created_context_link_suggestions"
    ]
    assert result["listed_pending"] >= 2
    assert result["reviewed"]["data"]["applied"] == 2
    assert result["reviewed"]["diagnostics"]["side_effects"] == [
        "reviewed_context_link_suggestions_batch"
    ]
    assert result["links"]["data"]["items"][0]["target_id"] == fact["data"]["id"]
    assert result["history"]["data"]["items"][0]["status"] in {"approved", "rejected"}
    assert result["browser"]["data"]["memory_scope"]["external_ref"] == "default"
    assert fact["data"]["id"] in {item["id"] for item in result["browser"]["data"]["facts"]}
    assert document["data"]["id"] in {
        item["id"] for item in result["browser"]["data"]["documents"]
    }
    assert result["browser"]["data"]["stats"]["active_context_links"] == 1
    assert result["browser"]["data"]["context_links"][0]["target_id"] == fact["data"]["id"]
    assert result["browser"]["data"]["diagnostics"]["browser_version"] == "memory-browser-v1"


async def _review_links_with_mcp_service(
    *,
    base_url: str,
    token: str,
    source_id: str,
    target_fact_id: str,
) -> dict[str, object]:
    service = MemoryToolService(
        gateway=HttpMemoryGateway(
            base_url=base_url,
            auth_token=token,
            timeout_seconds=5,
        ),
        settings=MemoryMcpSettings(
            default_space_slug="context-link-mcp-e2e",
            default_memory_scope_external_ref="default",
        ),
    )
    suggested = await service.suggest_context_links(
        thread_external_ref="review",
        source_type="capture",
        source_id=source_id,
        text="Alex Project Atlas screenshot memory browser review flow",
        persist=True,
        limit=8,
    )
    accepted = next(
        item
        for item in suggested["data"]["candidates"]
        if item["target_type"] == "fact" and item["target_id"] == target_fact_id
    )
    rejected = next(
        item
        for item in suggested["data"]["candidates"]
        if item["suggestion_id"] != accepted["suggestion_id"]
    )
    pending = await service.list_context_link_suggestions(
        source_type="capture",
        source_id=source_id,
        limit=20,
    )
    reviewed = await service.review_context_link_suggestions_batch(
        items=[
            {
                "suggestion_id": accepted["suggestion_id"],
                "action": "approve",
                "target_type": "fact",
                "target_id": target_fact_id,
                "relation_type": "supports",
                "confidence": "high",
                "link_reason": "mcp reviewer selected exact fact target",
            },
            {
                "suggestion_id": rejected["suggestion_id"],
                "action": "reject",
                "reason": "mcp reviewer rejected lower priority target",
            },
        ],
        continue_on_error=True,
    )
    links = await service.list_context_links(
        source_type="capture",
        source_id=source_id,
        status="active",
    )
    history = await service.list_context_link_suggestions(
        source_type="capture",
        source_id=source_id,
        statuses=["approved", "rejected"],
        limit=20,
    )
    browser = await service.browse_scope(
        limit=20,
        fact_status="active",
        document_status="active",
        link_status="active",
        suggestion_status="approved",
    )
    return {
        "suggested": suggested,
        "listed_pending": len(pending["data"]["items"]),
        "reviewed": reviewed,
        "links": links,
        "history": history,
        "browser": browser,
    }
