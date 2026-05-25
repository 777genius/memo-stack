import asyncio
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from memory_adapters.noop import (
    NoopEmbeddingAdapter,
    NoopGraphMemoryAdapter,
    NoopVectorMemoryAdapter,
)
from memory_core.application import (
    BuildContextQuery,
    BuildContextUseCase,
    EnsureScopeCommand,
    ForgetFactCommand,
)
from memory_core.domain.entities import ProfileId, SpaceId, TrustLevel
from memory_core.ports.adapters import (
    AdapterCapabilities,
    EmbeddingResult,
    GraphCandidate,
    GraphSearchResult,
    PortStatus,
    VectorCandidate,
    VectorSearchResult,
)
from memory_server.api.legacy_hackinterview import _legacy_trust
from memory_server.config import DeployProfile, MemoryPolicyMode, Settings
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


def make_client_with_settings(tmp_path: Path, **overrides: Any) -> TestClient:
    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'memory.db'}",
            auto_create_schema=True,
            service_token="test-token",
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
            **overrides,
        )
    )
    return TestClient(app)


def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def legacy_event(session_id: str, event_id: str, text: str) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "event_id": event_id,
        "source": "system_audio",
        "seq_start": 1,
        "seq_end": 1,
        "text": text,
        "language": "ru",
        "kind_hint": "constraint",
        "metadata": {
            "source_event_id": event_id,
            "explicit_interview_context": True,
            "attached_to_prompt": False,
            "final_answer": False,
            "request_scoped": False,
        },
    }


def test_legacy_unknown_source_maps_to_low_trust() -> None:
    assert _legacy_trust("unknown_screen_scraper") == TrustLevel.LOW


def test_legacy_ingest_context_duplicate_and_delete_session(tmp_path: Path) -> None:
    session_id = "legacy-session-1"
    with make_client(tmp_path) as client:
        created = client.post(
            "/api/v1/interview-memory/ingest",
            json=legacy_event(
                session_id,
                "event-constraint",
                "Проект Северный мост: нужна очередь FIFO, не стек LIFO.",
            ),
            headers=auth_headers(),
        )
        duplicate = client.post(
            "/api/v1/interview-memory/ingest",
            json=legacy_event(
                session_id,
                "event-constraint",
                "Проект Северный мост: нужна очередь FIFO, не стек LIFO.",
            ),
            headers=auth_headers(),
        )
        context = client.post(
            "/api/v1/interview-memory/context",
            json={
                "session_id": session_id,
                "context_snapshot_id": "ctx-test",
                "current_request": {
                    "id": "req-1",
                    "label": "request",
                    "text": "Что помнить про очередь?",
                },
                "budget_max_chars": 6000,
                "max_memory_results": 8,
            },
            headers=auth_headers(),
        )
        status_before = client.get(
            f"/api/v1/interview-memory/sessions/{session_id}/status",
            headers=auth_headers(),
        )
        deleted = client.delete(
            f"/api/v1/interview-memory/sessions/{session_id}",
            headers=auth_headers(),
        )
        status_after = client.get(
            f"/api/v1/interview-memory/sessions/{session_id}/status",
            headers=auth_headers(),
        )

    assert created.status_code == 200
    assert created.json()["data"]["durability"] == "durable"
    assert created.json()["data"]["stored_chunks"] == 1
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["stored_chunks"] == 0
    assert duplicate.json()["data"]["duplicate_chunks"] >= 1
    assert context.status_code == 200
    assert "Северный мост" in context.json()["data"]["text"]
    assert context.json()["data"]["artifact"]["context_snapshot_id"] == "ctx-test"
    assert status_before.json()["data"]["chunks"] == 1
    assert deleted.json()["data"]["deleted_chunks"] == 1
    assert status_after.json()["data"] == {
        "chunks": 0,
        "facts": 0,
        "jobs": 0,
        "pending_jobs": 0,
    }


def test_v1_episode_context_status_duplicate_and_delete_thread_memory(
    tmp_path: Path,
) -> None:
    scope = {
        "space_slug": "hackinterview",
        "profile_external_ref": "default",
        "thread_external_ref": "v1-session-1",
    }
    episode = {
        **scope,
        "source_type": "system_audio",
        "source_external_id": "v1-event-constraint",
        "text": "V1_EPISODE_MARKER: нужна очередь FIFO, не стек LIFO.",
        "language": "ru",
        "kind_hint": "constraint",
        "speaker": "interviewer",
        "trust_level": "medium",
        "metadata": {
            "source_event_id": "v1-event-constraint",
            "explicit_interview_context": True,
            "attached_to_prompt": False,
            "final_answer": False,
            "request_scoped": False,
        },
        "idempotency_key": "v1-event-constraint",
    }

    with make_client(tmp_path) as client:
        created = client.post("/v1/episodes", json=episode, headers=auth_headers())
        duplicate = client.post("/v1/episodes", json=episode, headers=auth_headers())
        secondary_created = client.post(
            "/v1/episodes",
            json={
                **episode,
                "profile_external_ref": "secondary",
                "thread_external_ref": "v1-session-1-secondary",
            },
            headers=auth_headers(),
        )
        resolved = asyncio.run(
            client.app.state.container.ensure_scope.execute(
                EnsureScopeCommand(
                    space_slug=scope["space_slug"],
                    profile_external_ref=scope["profile_external_ref"],
                    thread_external_ref=scope["thread_external_ref"],
                )
            )
        )
        scoped_fact = client.post(
            "/v1/facts",
            json={
                "space_id": str(resolved.space_id),
                "profile_id": str(resolved.profile_id),
                "thread_id": str(resolved.thread_id),
                "text": "V1_THREAD_DELETE_FACT_MARKER should enqueue graph cleanup.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "thread-delete-fact"}],
            },
            headers=auth_headers(),
        )
        context = client.post(
            "/v1/context",
            json={
                **scope,
                "query": "Что помнить про V1_EPISODE_MARKER и очередь?",
                "token_budget": 512,
                "max_chunks": 8,
            },
            headers=auth_headers(),
        )
        status_before = client.post(
            "/v1/thread-memory/status",
            json=scope,
            headers=auth_headers(),
        )
        deleted = client.request(
            "DELETE",
            "/v1/thread-memory",
            json=scope,
            headers=auth_headers(),
        )
        status_after = client.post(
            "/v1/thread-memory/status",
            json=scope,
            headers=auth_headers(),
        )
        diagnostics = client.get("/v1/diagnostics/outbox", headers=auth_headers())

    assert created.status_code == 200
    assert created.json()["data"]["durability"] == "durable"
    assert created.json()["data"]["stored_chunks"] == 1
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["stored_chunks"] == 0
    assert duplicate.json()["data"]["duplicate_chunks"] >= 1
    assert secondary_created.status_code == 200
    assert secondary_created.json()["data"]["stored_chunks"] == 1
    assert secondary_created.json()["data"]["episode_id"] != created.json()["data"]["episode_id"]
    assert scoped_fact.status_code == 201
    assert context.status_code == 200
    assert "V1_EPISODE_MARKER" in context.json()["data"]["rendered_text"]
    assert status_before.status_code == 200
    assert status_before.json()["data"]["chunks"] == 1
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted_chunks"] == 1
    assert deleted.json()["data"]["deleted_facts"] == 1
    assert deleted.json()["data"]["deleted_jobs"] == 2
    assert status_after.json()["data"] == {
        "chunks": 0,
        "facts": 0,
        "jobs": 0,
        "pending_jobs": 0,
    }
    event_types = [item["event_type"] for item in diagnostics.json()["data"]["items"]]
    assert "vector.delete_chunks" in event_types
    assert "graph.delete_fact" in event_types


