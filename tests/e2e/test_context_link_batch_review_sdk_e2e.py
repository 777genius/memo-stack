from __future__ import annotations

from pathlib import Path

from infinity_context_sdk import InfinityContextClient
from infinity_context_server_harness import run_infinity_context_server


def test_context_link_batch_review_sdk_e2e(tmp_path: Path) -> None:
    with run_infinity_context_server(
        tmp_path,
        database_name="context-link-batch-review-sdk.db",
        extra_env={"MEMORY_CAPTURE_MODE": "suggest"},
    ) as server:
        client = InfinityContextClient(base_url=server.base_url, token=server.token)
        first_fact = client.remember_fact(
            space_slug="context-link-batch-sdk-e2e",
            memory_scope_external_ref="default",
            thread_external_ref="review",
            text="Alex said Project Atlas review screenshots support the memory browser.",
            kind="note",
            source_refs=[{"source_type": "manual", "source_id": "batch-sdk-target-1"}],
            tags=["alex", "atlas", "review"],
            idempotency_key="context-link-batch-sdk-target-1",
        )
        client.remember_fact(
            space_slug="context-link-batch-sdk-e2e",
            memory_scope_external_ref="default",
            thread_external_ref="review",
            text="Project Atlas review history should keep rejected link suggestions visible.",
            kind="note",
            source_refs=[{"source_type": "manual", "source_id": "batch-sdk-target-2"}],
            tags=["atlas", "review"],
            idempotency_key="context-link-batch-sdk-target-2",
        )
        capture = client.create_capture(
            space_slug="context-link-batch-sdk-e2e",
            memory_scope_external_ref="default",
            thread_external_ref="review",
            source_agent="memo-frontend",
            source_kind="manual",
            event_type="QuickCapture",
            actor_role="user",
            source_event_id="context-link-batch-sdk-capture",
            text="Save Alex Project Atlas screenshot for memory browser review history.",
            source_authority="user_statement",
        )
        suggestions = client.suggest_context_links(
            space_slug="context-link-batch-sdk-e2e",
            memory_scope_external_ref="default",
            thread_external_ref="review",
            source_type="capture",
            source_id=capture["data"]["id"],
            text="Alex Project Atlas screenshot review history",
            persist=True,
            limit=8,
        )
        fact_candidate = next(
            item
            for item in suggestions["data"]["candidates"]
            if item["target_type"] == "fact" and item["target_id"] == first_fact["data"]["id"]
        )
        reject_candidate = next(
            item
            for item in suggestions["data"]["candidates"]
            if item["suggestion_id"] != fact_candidate["suggestion_id"]
        )

        reviewed = client.review_context_link_suggestions_batch(
            [
                {
                    "suggestion_id": fact_candidate["suggestion_id"],
                    "action": "approve",
                    "reason": "sdk batch accepted canonical fact",
                    "target_type": "fact",
                    "target_id": first_fact["data"]["id"],
                    "relation_type": "supports",
                    "confidence": "high",
                    "link_reason": "batch reviewer selected exact fact target",
                },
                {
                    "suggestion_id": reject_candidate["suggestion_id"],
                    "action": "reject",
                    "reason": "sdk batch rejected lower priority candidate",
                },
            ],
            continue_on_error=True,
            visible_filter={
                "space_slug": "context-link-batch-sdk-e2e",
                "memory_scope_external_ref": "default",
                "source_type": "capture",
                "source_id": capture["data"]["id"],
                "status": "pending",
                "limit": 20,
            },
        )
        links = client.list_context_links(
            space_slug="context-link-batch-sdk-e2e",
            memory_scope_external_ref="default",
            source_type="capture",
            source_id=capture["data"]["id"],
        )
        target_links = client.list_context_links(
            space_slug="context-link-batch-sdk-e2e",
            memory_scope_external_ref="default",
            target_type="fact",
            target_id=first_fact["data"]["id"],
            relation_type="supports",
        )
        history = client.list_context_link_suggestions(
            space_slug="context-link-batch-sdk-e2e",
            memory_scope_external_ref="default",
            source_type="capture",
            source_id=capture["data"]["id"],
            statuses="approved,rejected",
            limit=20,
        )
        target_history = client.list_context_link_suggestions(
            space_slug="context-link-batch-sdk-e2e",
            memory_scope_external_ref="default",
            target_type="fact",
            target_id=first_fact["data"]["id"],
            statuses="approved,rejected",
            limit=20,
        )

    assert reviewed["data"]["applied"] == 2
    assert reviewed["data"]["failed"] == 0
    assert reviewed["data"]["stopped"] is False
    diagnostics = reviewed["data"]["diagnostics"]
    assert diagnostics["requested_count"] == 2
    assert diagnostics["continue_on_error"] is True
    assert diagnostics["batch_limit"] == 50
    assert diagnostics["visible_filter_applied"] is True
    assert diagnostics["visible_filter_result_count"] >= 2
    assert diagnostics["visible_filter_limit"] == 20
    assert diagnostics["visible_filter_statuses"] == ["pending"]
    assert diagnostics["visible_filter_source_type"] == "capture"
    assert diagnostics["visible_filter_has_source_id"] is True
    assert "visible_filter_source_id" not in diagnostics
    assert "visible_filter_target_id" not in diagnostics
    assert [item["status"] for item in reviewed["data"]["results"]] == ["applied", "applied"]
    approved_result = reviewed["data"]["results"][0]
    rejected_result = reviewed["data"]["results"][1]
    assert approved_result["suggestion"]["status"] == "approved"
    assert approved_result["link"]["target_id"] == first_fact["data"]["id"]
    assert approved_result["link"]["relation_type"] == "supports"
    assert approved_result["link"]["confidence"] == "high"
    assert approved_result["link"]["reason"] == "batch reviewer selected exact fact target"
    assert rejected_result["suggestion"]["status"] == "rejected"
    assert rejected_result["suggestion"]["review_reason"] == (
        "sdk batch rejected lower priority candidate"
    )
    assert [item["id"] for item in links["data"]] == [approved_result["link"]["id"]]
    assert [item["id"] for item in target_links["data"]] == [approved_result["link"]["id"]]
    by_id = {item["id"]: item for item in history["data"]}
    assert by_id[fact_candidate["suggestion_id"]]["status"] == "approved"
    assert by_id[reject_candidate["suggestion_id"]]["status"] == "rejected"
    assert [item["id"] for item in target_history["data"]] == [
        fact_candidate["suggestion_id"]
    ]
