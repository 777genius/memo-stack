"""Asset extraction orchestration use cases."""

from __future__ import annotations

import json
from hashlib import sha256
from math import ceil

from memo_stack_core.application.dto import (
    AssetExtractionResult,
    AssetExtractionsResult,
    ExtractionArtifactBytesResult,
    GetAssetExtractionQuery,
    GetExtractionArtifactQuery,
    IngestDocumentCommand,
    ListAssetExtractionsQuery,
    RequestAssetExtractionCommand,
    RetryAssetExtractionCommand,
    RunAssetExtractionCommand,
)
from memo_stack_core.application.normalize import content_hash
from memo_stack_core.domain.assets import AssetStatus
from memo_stack_core.domain.errors import (
    MemoryInfrastructureError,
    MemoryNotFoundError,
    MemoryQuotaExceededError,
    MemoryValidationError,
)
from memo_stack_core.domain.events import OutboxEvent
from memo_stack_core.domain.extraction import (
    AssetExtractionJob,
    AssetExtractionJobId,
    AssetExtractionStatus,
    ExtractionArtifact,
    ExtractionArtifactId,
)
from memo_stack_core.domain.usage import (
    USAGE_RECONCILIATION_SOURCE_TYPE,
    ProductPlan,
    UsageRecord,
    UsageRecordId,
    UsageResource,
    UsageSubjectType,
    UsageWindow,
    admit_usage,
)
from memo_stack_core.ports.assets import BlobStoragePort
from memo_stack_core.ports.clock import ClockPort
from memo_stack_core.ports.extraction import (
    ContentExtractionPort,
    ExtractedElement,
    ExtractionArtifactCandidate,
    ExtractionLimits,
    ExtractionRequest,
    ExtractionResult,
    FileTypeDetectionRequest,
    FileTypeDetectorPort,
)
from memo_stack_core.ports.ids import IdGeneratorPort
from memo_stack_core.ports.unit_of_work import UnitOfWorkFactoryPort

_DEFAULT_PARSER_CONFIG_VERSION = "v1"
_SOURCE_TYPE = "asset_extraction"
_MAX_SOURCE_REFS = 200