def test_legacy_scope_creation_is_safe_under_parallel_sessions(tmp_path: Path) -> None:
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
    with TestClient(app):
        container = app.state.container

        async def create_scopes() -> list:
            return await asyncio.gather(
                *[
                    container.ensure_scope.execute(
                        EnsureScopeCommand(
                            space_slug="hackinterview",
                            profile_external_ref="default",
                            thread_external_ref=f"parallel-session-{index}",
                        )
                    )
                    for index in range(8)
                ]
            )

        results = asyncio.run(create_scopes())

    assert len({result.space_id for result in results}) == 1
    assert len({result.profile_id for result in results}) == 1
    assert len({result.thread_id for result in results}) == 8


def test_delete_session_only_removes_scoped_outbox_jobs(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        first = client.post(
            "/api/v1/interview-memory/ingest",
            json=legacy_event(
                "session-delete-a",
                "event-a",
                "Scoped delete A keeps only its own queue cleanup.",
            ),
            headers=auth_headers(),
        )
        second = client.post(
            "/api/v1/interview-memory/ingest",
            json=legacy_event(
                "session-delete-b",
                "event-b",
                "Scoped delete B must keep its own pending outbox job.",
            ),
            headers=auth_headers(),
        )
        first_status_before = client.get(
            "/api/v1/interview-memory/sessions/session-delete-a/status",
            headers=auth_headers(),
        )
        second_status_before = client.get(
            "/api/v1/interview-memory/sessions/session-delete-b/status",
            headers=auth_headers(),
        )
        deleted = client.delete(
            "/api/v1/interview-memory/sessions/session-delete-a",
            headers=auth_headers(),
        )
        first_status_after = client.get(
            "/api/v1/interview-memory/sessions/session-delete-a/status",
            headers=auth_headers(),
        )
        second_status_after = client.get(
            "/api/v1/interview-memory/sessions/session-delete-b/status",
            headers=auth_headers(),
        )
        diagnostics = client.get("/v1/diagnostics/outbox", headers=auth_headers())

    assert first.status_code == 200
    assert second.status_code == 200
    assert first_status_before.json()["data"]["jobs"] == 1
    assert second_status_before.json()["data"]["jobs"] == 1
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted_chunks"] == 1
    assert deleted.json()["data"]["deleted_jobs"] == 1
    assert first_status_after.json()["data"]["jobs"] == 0
    assert second_status_after.json()["data"]["chunks"] == 1
    assert second_status_after.json()["data"]["jobs"] == 1
    assert diagnostics.json()["data"]["counts"]["pending"] == 2


def test_legacy_ignores_low_trust_ai_and_request_scoped_microphone(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        ai = client.post(
            "/api/v1/interview-memory/ingest",
            json={
                **legacy_event(
                    "session-low-trust",
                    "ai-final",
                    "Черновой AI ответ: использовать стек.",
                ),
                "source": "ai_response",
                "metadata": {"final_answer": True},
            },
            headers=auth_headers(),
        )
        mic = client.post(
            "/api/v1/interview-memory/ingest",
            json={
                **legacy_event("session-low-trust", "mic-1", "Я думаю вслух, не интервью."),
                "source": "microphone",
                "metadata": {"explicit_interview_context": False},
            },
            headers=auth_headers(),
        )
        status = client.get(
            "/api/v1/interview-memory/sessions/session-low-trust/status",
            headers=auth_headers(),
        )

    assert ai.status_code == 200
    assert ai.json()["data"]["durability"] == "ignore"
    assert mic.status_code == 200
    assert mic.json()["data"]["durability"] == "request_scoped_only"
    assert status.json()["data"]["chunks"] == 0


def test_document_ingest_and_public_context_keyword_recall(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        document = client.post(
            "/v1/documents",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "title": "Architecture notes",
                "text": "Memory Platform uses Postgres as canonical truth. Qdrant is derived.",
                "source_type": "document",
                "source_external_id": "doc-1",
            },
            headers=auth_headers(),
        )
        document_id = document.json()["data"]["id"]
        loaded = client.get(f"/v1/documents/{document_id}", headers=auth_headers())
        context = client.post(
            "/v1/context",
            json={
                "space_id": "space_hackinterview",
                "profile_ids": ["profile_default"],
                "query": "What is canonical truth?",
                "token_budget": 512,
                "max_chunks": 4,
            },
            headers=auth_headers(),
        )

    assert document.status_code == 201
    assert document.json()["data"]["chunks"] == 1
    assert loaded.status_code == 200
    assert loaded.json()["data"]["id"] == document_id
    assert context.status_code == 200
    assert "Postgres as canonical truth" in context.json()["data"]["rendered_text"]


def test_v1_document_ingest_accepts_external_scope_and_thread_context(
    tmp_path: Path,
) -> None:
    scope = {
        "space_slug": "hackinterview",
        "profile_external_ref": "default",
        "thread_external_ref": "document-session-1",
    }
    with make_client(tmp_path) as client:
        document = client.post(
            "/v1/documents",
            json={
                **scope,
                "title": "Profile notes",
                "text": (
                    "V1_DOCUMENT_SCOPE_MARKER: импорт документа должен читаться из thread context."
                ),
                "source_type": "document",
                "source_external_id": "doc-external-scope",
            },
            headers=auth_headers(),
        )
        context = client.post(
            "/v1/context",
            json={
                **scope,
                "query": "Что сказано про V1_DOCUMENT_SCOPE_MARKER?",
                "token_budget": 512,
                "max_chunks": 4,
            },
            headers=auth_headers(),
        )

    assert document.status_code == 201
    assert document.json()["data"]["space_id"].startswith("space_")
    assert document.json()["data"]["profile_id"].startswith("profile_")
    assert document.json()["data"]["thread_id"] is not None
    assert context.status_code == 200
    assert "V1_DOCUMENT_SCOPE_MARKER" in context.json()["data"]["rendered_text"]


def test_thread_scoped_document_reimport_same_hash_stays_visible_per_thread(
    tmp_path: Path,
) -> None:
    first_scope = {
        "space_slug": "hackinterview",
        "profile_external_ref": "default",
        "thread_external_ref": "document-thread-a",
    }
    second_scope = {
        "space_slug": "hackinterview",
        "profile_external_ref": "default",
        "thread_external_ref": "document-thread-b",
    }
    document_text = (
        "THREAD_DOC_DEDUPE_MARKER must be independently visible in every thread import."
    )
    with make_client(tmp_path) as client:
        first = client.post(
            "/v1/documents",
            json={
                **first_scope,
                "title": "Thread scoped doc A",
                "text": document_text,
                "source_type": "document",
                "source_external_id": "same-source-document",
            },
            headers={**auth_headers(), "Idempotency-Key": "same-thread-doc-key"},
        )
        second = client.post(
            "/v1/documents",
            json={
                **second_scope,
                "title": "Thread scoped doc B",
                "text": document_text,
                "source_type": "document",
                "source_external_id": "same-source-document",
            },
            headers={**auth_headers(), "Idempotency-Key": "same-thread-doc-key"},
        )
        first_context = client.post(
            "/v1/context",
            json={**first_scope, "query": "THREAD_DOC_DEDUPE_MARKER", "token_budget": 512},
            headers=auth_headers(),
        )
        second_context = client.post(
            "/v1/context",
            json={**second_scope, "query": "THREAD_DOC_DEDUPE_MARKER", "token_budget": 512},
            headers=auth_headers(),
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["data"]["id"] != second.json()["data"]["id"]
    assert first_context.status_code == 200
    assert second_context.status_code == 200
    assert "THREAD_DOC_DEDUPE_MARKER" in first_context.json()["data"]["rendered_text"]
    assert "THREAD_DOC_DEDUPE_MARKER" in second_context.json()["data"]["rendered_text"]


def test_document_reimport_same_hash_is_noop_even_with_new_idempotency_key(
    tmp_path: Path,
) -> None:
    payload = {
        "space_id": "space_hackinterview",
        "profile_id": "profile_default",
        "title": "Reimport notes",
        "text": "DOC_REIMPORT_MARKER should only create one canonical document.",
        "source_type": "document",
        "source_external_id": "doc-reimport",
    }
    with make_client(tmp_path) as client:
        first = client.post(
            "/v1/documents",
            json=payload,
            headers={**auth_headers(), "Idempotency-Key": "doc-reimport-first"},
        )
        second = client.post(
            "/v1/documents",
            json=payload,
            headers={**auth_headers(), "Idempotency-Key": "doc-reimport-second"},
        )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["data"]["id"] == first.json()["data"]["id"]
    assert second.json()["data"]["duplicate_chunks"] == first.json()["data"]["chunks"]
    assert second.json()["data"]["indexing_status"] == "already_indexed_or_pending"


def test_document_reimport_same_hash_different_source_id_is_noop(tmp_path: Path) -> None:
    base_payload = {
        "space_id": "space_hackinterview",
        "profile_id": "profile_default",
        "title": "Same content notes",
        "text": "DOC_REIMPORT_SOURCE_MARKER should not duplicate chunks.",
        "source_type": "document",
    }
    with make_client(tmp_path) as client:
        first = client.post(
            "/v1/documents",
            json={**base_payload, "source_external_id": "doc-reimport-source-a"},
            headers=auth_headers(),
        )
        second = client.post(
            "/v1/documents",
            json={**base_payload, "source_external_id": "doc-reimport-source-b"},
            headers=auth_headers(),
        )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["data"]["id"] == first.json()["data"]["id"]
    assert second.json()["data"]["duplicate_chunks"] == first.json()["data"]["chunks"]
    assert second.json()["data"]["indexing_status"] == "already_indexed_or_pending"


def test_document_reimport_same_hash_different_profile_stays_isolated(
    tmp_path: Path,
) -> None:
    base_payload = {
        "space_id": "space_hackinterview",
        "title": "Shared source notes",
        "text": "DOC_REIMPORT_PROFILE_MARKER should stay scoped per profile.",
        "source_type": "document",
        "source_external_id": "doc-reimport-profile",
    }
    with make_client(tmp_path) as client:
        first = client.post(
            "/v1/documents",
            json={**base_payload, "profile_id": "profile_default"},
            headers={**auth_headers(), "Idempotency-Key": "profile-scoped-doc-key"},
        )
        second = client.post(
            "/v1/documents",
            json={**base_payload, "profile_id": "profile_secondary"},
            headers={**auth_headers(), "Idempotency-Key": "profile-scoped-doc-key"},
        )
        default_context = client.post(
            "/v1/context",
            json={
                "space_id": "space_hackinterview",
                "profile_ids": ["profile_default"],
                "query": "DOC_REIMPORT_PROFILE_MARKER",
                "token_budget": 512,
            },
            headers=auth_headers(),
        )
        secondary_context = client.post(
            "/v1/context",
            json={
                "space_id": "space_hackinterview",
                "profile_ids": ["profile_secondary"],
                "query": "DOC_REIMPORT_PROFILE_MARKER",
                "token_budget": 512,
            },
            headers=auth_headers(),
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["data"]["id"] != second.json()["data"]["id"]
    assert default_context.status_code == 200
    assert secondary_context.status_code == 200
    assert "Profile profile_default:" in default_context.json()["data"]["rendered_text"]
    assert "Profile profile_secondary:" in secondary_context.json()["data"]["rendered_text"]


def test_restricted_fact_and_document_are_excluded_from_context(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        document = client.post(
            "/v1/documents",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "title": "Restricted notes",
                "text": "RESTRICTED_DOC_MARKER must stay out of prompt context.",
                "source_type": "document",
                "source_external_id": "restricted-doc",
                "classification": "restricted",
            },
            headers=auth_headers(),
        )
        fact = client.post(
            "/v1/facts",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "text": "RESTRICTED_FACT_MARKER must stay out of prompt context.",
                "kind": "note",
                "classification": "restricted",
                "source_refs": [{"source_type": "manual", "source_id": "restricted-fact"}],
            },
            headers=auth_headers(),
        )
        context = client.post(
            "/v1/context",
            json={
                "space_id": "space_hackinterview",
                "profile_ids": ["profile_default"],
                "query": "RESTRICTED_DOC_MARKER RESTRICTED_FACT_MARKER",
                "token_budget": 512,
            },
            headers=auth_headers(),
        )

    assert document.status_code == 201
    assert document.json()["data"]["classification"] == "restricted"
    assert fact.status_code == 201
    assert context.status_code == 200
    rendered = context.json()["data"]["rendered_text"]
    assert "RESTRICTED_DOC_MARKER" not in rendered
    assert "RESTRICTED_FACT_MARKER" not in rendered


def test_delete_document_hides_chunks_and_enqueues_vector_delete(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        document = client.post(
            "/v1/documents",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "title": "Delete notes",
                "text": "DELETE_DOC_MARKER should disappear after document delete.",
                "source_type": "document",
                "source_external_id": "doc-delete",
            },
            headers=auth_headers(),
        )
        document_id = document.json()["data"]["id"]
        chunk = client.get(f"/v1/documents/{document_id}/chunks", headers=auth_headers()).json()[
            "data"
        ][0]
        fact = client.post(
            "/v1/facts",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "text": "DELETE_DOC_FACT_MARKER should disappear with its source document.",
                "kind": "note",
                "source_refs": [
                    {
                        "source_type": "document",
                        "source_id": document_id,
                        "chunk_id": chunk["id"],
                    }
                ],
            },
            headers=auth_headers(),
        )
        document_fact = client.post(
            "/v1/facts",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "text": "DELETE_DOC_WIDE_FACT_MARKER should disappear with document id source.",
                "kind": "note",
                "source_refs": [
                    {
                        "source_type": "document",
                        "source_id": document_id,
                    }
                ],
            },
            headers=auth_headers(),
        )
        before = client.post(
            "/v1/context",
            json={
                "space_id": "space_hackinterview",
                "profile_ids": ["profile_default"],
                "query": "DELETE_DOC_MARKER DELETE_DOC_FACT_MARKER DELETE_DOC_WIDE_FACT_MARKER",
                "token_budget": 512,
            },
            headers=auth_headers(),
        )
        deleted = client.delete(f"/v1/documents/{document_id}", headers=auth_headers())
        chunks = client.get(f"/v1/documents/{document_id}/chunks", headers=auth_headers())
        after = client.post(
            "/v1/context",
            json={
                "space_id": "space_hackinterview",
                "profile_ids": ["profile_default"],
                "query": "DELETE_DOC_MARKER DELETE_DOC_FACT_MARKER DELETE_DOC_WIDE_FACT_MARKER",
                "token_budget": 512,
            },
            headers=auth_headers(),
        )

    assert fact.status_code == 201
    assert document_fact.status_code == 201
    assert before.status_code == 200
    assert "DELETE_DOC_MARKER" in before.json()["data"]["rendered_text"]
    assert "DELETE_DOC_FACT_MARKER" in before.json()["data"]["rendered_text"]
    assert "DELETE_DOC_WIDE_FACT_MARKER" in before.json()["data"]["rendered_text"]
    assert deleted.status_code == 200
    assert deleted.json()["data"]["status"] == "deleted"
    assert deleted.json()["data"]["deleted_chunks"] == 1
    assert deleted.json()["data"]["deleted_facts"] == 2
    assert chunks.status_code == 200
    assert chunks.json()["data"] == []
    assert "DELETE_DOC_MARKER" not in after.json()["data"]["rendered_text"]
    assert "DELETE_DOC_FACT_MARKER" not in after.json()["data"]["rendered_text"]
    assert "DELETE_DOC_WIDE_FACT_MARKER" not in after.json()["data"]["rendered_text"]


def test_delete_document_does_not_delete_cross_profile_fact_refs(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        document = client.post(
            "/v1/documents",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "title": "Scoped delete notes",
                "text": "CROSS_PROFILE_DELETE_DOC_MARKER belongs to default profile.",
                "source_type": "document",
                "source_external_id": "doc-cross-profile-delete",
            },
            headers=auth_headers(),
        )
        document_id = document.json()["data"]["id"]
        chunk = client.get(f"/v1/documents/{document_id}/chunks", headers=auth_headers()).json()[
            "data"
        ][0]
        cross_profile_fact = client.post(
            "/v1/facts",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_secondary",
                "text": (
                    "CROSS_PROFILE_FACT_REF_MARKER must survive another "
                    "profile document delete."
                ),
                "kind": "note",
                "source_refs": [
                    {
                        "source_type": "document",
                        "source_id": document_id,
                        "chunk_id": chunk["id"],
                    }
                ],
            },
            headers=auth_headers(),
        )
        deleted = client.delete(f"/v1/documents/{document_id}", headers=auth_headers())
        secondary_context = client.post(
            "/v1/context",
            json={
                "space_id": "space_hackinterview",
                "profile_ids": ["profile_secondary"],
                "query": "CROSS_PROFILE_FACT_REF_MARKER",
                "token_budget": 512,
            },
            headers=auth_headers(),
        )

    assert document.status_code == 201
    assert cross_profile_fact.status_code == 201
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted_facts"] == 0
    assert "CROSS_PROFILE_FACT_REF_MARKER" in secondary_context.json()["data"]["rendered_text"]


