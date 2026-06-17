from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

from memo_stack_server.memory_scope_transfer_assets import asset_from_json, asset_to_json
from memo_stack_server.memory_scope_transfer_context import context_link_suggestion_from_json
from memo_stack_server.memory_scope_transfer_extractions import (
    extraction_artifact_from_json,
    extraction_job_from_json,
    extraction_job_to_json,
)
from memo_stack_server.memory_scope_transfer_records import (
    anchor_from_json,
    capture_from_json,
    capture_to_json,
)
from memo_stack_server.memory_scope_transfer_relations import relation_from_json


def test_snapshot_asset_import_redacts_metadata() -> None:
    raw_secret = "sk-proj-secretvalue1234567890"
    row = asset_from_json(
        {
            "id": "asset_1",
            "filename": "safe.txt",
            "content_type": "text/plain",
            "byte_size": 12,
            "sha256_hex": "a" * 64,
            "metadata_json": {"debug": f"Bearer {raw_secret}", "token": raw_secret},
        },
        space_id="space_1",
        memory_scope_id="scope_1",
        now=_now(),
    )

    rendered = json.dumps(row.metadata_json, sort_keys=True)
    assert raw_secret not in rendered
    assert "token" not in row.metadata_json
    assert "[redacted]" in rendered


def test_snapshot_export_redacts_legacy_row_metadata() -> None:
    raw_secret = "sk-proj-secretvalue1234567890"
    now = _now()
    asset = asset_to_json(
        SimpleNamespace(
            id="asset_1",
            thread_id=None,
            filename="safe.txt",
            content_type="text/plain",
            byte_size=12,
            sha256_hex="a" * 64,
            storage_backend="local",
            storage_key="safe.txt",
            status="stored",
            classification="internal",
            metadata_json={"debug": f"Bearer {raw_secret}", "token": raw_secret},
            created_at=now,
            updated_at=now,
        )
    )
    job = extraction_job_to_json(
        SimpleNamespace(
            id="job_1",
            asset_id="asset_1",
            thread_id=None,
            parser_profile="standard_local",
            parser_config_hash="hash",
            source_sha256_hex="a" * 64,
            parser_name=f"parser {raw_secret}",
            parser_version=None,
            model_version=None,
            status="failed",
            attempt_count=1,
            safe_error_code="asset_extraction.provider_error",
            safe_error_message=f"failed Bearer {raw_secret}",
            result_document_ids_json=[],
            metadata_json={"debug": f"Bearer {raw_secret}", "api_key": raw_secret},
            created_at=now,
            updated_at=now,
            started_at=None,
            finished_at=None,
            lease_owner=None,
            lease_expires_at=None,
            heartbeat_at=None,
            retry_after_at=None,
            cancellation_requested_at=None,
            retry_disposition=None,
        )
    )
    capture = capture_to_json(
        SimpleNamespace(
            id="capture_1",
            thread_id=None,
            source_agent="test",
            source_kind="manual",
            event_type="Capture",
            actor_role="user",
            text_redacted="safe text",
            evidence_refs_json=[],
            payload_hash="hash",
            idempotency_key="idem",
            status="accepted",
            consolidation_status="pending",
            trust_level="medium",
            source_authority="unknown",
            sensitivity="medium",
            data_classification="internal",
            occurred_at=now,
            received_at=now,
            created_at=now,
            updated_at=now,
            metadata_json={"debug": f"Bearer {raw_secret}", "secret": raw_secret},
            source_event_id=None,
            source_actor_external_ref=None,
            client_instance_id=None,
            agent_session_external_ref=None,
            turn_external_ref=None,
            parent_capture_id=None,
            sequence_index=None,
            trace_id=None,
            schema_version=1,
            parser_version="parser-v1",
            redaction_version="redaction-v1",
            admission_version="admission-v1",
            normalization_version="normalization-v1",
            policy_version="policy-v1",
            extractor_version=None,
            extractor_prompt_version=None,
            resolver_version=None,
            last_error_code="extractor_failed",
            last_error_message=f"failed {raw_secret}",
        ),
        redacted=False,
    )

    rendered = json.dumps({"asset": asset, "capture": capture, "job": job}, sort_keys=True)
    assert raw_secret not in rendered
    assert "token" not in asset["metadata_json"]
    assert "api_key" not in job["metadata_json"]
    assert "secret" not in capture["metadata_json"]
    assert "[redacted]" in rendered


