from fastapi.testclient import TestClient
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


def test_openapi_contains_stable_v1_fields() -> None:
    body = build_test_client().get("/openapi.json").json()

    assert body["info"] == {"title": "Memory Platform", "version": "0.1.0"}
    paths = body["paths"]
    assert "/v1/facts" in paths
    assert "/v1/facts/{fact_id}" in paths
    assert "/v1/documents" in paths
    assert "/v1/context" in paths
    assert "/v1/search" in paths

    schemas = body["components"]["schemas"]
    assert set(schemas["RememberFactRequest"]["required"]) == {"text", "source_refs"}
    assert set(schemas["UpdateFactRequest"]["required"]) == {
        "expected_version",
        "text",
        "reason",
        "source_refs",
    }
    assert set(schemas["IngestDocumentRequest"]["required"]) == {
        "title",
        "text",
        "source_external_id",
    }
    assert set(schemas["ContextRequest"]["required"]) == {"query"}
    assert "profile_external_refs" in schemas["ContextRequest"]["properties"]
    assert "consistency_mode" in schemas["ContextRequest"]["properties"]
    assert "classification" in schemas["RememberFactRequest"]["properties"]
    assert "classification" in schemas["IngestDocumentRequest"]["properties"]


def test_openapi_contains_legacy_routes_when_compatibility_adapter_enabled() -> None:
    app = create_app(
        Settings(
            deploy_profile=DeployProfile.TEST,
            qdrant_enabled=False,
            graphiti_enabled=False,
            embeddings_enabled=False,
            legacy_client_enabled=True,
        )
    )
    body = TestClient(app).get("/openapi.json").json()

    paths = body["paths"]
    assert "/api/v1/interview-memory/context" in paths
    schemas = body["components"]["schemas"]
    assert set(schemas["LegacyContextRequest"]["required"]) == {
        "session_id",
        "current_request",
    }
