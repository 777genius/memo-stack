from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from hashlib import sha256

from infinity_context_core.application.use_cases.asset_extractions import RunAssetExtractionUseCase
from infinity_context_core.domain.assets import MemoryAssetId
from infinity_context_core.domain.entities import MemoryScopeId, SpaceId, ThreadId
from infinity_context_core.domain.extraction import (
    AssetExtractionJob,
    AssetExtractionJobId,
    AssetExtractionStatus,
    ExtractionRetryDisposition,
)
from infinity_context_core.ports.extraction import ExtractionLimits, ExtractionResult


class _Clock:
    def now(self) -> datetime:
        return datetime(2026, 6, 18, tzinfo=UTC)


class _Ids:
    def new_id(self, prefix: str) -> str:
        return f"{prefix}_1"

    def projection_id(self, adapter: str, aggregate_type: str, aggregate_id: str) -> str:
        return f"{adapter}:{aggregate_type}:{aggregate_id}"


class _AssetExtractions:
    def __init__(self, job: AssetExtractionJob) -> None:
        self.job = job

    async def get_by_id(self, job_id: str) -> AssetExtractionJob | None:
        assert job_id == str(self.job.id)
        return self.job

    async def save(self, job: AssetExtractionJob) -> AssetExtractionJob:
        self.job = job
        return job


class _Uow:
    def __init__(self, asset_extractions: _AssetExtractions) -> None:
        self.asset_extractions = asset_extractions
        self.committed = False

    async def __aenter__(self) -> _Uow:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


class _UowFactory:
    def __init__(self, job: AssetExtractionJob) -> None:
        self.asset_extractions = _AssetExtractions(job)
        self.instances: list[_Uow] = []

    def __call__(self) -> _Uow:
        uow = _Uow(self.asset_extractions)
        self.instances.append(uow)
        return uow


def test_success_finalization_preserves_existing_terminal_job_state() -> None:
    failed_job = _running_job().mark_failed(
        now=_now(),
        code="asset_extraction.provider_timeout",
        message="Provider timed out",
        retry_disposition=ExtractionRetryDisposition.RETRYABLE,
    )
    use_case, uow_factory = _use_case(failed_job)

    saved = asyncio.run(
        use_case._mark_succeeded(  # noqa: SLF001 - lifecycle race invariant.
            failed_job,
            result=_result(),
            extracted_text_value="committed evidence",
            result_document_ids=("document_1",),
        )
    )

    assert saved.status == AssetExtractionStatus.FAILED
    assert saved.safe_error_code == "asset_extraction.provider_timeout"
    assert saved.result_document_ids == ()
    assert saved.metadata["success_finalization_status"] == "skipped_non_running_state"
    assert saved.metadata["success_finalization_skipped_status"] == "failed"
    assert uow_factory.instances[-1].committed is True


def _use_case(
    job: AssetExtractionJob,
) -> tuple[RunAssetExtractionUseCase, _UowFactory]:
    uow_factory = _UowFactory(job)
    return (
        RunAssetExtractionUseCase(
            uow_factory=uow_factory,
            blob_storage=object(),
            detector=object(),
            extractor=object(),
            ingest_document=object(),
            clock=_Clock(),
            ids=_Ids(),
            limits=ExtractionLimits(max_bytes=1_000_000),
        ),
        uow_factory,
    )


def _running_job() -> AssetExtractionJob:
    return _job().mark_running(
        now=_now(),
        lease_owner="worker_1",
        lease_expires_at=datetime(2026, 6, 18, 0, 15, tzinfo=UTC),
    )


def _job() -> AssetExtractionJob:
    return AssetExtractionJob.create(
        job_id=AssetExtractionJobId("extract_1"),
        asset_id=MemoryAssetId("asset_1"),
        space_id=SpaceId("space_1"),
        memory_scope_id=MemoryScopeId("scope_1"),
        thread_id=ThreadId("thread_1"),
        parser_profile="standard_local",
        parser_config_hash="profile_hash",
        source_sha256_hex=sha256(b"asset").hexdigest(),
        now=_now(),
    )


def _result() -> ExtractionResult:
    return ExtractionResult(
        status="succeeded",
        normalized_content_type="text/plain",
        title="capture.txt",
        markdown="committed evidence",
        parser_name="test_parser",
        parser_version="v1",
    )


def _now() -> datetime:
    return datetime(2026, 6, 18, tzinfo=UTC)
