from fastapi.testclient import TestClient
from memory_core.domain.errors import MemoryInfrastructureError, MemoryInvariantError
from memory_server.config import DeployProfile, Settings
from memory_server.main import create_app


def build_test_client() -> TestClient:
    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
        )
    )
    return TestClient(app)


def test_health_returns_ok() -> None:
    response = build_test_client().get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "memory-platform",
        "deploy_profile": "test",
    }


def test_root_health_alias_supports_hackinterview_canary() -> None:
    response = build_test_client().get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_capabilities_return_noop_adapters() -> None:
    response = build_test_client().get("/v1/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["service_name"] == "memory-platform"
    assert body["deploy_profile"] == "test"
    assert body["policy_mode"] == "active_context"
    assert set(body["adapters"]) == {"qdrant", "graphiti", "embeddings"}
    assert body["adapters"]["qdrant"]["enabled"] is False
    assert body["adapters"]["graphiti"]["enabled"] is False
    assert body["adapters"]["embeddings"]["enabled"] is False
    assert body["limits"]["max_context_tokens"] == 1800


def test_unexpected_exception_maps_to_safe_internal_error() -> None:
    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
        )
    )

    @app.get("/raise-raw-secret")
    async def raise_raw_secret() -> None:
        raise RuntimeError("RAW_INTERNAL_SECRET_MARKER must not leak")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/raise-raw-secret")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "memory.internal",
            "message": "Internal error",
            "retryable": True,
        }
    }
    assert "RAW_INTERNAL_SECRET_MARKER" not in response.text


def test_invariant_error_maps_to_safe_internal_error() -> None:
    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
        )
    )

    @app.get("/raise-invariant-secret")
    async def raise_invariant_secret() -> None:
        raise MemoryInvariantError("RAW_INVARIANT_SECRET_MARKER must not leak")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/raise-invariant-secret")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "memory.internal",
            "message": "Internal error",
            "retryable": True,
        }
    }
    assert "RAW_INVARIANT_SECRET_MARKER" not in response.text


def test_infrastructure_error_maps_to_safe_provider_unavailable() -> None:
    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
        )
    )

    @app.get("/raise-provider-secret")
    async def raise_provider_secret() -> None:
        raise MemoryInfrastructureError("RAW_PROVIDER_SECRET_MARKER must not leak")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/raise-provider-secret")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "memory.provider_unavailable",
            "message": "Provider unavailable",
            "retryable": True,
        }
    }
    assert "RAW_PROVIDER_SECRET_MARKER" not in response.text