class RequestAssetExtractionUseCase:
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactoryPort,
        clock: ClockPort,
        ids: IdGeneratorPort,
        plan: ProductPlan,
        default_parser_profile: str = "standard_local",
        default_unknown_media_seconds: int = 600,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._ids = ids
        self._plan = plan
        self._default_parser_profile = default_parser_profile
        self._default_unknown_media_seconds = max(1, default_unknown_media_seconds)

    async def execute(self, command: RequestAssetExtractionCommand) -> AssetExtractionResult:
        parser_profile = (command.parser_profile or self._default_parser_profile).strip()
        if not parser_profile:
            raise MemoryValidationError("Parser profile is required")
        parser_config_hash = _parser_config_hash(parser_profile)
        async with self._uow_factory() as uow:
            asset = await uow.assets.get_by_id(command.asset_id)
            if asset is None or asset.status != AssetStatus.STORED:
                raise MemoryNotFoundError("Asset not found")
            existing = await uow.asset_extractions.find_active_for_asset_profile(
                asset_id=str(asset.id),
                parser_profile=parser_profile,
                parser_config_hash=parser_config_hash,
                source_sha256_hex=asset.sha256_hex,
            )
            if existing is not None:
                artifacts = await uow.asset_extractions.list_artifacts(job_id=str(existing.id))
                return AssetExtractionResult(
                    job=existing,
                    artifacts=tuple(artifacts),
                    duplicate=True,
                    indexing_status=_indexing_status(existing.status),
                )

            now = self._clock.now()
            window = UsageWindow.calendar_month_for(now)
            estimated_media_seconds = _estimated_media_analysis_seconds(
                asset,
                default_unknown_media_seconds=self._default_unknown_media_seconds,
            )
            usage_decision = None
            if estimated_media_seconds > 0:
                used = await uow.usage.sum_quantity(
                    subject_type=UsageSubjectType.SPACE.value,
                    subject_id=str(asset.space_id),
                    resource=UsageResource.MEDIA_ANALYSIS_SECONDS.value,
                    window_start=window.start,
                    window_end=window.end,
                )
                usage_decision = admit_usage(
                    plan=self._plan,
                    resource=UsageResource.MEDIA_ANALYSIS_SECONDS,
                    used=used,
                    requested=estimated_media_seconds,
                    window=window,
                )
                if not usage_decision.allowed:
                    raise MemoryQuotaExceededError(
                        "Media analysis monthly quota would be exceeded"
                    )
            job = AssetExtractionJob.create(
                job_id=AssetExtractionJobId(self._ids.new_id("extract")),
                asset_id=asset.id,
                space_id=asset.space_id,
                memory_scope_id=asset.memory_scope_id,
                thread_id=asset.thread_id,
                parser_profile=parser_profile,
                parser_config_hash=parser_config_hash,
                source_sha256_hex=asset.sha256_hex,
                now=now,
                metadata={
                    "filename": asset.filename,
                    "content_type": asset.content_type,
                    "processing_stage": "queued",
                    "progress_percent": 0,
                    "progress_message": "Waiting for extraction worker",
                    "usage_plan_tier": self._plan.tier.value,
                    "usage_media_analysis_seconds_requested": estimated_media_seconds,
                    "usage_media_analysis_seconds_limit": (
                        self._plan.media_analysis_seconds_per_month
                    ),
                    "usage_window_start": window.start.isoformat(),
                    "usage_window_end": window.end.isoformat(),
                    **(
                        {
                            "usage_media_analysis_seconds_used": (
                                usage_decision.snapshot.used
                            ),
                            "usage_media_analysis_seconds_remaining": (
                                usage_decision.snapshot.remaining
                            ),
                        }
                        if usage_decision is not None
                        else {}
                    ),
                },
            )
            saved = await uow.asset_extractions.create(job)
            if estimated_media_seconds > 0:
                usage_key = _usage_idempotency_key(
                    asset_id=str(asset.id),
                    parser_profile=parser_profile,
                    parser_config_hash=parser_config_hash,
                    source_sha256_hex=asset.sha256_hex,
                )
                existing_usage = await uow.usage.find_by_idempotency_key(usage_key)
                if existing_usage is None:
                    await uow.usage.create(
                        UsageRecord.create(
                            record_id=UsageRecordId(self._ids.new_id("usage")),
                            subject_type=UsageSubjectType.SPACE.value,
                            subject_id=str(asset.space_id),
                            space_id=asset.space_id,
                            memory_scope_id=asset.memory_scope_id,
                            resource=UsageResource.MEDIA_ANALYSIS_SECONDS.value,
                            quantity=estimated_media_seconds,
                            source_type="asset_extraction",
                            source_id=str(saved.id),
                            idempotency_key=usage_key,
                            window=window,
                            now=now,
                            metadata={
                                "asset_id": str(asset.id),
                                "parser_profile": parser_profile,
                                "filename": asset.filename,
                                "content_type": asset.content_type,
                            },
                        )
                    )
            await uow.outbox.enqueue(_asset_extract_event(saved))
            await uow.commit()
        return AssetExtractionResult(job=saved, indexing_status="pending")


class GetAssetExtractionUseCase:
    def __init__(self, *, uow_factory: UnitOfWorkFactoryPort) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: GetAssetExtractionQuery) -> AssetExtractionResult:
        async with self._uow_factory() as uow:
            job = await uow.asset_extractions.get_by_id(query.job_id)
            if job is None:
                raise MemoryNotFoundError("Asset extraction job not found")
            artifacts = await uow.asset_extractions.list_artifacts(job_id=str(job.id))
        return AssetExtractionResult(
            job=job,
            artifacts=tuple(artifacts),
            indexing_status=_indexing_status(job.status),
        )


