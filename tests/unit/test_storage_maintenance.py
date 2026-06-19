import asyncio
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from infinity_context_server.config import CaptureMode, DeployProfile, Settings
from infinity_context_server.main import create_app
from infinity_context_server.storage_maintenance import (
    _IN_PROCESS_LOCK,
    acquire_asset_storage_maintenance_lock,
    run_asset_storage_maintenance,
)
from infinity_context_server.worker import OutboxWorker, OutboxWorkerFilter


def test_worker_skips_asset_storage_maintenance_when_disabled(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        processed = asyncio.run(
            OutboxWorker(
                client.app.state.container,
                worker_filter=OutboxWorkerFilter.from_values(workload_classes=("extraction",)),
            ).run_once(limit=1)
        )
        metrics = client.get("/v1/diagnostics/metrics", headers=_auth_headers())

    assert processed == 0
    storage = metrics.json()["data"]["storage"]
    assert storage["maintenance"]["enabled"] is False
    assert storage["maintenance"]["run_count"] == 0
    assert storage["maintenance"]["last_trace"] is None


def test_worker_runs_due_asset_storage_maintenance_and_reports_integrity_degradation(
    tmp_path: Path,
) -> None:
    storage_dir = tmp_path / "assets"
    with _make_client(
        tmp_path,
        asset_storage_dir=str(storage_dir),
        asset_storage_maintenance_enabled=True,
        asset_storage_maintenance_interval_seconds=3600,
        asset_storage_maintenance_limit=10,
        asset_storage_integrity_max_blob_read_bytes=1024,
    ) as client:
        upload = client.post(
            "/v1/assets",
            params={
                "space_slug": "maintenance",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "storage",
                "filename": "missing-blob.txt",
            },
            content=b"blob should be missing during maintenance",
            headers=_auth_headers({"Content-Type": "text/plain"}),
        )
        assert upload.status_code == 201, upload.text
        for path in storage_dir.rglob("*"):
            if path.is_file():
                path.unlink()

        worker = OutboxWorker(
            client.app.state.container,
            worker_filter=OutboxWorkerFilter.from_values(workload_classes=("extraction",)),
        )
        first_processed = asyncio.run(worker.run_once(limit=1))
        second_processed = asyncio.run(worker.run_once(limit=1))
        metrics = client.get("/v1/diagnostics/metrics", headers=_auth_headers())

    assert first_processed == 0
    assert second_processed == 0
    data = metrics.json()["data"]
    maintenance = data["storage"]["maintenance"]
    assert maintenance["enabled"] is True
    assert maintenance["run_count"] == 1
    assert maintenance["degraded_count"] == 1
    assert maintenance["last_trace"]["status"] == "degraded"
    assert maintenance["last_trace"]["cleanup_status"] == "ok"
    assert maintenance["last_trace"]["cleanup_dry_run"] is True
    assert maintenance["last_trace"]["integrity_status"] == "degraded"
    assert maintenance["last_trace"]["integrity_missing_count"] == 1
    assert maintenance["last_trace"]["storage_keys_are_redacted"] is True
    assert any(alert["name"] == "asset_storage_maintenance_degraded" for alert in data["alerts"])
    assert "missing-blob.txt" not in str(data)


def test_asset_storage_maintenance_skips_when_in_process_lock_is_held(tmp_path: Path) -> None:
    async def run() -> dict[str, Any]:
        with _make_client(
            tmp_path,
            asset_storage_maintenance_enabled=True,
        ) as client:
            await _IN_PROCESS_LOCK.acquire()
            try:
                trace = await run_asset_storage_maintenance(client.app.state.container)
            finally:
                _IN_PROCESS_LOCK.release()
            metrics = client.get("/v1/diagnostics/metrics", headers=_auth_headers())
            return {"trace": trace, "metrics": metrics.json()["data"]}

    result = asyncio.run(run())
    trace = result["trace"]
    maintenance = result["metrics"]["storage"]["maintenance"]
    assert trace["status"] == "skipped"
    assert trace["lock_backend"] == "in_process"
    assert trace["lock_acquired"] is False
    assert maintenance["run_count"] == 1
    assert maintenance["skipped_count"] == 1
    assert maintenance["degraded_count"] == 0
    assert maintenance["last_trace"]["lock_skipped"] is True
    assert not any(
        alert["name"] == "asset_storage_maintenance_degraded"
        for alert in result["metrics"]["alerts"]
    )


def test_postgres_advisory_lock_releases_after_success() -> None:
    async def run() -> _FakePostgresEngine:
        engine = _FakePostgresEngine(results=[True, True])
        container = _FakeLockContainer(engine)
        async with acquire_asset_storage_maintenance_lock(container) as lock:
            assert lock.acquired is True
            assert lock.backend == "postgres_advisory_lock"
        return engine

    engine = asyncio.run(run())
    assert engine.connection.calls == [
        "select pg_try_advisory_lock(:lock_key)",
        "select pg_advisory_unlock(:lock_key)",
    ]


def test_postgres_advisory_lock_skip_does_not_unlock_unheld_lock() -> None:
    async def run() -> _FakePostgresEngine:
        engine = _FakePostgresEngine(results=[False])
        container = _FakeLockContainer(engine)
        async with acquire_asset_storage_maintenance_lock(container) as lock:
            assert lock.acquired is False
            assert lock.backend == "postgres_advisory_lock"
        return engine

    engine = asyncio.run(run())
    assert engine.connection.calls == ["select pg_try_advisory_lock(:lock_key)"]


def _make_client(tmp_path: Path, **overrides: Any) -> TestClient:
    settings_values: dict[str, Any] = {
        "deploy_profile": DeployProfile.TEST,
        "database_url": f"sqlite+aiosqlite:///{tmp_path / 'maintenance.db'}",
        "auto_create_schema": True,
        "service_token": "test-token",
        "capture_mode": CaptureMode.SUGGEST,
        "qdrant_enabled": False,
        "graphiti_enabled": False,
        "embeddings_enabled": False,
        "asset_storage_dir": str(tmp_path / "assets"),
        **overrides,
    }
    app = create_app(
        Settings(**settings_values)
    )
    return TestClient(app)


def _auth_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"Authorization": "Bearer test-token"}
    if extra:
        headers.update(extra)
    return headers


class _FakeDialect:
    name = "postgresql"


class _FakePostgresConnection:
    def __init__(self, results: list[bool]) -> None:
        self._results = results
        self.calls: list[str] = []

    async def __aenter__(self) -> "_FakePostgresConnection":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def scalar(self, statement: object, _params: object) -> bool:
        self.calls.append(str(statement))
        return self._results.pop(0)


class _FakePostgresEngine:
    dialect = _FakeDialect()

    def __init__(self, results: list[bool]) -> None:
        self.connection = _FakePostgresConnection(results)

    def connect(self) -> _FakePostgresConnection:
        return self.connection


class _FakeLockContainer:
    def __init__(self, engine: _FakePostgresEngine) -> None:
        self.engine = engine
