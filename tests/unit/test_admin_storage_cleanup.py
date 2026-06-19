import json
from datetime import UTC, datetime

from infinity_context_core.application.use_cases.blob_storage_cleanup import (
    BlobStorageCleanupDecision,
)
from infinity_context_server.admin import _cleanup_decision_payload


def test_cleanup_decision_payload_is_json_safe() -> None:
    payload = _cleanup_decision_payload(
        BlobStorageCleanupDecision(
            action="would_delete",
            reason="orphan_blob",
            storage_key_hash="abc123",
            storage_key_extension=".txt",
            storage_key_path_depth=4,
            byte_size=10,
            updated_at=datetime(2026, 6, 19, tzinfo=UTC),
        )
    )

    assert payload["updated_at"] == "2026-06-19T00:00:00+00:00"
    json.dumps(payload)