def test_document_reimport_same_hash_after_delete_creates_new_active_document(
    tmp_path: Path,
) -> None:
    payload = {
        "space_slug": "hackinterview",
        "profile_external_ref": "default",
        "thread_external_ref": "doc-delete-reimport-thread",
        "title": "Reimport after delete",
        "text": "DELETE_REIMPORT_DOC_MARKER should be visible only from the new document.",
        "source_type": "document",
        "source_external_id": "delete-reimport-old-source",
    }
    with make_client(tmp_path) as client:
        first = client.post("/v1/documents", json=payload, headers=auth_headers())
        first_id = first.json()["data"]["id"]
        deleted = client.delete(f"/v1/documents/{first_id}", headers=auth_headers())
        second = client.post(
            "/v1/documents",
            json={**payload, "source_external_id": "delete-reimport-new-source"},
            headers=auth_headers(),
        )
        context = client.post(
            "/v1/context",
            json={
                "space_slug": "hackinterview",
                "profile_external_ref": "default",
                "thread_external_ref": "doc-delete-reimport-thread",
                "query": "DELETE_REIMPORT_DOC_MARKER",
                "token_budget": 512,
            },
            headers=auth_headers(),
        )

    assert first.status_code == 201
    assert deleted.status_code == 200
    assert second.status_code == 201
    assert second.json()["data"]["id"] != first_id
    assert second.json()["data"]["chunks"] == first.json()["data"]["chunks"]
    assert "DELETE_REIMPORT_DOC_MARKER" in context.json()["data"]["rendered_text"]


