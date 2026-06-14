from datetime import UTC, datetime, timedelta

from memo_stack_core.domain.assets import MemoryAssetId
from memo_stack_core.domain.entities import MemoryScopeId, SpaceId, ThreadId
from memo_stack_core.domain.extraction import (
    AssetExtractionJob,
    AssetExtractionJobId,
    AssetExtractionStatus,
    ExtractionArtifact,
    ExtractionArtifactId,
    ExtractionArtifactType,
    ExtractionRetryDisposition,
)


def test_normalized_json_is_a_supported_extraction_artifact_type() -> None:
    artifact = ExtractionArtifact.create(
        artifact_id=ExtractionArtifactId("artifact-normalized"),
        job_id=AssetExtractionJobId("job-docling"),
        asset_id=MemoryAssetId("asset-docling"),
        artifact_type="normalized_json",
        storage_backend="local",
        storage_key="scope/job/docling-normalized.json",
        sha256_hex="a" * 64,
        byte_size=128,
        now=datetime(2026, 6, 14, tzinfo=UTC),
        metadata={"content_type": "application/json"},
    )

    assert artifact.artifact_type == ExtractionArtifactType.NORMALIZED_JSON


def test_image_region_artifacts_are_supported_extraction_artifact_types() -> None:
    assert _artifact("image_regions").artifact_type == ExtractionArtifactType.IMAGE_REGIONS
    assert _artifact("vision_json").artifact_type == ExtractionArtifactType.VISION_JSON


def test_extraction_job_running_records_lease_and_heartbeat() -> None:
    now = datetime(2026, 6, 14, 10, tzinfo=UTC)
    lease_expires_at = now + timedelta(minutes=15)

    running = _job(now).mark_running(
        now=now,
        lease_owner="outbox:42",
        lease_expires_at=lease_expires_at,
    )

    assert running.status == AssetExtractionStatus.RUNNING
    assert running.attempt_count == 1
    assert running.lease_owner == "outbox:42"
    assert running.lease_expires_at == lease_expires_at
    assert running.heartbeat_at == now


def test_extraction_job_heartbeat_extends_lease_and_progress() -> None:
    now = datetime(2026, 6, 14, 10, tzinfo=UTC)
    running = _job(now).mark_running(
        now=now,
        lease_owner="outbox:42",
        lease_expires_at=now + timedelta(minutes=15),
    )
    heartbeat_at = now + timedelta(minutes=2)
    extended = heartbeat_at + timedelta(minutes=15)

    updated = running.record_heartbeat(
        now=heartbeat_at,
        lease_expires_at=extended,
        metadata={"processing_stage": "extracting_content", "progress_percent": 45},
    )

    assert updated.heartbeat_at == heartbeat_at
    assert updated.lease_expires_at == extended
    assert updated.metadata["processing_stage"] == "extracting_content"
    assert updated.metadata["progress_percent"] == 45


def test_pending_extraction_cancel_becomes_terminal() -> None:
    now = datetime(2026, 6, 14, 10, tzinfo=UTC)

    canceled = _job(now).request_cancellation(now=now + timedelta(seconds=3))

    assert canceled.status == AssetExtractionStatus.CANCELED
    assert canceled.cancellation_requested_at == now + timedelta(seconds=3)
    assert canceled.finished_at == now + timedelta(seconds=3)
    assert canceled.retry_disposition == ExtractionRetryDisposition.PERMANENT
    assert canceled.safe_error_code == "asset_extraction.canceled"


def test_failed_extraction_records_retry_disposition_and_retry_after() -> None:
    now = datetime(2026, 6, 14, 10, tzinfo=UTC)
    running = _job(now).mark_running(
        now=now,
        lease_owner="outbox:42",
        lease_expires_at=now + timedelta(minutes=15),
    )
    retry_after_at = now + timedelta(seconds=30)

    failed = running.mark_failed(
        now=now + timedelta(seconds=10),
        code="asset_extraction.provider_timeout",
        message="Provider timed out",
        retry_disposition=ExtractionRetryDisposition.RETRYABLE,
        retry_after_at=retry_after_at,
    )

    assert failed.status == AssetExtractionStatus.FAILED
    assert failed.retry_disposition == ExtractionRetryDisposition.RETRYABLE
    assert failed.retry_after_at == retry_after_at
    assert failed.lease_owner is None
    assert failed.heartbeat_at is None


def test_retry_clears_execution_state() -> None:
    now = datetime(2026, 6, 14, 10, tzinfo=UTC)
    failed = _job(now).mark_running(
        now=now,
        lease_owner="outbox:42",
        lease_expires_at=now + timedelta(minutes=15),
    ).mark_failed(
        now=now + timedelta(seconds=5),
        code="asset_extraction.provider_timeout",
        message="Provider timed out",
        retry_disposition=ExtractionRetryDisposition.RETRYABLE,
        retry_after_at=now + timedelta(seconds=30),
    )

    retried = failed.reset_for_retry(now=now + timedelta(minutes=1))

    assert retried.status == AssetExtractionStatus.PENDING
    assert retried.lease_owner is None
    assert retried.lease_expires_at is None
    assert retried.heartbeat_at is None
    assert retried.retry_after_at is None
    assert retried.retry_disposition is None


def _artifact(artifact_type: str) -> ExtractionArtifact:
    return ExtractionArtifact.create(
        artifact_id=ExtractionArtifactId(f"artifact-{artifact_type}"),
        job_id=AssetExtractionJobId("job-image"),
        asset_id=MemoryAssetId("asset-image"),
        artifact_type=artifact_type,
        storage_backend="local",
        storage_key=f"scope/job/{artifact_type}.json",
        sha256_hex="b" * 64,
        byte_size=128,
        now=datetime(2026, 6, 14, tzinfo=UTC),
        metadata={"content_type": "application/json"},
    )


def _job(now: datetime) -> AssetExtractionJob:
    return AssetExtractionJob.create(
        job_id=AssetExtractionJobId("extract-1"),
        asset_id=MemoryAssetId("asset-1"),
        space_id=SpaceId("space-1"),
        memory_scope_id=MemoryScopeId("scope-1"),
        thread_id=ThreadId("thread-1"),
        parser_profile="standard_local",
        parser_config_hash="f" * 64,
        source_sha256_hex="a" * 64,
        now=now,
        metadata={"processing_stage": "queued"},
    )
