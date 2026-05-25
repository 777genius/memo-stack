import asyncio
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from memory_adapters.postgres import create_schema
from memory_adapters.postgres.models import MemoryOutboxRow
from memory_core.ports.adapters import AdapterCapabilities, VectorWriteResult
from memory_server.admin import seed_defaults
from memory_server.composition import build_container
from memory_server.config import DeployProfile, Settings
from memory_server.db import upgrade
from memory_server.doctor import run_doctor
from memory_server.eval import run_small_golden
from memory_server.main import create_app
from memory_server.worker import OutboxWorker, _safe_error
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession


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


def fact_payload(text: str = "Graph jobs stay safe when Graphiti is disabled.") -> dict[str, Any]:
    return {
        "space_id": "space_hackinterview",
        "profile_id": "profile_default",
        "text": text,
        "kind": "architecture_decision",
        "source_refs": [{"source_type": "manual", "source_id": "worker-test"}],
    }


async def outbox_statuses(client: TestClient) -> list[str]:
    engine = client.app.state.container.engine
    async with AsyncSession(engine) as session:
        return list(
            (
                await session.execute(select(MemoryOutboxRow.status).order_by(MemoryOutboxRow.id))
            ).scalars()
        )


def test_outbox_worker_no_pending_jobs_is_stable(tmp_path: Path) -> None:
    async def run() -> int:
        container = build_container(
            Settings(
                deploy_profile=DeployProfile.TEST,
                database_url=f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}",
                service_token="test-token",
            )
        )
        await create_schema(container.engine)
        return await OutboxWorker(container).run_once(limit=10)

    assert asyncio.run(run()) == 0