def test_process_document_reenqueues_active_chunks(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        document = client.post(
            "/v1/documents",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "title": "Process notes",
                "text": "PROCESS_DOC_MARKER should be reindexed on demand.",
                "source_type": "document",
                "source_external_id": "doc-process",
            },
            headers=auth_headers(),
        )
        document_id = document.json()["data"]["id"]
        processed = client.post(
            f"/v1/documents/{document_id}/process",
            headers={**auth_headers(), "Idempotency-Key": "process-doc-1"},
        )
        replay = client.post(
            f"/v1/documents/{document_id}/process",
            headers={**auth_headers(), "Idempotency-Key": "process-doc-1"},
        )
        diagnostics = client.get("/v1/diagnostics/outbox", headers=auth_headers())

    assert processed.status_code == 200
    assert processed.json()["data"]["id"] == document_id
    assert processed.json()["data"]["chunks"] == 1
    assert processed.json()["data"]["indexing_status"] == "pending"
    assert replay.status_code == 200
    assert replay.json()["data"]["id"] == document_id
    assert replay.json()["data"]["chunks"] == 1
    assert replay.json()["data"]["indexing_status"] == "already_indexed_or_pending"
    assert diagnostics.status_code == 200
    assert diagnostics.json()["data"]["counts"]["pending"] == 2


def test_process_document_idempotency_key_conflicts_on_different_document(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        first = client.post(
            "/v1/documents",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "title": "First process notes",
                "text": "First document process idempotency marker.",
                "source_type": "document",
                "source_external_id": "doc-process-first",
            },
            headers=auth_headers(),
        )
        second = client.post(
            "/v1/documents",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "title": "Second process notes",
                "text": "Second document process idempotency marker.",
                "source_type": "document",
                "source_external_id": "doc-process-second",
            },
            headers=auth_headers(),
        )
        first_id = first.json()["data"]["id"]
        second_id = second.json()["data"]["id"]
        processed = client.post(
            f"/v1/documents/{first_id}/process",
            headers={**auth_headers(), "Idempotency-Key": "process-shared-key"},
        )
        conflict = client.post(
            f"/v1/documents/{second_id}/process",
            headers={**auth_headers(), "Idempotency-Key": "process-shared-key"},
        )

    assert processed.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "memory.conflict"


