from __future__ import annotations

from pathlib import Path

import httpx
from infinity_context_server_harness import run_infinity_context_server


def test_context_link_review_override_e2e(tmp_path: Path) -> None:
    with (
        run_infinity_context_server(
            tmp_path,
            database_name="context-link-override.db",
            extra_env={"MEMORY_CAPTURE_MODE": "suggest"},
        ) as server,
        httpx.Client(
            base_url=server.base_url,
            headers={"Authorization": f"Bearer {server.token}"},
            timeout=20,
        ) as client,
    ):
        suggested_fact = client.post(
            "/v1/facts",
            json={
                "space_slug": "context-link-override-e2e",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "review",
                "text": "Alex mentioned Project Atlas screenshot evidence in review chat.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "suggested"}],
            },
            headers={"Idempotency-Key": "context-link-override-e2e-suggested"},
        )
        override_fact = client.post(
            "/v1/facts",
            json={
                "space_slug": "context-link-override-e2e",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "review",
                "text": "Project Atlas final artifact is the canonical review target.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "override"}],
            },
            headers={"Idempotency-Key": "context-link-override-e2e-target"},
        )
        capture = client.post(
            "/v1/captures",
            json={
                "space_slug": "context-link-override-e2e",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "review",
                "source_agent": "memo-frontend",
                "source_kind": "manual",
                "event_type": "QuickCapture",
                "actor_role": "user",
                "source_event_id": "context-link-override-e2e-capture",
                "text": "Save screenshot context from Alex Project Atlas review.",
                "source_authority": "user_statement",
            },
        )
        assert suggested_fact.status_code == 201, suggested_fact.text
        assert override_fact.status_code == 201, override_fact.text
        assert capture.status_code == 201, capture.text

        suggestions = client.post(
            "/v1/link-suggestions",
            json={
                "space_slug": "context-link-override-e2e",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "review",
                "source_type": "capture",
                "source_id": capture.json()["data"]["id"],
                "text": "Alex Project Atlas screenshot review context",
                "persist": True,
                "limit": 8,
            },
        )
        assert suggestions.status_code == 200, suggestions.text
        original_fact_candidate = next(
            item
            for item in suggestions.json()["data"]["candidates"]
            if item["target_type"] == "fact"
        )

        approved = client.post(
            f"/v1/context-link-suggestions/{original_fact_candidate['suggestion_id']}/review",
            json={
                "action": "approve",
                "reason": "e2e corrected target",
                "target_type": "fact",
                "target_id": override_fact.json()["data"]["id"],
                "relation_type": "supports",
                "confidence": "high",
                "link_reason": "reviewer selected canonical target",
            },
        )
        assert approved.status_code == 200, approved.text

        link = approved.json()["data"]["link"]
        assert link["source_id"] == capture.json()["data"]["id"]
        assert link["target_id"] == override_fact.json()["data"]["id"]
        assert link["relation_type"] == "supports"
        assert link["confidence"] == "high"
        assert link["reason"] == "reviewer selected canonical target"
        assert link["metadata"]["approved_override"] is True
        assert link["metadata"]["original_target_id"] == original_fact_candidate["target_id"]

        listed = client.get(
            "/v1/context-links",
            params={
                "space_slug": "context-link-override-e2e",
                "memory_scope_external_ref": "default",
                "source_type": "capture",
                "source_id": capture.json()["data"]["id"],
            },
        )
        assert listed.status_code == 200, listed.text
        assert [item["target_id"] for item in listed.json()["data"]] == [
            override_fact.json()["data"]["id"]
        ]

        scope_links = client.get(
            "/v1/context-links",
            params={
                "space_slug": "context-link-override-e2e",
                "memory_scope_external_ref": "default",
            },
        )
        assert scope_links.status_code == 200, scope_links.text
        assert [item["id"] for item in scope_links.json()["data"]] == [link["id"]]
