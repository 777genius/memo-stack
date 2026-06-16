from __future__ import annotations

from pathlib import Path

from memo_stack_sdk import MemoStackClient
from memo_stack_server_harness import run_memo_stack_server


def test_manual_context_link_sdk_e2e(tmp_path: Path) -> None:
    with run_memo_stack_server(
        tmp_path,
        database_name="manual-context-link.db",
        extra_env={"MEMORY_CAPTURE_MODE": "suggest"},
    ) as server:
        client = MemoStackClient(base_url=server.base_url, token=server.token)
        fact = client.remember_fact(
            space_slug="manual-link-e2e",
            memory_scope_external_ref="default",
            thread_external_ref="review",
            text="Project Atlas canonical target for a manual memory link.",
            kind="note",
            source_refs=[{"source_type": "manual", "source_id": "manual-link-target"}],
            idempotency_key="manual-context-link-target",
        )
        capture = client.create_capture(
            space_slug="manual-link-e2e",
            memory_scope_external_ref="default",
            thread_external_ref="review",
            source_agent="memo-frontend",
            source_kind="manual",
            event_type="QuickCapture",
            actor_role="user",
            source_event_id="manual-context-link-capture",
            text="Screenshot from Alex belongs to the Project Atlas canonical target.",
            source_authority="user_statement",
        )

        created = client.create_context_link(
            space_slug="manual-link-e2e",
            memory_scope_external_ref="default",
            source_type="capture",
            source_id=capture["data"]["id"],
            target_type="fact",
            target_id=fact["data"]["id"],
            relation_type="supports",
            confidence="high",
            reason="manual reviewer selected canonical target",
            metadata={"created_from": "sdk_e2e"},
        )
        duplicate = client.create_context_link(
            space_slug="manual-link-e2e",
            memory_scope_external_ref="default",
            source_type="capture",
            source_id=capture["data"]["id"],
            target_type="fact",
            target_id=fact["data"]["id"],
            relation_type="supports",
            confidence="high",
            reason="manual reviewer selected canonical target",
            metadata={"created_from": "sdk_e2e_duplicate"},
        )
        listed = client.list_context_links(
            space_slug="manual-link-e2e",
            memory_scope_external_ref="default",
            status="active",
        )
        link = created["data"]
        deleted = client.delete_context_link(link["id"])
        active_after_delete = client.list_context_links(
            space_slug="manual-link-e2e",
            memory_scope_external_ref="default",
            status="active",
        )
        deleted_links = client.list_context_links(
            space_slug="manual-link-e2e",
            memory_scope_external_ref="default",
            status="deleted",
        )

        assert link["duplicate"] is False
        assert link["source_id"] == capture["data"]["id"]
        assert link["target_id"] == fact["data"]["id"]
        assert link["relation_type"] == "supports"
        assert link["confidence"] == "high"
        assert link["metadata"]["created_from"] == "sdk_e2e"
        assert duplicate["data"]["duplicate"] is True
        assert duplicate["data"]["id"] == link["id"]
        assert [item["id"] for item in listed["data"]] == [link["id"]]
        assert deleted["data"]["id"] == link["id"]
        assert deleted["data"]["status"] == "deleted"
        assert active_after_delete["data"] == []
        assert [item["id"] for item in deleted_links["data"]] == [link["id"]]