class ListAssetExtractionsUseCase:
    def __init__(self, *, uow_factory: UnitOfWorkFactoryPort) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: ListAssetExtractionsQuery) -> AssetExtractionsResult:
        async with self._uow_factory() as uow:
            if query.asset_id:
                jobs = await uow.asset_extractions.list_for_asset(
                    asset_id=query.asset_id,
                    status=query.status,
                    limit=query.limit,
                    cursor_created_at=query.cursor_created_at,
                    cursor_id=query.cursor_id,
                )
            elif query.space_id and query.memory_scope_id:
                jobs = await uow.asset_extractions.list_for_scope(
                    space_id=str(query.space_id),
                    memory_scope_id=str(query.memory_scope_id),
                    thread_id=str(query.thread_id) if query.thread_id else None,
                    status=query.status,
                    limit=query.limit,
                    cursor_created_at=query.cursor_created_at,
                    cursor_id=query.cursor_id,
                )
            else:
                raise MemoryValidationError(
                    "asset_id or space_id and memory_scope_id are required"
                )
        return AssetExtractionsResult(jobs=tuple(jobs))


class ReadExtractionArtifactBytesUseCase:
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactoryPort,
        blob_storage: BlobStoragePort,
    ) -> None:
        self._uow_factory = uow_factory
        self._blob_storage = blob_storage

    async def execute(self, query: GetExtractionArtifactQuery) -> ExtractionArtifactBytesResult:
        async with self._uow_factory() as uow:
            artifact = await uow.asset_extractions.get_artifact_by_id(query.artifact_id)
        if artifact is None:
            raise MemoryNotFoundError("Extraction artifact not found")
        content = await self._blob_storage.read_bytes(storage_key=artifact.storage_key)
        return ExtractionArtifactBytesResult(artifact=artifact, content=content)


class RetryAssetExtractionUseCase:
    def __init__(self, *, uow_factory: UnitOfWorkFactoryPort, clock: ClockPort) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, command: RetryAssetExtractionCommand) -> AssetExtractionResult:
        async with self._uow_factory() as uow:
            job = await uow.asset_extractions.get_by_id(command.job_id)
            if job is None:
                raise MemoryNotFoundError("Asset extraction job not found")
            retried = job.reset_for_retry(now=self._clock.now())
            saved = await uow.asset_extractions.save(retried)
            await uow.outbox.enqueue(_asset_extract_event(saved))
            await uow.commit()
        return AssetExtractionResult(job=saved, indexing_status="pending")