def test_outbox_worker_marks_disabled_projection_jobs_done(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        created = client.post("/v1/facts", json=fact_payload(), headers=auth_headers())
        processed = asyncio.run(OutboxWorker(client.app.state.container).run_once(limit=10))
        statuses = asyncio.run(outbox_statuses(client))

    assert created.status_code == 201
    assert processed == 1
    assert statuses == ["done"]


def test_expired_running_outbox_job_is_recovered_and_processed(tmp_path: Path) -> None:
    async def run() -> tuple[int, str, int, str | None]:
        container = build_container(
            Settings(
                deploy_profile=DeployProfile.TEST,
                database_url=f"sqlite+aiosqlite:///{tmp_path / 'expired-running.db'}",
                service_token="test-token",
            )
        )
        await create_schema(container.engine)
        now = container.clock.now()
        async with AsyncSession(container.engine) as session:
            session.add(
                MemoryOutboxRow(
                    event_type="graph.delete_fact",
                    aggregate_type="fact",
                    aggregate_id="fact_missing_after_worker_crash",
                    aggregate_version=None,
                    payload_json={},
                    status="running",
                    attempt_count=0,
                    next_attempt_at=now + timedelta(hours=1),
                    last_safe_error="Previous worker crashed mid-job",
                    created_at=now - timedelta(minutes=10),
                    updated_at=now - timedelta(minutes=6),
                )
            )
            await session.commit()

        processed = await OutboxWorker(container).run_once(limit=10)
        async with AsyncSession(container.engine) as session:
            row = (
                await session.execute(select(MemoryOutboxRow).where(MemoryOutboxRow.id == 1))
            ).scalar_one()
            return processed, row.status, row.attempt_count, row.last_safe_error

    processed, status, attempt_count, last_safe_error = asyncio.run(run())

    assert processed == 1
    assert status == "done"
    assert attempt_count == 1
    assert last_safe_error is None


def test_thread_cleanup_graph_delete_uses_payload_fact_id(tmp_path: Path) -> None:
    class RecordingGraphAdapter:
        def __init__(self) -> None:
            self.deleted_fact_ids: list[str] = []

        async def delete_fact(self, fact_id: str) -> VectorWriteResult:
            self.deleted_fact_ids.append(fact_id)
            return VectorWriteResult.ok(1)

    async def run() -> tuple[int, tuple[str, ...], str]:
        container = build_container(
            Settings(
                deploy_profile=DeployProfile.TEST,
                database_url=f"sqlite+aiosqlite:///{tmp_path / 'thread-cleanup.db'}",
                service_token="test-token",
            )
        )
        await create_schema(container.engine)
        graph = RecordingGraphAdapter()
        object.__setattr__(container, "graph_index", graph)
        now = container.clock.now()
        async with AsyncSession(container.engine) as session:
            session.add(
                MemoryOutboxRow(
                    event_type="graph.delete_fact",
                    aggregate_type="thread",
                    aggregate_id="thread_deleted_session",
                    aggregate_version=None,
                    payload_json={"fact_id": "fact_deleted_by_thread_cleanup"},
                    status="pending",
                    attempt_count=0,
                    next_attempt_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

        processed = await OutboxWorker(container).run_once(limit=10)
        async with AsyncSession(container.engine) as session:
            status = (
                await session.execute(select(MemoryOutboxRow.status).where(MemoryOutboxRow.id == 1))
            ).scalar_one()
        return processed, tuple(graph.deleted_fact_ids), status

    processed, deleted_fact_ids, status = asyncio.run(run())

    assert processed == 1
    assert deleted_fact_ids == ("fact_deleted_by_thread_cleanup",)
    assert status == "done"


def test_expired_running_outbox_job_becomes_dead_after_max_attempts(tmp_path: Path) -> None:
    async def run() -> tuple[int, str, int, str | None]:
        container = build_container(
            Settings(
                deploy_profile=DeployProfile.TEST,
                database_url=f"sqlite+aiosqlite:///{tmp_path / 'expired-running-dead.db'}",
                service_token="test-token",
            )
        )
        await create_schema(container.engine)
        now = container.clock.now()
        async with AsyncSession(container.engine) as session:
            session.add(
                MemoryOutboxRow(
                    event_type="graph.delete_fact",
                    aggregate_type="fact",
                    aggregate_id="fact_repeated_worker_crash",
                    aggregate_version=None,
                    payload_json={},
                    status="running",
                    attempt_count=4,
                    next_attempt_at=now + timedelta(hours=1),
                    last_safe_error="Previous worker crashed mid-job",
                    created_at=now - timedelta(minutes=20),
                    updated_at=now - timedelta(minutes=6),
                )
            )
            await session.commit()

        processed = await OutboxWorker(container).run_once(limit=10)
        async with AsyncSession(container.engine) as session:
            row = (
                await session.execute(select(MemoryOutboxRow).where(MemoryOutboxRow.id == 1))
            ).scalar_one()
            return processed, row.status, row.attempt_count, row.last_safe_error

    processed, status, attempt_count, last_safe_error = asyncio.run(run())

    assert processed == 0
    assert status == "dead"
    assert attempt_count == 5
    assert last_safe_error == "Worker lease expired"


def test_unknown_document_is_not_embedded_but_job_completes(tmp_path: Path) -> None:
    class FailingEmbedder:
        calls = 0

        async def embed_texts(self, _texts):
            self.calls += 1
            raise AssertionError("unknown documents must not be embedded")

    with make_client(tmp_path) as client:
        created = client.post(
            "/v1/documents",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "title": "Unknown document",
                "text": "UNKNOWN_CLASSIFICATION_MARKER should be stored only.",
                "source_type": "document",
                "source_external_id": "unknown-doc",
            },
            headers=auth_headers(),
        )
        embedder = FailingEmbedder()
        object.__setattr__(client.app.state.container, "embedder", embedder)
        processed = asyncio.run(OutboxWorker(client.app.state.container).run_once(limit=10))
        statuses = asyncio.run(outbox_statuses(client))

    assert created.status_code == 201
    assert created.json()["data"]["classification"] == "unknown"
    assert processed == 1
    assert statuses == ["done"]
    assert embedder.calls == 0


def test_vector_disabled_internal_document_job_skips_embedding_and_completes(
    tmp_path: Path,
) -> None:
    class FailingEmbedder:
        calls = 0

        async def embed_texts(self, _texts):
            self.calls += 1
            raise AssertionError("disabled vector projection must not call embeddings")

    with make_client(tmp_path) as client:
        created = client.post(
            "/v1/documents",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "title": "Internal document",
                "text": "VECTOR_DISABLED_INTERNAL_DOC_MARKER should stay canonical only.",
                "source_type": "document",
                "source_external_id": "internal-vector-disabled-doc",
                "classification": "internal",
            },
            headers=auth_headers(),
        )
        embedder = FailingEmbedder()
        object.__setattr__(client.app.state.container, "embedder", embedder)
        processed = asyncio.run(OutboxWorker(client.app.state.container).run_once(limit=10))
        statuses = asyncio.run(outbox_statuses(client))

    assert created.status_code == 201
    assert processed == 1
    assert statuses == ["done"]
    assert embedder.calls == 0


def test_unhealthy_vector_projection_retries_without_embedding_cost(tmp_path: Path) -> None:
    class UnhealthyVectorAdapter:
        async def capabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities(
                name="qdrant",
                enabled=True,
                healthy=False,
                supports_upsert=False,
                supports_delete=True,
                supports_search=False,
                supports_filters=True,
                degraded_reason="qdrant.timeout",
            )

        async def upsert_chunks(self, *_args: object, **_kwargs: object) -> VectorWriteResult:
            raise AssertionError("unhealthy vector adapter must fail before upsert")

        async def delete_chunks(self, *_args: object, **_kwargs: object) -> VectorWriteResult:
            raise AssertionError("delete should not be called for active chunks")

    class FailingEmbedder:
        calls = 0

        async def embed_texts(self, _texts):
            self.calls += 1
            raise AssertionError("unhealthy vector projection must not call embeddings")

    async def row_state(client: TestClient) -> tuple[str, int, str | None]:
        engine = client.app.state.container.engine
        async with AsyncSession(engine) as session:
            row = (
                await session.execute(select(MemoryOutboxRow).order_by(MemoryOutboxRow.id))
            ).scalar_one()
            return row.status, row.attempt_count, row.last_safe_error

    with make_client(tmp_path) as client:
        created = client.post(
            "/v1/documents",
            json={
                "space_id": "space_hackinterview",
                "profile_id": "profile_default",
                "title": "Internal document",
                "text": "VECTOR_UNHEALTHY_RETRY_MARKER should leave projection pending.",
                "source_type": "document",
                "source_external_id": "internal-vector-unhealthy-doc",
                "classification": "internal",
            },
            headers=auth_headers(),
        )
        embedder = FailingEmbedder()
        object.__setattr__(client.app.state.container, "vector_index", UnhealthyVectorAdapter())
        object.__setattr__(client.app.state.container, "embedder", embedder)
        processed = asyncio.run(OutboxWorker(client.app.state.container).run_once(limit=10))
        status, attempt_count, last_safe_error = asyncio.run(row_state(client))

    assert created.status_code == 201
    assert processed == 1
    assert status == "retry_pending"
    assert attempt_count == 1
    assert last_safe_error == "RuntimeError"
    assert embedder.calls == 0


def test_stale_graph_upsert_event_is_skipped_after_fact_update(tmp_path: Path) -> None:
    class RecordingGraphAdapter:
        def __init__(self) -> None:
            self.upserted: list[str] = []

        async def upsert_fact(
            self,
            fact_id: str,
            _text: str,
            _metadata: dict[str, str],
        ) -> VectorWriteResult:
            self.upserted.append(fact_id)
            return VectorWriteResult.ok(1)

        async def delete_fact(self, _fact_id: str) -> VectorWriteResult:
            return VectorWriteResult.ok(1)

    with make_client(tmp_path) as client:
        created = client.post("/v1/facts", json=fact_payload(), headers=auth_headers())
        fact_id = created.json()["data"]["id"]
        updated = client.patch(
            f"/v1/facts/{fact_id}",
            json={
                "expected_version": 1,
                "text": "Graph jobs must skip stale versions.",
                "reason": "Worker version guard",
                "source_refs": [{"source_type": "manual", "source_id": "worker-version"}],
            },
            headers=auth_headers(),
        )
        graph = RecordingGraphAdapter()
        object.__setattr__(client.app.state.container, "graph_index", graph)
        processed = asyncio.run(OutboxWorker(client.app.state.container).run_once(limit=1))
        statuses = asyncio.run(outbox_statuses(client))

    assert created.status_code == 201
    assert updated.status_code == 200
    assert processed == 1
    assert graph.upserted == []
    assert statuses == ["done", "pending"]


def test_degraded_graph_projection_job_retries_without_losing_fact(tmp_path: Path) -> None:
    class DegradedGraphAdapter:
        async def upsert_fact(
            self,
            _fact_id: str,
            _text: str,
            _metadata: dict[str, str],
        ) -> VectorWriteResult:
            return VectorWriteResult.degraded("graph.unavailable", retryable=True)

        async def delete_fact(self, _fact_id: str) -> VectorWriteResult:
            return VectorWriteResult.degraded("graph.unavailable", retryable=True)

    async def row_state(client: TestClient) -> tuple[str, int, str | None]:
        engine = client.app.state.container.engine
        async with AsyncSession(engine) as session:
            row = (
                await session.execute(select(MemoryOutboxRow).order_by(MemoryOutboxRow.id))
            ).scalar_one()
            return row.status, row.attempt_count, row.last_safe_error

    with make_client(tmp_path) as client:
        created = client.post(
            "/v1/facts",
            json=fact_payload("GRAPH_DEGRADED_FACT_MARKER remains canonical."),
            headers=auth_headers(),
        )
        object.__setattr__(client.app.state.container, "graph_index", DegradedGraphAdapter())
        processed = asyncio.run(OutboxWorker(client.app.state.container).run_once(limit=10))
        status, attempt_count, last_safe_error = asyncio.run(row_state(client))
        fact = client.get(f"/v1/facts/{created.json()['data']['id']}", headers=auth_headers())

    assert created.status_code == 201
    assert processed == 1
    assert status == "retry_pending"
    assert attempt_count == 1
    assert last_safe_error == "RuntimeError"
    assert fact.json()["data"]["text"] == "GRAPH_DEGRADED_FACT_MARKER remains canonical."


def test_worker_safe_error_omits_raw_exception_text() -> None:
    error = RuntimeError("RAW_PROVIDER_SECRET_MARKER should not be persisted")

    assert _safe_error(error) == "RuntimeError"


def test_outbox_poison_job_becomes_dead_with_safe_error(tmp_path: Path) -> None:
    async def run() -> tuple[str, int, str | None]:
        container = build_container(
            Settings(
                deploy_profile=DeployProfile.TEST,
                database_url=f"sqlite+aiosqlite:///{tmp_path / 'poison.db'}",
                service_token="test-token",
            )
        )
        await create_schema(container.engine)
        now = container.clock.now()
        async with AsyncSession(container.engine) as session:
            session.add(
                MemoryOutboxRow(
                    event_type="unknown.poison",
                    aggregate_type="test",
                    aggregate_id="RAW_POISON_PAYLOAD_MARKER",
                    aggregate_version=None,
                    payload_json={"raw": "RAW_POISON_PAYLOAD_MARKER"},
                    status="pending",
                    attempt_count=0,
                    next_attempt_at=now,
                    last_safe_error=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

        worker = OutboxWorker(container)
        for _ in range(5):
            assert await worker.run_once(limit=10) == 1
            async with AsyncSession(container.engine) as session:
                await session.execute(
                    update(MemoryOutboxRow).values(next_attempt_at=container.clock.now())
                )
                await session.commit()

        async with AsyncSession(container.engine) as session:
            row = (
                await session.execute(select(MemoryOutboxRow).where(MemoryOutboxRow.id == 1))
            ).scalar_one()
            return row.status, row.attempt_count, row.last_safe_error

    status, attempt_count, last_safe_error = asyncio.run(run())

    assert status == "dead"
    assert attempt_count == 5
    assert last_safe_error == "ValueError"
    assert "RAW_POISON_PAYLOAD_MARKER" not in str(last_safe_error)


def test_small_golden_eval_passes() -> None:
    result = run_small_golden()

    assert result["ok"] is True
    assert result["checks"]["memory_evidence_guard"] is True


def test_db_upgrade_and_seed_defaults_cli_functions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "test")
    monkeypatch.setenv("MEMORY_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'cli.db'}")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "test-token")

    upgraded = asyncio.run(upgrade())
    seeded = asyncio.run(seed_defaults())

    assert upgraded == {"operation": "upgrade", "status": "ok"}
    assert seeded["status"] == "ok"
    assert str(seeded["space_id"]).startswith("space_")
    assert str(seeded["profile_id"]).startswith("profile_")


def test_readiness_doctor_entrypoint_is_safe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEMORY_DEPLOY_PROFILE", "test")
    monkeypatch.setenv("MEMORY_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'doctor.db'}")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "test-token")
    asyncio.run(upgrade())

    result = asyncio.run(run_doctor())

    assert result["status"] == "ok"
    assert "RAW_" not in str(result)
