from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from memory_server.config import DeployProfile, Settings
from memory_server.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'memory.db'}",
            auto_create_schema=True,
            service_token="test-token",
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
        )
    )
    return TestClient(app)


def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def suggestion_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "space_id": "space_hackinterview",
        "profile_id": "profile_default",
        "candidate_text": "Use Postgres as canonical truth.",
        "kind": "architecture_decision",
        "safe_reason": "manual_review",
        "confidence": "medium",
        "trust_level": "medium",
        "source_refs": [{"source_type": "manual", "source_id": "review-1"}],
    }
    payload.update(overrides)
    return payload


def test_pending_suggestion_not_in_context_and_approve_creates_fact(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        created = client.post(
            "/v1/suggestions",
            json=suggestion_payload(),
            headers=auth_headers(),
        )
        suggestion_id = created.json()["data"]["id"]
        before = client.post(
            "/v1/context",
            json={
                "space_id": "space_hackinterview",
                "profile_ids": ["profile_default"],
                "query": "canonical truth",
                "token_budget": 512,
            },
            headers=auth_headers(),
        )
        approved = client.post(
            f"/v1/suggestions/{suggestion_id}/approve",
            json={"reason": "reviewed"},
            headers=auth_headers(),
        )
        after = client.post(
            "/v1/context",
            json={
                "space_id": "space_hackinterview",
                "profile_ids": ["profile_default"],
                "query": "canonical truth",
                "token_budget": 512,
            },
            headers=auth_headers(),
        )

    assert created.status_code == 201
    assert created.json()["data"]["status"] == "pending"
    assert "Use Postgres as canonical truth" not in before.json()["data"]["rendered_text"]
    assert approved.status_code == 200
    assert approved.json()["data"]["suggestion"]["status"] == "approved"
    assert approved.json()["data"]["fact"]["version"] == 1
    assert "Use Postgres as canonical truth" in after.json()["data"]["rendered_text"]


def test_rejected_suggestion_never_appears_in_context(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        created = client.post(
            "/v1/suggestions",
            json=suggestion_payload(candidate_text="Rejected memory marker."),
            headers=auth_headers(),
        )
        suggestion_id = created.json()["data"]["id"]
        rejected = client.post(
            f"/v1/suggestions/{suggestion_id}/reject",
            json={"reason": "bad memory"},
            headers=auth_headers(),
        )
        context = client.post(
            "/v1/context",
            json={
                "space_id": "space_hackinterview",
                "profile_ids": ["profile_default"],
                "query": "Rejected memory marker",
                "token_budget": 512,
            },
            headers=auth_headers(),
        )

    assert rejected.status_code == 200
    assert rejected.json()["data"]["status"] == "rejected"
    assert "Rejected memory marker" not in context.json()["data"]["rendered_text"]


def test_assistant_suggestion_cannot_auto_promote(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        created = client.post(
            "/v1/suggestions",
            json=suggestion_payload(
                candidate_text="AI draft should remain pending.",
                trust_level="low",
                safe_reason="assistant_output",
                auto_approve=True,
                source_refs=[{"source_type": "ai_response", "source_id": "ai-1"}],
            ),
            headers=auth_headers(),
        )

    assert created.status_code == 201
    assert created.json()["data"]["status"] == "pending"
    assert "auto_approve_blocked_low_trust" in created.json()["data"]["safe_reason"]


def test_list_suggestions_rejects_unknown_status(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.get(
            "/v1/suggestions",
            params={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "status": "mispelled",
            },
            headers=auth_headers(),
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "memory.validation"


def test_weak_source_cannot_supersede_strong_fact_without_force(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        high = client.post(
            "/v1/suggestions",
            json=suggestion_payload(
                candidate_text="Strong reviewed fact.",
                trust_level="high",
                confidence="high",
                safe_reason="human_review",
            ),
            headers=auth_headers(),
        )
        high_id = high.json()["data"]["id"]
        high_approved = client.post(
            f"/v1/suggestions/{high_id}/approve",
            json={"reason": "reviewed"},
            headers=auth_headers(),
        )
        fact = high_approved.json()["data"]["fact"]

        weak = client.post(
            "/v1/suggestions",
            json=suggestion_payload(
                candidate_text="Weak correction should not replace strong fact.",
                trust_level="low",
                safe_reason="weak_source",
                target_fact_id=fact["id"],
                target_fact_version=fact["version"],
            ),
            headers=auth_headers(),
        )
        weak_id = weak.json()["data"]["id"]
        conflict = client.post(
            f"/v1/suggestions/{weak_id}/approve",
            json={"reason": "try weak update"},
            headers=auth_headers(),
        )
        forced = client.post(
            f"/v1/suggestions/{weak_id}/approve",
            json={"reason": "explicit reviewer override", "force": True},
            headers=auth_headers(),
        )

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "memory.conflict"
    assert forced.status_code == 200
    assert forced.json()["data"]["fact"]["version"] == 2


def test_suggestion_cannot_update_target_fact_from_another_profile(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        other_fact = client.post(
            "/v1/facts",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_secondary",
                "text": "CROSS_PROFILE_TARGET_FACT must stay unchanged.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "other-profile"}],
            },
            headers=auth_headers(),
        )
        fact = other_fact.json()["data"]
        suggestion = client.post(
            "/v1/suggestions",
            json=suggestion_payload(
                candidate_text="CROSS_PROFILE_TARGET_FACT overwritten by wrong profile.",
                target_fact_id=fact["id"],
                target_fact_version=fact["version"],
                source_refs=[{"source_type": "manual", "source_id": "wrong-profile"}],
            ),
            headers=auth_headers(),
        )
        suggestion_id = suggestion.json()["data"]["id"]
        approved = client.post(
            f"/v1/suggestions/{suggestion_id}/approve",
            json={"reason": "should not cross profile"},
            headers=auth_headers(),
        )
        unchanged = client.get(f"/v1/facts/{fact['id']}", headers=auth_headers())

    assert other_fact.status_code == 201
    assert suggestion.status_code == 201
    assert approved.status_code == 404
    assert approved.json()["error"]["code"] == "memory.not_found"
    assert unchanged.json()["data"]["text"] == "CROSS_PROFILE_TARGET_FACT must stay unchanged."