class RunAssetExtractionUseCase:
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactoryPort,
        blob_storage: BlobStoragePort,
        detector: FileTypeDetectorPort,
        extractor: ContentExtractionPort,
        ingest_document,
        clock: ClockPort,
        ids: IdGeneratorPort,
        limits: ExtractionLimits,
        artifact_storage_backend: str = "local",
    ) -> None:
        self._uow_factory = uow_factory
        self._blob_storage = blob_storage
        self._detector = detector
        self._extractor = extractor
        self._ingest_document = ingest_document
        self._clock = clock
        self._ids = ids
        self._limits = limits
        self._artifact_storage_backend = artifact_storage_backend

    async def execute(self, command: RunAssetExtractionCommand) -> AssetExtractionResult:
        job = await self._mark_running(command)
        if job.status == AssetExtractionStatus.SUCCEEDED:
            async with self._uow_factory() as uow:
                artifacts = await uow.asset_extractions.list_artifacts(job_id=str(job.id))
            return AssetExtractionResult(
                job=job,
                artifacts=tuple(artifacts),
                indexing_status=_indexing_status(job.status),
            )
        async with self._uow_factory() as uow:
            asset = await uow.assets.get_by_id(str(job.asset_id))
        if asset is None or asset.status != AssetStatus.STORED:
            failed = await self._mark_failed(
                job,
                code="asset_extraction.asset_missing",
                message="Asset is missing or unavailable",
            )
            return AssetExtractionResult(job=failed, indexing_status="failed")

        try:
            content = await self._blob_storage.read_bytes(storage_key=asset.storage_key)
            await self._save_progress(
                job,
                stage="detecting_type",
                percent=20,
                message="Detecting file type",
            )
            detection = await self._detector.detect(
                FileTypeDetectionRequest(
                    filename=asset.filename,
                    declared_content_type=asset.content_type,
                    content=content,
                )
            )
            await self._save_progress(
                job,
                stage="extracting_content",
                percent=45,
                message="Extracting searchable content",
            )
            result = await self._extractor.extract(
                ExtractionRequest(
                    job_id=str(job.id),
                    asset_id=str(asset.id),
                    filename=asset.filename,
                    declared_content_type=asset.content_type,
                    detected_content_type=detection.content_type,
                    byte_size=asset.byte_size,
                    sha256_hex=asset.sha256_hex,
                    content=content,
                    parser_profile=job.parser_profile,
                    limits=self._limits,
                )
            )
        except Exception as exc:
            failed = await self._mark_failed(
                job,
                code=_safe_exception_code(exc),
                message=_safe_exception_message(exc),
            )
            raise MemoryInfrastructureError("Asset extraction failed") from exc

        if result.status == "unsupported":
            job = await self._reconcile_media_usage(job, result=result)
            unsupported = await self._mark_unsupported(job, result=result)
            return AssetExtractionResult(job=unsupported, indexing_status="unsupported")
        if result.status != "succeeded":
            failed = await self._mark_failed(
                job,
                code=result.safe_error_code or "asset_extraction.invalid_status",
                message=result.safe_error_message or "Extractor returned invalid status",
                metadata=result.technical_metadata,
            )
            raise MemoryInfrastructureError("Asset extraction returned invalid status")

        extracted_text = _extracted_text(result)
        if not extracted_text.strip():
            job = await self._reconcile_media_usage(job, result=result)
            unsupported = await self._mark_unsupported(
                job,
                result=ExtractionResult(
                    status="unsupported",
                    normalized_content_type=result.normalized_content_type,
                    title=result.title,
                    technical_metadata=result.technical_metadata,
                    diagnostics=result.diagnostics,
                    parser_name=result.parser_name,
                    parser_version=result.parser_version,
                    model_version=result.model_version,
                    safe_error_code="asset_extraction.empty_text",
                    safe_error_message="Extractor returned no searchable text",
                ),
            )
            return AssetExtractionResult(job=unsupported, indexing_status="unsupported")

        ingest = await self._ingest_document.execute(
            IngestDocumentCommand(
                space_id=asset.space_id,
                memory_scope_id=asset.memory_scope_id,
                thread_id=asset.thread_id,
                title=result.title or asset.filename,
                source_type=_SOURCE_TYPE,
                source_external_id=str(job.id),
                text=extracted_text,
                idempotency_key=f"asset_extraction:{job.id}:{content_hash(extracted_text)}",
                classification=asset.classification,
                chunk_metadata=_asset_extraction_chunk_metadata(
                    asset=asset,
                    job=job,
                    result=result,
                    extracted_text=extracted_text,
                ),
            )
        )
        await self._save_progress(
            job,
            stage="storing_artifacts",
            percent=80,
            message="Storing extracted evidence",
        )
        artifacts = await self._store_artifacts(
            job=job,
            result=result,
            markdown=extracted_text,
        )
        await self._save_progress(
            job,
            stage="indexing_memory",
            percent=90,
            message="Indexing extracted memory",
        )
        succeeded = await self._mark_succeeded(
            await self._reconcile_media_usage(job, result=result),
            result=result,
            result_document_ids=(str(ingest.document.id),),
        )
        return AssetExtractionResult(
            job=succeeded,
            artifacts=tuple(artifacts),
            indexing_status=ingest.indexing_status,
        )

    async def _mark_running(self, command: RunAssetExtractionCommand) -> AssetExtractionJob:
        async with self._uow_factory() as uow:
            job = await uow.asset_extractions.get_by_id(command.job_id)
            if job is None:
                raise MemoryNotFoundError("Asset extraction job not found")
            if job.status == AssetExtractionStatus.SUCCEEDED:
                return job
            running = job.mark_running(now=self._clock.now())
            running = running.with_metadata_updates(
                now=self._clock.now(),
                metadata={
                    "processing_stage": "reading_asset",
                    "progress_percent": 10,
                    "progress_message": "Reading uploaded asset",
                },
            )
            saved = await uow.asset_extractions.save(running)
            await uow.commit()
        return saved

    async def _save_progress(
        self,
        job: AssetExtractionJob,
        *,
        stage: str,
        percent: int,
        message: str,
    ) -> None:
        async with self._uow_factory() as uow:
            current = await uow.asset_extractions.get_by_id(str(job.id))
            if current is None:
                raise MemoryNotFoundError("Asset extraction job not found")
            if current.status != AssetExtractionStatus.RUNNING:
                return
            updated = current.with_metadata_updates(
                now=self._clock.now(),
                metadata={
                    "processing_stage": stage,
                    "progress_percent": max(0, min(percent, 99)),
                    "progress_message": message,
                },
            )
            await uow.asset_extractions.save(updated)
            await uow.commit()

    async def _store_artifacts(
        self,
        *,
        job: AssetExtractionJob,
        result: ExtractionResult,
        markdown: str,
    ) -> list[ExtractionArtifact]:
        candidates = [
            ExtractionArtifactCandidate(
                artifact_type="markdown",
                filename="extracted.md",
                content_type="text/markdown",
                content=markdown.encode("utf-8"),
                metadata={"parser": result.parser_name},
            ),
            ExtractionArtifactCandidate(
                artifact_type="extracted_json",
                filename="extracted.json",
                content_type="application/json",
                content=_result_json(result).encode("utf-8"),
                metadata={"parser": result.parser_name},
            ),
            *result.artifacts,
        ]
        stored: list[ExtractionArtifact] = []
        now = self._clock.now()
        for candidate in candidates:
            if not candidate.content:
                continue
            digest = sha256(candidate.content).hexdigest()
            artifact = ExtractionArtifact.create(
                artifact_id=ExtractionArtifactId(self._ids.new_id("artifact")),
                job_id=job.id,
                asset_id=job.asset_id,
                artifact_type=candidate.artifact_type,
                storage_backend=self._artifact_storage_backend,
                storage_key=_artifact_storage_key(
                    space_id=str(job.space_id),
                    memory_scope_id=str(job.memory_scope_id),
                    job_id=str(job.id),
                    digest=digest,
                    filename=candidate.filename,
                ),
                sha256_hex=digest,
                byte_size=len(candidate.content),
                now=now,
                metadata={
                    "content_type": candidate.content_type,
                    "filename": candidate.filename,
                    **candidate.metadata,
                },
            )
            await self._blob_storage.write_bytes(
                storage_key=artifact.storage_key,
                content=candidate.content,
            )
            stored.append(artifact)
        if stored:
            async with self._uow_factory() as uow:
                persisted = []
                for artifact in stored:
                    persisted.append(await uow.asset_extractions.create_artifact(artifact))
                await uow.commit()
            return persisted
        return []

    async def _mark_succeeded(
        self,
        job: AssetExtractionJob,
        *,
        result: ExtractionResult,
        result_document_ids: tuple[str, ...],
    ) -> AssetExtractionJob:
        async with self._uow_factory() as uow:
            current = await uow.asset_extractions.get_by_id(str(job.id))
            if current is None:
                raise MemoryNotFoundError("Asset extraction job not found")
            if current.status != AssetExtractionStatus.RUNNING:
                current = current.mark_running(now=self._clock.now())
            succeeded = current.mark_succeeded(
                now=self._clock.now(),
                result_document_ids=result_document_ids,
                parser_name=result.parser_name,
                parser_version=result.parser_version,
                model_version=result.model_version,
                metadata={
                    "normalized_content_type": result.normalized_content_type,
                    "language": result.language,
                    "element_count": len(result.elements),
                    **result.technical_metadata,
                },
            )
            saved = await uow.asset_extractions.save(succeeded)
            await uow.commit()
        return saved

    async def _reconcile_media_usage(
        self,
        job: AssetExtractionJob,
        *,
        result: ExtractionResult,
    ) -> AssetExtractionJob:
        actual_seconds = _actual_media_analysis_seconds(result)
        if actual_seconds is None:
            return job
        reserved_seconds = _positive_int(
            job.metadata.get("usage_media_analysis_seconds_requested")
        )
        if reserved_seconds is None or reserved_seconds <= 0:
            return job
        desired_delta = actual_seconds - reserved_seconds
        reconciliation_metadata = {
            "usage_media_analysis_seconds_actual": actual_seconds,
            "usage_media_analysis_seconds_delta": desired_delta,
            "usage_media_analysis_seconds_final": actual_seconds,
            "usage_reconciled": True,
        }

        window = UsageWindow.calendar_month_for(self._clock.now())
        key = _usage_reconciliation_idempotency_key(
            job_id=str(job.id),
            actual_seconds=actual_seconds,
        )
        async with self._uow_factory() as uow:
            current = await uow.asset_extractions.get_by_id(str(job.id))
            if current is None:
                raise MemoryNotFoundError("Asset extraction job not found")
            existing_adjustments = await uow.usage.list_for_source(
                source_type=USAGE_RECONCILIATION_SOURCE_TYPE,
                source_id=str(current.id),
                resource=UsageResource.MEDIA_ANALYSIS_SECONDS.value,
            )
            already_recorded_delta = sum(record.quantity for record in existing_adjustments)
            delta_to_record = desired_delta - already_recorded_delta
            existing = await uow.usage.find_by_idempotency_key(key)
            if delta_to_record != 0 and existing is None:
                await uow.usage.create(
                    UsageRecord.create(
                        record_id=UsageRecordId(self._ids.new_id("usage")),
                        subject_type=UsageSubjectType.SPACE.value,
                        subject_id=str(current.space_id),
                        space_id=current.space_id,
                        memory_scope_id=current.memory_scope_id,
                        resource=UsageResource.MEDIA_ANALYSIS_SECONDS.value,
                        quantity=delta_to_record,
                        source_type=USAGE_RECONCILIATION_SOURCE_TYPE,
                        source_id=str(current.id),
                        idempotency_key=key,
                        window=window,
                        now=self._clock.now(),
                        metadata={
                            "reserved_seconds": reserved_seconds,
                            "actual_seconds": actual_seconds,
                            "desired_delta_seconds": desired_delta,
                            "delta_seconds": delta_to_record,
                            "parser_profile": current.parser_profile,
                            "result_content_type": result.normalized_content_type,
                        },
                    )
                )
            updated = current.with_metadata_updates(
                now=self._clock.now(),
                metadata=reconciliation_metadata,
            )
            saved = await uow.asset_extractions.save(updated)
            await uow.commit()
        return saved

    async def _update_job_metadata(
        self,
        job: AssetExtractionJob,
        *,
        metadata: dict[str, object],
    ) -> AssetExtractionJob:
        async with self._uow_factory() as uow:
            current = await uow.asset_extractions.get_by_id(str(job.id))
            if current is None:
                raise MemoryNotFoundError("Asset extraction job not found")
            updated = current.with_metadata_updates(now=self._clock.now(), metadata=metadata)
            saved = await uow.asset_extractions.save(updated)
            await uow.commit()
        return saved

    async def _mark_unsupported(
        self,
        job: AssetExtractionJob,
        *,
        result: ExtractionResult,
    ) -> AssetExtractionJob:
        async with self._uow_factory() as uow:
            current = await uow.asset_extractions.get_by_id(str(job.id))
            if current is None:
                raise MemoryNotFoundError("Asset extraction job not found")
            unsupported = current.mark_unsupported(
                now=self._clock.now(),
                code=result.safe_error_code or "asset_extraction.unsupported",
                message=result.safe_error_message or "Asset type is unsupported",
                metadata={
                    "normalized_content_type": result.normalized_content_type,
                    **result.technical_metadata,
                },
            )
            saved = await uow.asset_extractions.save(unsupported)
            await uow.commit()
        return saved

    async def _mark_failed(
        self,
        job: AssetExtractionJob,
        *,
        code: str,
        message: str,
        metadata: dict[str, object] | None = None,
    ) -> AssetExtractionJob:
        async with self._uow_factory() as uow:
            current = await uow.asset_extractions.get_by_id(str(job.id))
            if current is None:
                raise MemoryNotFoundError("Asset extraction job not found")
            failed = current.mark_failed(
                now=self._clock.now(),
                code=code,
                message=message,
                metadata=metadata,
            )
            saved = await uow.asset_extractions.save(failed)
            await uow.commit()
        return saved