def test_legacy_context_prioritizes_unique_terms_over_repeated_filler(
    tmp_path: Path,
) -> None:
    session_id = "legacy-retrieval-scoring"
    with make_client(tmp_path) as client:
        marker = client.post(
            "/api/v1/interview-memory/ingest",
            json=legacy_event(
                session_id,
                "scoring-marker",
                (
                    "DOCMEM_ALGO_TEST: для очереди событий нужно FIFO, не LIFO стек. "
                    "Целевая сложность O(n), без рекурсии."
                ),
            ),
            headers=auth_headers(),
        )
        filler_results = [
            client.post(
                "/api/v1/interview-memory/ingest",
                json=legacy_event(
                    session_id,
                    f"scoring-filler-{index}",
                    " ".join(["для"] * 260),
                ),
                headers=auth_headers(),
            )
            for index in range(12)
        ]
        context = client.post(
            "/api/v1/interview-memory/context",
            json={
                "session_id": session_id,
                "context_snapshot_id": "ctx-scoring",
                "current_request": {
                    "id": "req-scoring",
                    "label": "request",
                    "text": (
                        "Какое правило для очереди событий и сложности решения указано в документе?"
                    ),
                },
                "budget_max_chars": 3000,
                "max_memory_results": 4,
            },
            headers=auth_headers(),
        )

    assert marker.status_code == 200
    assert all(result.status_code == 200 for result in filler_results)
    assert context.status_code == 200
    assert "DOCMEM_ALGO_TEST" in context.json()["data"]["text"]


def test_fact_keyword_recall_searches_beyond_recent_limit(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        target = client.post(
            "/v1/facts",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "text": "DEEP_FACT_RECALL_MARKER: use a temporal graph only as derived evidence.",
                "kind": "architecture_decision",
                "source_refs": [{"source_type": "manual", "source_id": "deep-fact"}],
            },
            headers=auth_headers(),
        )
        filler_results = [
            client.post(
                "/v1/facts",
                json={
                    "space_id": "space_hackinterview",
                    "profile_id": "profile_default",
                    "text": f"Recent irrelevant memory filler {index}.",
                    "kind": "note",
                    "source_refs": [
                        {"source_type": "manual", "source_id": f"deep-fact-filler-{index}"}
                    ],
                },
                headers=auth_headers(),
            )
            for index in range(10)
        ]
        context = client.post(
            "/v1/context",
            json={
                "space_id": "space_hackinterview",
                "profile_ids": ["profile_default"],
                "query": "DEEP_FACT_RECALL_MARKER temporal graph evidence",
                "token_budget": 512,
                "max_facts": 1,
                "max_chunks": 0,
            },
            headers=auth_headers(),
        )

    assert target.status_code == 201
    assert all(result.status_code == 201 for result in filler_results)
    assert context.status_code == 200
    assert "DEEP_FACT_RECALL_MARKER" in context.json()["data"]["rendered_text"]
    assert len(context.json()["data"]["items"]) == 1


def test_chunk_keyword_recall_searches_beyond_recent_limit(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        target = client.post(
            "/v1/documents",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "title": "Deep chunk recall",
                "text": "DEEP_CHUNK_RECALL_MARKER: Graphiti is derived, Postgres stays canonical.",
                "source_type": "document",
                "source_external_id": "deep-chunk",
            },
            headers=auth_headers(),
        )
        filler_results = [
            client.post(
                "/v1/documents",
                json={
                    "space_id": "space_hackinterview",
                    "profile_id": "profile_default",
                    "title": f"Recent filler {index}",
                    "text": f"Recent irrelevant document filler {index}.",
                    "source_type": "document",
                    "source_external_id": f"deep-chunk-filler-{index}",
                },
                headers=auth_headers(),
            )
            for index in range(8)
        ]
        context = client.post(
            "/v1/context",
            json={
                "space_id": "space_hackinterview",
                "profile_ids": ["profile_default"],
                "query": "DEEP_CHUNK_RECALL_MARKER Graphiti canonical",
                "token_budget": 512,
                "max_facts": 0,
                "max_chunks": 1,
            },
            headers=auth_headers(),
        )

    assert target.status_code == 201
    assert all(result.status_code == 201 for result in filler_results)
    assert context.status_code == 200
    assert "DEEP_CHUNK_RECALL_MARKER" in context.json()["data"]["rendered_text"]
    assert len(context.json()["data"]["items"]) == 1


def test_public_context_respects_server_rendered_char_cap(tmp_path: Path) -> None:
    with make_client_with_settings(tmp_path, max_context_chars=1000) as client:
        created = [
            client.post(
                "/v1/facts",
                json={
                    "space_id": "space_hackinterview",
                    "profile_id": "profile_default",
                    "text": f"PUBLIC_CHAR_CAP_MARKER fact {index}. " + ("important details " * 20),
                    "kind": "note",
                    "source_refs": [
                        {"source_type": "manual", "source_id": f"public-char-cap-{index}"}
                    ],
                },
                headers=auth_headers(),
            )
            for index in range(8)
        ]
        context = client.post(
            "/v1/context",
            json={
                "space_id": "space_hackinterview",
                "profile_ids": ["profile_default"],
                "query": "PUBLIC_CHAR_CAP_MARKER",
                "token_budget": 16000,
                "max_facts": 8,
                "max_chunks": 0,
            },
            headers=auth_headers(),
        )

    rendered = context.json()["data"]["rendered_text"]
    diagnostics = context.json()["data"]["diagnostics"]
    assert all(response.status_code == 201 for response in created)
    assert context.status_code == 200
    assert len(rendered) <= 1000
    assert diagnostics["max_rendered_chars"] == 1000
    assert diagnostics["dropped_by_char_cap"] > 0


def test_context_filters_deleted_facts(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        fact = client.post(
            "/v1/facts",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "text": "Never render deleted fact marker.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "manual-delete"}],
            },
            headers=auth_headers(),
        )
        fact_id = fact.json()["data"]["id"]
        before = client.post(
            "/v1/context",
            json={
                "space_id": "space_hackinterview",
                "profile_ids": ["profile_default"],
                "query": "deleted fact marker",
                "token_budget": 512,
            },
            headers=auth_headers(),
        )
        deleted = client.delete(f"/v1/facts/{fact_id}", headers=auth_headers())
        after = client.post(
            "/v1/context",
            json={
                "space_id": "space_hackinterview",
                "profile_ids": ["profile_default"],
                "query": "deleted fact marker",
                "token_budget": 512,
            },
            headers=auth_headers(),
        )

    assert before.status_code == 200
    assert "Never render deleted fact marker" in before.json()["data"]["rendered_text"]
    assert deleted.status_code == 200
    assert "Never render deleted fact marker" not in after.json()["data"]["rendered_text"]


