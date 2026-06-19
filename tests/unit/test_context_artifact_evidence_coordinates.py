import asyncio

from test_context_provider_consistency import (
    _store_media_manifest_artifact,
    auth_headers,
    make_client,
)


def test_context_sanitizes_invalid_media_manifest_coordinates(tmp_path) -> None:
    with make_client(tmp_path) as client:
        container = client.app.state.container
        upload = client.post(
            "/v1/assets",
            params={
                "space_slug": container.settings.default_space_slug,
                "memory_scope_external_ref": container.settings.default_memory_scope_external_ref,
                "thread_external_ref": "thread-invalid-coordinate-context",
                "filename": "bad-provider-output.json",
            },
            content=b"provider manifest fixture",
            headers={**auth_headers(), "Content-Type": "application/json"},
        )
        assert upload.status_code == 201, upload.text
        asset = upload.json()["data"]
        asyncio.run(
            _store_media_manifest_artifact(
                container,
                asset=asset,
                payload={
                    "schema_version": "infinity_context.multimodal_manifest.v1",
                    "evidence_items": [
                        {
                            "id": "bad-time",
                            "kind": "transcript_segment",
                            "modality": "audio",
                            "text_preview": (
                                "INVALID_COORD_CONTEXT_MARKER transcript still matters."
                            ),
                            "time_range": {"start_ms": 5000, "end_ms": 1000},
                            "confidence": 0.9,
                        },
                        {
                            "id": "bad-bbox",
                            "kind": "ocr_region",
                            "modality": "image",
                            "text_preview": (
                                "INVALID_COORD_CONTEXT_MARKER screenshot text still matters."
                            ),
                            "bbox": [-1.0, 10.0, 120.0, 44.0],
                            "confidence": 0.9,
                        },
                    ],
                },
            )
        )

        context = client.post(
            "/v1/context",
            json={
                "space_slug": container.settings.default_space_slug,
                "memory_scope_external_ref": container.settings.default_memory_scope_external_ref,
                "thread_external_ref": "thread-invalid-coordinate-context",
                "query": "INVALID_COORD_CONTEXT_MARKER",
                "max_facts": 0,
                "max_chunks": 0,
                "max_evidence_items": 5,
                "token_budget": 512,
            },
            headers=auth_headers(),
        )

    assert context.status_code == 200, context.text
    data = context.json()["data"]
    rendered = data["rendered_text"]
    diagnostics = data["diagnostics"]
    assert "transcript still matters" in rendered
    assert "screenshot text still matters" in rendered
    assert "time_ms=5000-1000" not in rendered
    assert "bbox=-1" not in rendered
    assert diagnostics["artifact_evidence_items_used"] == 2
    assert diagnostics["artifact_evidence_invalid_time_range_count"] == 1
    assert diagnostics["artifact_evidence_invalid_bbox_count"] == 1
    assert diagnostics["artifact_evidence_coordinate_signal_count"] == 0
    assert diagnostics["source_refs_with_time_range_count"] == 0
    assert diagnostics["source_refs_with_bbox_count"] == 0
    assert all(item["citations"][0]["time_range_ms"] is None for item in data["items"])
    assert all(item["citations"][0]["bbox"] is None for item in data["items"])