def _asset_extract_event(job: AssetExtractionJob) -> OutboxEvent:
    return OutboxEvent(
        event_type="asset.extract",
        aggregate_type="asset_extraction_job",
        aggregate_id=str(job.id),
        workload_class="extraction",
        fairness_key=f"{job.space_id}:{job.memory_scope_id}",
        payload={
            "job_id": str(job.id),
            "asset_id": str(job.asset_id),
            "parser_profile": job.parser_profile,
        },
    )


def _parser_config_hash(parser_profile: str) -> str:
    raw = f"{parser_profile}:{_DEFAULT_PARSER_CONFIG_VERSION}"
    return sha256(raw.encode("utf-8")).hexdigest()


def _usage_idempotency_key(
    *,
    asset_id: str,
    parser_profile: str,
    parser_config_hash: str,
    source_sha256_hex: str,
) -> str:
    return (
        "asset_extraction_media:"
        f"{asset_id}:{parser_profile}:{parser_config_hash}:{source_sha256_hex}"
    )


def _usage_reconciliation_idempotency_key(*, job_id: str, actual_seconds: int) -> str:
    return f"asset_extraction_media_reconcile:{job_id}:{actual_seconds}"


def _estimated_media_analysis_seconds(
    asset,
    *,
    default_unknown_media_seconds: int,
) -> int:
    content_type = asset.content_type.lower()
    if not (content_type.startswith("audio/") or content_type.startswith("video/")):
        return 0
    for key in (
        "media_duration_seconds",
        "estimated_media_seconds",
        "duration_seconds",
    ):
        parsed = _positive_int(asset.metadata.get(key))
        if parsed is not None:
            return parsed
    return default_unknown_media_seconds