def test_multi_profile_context_keeps_profile_sections(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        first = client.post(
            "/v1/facts",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "text": "PROFILE_DEFAULT_MARKER owns fifo choice.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "profile-default"}],
            },
            headers=auth_headers(),
        )
        second = client.post(
            "/v1/facts",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_secondary",
                "text": "PROFILE_SECONDARY_MARKER owns queue constraint.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "profile-secondary"}],
            },
            headers=auth_headers(),
        )
        context = client.post(
            "/v1/context",
            json={
                "space_id": "space_hackinterview",
                "profile_ids": ["profile_default", "profile_secondary"],
                "query": "PROFILE_DEFAULT_MARKER PROFILE_SECONDARY_MARKER",
                "token_budget": 512,
            },
            headers=auth_headers(),
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert context.status_code == 200
    rendered = context.json()["data"]["rendered_text"]
    assert "Profile profile_default:" in rendered
    assert "Profile profile_secondary:" in rendered
    assert "PROFILE_DEFAULT_MARKER" in rendered
    assert "PROFILE_SECONDARY_MARKER" in rendered
    item_profiles = {item["diagnostics"]["profile_id"] for item in context.json()["data"]["items"]}
    item_profile_fields = {item["profile_id"] for item in context.json()["data"]["items"]}
    assert item_profiles == {"profile_default", "profile_secondary"}
    assert item_profile_fields == {"profile_default", "profile_secondary"}


def test_thread_context_includes_current_thread_and_profile_wide_facts_only(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        container = client.app.state.container
        current_scope = asyncio.run(
            container.ensure_scope.execute(
                EnsureScopeCommand(
                    space_slug="hackinterview",
                    profile_external_ref="default",
                    thread_external_ref="fact-thread-current",
                )
            )
        )
        other_scope = asyncio.run(
            container.ensure_scope.execute(
                EnsureScopeCommand(
                    space_slug="hackinterview",
                    profile_external_ref="default",
                    thread_external_ref="fact-thread-other",
                )
            )
        )
        current_fact = client.post(
            "/v1/facts",
            json={
                "space_id": str(current_scope.space_id),
                "profile_id": str(current_scope.profile_id),
                "thread_id": str(current_scope.thread_id),
                "text": "THREAD_SCOPE_MARKER current thread fact.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "current-thread"}],
            },
            headers=auth_headers(),
        )
        other_fact = client.post(
            "/v1/facts",
            json={
                "space_id": str(other_scope.space_id),
                "profile_id": str(other_scope.profile_id),
                "thread_id": str(other_scope.thread_id),
                "text": "THREAD_SCOPE_MARKER wrong other thread fact.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "other-thread"}],
            },
            headers=auth_headers(),
        )
        profile_fact = client.post(
            "/v1/facts",
            json={
                "space_id": str(current_scope.space_id),
                "profile_id": str(current_scope.profile_id),
                "text": "THREAD_SCOPE_MARKER profile-wide fact.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "profile-wide"}],
            },
            headers=auth_headers(),
        )
        context = client.post(
            "/v1/context",
            json={
                "space_id": str(current_scope.space_id),
                "profile_ids": [str(current_scope.profile_id)],
                "thread_id": str(current_scope.thread_id),
                "query": "THREAD_SCOPE_MARKER",
                "token_budget": 512,
                "max_facts": 8,
            },
            headers=auth_headers(),
        )

    assert current_fact.status_code == 201
    assert other_fact.status_code == 201
    assert profile_fact.status_code == 201
    assert context.status_code == 200
    rendered = context.json()["data"]["rendered_text"]
    assert "THREAD_SCOPE_MARKER current thread fact." in rendered
    assert "THREAD_SCOPE_MARKER profile-wide fact." in rendered
    assert "THREAD_SCOPE_MARKER wrong other thread fact." not in rendered


class FakeGraphAdapter:
    def __init__(self, fact_id: str) -> None:
        self._fact_id = fact_id

    async def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            name="fake-graph",
            enabled=True,
            healthy=True,
            supports_upsert=True,
            supports_delete=True,
            supports_search=True,
            supports_filters=True,
            supports_temporal_queries=True,
        )

    async def search(self, **_kwargs: object) -> GraphSearchResult:
        return GraphSearchResult.ok(
            [
                GraphCandidate(
                    source_fact_ids=(self._fact_id,),
                    source_chunk_ids=(),
                    relation_label="test",
                    score=1.0,
                    diagnostics={},
                )
            ]
        )


class FakeEmbeddingAdapter:
    async def embed_texts(self, *_args: object, **_kwargs: object) -> EmbeddingResult:
        return EmbeddingResult(status=PortStatus.OK, vectors=((0.1, 0.2, 0.3),))


class FakeVectorAdapter:
    def __init__(self, chunk_id: str) -> None:
        self._chunk_id = chunk_id

    async def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            name="fake-vector",
            enabled=True,
            healthy=True,
            supports_upsert=True,
            supports_delete=True,
            supports_search=True,
            supports_filters=True,
        )

    async def search_chunks(self, **_kwargs: object) -> VectorSearchResult:
        return VectorSearchResult.ok(
            [
                VectorCandidate(
                    chunk_id=self._chunk_id,
                    space_id="",
                    profile_id="",
                    score=1.0,
                    projection_version="test",
                )
            ]
        )


def test_context_does_not_embed_when_vector_adapter_is_disabled(tmp_path: Path) -> None:
    class FailingEmbeddingAdapter:
        calls = 0

        async def embed_texts(self, *_args: object, **_kwargs: object) -> EmbeddingResult:
            self.calls += 1
            raise AssertionError("disabled vector retrieval must not call embeddings")

    with make_client(tmp_path) as client:
        embedder = FailingEmbeddingAdapter()
        container = client.app.state.container
        use_case = BuildContextUseCase(
            uow_factory=container.uow_factory,
            ids=container.ids,
            vector_index=NoopVectorMemoryAdapter(),
            graph_index=NoopGraphMemoryAdapter(),
            embedder=embedder,
        )
        context = asyncio.run(
            use_case.execute(
                BuildContextQuery(
                    space_id=SpaceId("space_hackinterview"),
                    profile_ids=(ProfileId("profile_default"),),
                    query="VECTOR_DISABLED_COST_GUARD",
                    token_budget=512,
                )
            )
        )

    assert embedder.calls == 0
    assert context.diagnostics["vector_status"] == "disabled"
    assert context.diagnostics["vector_degraded_reason"] == "disabled"


def test_context_marks_unavailable_vector_adapter_degraded_without_embedding(
    tmp_path: Path,
) -> None:
    class UnavailableVectorAdapter:
        async def capabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                name="qdrant",
                enabled=False,
                healthy=True,
                supports_upsert=False,
                supports_delete=False,
                supports_search=False,
                supports_filters=False,
                degraded_reason="qdrant_sdk_missing",
            )

        async def search_chunks(self, **_kwargs: object) -> VectorSearchResult:
            raise AssertionError("unavailable vector adapter must not be searched")

    class FailingEmbeddingAdapter:
        calls = 0

        async def embed_texts(self, *_args: object, **_kwargs: object) -> EmbeddingResult:
            self.calls += 1
            raise AssertionError("unavailable vector retrieval must not call embeddings")

    with make_client(tmp_path) as client:
        embedder = FailingEmbeddingAdapter()
        container = client.app.state.container
        use_case = BuildContextUseCase(
            uow_factory=container.uow_factory,
            ids=container.ids,
            vector_index=UnavailableVectorAdapter(),
            graph_index=NoopGraphMemoryAdapter(),
            embedder=embedder,
        )
        context = asyncio.run(
            use_case.execute(
                BuildContextQuery(
                    space_id=SpaceId("space_hackinterview"),
                    profile_ids=(ProfileId("profile_default"),),
                    query="VECTOR_UNAVAILABLE_COST_GUARD",
                    token_budget=512,
                )
            )
        )

    assert embedder.calls == 0
    assert context.diagnostics["vector_status"] == "degraded"
    assert context.diagnostics["vector_degraded_reason"] == "qdrant_sdk_missing"


