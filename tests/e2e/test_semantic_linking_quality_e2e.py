from __future__ import annotations

from pathlib import Path

import httpx
from infinity_context_server_harness import run_infinity_context_server


def test_semantic_linking_quality_golden_cases_e2e(tmp_path: Path) -> None:
    with (
        run_infinity_context_server(
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

        same_name_capture = _capture(
            client,
            source_event_id="same-name-anchor-capture",
            text="Alex wrote that Project Alex is a separate workspace.",
            thread_external_ref="quality-review",
        )
        same_name_suggestions = client.post(
            "/v1/link-suggestions",
            json={
                "space_slug": "semantic-linking-quality",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "quality-review",
                "source_type": "capture",
                "source_id": same_name_capture["id"],
                "text": "Alex wrote that Project Alex is a separate workspace",
                "persist": True,
                "limit": 8,
            },
        )
        assert same_name_suggestions.status_code == 200, same_name_suggestions.text
        same_name_anchor_labels = {
            (item["metadata"].get("anchor_kind"), item["metadata"].get("normalized_key"))
            for item in same_name_suggestions.json()["data"]["candidates"]
            if item["target_type"] == "anchor"
        }
        assert ("person", "alex") in same_name_anchor_labels
        assert ("project", "alex") in same_name_anchor_labels

        wrong_project_capture = _capture(
            client,
            source_event_id="wrong-project-identity-capture",
            text=(
                "Project Apollo onboarding pricing invoice threshold approval is "
                "separate from Atlas and Aurora."
            ),
            thread_external_ref="quality-review",
        )
        wrong_project_suggestions = client.post(
            "/v1/link-suggestions",
            json={
                "space_slug": "semantic-linking-quality",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "quality-review",
                "source_type": "capture",
                "source_id": wrong_project_capture["id"],
                "text": "Project Apollo onboarding pricing invoice threshold approval",
                "persist": True,
                "limit": 12,
            },
        )
        assert wrong_project_suggestions.status_code == 200, wrong_project_suggestions.text
        wrong_project_data = wrong_project_suggestions.json()["data"]
        wrong_project_candidates = wrong_project_data["candidates"]
        assert all(
            item["target_id"] not in {target_fact["id"], distractor_fact["id"]}
            for item in wrong_project_candidates
            if item["target_type"] == "fact"
        )
        assert all(
            item["metadata"].get("canonical_key") not in {"atlas", "aurora"}
            for item in wrong_project_candidates
            if item["target_type"] == "anchor"
            and item["metadata"].get("anchor_kind") == "project"
        )
        assert (
            wrong_project_data["diagnostics"]["link_policy_denied_reason_counts"][
                "exclusive_anchor_mismatch"
            ]
            >= 1
        )

        approved = client.post(
            f"/v1/context-link-suggestions/{fact_candidates[0]['suggestion_id']}/review",
            json={"action": "approve", "reason": "quality golden accepted top target"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["data"]["link"]["target_id"] == target_fact["id"]

        call_fact = _remember_fact(
            client,
            text=(
                "Alex Project Atlas call from last week covered migration rollback "
                "window ownership and production risk handoff."
            ),
            source_id="atlas-migration-call",
        )
        chat_distractor_fact = _remember_fact(
            client,
            text=(
                "Alex Project Atlas chat from an hour ago covered billing dashboard "
                "copy and button icons."
            ),
            source_id="atlas-billing-chat",
        )
        call_capture = _capture(
            client,
            source_event_id="atlas-migration-call-capture",
            text=(
                "Please link this note to the Alex Project Atlas call last week "
                "about migration rollback window and production risk handoff."
            ),
            thread_external_ref="quality-review",
        )

        event_suggestions = client.post(
            "/v1/link-suggestions",
            json={
                "space_slug": "semantic-linking-quality",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "quality-review",
                "source_type": "capture",
                "source_id": call_capture["id"],
                "text": (
                    "Alex Project Atlas call last week migration rollback production risk handoff"
                ),
                "persist": True,
                "limit": 8,
            },
        )
        assert event_suggestions.status_code == 200, event_suggestions.text
        event_fact_candidates = [
            item
            for item in event_suggestions.json()["data"]["candidates"]
            if item["target_type"] == "fact"
        ]
        assert event_fact_candidates[0]["target_id"] == call_fact["id"]
        assert event_fact_candidates[0]["score"] > _candidate_score(
            event_fact_candidates,
            chat_distractor_fact["id"],
        )

        multilingual_fact = _remember_fact(
            client,
            text=(
                "Alex Project Atlas payment escalation call an hour ago confirmed "
                "invoice threshold approval with finance."
            ),
            source_id="atlas-payment-escalation-call",
        )
        multilingual_distractor_fact = _remember_fact(
            client,
            text=(
                "Alex Project Aurora payment escalation chat an hour ago covered "
                "brand landing page copy."
            ),
            source_id="aurora-payment-escalation-chat",
        )
        multilingual_capture = _capture(
            client,
            source_event_id="ru-atlas-payment-escalation-capture",
            text=(
                "Скрин после созвона с Алексом час назад по проекту Atlas: "
                "нужно одобрить invoice threshold с finance."
            ),
            thread_external_ref="quality-review",
        )
        multilingual_suggestions = client.post(
            "/v1/link-suggestions",
            json={
                "space_slug": "semantic-linking-quality",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "quality-review",
                "source_type": "capture",
                "source_id": multilingual_capture["id"],
                "text": (
                    "Скрин после созвона с Алексом час назад по проекту Atlas "
                    "одобрить invoice threshold finance"
                ),
                "persist": True,
                "limit": 10,
            },
        )
        assert multilingual_suggestions.status_code == 200, multilingual_suggestions.text
        multilingual_data = multilingual_suggestions.json()["data"]
        multilingual_fact_candidates = [
            item for item in multilingual_data["candidates"] if item["target_type"] == "fact"
        ]
        assert multilingual_fact_candidates[0]["target_id"] == multilingual_fact["id"]
        assert multilingual_fact_candidates[0]["score"] > _candidate_score(
            multilingual_fact_candidates,
            multilingual_distractor_fact["id"],
        )
        assert {"person:aleks", "atlas", "invoice", "threshold", "finance"}.issubset(
            set(multilingual_fact_candidates[0]["metadata"]["matched_terms"])
        )
        multilingual_anchor_labels = {
            (item["metadata"].get("anchor_kind"), item["metadata"].get("normalized_key"))
            for item in multilingual_data["candidates"]
            if item["target_type"] == "anchor"
        }
        assert ("person", "алекс") in multilingual_anchor_labels
        assert ("project", "atlas") in multilingual_anchor_labels
        assert any(
            kind == "event" and "час назад" in key
            for kind, key in multilingual_anchor_labels
        )

        document = _ingest_document(
            client,
            title="Project Atlas onboarding pricing SOP",
            text=(
                "Project Atlas onboarding pricing SOP. Screenshots showing invoice "
                "threshold approval should be attached to this document evidence "
                "before the finance handoff."
            ),
            source_external_id="atlas-pricing-sop",
        )
        document_capture = _capture(
            client,
            source_event_id="atlas-pricing-sop-screenshot",
            text=(
                "Screenshot from the Project Atlas onboarding pricing SOP showing "
                "invoice threshold approval before finance handoff."
            ),
            thread_external_ref="document-review",
        )
        document_suggestions = client.post(
            "/v1/link-suggestions",
            json={
                "space_slug": "semantic-linking-quality",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "document-review",
                "source_type": "capture",
                "source_id": document_capture["id"],
                "text": (
                    "Project Atlas onboarding pricing SOP invoice threshold "
                    "approval finance handoff"
                ),
                "persist": True,
                "limit": 8,
            },
        )
        assert document_suggestions.status_code == 200, document_suggestions.text
        document_candidates = [
            item
            for item in document_suggestions.json()["data"]["candidates"]
            if item["target_type"] == "document"
        ]
        chunk_candidates = [
            item
            for item in document_suggestions.json()["data"]["candidates"]
            if item["target_type"] == "chunk"
        ]
        assert document_candidates[0]["target_id"] == document["id"]
        assert chunk_candidates[0]["metadata"]["document_id"] == document["id"]
        assert "text_match" in chunk_candidates[0]["metadata"]["reason_codes"]

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

        rejected_fact = _remember_fact(
            client,
            text=(
                "Project Atlas screenshot evidence mentions Alex and a rejected "
                "vendor onboarding checklist."
            ),
            source_id="atlas-rejected-screenshot-link",
        )
        rejected_capture = _capture(
            client,
            source_event_id="atlas-rejected-screenshot-capture",
            text=(
                "Save Alex Project Atlas screenshot evidence for rejected vendor "
                "onboarding checklist review."
            ),
            thread_external_ref="quality-review",
        )
        rejected_payload = {
            "space_slug": "semantic-linking-quality",
            "memory_scope_external_ref": "default",
            "thread_external_ref": "quality-review",
            "source_type": "capture",
            "source_id": rejected_capture["id"],
            "text": "Alex Project Atlas screenshot evidence rejected vendor onboarding checklist",
            "persist": True,
            "limit": 8,
        }
        rejected_suggestions = client.post("/v1/link-suggestions", json=rejected_payload)
        assert rejected_suggestions.status_code == 200, rejected_suggestions.text
        rejected_candidate = next(
            item
            for item in rejected_suggestions.json()["data"]["candidates"]
            if item["target_type"] == "fact" and item["target_id"] == rejected_fact["id"]
        )
        rejected_review = client.post(
            f"/v1/context-link-suggestions/{rejected_candidate['suggestion_id']}/review",
            json={"action": "reject", "reason": "quality golden rejected duplicate link"},
        )
        assert rejected_review.status_code == 200, rejected_review.text

        repeated_rejected_suggestions = client.post(
            "/v1/link-suggestions",
            json=rejected_payload,
        )
        assert repeated_rejected_suggestions.status_code == 200
        repeated_rejected_data = repeated_rejected_suggestions.json()["data"]
        assert all(
            item["target_id"] != rejected_fact["id"]
            for item in repeated_rejected_data["candidates"]
            if item["target_type"] == "fact"
        )
        assert repeated_rejected_data["diagnostics"]["skipped_reviewed_suggestion_count"] >= 1
        assert (
            repeated_rejected_data["diagnostics"]["skipped_reviewed_suggestion_status_counts"][
                "rejected"
            ]
            >= 1
        )

        manual_person = client.post(
            "/v1/anchors",
            json={
                "space_slug": "semantic-linking-quality",
                "memory_scope_external_ref": "default",
                "kind": "person",
                "label": "Alex Cooper",
                "aliases": ["@alex.cooper"],
                "confidence": "high",
            },
        )
        assert manual_person.status_code == 200, manual_person.text
        manual_person_id = manual_person.json()["data"]["id"]
        initial_capture = _capture(
            client,
            source_event_id="alex-cooper-initial-capture",
            text="Alex C. sent Project Atlas invoice threshold notes after the call.",
            thread_external_ref="quality-review",
        )
        initial_suggestions = client.post(
            "/v1/link-suggestions",
            json={
                "space_slug": "semantic-linking-quality",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "quality-review",
                "source_type": "capture",
                "source_id": initial_capture["id"],
                "text": "Alex C. Project Atlas invoice threshold notes",
                "persist": True,
                "limit": 30,
            },
        )
        assert initial_suggestions.status_code == 200, initial_suggestions.text
        initial_data = initial_suggestions.json()["data"]
        initial_anchor_candidates = [
            item for item in initial_data["candidates"] if item["target_type"] == "anchor"
        ]
        assert all(
            item["metadata"].get("normalized_key") != "alex c"
            for item in initial_anchor_candidates
            if item["metadata"].get("anchor_kind") == "person"
        )

        listed_people = client.get(
            "/v1/anchors",
            params={
                "space_slug": "semantic-linking-quality",
                "memory_scope_external_ref": "default",
                "kind": "person",
                "limit": 100,
            },
        )
        assert listed_people.status_code == 200, listed_people.text
        people_by_id = {item["id"]: item for item in listed_people.json()["data"]}
        assert people_by_id[manual_person_id]["normalized_key"] == "alex cooper"
        assert "Alex C" in people_by_id[manual_person_id]["aliases"]
        assert all(item["normalized_key"] != "alex c" for item in people_by_id.values())

        cross_scope_fact = _remember_fact(
            client,
            space_slug="semantic-linking-quality-private",
            text=(
                "Project Zephyr private renewal memo names Casey as owner for "
                "the vendor risk exception."
            ),
            source_id="zephyr-private-renewal",
        )
        cross_scope_capture = _capture(
            client,
            space_slug="semantic-linking-quality-query",
            source_event_id="zephyr-cross-scope-capture",
            text=(
                "Project Zephyr private renewal memo names Casey as owner for "
                "the vendor risk exception."
            ),
        )
        cross_scope_suggestions = client.post(
            "/v1/link-suggestions",
            json={
                "space_slug": "semantic-linking-quality-query",
                "memory_scope_external_ref": "default",
                "source_type": "capture",
                "source_id": cross_scope_capture["id"],
                "text": "Project Zephyr private renewal Casey vendor risk exception",
                "persist": True,
                "limit": 8,
            },
        )
        assert cross_scope_suggestions.status_code == 200, cross_scope_suggestions.text
        cross_scope_fact_candidates = [
            item
            for item in cross_scope_suggestions.json()["data"]["candidates"]
            if item["target_type"] == "fact"
        ]
        assert cross_scope_fact
        assert cross_scope_fact_candidates == []


def _remember_fact(
    client: httpx.Client,
    *,
    text: str,
    source_id: str,
    space_slug: str = "semantic-linking-quality",
) -> dict[str, object]:
    response = client.post(
        "/v1/facts",
        json={
            "space_slug": space_slug,
            "memory_scope_external_ref": "default",
            "thread_external_ref": "quality-review",
            "text": text,
            "kind": "note",
            "source_refs": [{"source_type": "manual", "source_id": source_id}],
        },
        headers={"Idempotency-Key": f"{space_slug}-{source_id}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _capture(
    client: httpx.Client,
    *,
    source_event_id: str,
    text: str,
    thread_external_ref: str | None = None,
    space_slug: str = "semantic-linking-quality",
) -> dict[str, object]:
    response = client.post(
        "/v1/captures",
        json={
            "space_slug": space_slug,
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


def _ingest_document(
    client: httpx.Client,
    *,
    title: str,
    text: str,
    source_external_id: str,
) -> dict[str, object]:
    response = client.post(
        "/v1/documents",
        json={
            "space_slug": "semantic-linking-quality",
            "memory_scope_external_ref": "default",
            "thread_external_ref": "document-review",
            "title": title,
            "text": text,
            "source_type": "document",
            "source_external_id": source_external_id,
            "classification": "internal",
        },
        headers={"Idempotency-Key": f"semantic-linking-quality-{source_external_id}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _candidate_score(candidates: list[dict[str, object]], target_id: str) -> float:
    for candidate in candidates:
        if candidate["target_id"] == target_id:
            return float(candidate["score"])
    return 0.0