def _actual_media_analysis_seconds(result: ExtractionResult) -> int | None:
    if result.status == "unsupported":
        return 0
    if result.status != "succeeded":
        return None

    metadata = result.technical_metadata
    for key in (
        "usage_media_analysis_seconds_actual",
        "media_analysis_seconds_actual",
        "media_duration_seconds",
        "duration_seconds",
        "estimated_media_seconds",
    ):
        parsed = _positive_duration_seconds(metadata.get(key))
        if parsed is not None:
            return parsed

    duration_ms = _positive_number(metadata.get("duration_ms"))
    if duration_ms is not None:
        return max(1, int(ceil(duration_ms / 1000)))
    return None


def _positive_duration_seconds(value: object) -> int | None:
    number = _positive_number(value)
    if number is None:
        return None
    return max(1, int(ceil(number)))


def _positive_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if number > 0 else None
    if isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
        return number if number > 0 else None
    return None


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = int(value)
        return number if number > 0 else None
    if isinstance(value, str):
        try:
            number = int(float(value.strip()))
        except ValueError:
            return None
        return number if number > 0 else None
    return None


def _indexing_status(status: AssetExtractionStatus) -> str:
    return {
        AssetExtractionStatus.PENDING: "pending",
        AssetExtractionStatus.RUNNING: "running",
        AssetExtractionStatus.SUCCEEDED: "indexed_or_pending",
        AssetExtractionStatus.FAILED: "failed",
        AssetExtractionStatus.UNSUPPORTED: "unsupported",
        AssetExtractionStatus.CANCELED: "canceled",
        AssetExtractionStatus.STALE: "stale",
    }[status]