def test_snapshot_extraction_import_redacts_job_and_artifact_metadata() -> None:
    raw_secret = "sk-proj-secretvalue1234567890"
    job = extraction_job_from_json(
        {
            "id": "job_1",
            "asset_id": "asset_1",
            "parser_name": f"parser {raw_secret}",
            "safe_error_message": f"failed Bearer {raw_secret}",
            "metadata_json": {"debug": f"Bearer {raw_secret}", "api_key": raw_secret},
        },
        space_id="space_1",
        memory_scope_id="scope_1",
        now=_now(),
    )
    artifact = extraction_artifact_from_json(
        {
            "id": "artifact_1",
            "job_id": "job_1",
            "asset_id": "asset_1",
            "metadata_json": {"debug": f"Bearer {raw_secret}", "token": raw_secret},
        },
        now=_now(),
    )

    rendered = json.dumps(
        {
            "artifact": artifact.metadata_json,
            "job": job.metadata_json,
            "parser_name": job.parser_name,
            "safe_error_message": job.safe_error_message,
        },
        sort_keys=True,
    )
    assert raw_secret not in rendered
    assert "api_key" not in job.metadata_json
    assert "token" not in artifact.metadata_json
    assert "[redacted]" in rendered


def test_snapshot_capture_import_redacts_metadata_and_last_error() -> None:
    raw_secret = "sk-proj-secretvalue1234567890"
    row = capture_from_json(
        {
            "id": "capture_1",
            "metadata_json": {"debug": f"Bearer {raw_secret}", "secret": raw_secret},
            "last_error_message": f"extractor failed {raw_secret}",
        },
        space_id="space_1",
        memory_scope_id="scope_1",
        now=_now(),
    )

    rendered = json.dumps(
        {
            "last_error_message": row.last_error_message,
            "metadata": row.metadata_json,
        },
        sort_keys=True,
    )
    assert raw_secret not in rendered
    assert "secret" not in row.metadata_json
    assert "[redacted]" in rendered


def test_snapshot_context_suggestion_import_redacts_metadata() -> None:
    raw_secret = "sk-proj-secretvalue1234567890"
    row = context_link_suggestion_from_json(
        {
            "id": "suggestion_1",
            "metadata_json": {"debug": f"Bearer {raw_secret}", "token": raw_secret},
        },
        space_id="space_1",
        memory_scope_id="scope_1",
        now=_now(),
    )

    rendered = json.dumps(row.metadata_json, sort_keys=True)
    assert raw_secret not in rendered
    assert "token" not in row.metadata_json
    assert "[redacted]" in rendered


def test_snapshot_anchor_import_accepts_legacy_payload_without_evidence_fields() -> None:
    now = _now()
    row = anchor_from_json(
        {
            "id": "anchor_legacy_alex",
            "kind": "person",
            "normalized_key": "alex",
            "label": "Alex",
            "created_at": "2026-06-01T12:00:00+00:00",
            "updated_at": "2026-06-02T12:00:00+00:00",
        },
        space_id="space_1",
        memory_scope_id="scope_1",
        now=now,
    )

    assert row.confidence == "medium"
    assert row.evidence_refs_json == []
    assert row.observed_at is None
    assert row.valid_from is None
    assert row.valid_to is None
    assert row.metadata_json == {}


def test_snapshot_relation_import_accepts_legacy_payload_without_temporal_fields() -> None:
    row = relation_from_json(
        {
            "id": "relation_legacy",
            "source_fact_id": "fact_current",
            "target_fact_id": "fact_old",
            "relation_type": "supersedes",
            "created_at": "2026-06-01T12:00:00+00:00",
        },
        space_id="space_1",
        memory_scope_id="scope_1",
        now=_now(),
    )

    assert row.reason == "imported memory_scope snapshot relation"
    assert row.status == "active"
    assert row.observed_at == row.created_at
    assert row.valid_from is None
    assert row.valid_to is None


def _now() -> datetime:
    return datetime(2026, 6, 17, tzinfo=UTC)
