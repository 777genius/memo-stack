from pathlib import Path

from fastapi.testclient import TestClient
from memo_stack_server.config import DeployProfile, Settings
from memo_stack_server.main import create_app


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


def test_export_graph_includes_facts_documents_fragments_and_evidence_edges(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        document = client.post(
            "/v1/documents",
            json={
                "space_slug": "graph-export",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "thread-graph-export",
                "title": "ADR graph export",
                "text": "\n".join(
                    [
                        "## Decision",
                        "- Canonical memory graph exports from Postgres.",
                        "## Risks",
                        "- Graphiti is a projection and must not be the export source.",
                    ]
                ),
                "source_type": "document",
                "source_external_id": "adr-graph-export",
                "classification": "internal",
            },
            headers=auth_headers(),
        )
        document_id = document.json()["data"]["id"]
        chunks = client.get(
            f"/v1/documents/{document_id}/chunks",
            headers=auth_headers(),
        )
        chunk_id = chunks.json()["data"][0]["id"]
        fact = client.post(
            "/v1/facts",
            json={
                "space_slug": "graph-export",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "thread-graph-export",
                "text": "Canonical graph export must use Postgres as source of truth.",
                "kind": "architecture_decision",
                "source_refs": [
                    {
                        "source_type": "document",
                        "source_id": "adr-graph-export",
                        "chunk_id": chunk_id,
                        "quote_preview": "Canonical memory graph exports from Postgres.",
                    }
                ],
                "classification": "internal",
            },
            headers=auth_headers(),
        )
        episode = client.post(
            "/v1/episodes",
            json={
                "space_slug": "graph-export",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "thread-graph-export",
                "source_type": "system_audio",
                "source_external_id": "meeting-graph-export",
                "text": "Episode graph export marker should become a first-class graph node.",
                "speaker": "user",
                "trust_level": "high",
            },
            headers=auth_headers(),
        )
        assert episode.status_code == 200, episode.text
        episode_id = episode.json()["data"]["episode_id"]
        episode_fact = client.post(
            "/v1/facts",
            json={
                "space_slug": "graph-export",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "thread-graph-export",
                "text": "Episode evidence must be exportable as canonical graph context.",
                "kind": "note",
                "source_refs": [
                    {"source_type": "system_audio", "source_id": "meeting-graph-export"}
                ],
                "classification": "internal",
            },
            headers=auth_headers(),
        )
        related_fact = client.post(
            "/v1/facts",
            json={
                "space_slug": "graph-export",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "thread-graph-export",
                "text": "Graphiti remains a derived temporal graph adapter.",
                "kind": "architecture_decision",
                "source_refs": [{"source_type": "manual", "source_id": "graphiti-derived"}],
                "classification": "internal",
            },
            headers=auth_headers(),
        )
        relation = client.post(
            f"/v1/facts/{fact.json()['data']['id']}/relations",
            json={
                "target_fact_id": related_fact.json()["data"]["id"],
                "relation_type": "supports",
                "reason": "ADR links canonical export and derived graph policy.",
            },
            headers=auth_headers(),
        )
        graph = client.get(
            "/v1/export/graph.json",
            params={
                "space_slug": "graph-export",
                "memory_scope_external_ref": "default",
                "thread_external_ref": "thread-graph-export",
            },
            headers=auth_headers(),
        )

    assert document.status_code == 201
    assert chunks.status_code == 200
    assert fact.status_code == 201
    assert episode_fact.status_code == 201
    assert related_fact.status_code == 201
    assert relation.status_code == 201
    assert graph.status_code == 200
    data = graph.json()["data"]
    node_ids = {node["id"] for node in data["nodes"]}
    episode_chunk_nodes = [
        node
        for node in data["nodes"]
        if node["type"] == "chunk" and node["data"].get("episode_id") == episode_id
    ]
    edge_types = {edge["type"] for edge in data["edges"]}
    assert data["schema_version"] == "memo_stack.graph_export.v1"
    assert data["counts"]["facts"] == 3
    assert data["counts"]["documents"] == 1
    assert data["counts"]["episodes"] == 1
    assert data["counts"]["chunks"] == 3
    assert data["counts"]["relations"] == 1
    assert f"fact:{fact.json()['data']['id']}" in node_ids
    assert f"fact:{episode_fact.json()['data']['id']}" in node_ids
    assert f"document:{document_id}" in node_ids
    assert f"episode:{episode_id}" in node_ids
    assert f"chunk:{chunk_id}" in node_ids
    assert len(episode_chunk_nodes) == 1
    assert {
        "contains_fact",
        "contains_document",
        "contains_episode",
        "has_chunk",
        "evidenced_by_chunk",
        "evidenced_by_episode",
        "supports",
    }.issubset(edge_types)


def test_export_graph_excludes_restricted_memory_by_default(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        restricted = client.post(
            "/v1/facts",
            json={
                "space_id": "space_client_app",
                "memory_scope_id": "memory_scope_default",
                "text": "Restricted graph export marker must be hidden by default.",
                "kind": "note",
                "source_refs": [{"source_type": "manual", "source_id": "restricted"}],
                "classification": "restricted",
            },
            headers=auth_headers(),
        )
        default_graph = client.get(
            "/v1/export/graph.json",
            params={"space_id": "space_client_app", "memory_scope_id": "memory_scope_default"},
            headers=auth_headers(),
        )
        unrestricted_graph = client.get(
            "/v1/export/graph.json",
            params={
                "space_id": "space_client_app",
                "memory_scope_id": "memory_scope_default",
                "include_restricted": True,
            },
            headers=auth_headers(),
        )

    assert restricted.status_code == 201
    assert default_graph.json()["data"]["counts"]["facts"] == 0
    assert unrestricted_graph.json()["data"]["counts"]["facts"] == 1