def _extracted_text(result: ExtractionResult) -> str:
    if result.markdown and result.markdown.strip():
        return result.markdown.strip()
    return "\n\n".join(element.text.strip() for element in result.elements if element.text.strip())


def _asset_extraction_chunk_metadata(
    *,
    asset,
    job: AssetExtractionJob,
    result: ExtractionResult,
    extracted_text: str,
) -> dict[str, object]:
    refs = _extraction_source_refs(
        job=job,
        result=result,
        extracted_text=extracted_text,
    )
    metadata: dict[str, object] = {
        "source_kind": _SOURCE_TYPE,
        "asset_id": str(asset.id),
        "asset_filename": asset.filename,
        "asset_content_type": asset.content_type,
        "extraction_job_id": str(job.id),
        "parser_profile": job.parser_profile,
        "parser_name": result.parser_name,
        "normalized_content_type": result.normalized_content_type,
        "source_ref_count": len(refs),
        "source_refs": refs,
    }
    if result.parser_version:
        metadata["parser_version"] = result.parser_version
    if result.model_version:
        metadata["model_version"] = result.model_version
    if result.language:
        metadata["language"] = result.language
    return metadata


def _extraction_source_refs(
    *,
    job: AssetExtractionJob,
    result: ExtractionResult,
    extracted_text: str,
) -> list[dict[str, object]]:
    refs: list[dict[str, object]] = []
    cursor = 0
    for index, element in enumerate(result.elements):
        text = element.text.strip()
        if not text:
            continue
        span = _find_element_span(extracted_text, text, cursor)
        if span is not None:
            cursor = span[1]
        refs.append(
            _element_source_ref(
                job=job,
                index=index,
                element=element,
                text=text,
                span=span,
            )
        )
        if len(refs) >= _MAX_SOURCE_REFS:
            break
    if refs:
        return refs
    return [
        {
            "source_type": _SOURCE_TYPE,
            "source_id": str(job.id),
            "asset_id": str(job.asset_id),
            "kind": "extracted_text",
            "char_start": 0,
            "char_end": len(extracted_text),
            "quote_preview": extracted_text[:240],
        }
    ]