def test_context_does_not_search_when_graph_adapter_is_disabled(tmp_path: Path) -> None:
    class DisabledGraphAdapter:
        async def capabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                name="graphiti",
                enabled=False,
                healthy=True,
                supports_upsert=False,
                supports_delete=False,
                supports_search=False,
                supports_filters=False,
                supports_temporal_queries=False,
                degraded_reason="disabled",
            )

        async def search(self, **_kwargs: object) -> GraphSearchResult:
            raise AssertionError("disabled graph retrieval must not call search")

    with make_client(tmp_path) as client:
        container = client.app.state.container
        use_case = BuildContextUseCase(
            uow_factory=container.uow_factory,
            ids=container.ids,
            vector_index=NoopVectorMemoryAdapter(),
            graph_index=DisabledGraphAdapter(),
            embedder=NoopEmbeddingAdapter(),
        )
        context = asyncio.run(
            use_case.execute(
                BuildContextQuery(
                    space_id=SpaceId("space_hackinterview"),
                    profile_ids=(ProfileId("profile_default"),),
                    query="GRAPH_DISABLED_COST_GUARD",
                    token_budget=512,
                )
            )
        )

    assert context.diagnostics["graph_status"] == "disabled"
    assert context.diagnostics["graph_degraded_reason"] == "disabled"


def test_context_marks_unavailable_graph_adapter_degraded_without_search(
    tmp_path: Path,
) -> None:
    class UnavailableGraphAdapter:
        async def capabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                name="graphiti",
                enabled=False,
                healthy=False,
                supports_upsert=False,
                supports_delete=False,
                supports_search=False,
                supports_filters=False,
                supports_temporal_queries=True,
                degraded_reason="graphiti_unavailable",
            )

        async def search(self, **_kwargs: object) -> GraphSearchResult:
            raise AssertionError("unavailable graph retrieval must not call search")

    with make_client(tmp_path) as client:
        container = client.app.state.container
        use_case = BuildContextUseCase(
            uow_factory=container.uow_factory,
            ids=container.ids,
            vector_index=NoopVectorMemoryAdapter(),
            graph_index=UnavailableGraphAdapter(),
            embedder=NoopEmbeddingAdapter(),
        )
        context = asyncio.run(
            use_case.execute(
                BuildContextQuery(
                    space_id=SpaceId("space_hackinterview"),
                    profile_ids=(ProfileId("profile_default"),),
                    query="GRAPH_UNAVAILABLE_COST_GUARD",
                    token_budget=512,
                )
            )
        )

    assert context.diagnostics["graph_status"] == "degraded"
    assert context.diagnostics["graph_degraded_reason"] == "graphiti_unavailable"


def test_context_revalidates_direct_facts_after_adapter_delay(tmp_path: Path) -> None:
    class EmptyEnabledVectorAdapter:
        async def capabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                name="fake-vector",
                enabled=True,
                healthy=True,
                supports_upsert=True,
                supports_delete=True,
                supports_search=True,
                supports_filters=True,
            )

        async def search_chunks(self, **_kwargs: object) -> VectorSearchResult:
            return VectorSearchResult.ok([])

    class ForgetDuringEmbeddingAdapter:
        def __init__(self, container, fact_id: str) -> None:
            self._container = container
            self._fact_id = fact_id

        async def embed_texts(self, *_args: object, **_kwargs: object) -> EmbeddingResult:
            await self._container.forget_fact.execute(ForgetFactCommand(fact_id=self._fact_id))
            return EmbeddingResult.degraded("test.embedding_disabled", retryable=False)

    with make_client(tmp_path) as client:
        fact = client.post(
            "/v1/facts",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "text": "RACE_DELETE_FACT_MARKER must not survive final context validation.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "race-delete"}],
            },
            headers=auth_headers(),
        )
        fact_id = fact.json()["data"]["id"]
        container = client.app.state.container
        use_case = BuildContextUseCase(
            uow_factory=container.uow_factory,
            ids=container.ids,
            vector_index=EmptyEnabledVectorAdapter(),
            graph_index=NoopGraphMemoryAdapter(),
            embedder=ForgetDuringEmbeddingAdapter(container, fact_id),
        )
        context = asyncio.run(
            use_case.execute(
                BuildContextQuery(
                    space_id=SpaceId("space_hackinterview"),
                    profile_ids=(ProfileId("profile_default"),),
                    query="RACE_DELETE_FACT_MARKER",
                    token_budget=512,
                )
            )
        )

    assert fact.status_code == 201
    assert "RACE_DELETE_FACT_MARKER" not in context.rendered_text
    assert context.items == ()


def test_graph_candidates_are_hydrated_and_deleted_facts_are_filtered(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        fact = client.post(
            "/v1/facts",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "text": "Graph-only canonical memory marker.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "manual-graph"}],
            },
            headers=auth_headers(),
        )
        fact_id = fact.json()["data"]["id"]
        container = client.app.state.container
        use_case = BuildContextUseCase(
            uow_factory=container.uow_factory,
            ids=container.ids,
            vector_index=NoopVectorMemoryAdapter(),
            graph_index=FakeGraphAdapter(fact_id),
            embedder=NoopEmbeddingAdapter(),
        )
        active = asyncio.run(
            use_case.execute(
                BuildContextQuery(
                    space_id=SpaceId("space_hackinterview"),
                    profile_ids=(ProfileId("profile_default"),),
                    query="unrelated graph query",
                    token_budget=512,
                )
            )
        )
        client.delete(f"/v1/facts/{fact_id}", headers=auth_headers())
        deleted = asyncio.run(
            use_case.execute(
                BuildContextQuery(
                    space_id=SpaceId("space_hackinterview"),
                    profile_ids=(ProfileId("profile_default"),),
                    query="unrelated graph query",
                    token_budget=512,
                )
            )
        )

    assert "Graph-only canonical memory marker" in active.rendered_text
    assert active.diagnostics["stale_graph_drop_count"] == 0
    assert "Graph-only canonical memory marker" not in deleted.rendered_text
    assert deleted.diagnostics["stale_graph_drop_count"] == 1


