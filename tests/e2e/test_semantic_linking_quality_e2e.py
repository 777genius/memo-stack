from __future__ import annotations

from pathlib import Path

import httpx
from memo_stack_server_harness import run_memo_stack_server


def test_semantic_linking_quality_golden_cases_e2e(tmp_path: Path) -> None:
    with (
        run_memo_stack_server(
            tmp_path,
            database_name="semantic-linking-quality.db",
            extra_env={"MEMORY_CAPTURE_MODE": "suggest"},
        ) as server,
        httpx.Client(
            base_url=server.base_url,
            headers={"Authorization": f"Bearer {server.token}"},
            timeout=20,
        ) as client,
    ):
        target_fact = _remember_fact(
            client,
            text=(
                "Alex and Project Atlas onboarding pricing summary from an hour ago. "
                "The action item is invoice threshold approval."
            ),
            source_id="atlas-pricing",
        )
        distractor_fact = _remember_fact(
            client,
            text=(
                "Alex and Project Aurora branding notes from last week. "
                "The topic is logo color and launch copy."
            ),
            source_id="aurora-branding",
        )
        source_capture = _capture(
            client,
            source_event_id="atlas-pricing-capture",
            text=(
                "Screenshot note from Alex an hour ago about Project Atlas onboarding "
                "pricing and invoice threshold approval."
            ),
            thread_external_ref="quality-review",
        )

        suggestions = client.post(
            "/v1/link-suggestions",
            json={
                "space_slug": "semantic-linking-quality",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "quality-review",
                "source_type": "capture",
                "source_id": source_capture["id"],
                "text": "Alex hour ago Project Atlas onboarding pricing invoice threshold",
                "persist": True,
                "limit": 8,
            },
        )
        assert suggestions.status_code == 200, suggestions.text
        candidates = suggestions.json()["data"]["candidates"]
        fact_candidates = [item for item in candidates if item["target_type"] == "fact"]
        assert fact_candidates[0]["target_id"] == target_fact["id"]
        assert fact_candidates[0]["score"] > _candidate_score(
            fact_candidates,
            distractor_fact["id"],
        )
        assert fact_candidates[0]["suggestion_id"]
        assert "text_match" in fact_candidates[0]["metadata"]["reason_codes"]
        assert {"alex", "atlas", "pricing"}.issubset(
            set(fact_candidates[0]["metadata"]["matched_terms"])
        )
        anchor_labels = {
            (item["metadata"].get("anchor_kind"), item["metadata"].get("normalized_key"))
            for item in candidates
            if item["target_type"] == "anchor"
        }
        assert ("person", "alex") in anchor_labels
        assert ("project", "atlas") in anchor_labels

        approved = client.post(
            f"/v1/context-link-suggestions/{fact_candidates[0]['suggestion_id']}/review",
            json={"action": "approve", "reason": "quality golden accepted top target"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["data"]["link"]["target_id"] == target_fact["id"]

        unrelated_capture = _capture(
            client,
            source_event_id="unrelated-capture",
            text="lowercase grocery reminder about bananas milk and receipts",
        )
        unrelated = client.post(
            "/v1/link-suggestions",
            json={
                "space_slug": "semantic-linking-quality",
                "memory_scope_external_ref": "default",
                "source_type": "capture",
                "source_id": unrelated_capture["id"],
                "text": "lowercase grocery reminder bananas milk receipts",
                "persist": True,
                "limit": 8,
            },
        )
        assert unrelated.status_code == 200, unrelated.text
        assert unrelated.json()["data"]["candidates"] == []


def _remember_fact(client: httpx.Client, *, text: str, source_id: str) -> dict[str, object]:
    response = client.post(
        "/v1/facts",
        json={
            "space_slug": "semantic-linking-quality",
            "memory_scope_external_ref": "default",
            "thread_external_ref": "quality-review",
            "text": text,
            "kind": "note",
            "source_refs": [{"source_type": "manual", "source_id": source_id}],
        },
        headers={"Idempotency-Key": f"semantic-linking-quality-{source_id}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _capture(
    client: httpx.Client,
    *,
    source_event_id: str,
    text: str,
    thread_external_ref: str | None = None,
) -> dict[str, object]:
    response = client.post(
        "/v1/captures",
        json={
            "space_slug": "semantic-linking-quality",
            "memory_scope_external_ref": "default",
            "thread_external_ref": thread_external_ref,
            "source_agent": "memo-frontend",
            "source_kind": "manual",
            "event_type": "QuickCapture",
            "actor_role": "user",
            "source_event_id": source_event_id,
            "text": text,
            "source_authority": "user_statement",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _candidate_score(candidates: list[dict[str, object]], target_id: str) -> float:
    candidate = next(item for item in candidates if item["target_id"] == target_id)
    return float(candidate["score"])