def _element_source_ref(
    *,
    job: AssetExtractionJob,
    index: int,
    element: ExtractedElement,
    text: str,
    span: tuple[int, int] | None,
) -> dict[str, object]:
    ref: dict[str, object] = {
        "source_type": _SOURCE_TYPE,
        "source_id": str(job.id),
        "asset_id": str(job.asset_id),
        "element_index": index,
        "kind": element.kind,
        "quote_preview": text[:240],
    }
    if span is not None:
        ref["char_start"] = span[0]
        ref["char_end"] = span[1]
    if element.page_number is not None:
        ref["page_number"] = element.page_number
    if element.time_start_ms is not None:
        ref["time_start_ms"] = element.time_start_ms
    if element.time_end_ms is not None:
        ref["time_end_ms"] = element.time_end_ms
    if element.bbox is not None:
        ref["bbox"] = [float(value) for value in element.bbox]
    if element.confidence is not None:
        ref["confidence"] = element.confidence
    provider_source = element.metadata.get("source")
    if isinstance(provider_source, str) and provider_source.strip():
        ref["provider_source"] = provider_source.strip()[:120]
    return ref


def _find_element_span(
    extracted_text: str,
    element_text: str,
    cursor: int,
) -> tuple[int, int] | None:
    start = extracted_text.find(element_text, max(cursor, 0))
    if start < 0:
        start = extracted_text.find(element_text)
    if start < 0:
        return None
    return start, start + len(element_text)


def _result_json(result: ExtractionResult) -> str:
    payload = {
        "status": result.status,
        "normalized_content_type": result.normalized_content_type,
        "title": result.title,
        "language": result.language,
        "parser_name": result.parser_name,
        "parser_version": result.parser_version,
        "model_version": result.model_version,
        "technical_metadata": result.technical_metadata,
        "diagnostics": result.diagnostics,
        "elements": [
            {
                "kind": element.kind,
                "text": element.text,
                "page_number": element.page_number,
                "time_start_ms": element.time_start_ms,
                "time_end_ms": element.time_end_ms,
                "bbox": element.bbox,
                "confidence": element.confidence,
                "metadata": element.metadata,
            }
            for element in result.elements
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _artifact_storage_key(
    *,
    space_id: str,
    memory_scope_id: str,
    job_id: str,
    digest: str,
    filename: str,
) -> str:
    safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in filename)[:160]
    return f"{space_id}/{memory_scope_id}/extractions/{job_id}/{digest[:2]}/{digest}/{safe_name}"


def _safe_exception_code(exc: Exception) -> str:
    name = exc.__class__.__name__.lower()
    return f"asset_extraction.{name[:80]}"


def _safe_exception_message(exc: Exception) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    return text[:500]