def test_graph_candidates_from_same_profile_wrong_thread_are_filtered(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        container = client.app.state.container
        current_scope = asyncio.run(
            container.ensure_scope.execute(
                EnsureScopeCommand(
                    space_slug="hackinterview",
                    profile_external_ref="default",
                    thread_external_ref="graph-thread-current",
                )
            )
        )
        other_scope = asyncio.run(
            container.ensure_scope.execute(
                EnsureScopeCommand(
                    space_slug="hackinterview",
                    profile_external_ref="default",
                    thread_external_ref="graph-thread-other",
                )
            )
        )
        fact = client.post(
            "/v1/facts",
            json={
                "space_id": str(other_scope.space_id),
                "profile_id": str(other_scope.profile_id),
                "thread_id": str(other_scope.thread_id),
                "text": "WRONG_THREAD_GRAPH_MARKER must not hydrate into current context.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "wrong-thread-graph"}],
            },
            headers=auth_headers(),
        )
        use_case = BuildContextUseCase(
            uow_factory=container.uow_factory,
            ids=container.ids,
            vector_index=NoopVectorMemoryAdapter(),
            graph_index=FakeGraphAdapter(fact.json()["data"]["id"]),
            embedder=NoopEmbeddingAdapter(),
        )
        context = asyncio.run(
            use_case.execute(
                BuildContextQuery(
                    space_id=current_scope.space_id,
                    profile_ids=(current_scope.profile_id,),
                    thread_id=current_scope.thread_id,
                    query="unrelated graph query",
                    token_budget=512,
                )
            )
        )

    assert fact.status_code == 201
    assert "WRONG_THREAD_GRAPH_MARKER" not in context.rendered_text
    assert context.diagnostics["stale_graph_drop_count"] == 1


def test_vector_candidates_are_hydrated_and_deleted_chunks_are_filtered(tmp_path: Path) -> None:
    session_id = "vector-stale-session"
    with make_client(tmp_path) as client:
        client.post(
            "/api/v1/interview-memory/ingest",
            json=legacy_event(
                session_id,
                "vector-event",
                "VECTOR_ONLY_MARKER: hydrate this only through canonical chunk.",
            ),
            headers=auth_headers(),
        )
        container = client.app.state.container
        scope = asyncio.run(
            container.ensure_scope.execute(
                EnsureScopeCommand(
                    space_slug=container.settings.default_space_slug,
                    profile_external_ref=container.settings.default_profile_external_ref,
                    thread_external_ref=session_id,
                )
            )
        )
        chunk_id = asyncio.run(_first_chunk_id(container, scope, "VECTOR_ONLY_MARKER"))
        use_case = BuildContextUseCase(
            uow_factory=container.uow_factory,
            ids=container.ids,
            vector_index=FakeVectorAdapter(chunk_id),
            graph_index=NoopGraphMemoryAdapter(),
            embedder=FakeEmbeddingAdapter(),
        )
        active = asyncio.run(
            use_case.execute(
                BuildContextQuery(
                    space_id=scope.space_id,
                    profile_ids=(scope.profile_id,),
                    thread_id=scope.thread_id,
                    query="unrelated vector query",
                    token_budget=512,
                )
            )
        )
        client.delete(f"/api/v1/interview-memory/sessions/{session_id}", headers=auth_headers())
        deleted = asyncio.run(
            use_case.execute(
                BuildContextQuery(
                    space_id=scope.space_id,
                    profile_ids=(scope.profile_id,),
                    thread_id=scope.thread_id,
                    query="unrelated vector query",
                    token_budget=512,
                )
            )
        )

    assert "VECTOR_ONLY_MARKER" in active.rendered_text
    assert active.diagnostics["stale_vector_drop_count"] == 0
    assert "VECTOR_ONLY_MARKER" not in deleted.rendered_text
    assert deleted.diagnostics["stale_vector_drop_count"] == 1


def test_vector_candidates_from_same_profile_wrong_thread_are_filtered(
    tmp_path: Path,
) -> None:
    current_session_id = "vector-thread-current"
    other_session_id = "vector-thread-other"
    with make_client(tmp_path) as client:
        container = client.app.state.container
        current_scope = asyncio.run(
            container.ensure_scope.execute(
                EnsureScopeCommand(
                    space_slug=container.settings.default_space_slug,
                    profile_external_ref=container.settings.default_profile_external_ref,
                    thread_external_ref=current_session_id,
                )
            )
        )
        client.post(
            "/api/v1/interview-memory/ingest",
            json=legacy_event(
                other_session_id,
                "wrong-thread-vector-event",
                "WRONG_THREAD_VECTOR_MARKER must not hydrate into current context.",
            ),
            headers=auth_headers(),
        )
        other_scope = asyncio.run(
            container.ensure_scope.execute(
                EnsureScopeCommand(
                    space_slug=container.settings.default_space_slug,
                    profile_external_ref=container.settings.default_profile_external_ref,
                    thread_external_ref=other_session_id,
                )
            )
        )
        other_chunk_id = asyncio.run(
            _first_chunk_id(container, other_scope, "WRONG_THREAD_VECTOR_MARKER")
        )
        use_case = BuildContextUseCase(
            uow_factory=container.uow_factory,
            ids=container.ids,
            vector_index=FakeVectorAdapter(other_chunk_id),
            graph_index=NoopGraphMemoryAdapter(),
            embedder=FakeEmbeddingAdapter(),
        )
        context = asyncio.run(
            use_case.execute(
                BuildContextQuery(
                    space_id=current_scope.space_id,
                    profile_ids=(current_scope.profile_id,),
                    thread_id=current_scope.thread_id,
                    query="unrelated vector query",
                    token_budget=512,
                )
            )
        )

    assert "WRONG_THREAD_VECTOR_MARKER" not in context.rendered_text
    assert context.diagnostics["stale_vector_drop_count"] == 1


def test_disabled_policy_returns_no_legacy_memory_or_public_context(tmp_path: Path) -> None:
    with make_client_with_settings(tmp_path, policy_mode=MemoryPolicyMode.DISABLED) as client:
        ingest = client.post(
            "/api/v1/interview-memory/ingest",
            json=legacy_event("policy-disabled", "event-disabled", "POLICY_DISABLED_MARKER"),
            headers=auth_headers(),
        )
        context = client.post(
            "/v1/context",
            json={
                "space_id": "space_hackinterview",
                "profile_ids": ["profile_default"],
                "query": "POLICY_DISABLED_MARKER",
                "token_budget": 512,
            },
            headers=auth_headers(),
        )
        legacy_context = client.post(
            "/api/v1/interview-memory/context",
            json={
                "session_id": "policy-disabled",
                "context_snapshot_id": "ctx-policy-disabled",
                "current_request": {
                    "id": "req-1",
                    "label": "request",
                    "text": "current hard context only",
                },
                "budget_max_chars": 6000,
                "max_memory_results": 8,
            },
            headers=auth_headers(),
        )

    assert ingest.status_code == 200
    assert ingest.json()["data"]["durability"] == "ignore"
    assert context.status_code == 200
    assert context.json()["data"]["items"] == []
    assert context.json()["data"]["diagnostics"]["retrieval_disabled"] is True
    assert legacy_context.status_code == 200
    assert "current hard context only" in legacy_context.json()["data"]["text"]
    assert "POLICY_DISABLED_MARKER" not in legacy_context.json()["data"]["text"]


async def _first_chunk_id(container, scope, query: str) -> str:
    async with container.uow_factory() as uow:
        chunks = await uow.chunks.keyword_search(
            space_id=str(scope.space_id),
            profile_ids=(str(scope.profile_id),),
            thread_id=str(scope.thread_id) if scope.thread_id else None,
            query=query,
            limit=1,
        )
    return str(chunks[0].id)
