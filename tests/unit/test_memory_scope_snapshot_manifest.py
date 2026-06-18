from __future__ import annotations

from copy import deepcopy

from infinity_context_core.memory_scope_snapshots import (
    build_snapshot_manifest,
    verify_snapshot_manifest_payload,
)


def test_snapshot_manifest_verification_rejects_tampered_counts() -> None:
    snapshot = _snapshot()
    manifest = build_snapshot_manifest(
        snapshot=snapshot,
        space_slug="team",
        memory_scope_external_ref="atlas",
        redacted=False,
    )
    tampered = deepcopy(manifest)
    tampered["counts"]["facts"] = 99

    verification = verify_snapshot_manifest_payload(snapshot=snapshot, manifest=tampered)

    assert verification["ok"] is False
    assert verification["actual_sha256"] == verification["expected_sha256"]
    assert verification["errors"] == ["count_mismatch:facts"]


def test_snapshot_manifest_verification_rejects_schema_version_mismatch() -> None:
    snapshot = _snapshot()
    manifest = build_snapshot_manifest(
        snapshot=snapshot,
        space_slug="team",
        memory_scope_external_ref="atlas",
        redacted=False,
    )
    tampered = deepcopy(manifest)
    tampered["snapshot_schema_version"] = 8

    verification = verify_snapshot_manifest_payload(snapshot=snapshot, manifest=tampered)

    assert verification["ok"] is False
    assert verification["errors"] == ["snapshot_schema_version_mismatch"]


def test_snapshot_manifest_verification_rejects_redacted_mismatch() -> None:
    snapshot = _snapshot()
    manifest = build_snapshot_manifest(
        snapshot=snapshot,
        space_slug="team",
        memory_scope_external_ref="atlas",
        redacted=False,
    )
    tampered = deepcopy(manifest)
    tampered["redacted"] = True

    verification = verify_snapshot_manifest_payload(snapshot=snapshot, manifest=tampered)

    assert verification["ok"] is False
    assert verification["errors"] == ["redacted_mismatch"]


def test_snapshot_manifest_verification_rejects_missing_counts_contract() -> None:
    snapshot = _snapshot()
    manifest = build_snapshot_manifest(
        snapshot=snapshot,
        space_slug="team",
        memory_scope_external_ref="atlas",
        redacted=False,
    )
    tampered = deepcopy(manifest)
    tampered.pop("counts")

    verification = verify_snapshot_manifest_payload(snapshot=snapshot, manifest=tampered)

    assert verification["ok"] is False
    assert verification["errors"] == ["counts_missing"]


def _snapshot() -> dict[str, object]:
    return {
        "schema_version": 9,
        "redacted": False,
        "threads": [{"id": "thread_1"}],
        "facts": [{"id": "fact_1"}],
        "documents": [],
        "episodes": [],
        "chunks": [{"id": "chunk_1"}],
        "assets": [],
        "asset_blobs": [],
        "asset_extraction_jobs": [],
        "extraction_artifacts": [],
        "extraction_artifact_blobs": [],
        "captures": [],
        "anchors": [{"id": "anchor_1"}],
        "context_links": [],
        "context_link_suggestions": [],
        "relations": [],
        "source_refs": [],
    }
