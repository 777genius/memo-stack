"""Outbox worker for derived adapter side effects."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import timedelta

from memory_adapters.postgres.models import MemoryOutboxRow
from memory_core.domain.entities import FactStatus, LifecycleStatus
from memory_core.ports.adapters import (
    AdapterCapabilities,
    PortDiagnostic,
    PortStatus,
    VectorUpsertItem,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memory_server.composition import Container, build_container
from memory_server.config import Settings

MAX_ATTEMPTS = 5
RUNNING_LEASE_TIMEOUT = timedelta(minutes=5)


@dataclass(frozen=True)
class ClaimedOutboxJob:
    id: int
    event_type: str
    aggregate_id: str
    aggregate_version: int | None
    payload_json: dict[str, object]


class OutboxWorker:
    def __init__(self, container: Container) -> None:
        self._container = container

    async def run_once(self, *, limit: int = 25) -> int:
        jobs = await self._claim_pending(limit=limit)
        for job in jobs:
            try:
                await self._handle(job)
            except Exception as exc:
                await self._mark_retry_or_dead(job.id, _safe_error(exc))
            else:
                await self._mark_done(job.id)
        return len(jobs)

    async def _claim_pending(self, *, limit: int) -> list[ClaimedOutboxJob]:
        now = self._container.clock.now()
        async with AsyncSession(self._container.engine) as session:
            await self._recover_expired_running_jobs(session, now=now, limit=limit)
            rows = list(
                (
                    await session.execute(
                        select(MemoryOutboxRow)
                        .where(
                            MemoryOutboxRow.status.in_(("pending", "retry_pending")),
                            MemoryOutboxRow.next_attempt_at <= now,
                        )
                        .order_by(MemoryOutboxRow.created_at)
                        .limit(limit)
                        .with_for_update(skip_locked=True)
                    )
                ).scalars()
            )
            claimed = [
                ClaimedOutboxJob(
                    id=row.id,
                    event_type=row.event_type,
                    aggregate_id=row.aggregate_id,
                    aggregate_version=row.aggregate_version,
                    payload_json=dict(row.payload_json),
                )
                for row in rows
            ]
            for row in rows:
                row.status = "running"
                row.updated_at = now
            await session.commit()
            return claimed

    async def _recover_expired_running_jobs(
        self,
        session: AsyncSession,
        *,
        now,
        limit: int,
    ) -> None:
        lease_cutoff = now - RUNNING_LEASE_TIMEOUT
        rows = list(
            (
                await session.execute(
                    select(MemoryOutboxRow)
                    .where(
                        MemoryOutboxRow.status == "running",
                        MemoryOutboxRow.updated_at <= lease_cutoff,
                    )
                    .order_by(MemoryOutboxRow.updated_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).scalars()
        )
        for row in rows:
            row.attempt_count += 1
            row.last_safe_error = "Worker lease expired"
            row.updated_at = now
            if row.attempt_count >= MAX_ATTEMPTS:
                row.status = "dead"
            else:
                row.status = "retry_pending"
                row.next_attempt_at = now

    async def _handle(self, job: ClaimedOutboxJob) -> None:
        if job.event_type in {"vector.upsert_chunk", "vector.upsert_chunks"}:
            await self._handle_vector_upsert(job)
        elif job.event_type == "vector.delete_chunks":
            chunk_ids = tuple(str(value) for value in job.payload_json.get("chunk_ids", []))
            result = await self._container.vector_index.delete_chunks(chunk_ids)
            _raise_if_degraded(result.status, "vector.delete_chunks", result.diagnostics)
        elif job.event_type == "graph.upsert_fact":
            await self._handle_graph_upsert(job)
        elif job.event_type == "graph.delete_fact":
            fact_id = str(job.payload_json.get("fact_id") or job.aggregate_id)
            result = await self._container.graph_index.delete_fact(fact_id)
            _raise_if_degraded(result.status, "graph.delete_fact", result.diagnostics)
        else:
            raise ValueError(f"Unknown outbox event type: {job.event_type}")

    async def _handle_vector_upsert(self, job: ClaimedOutboxJob) -> None:
        chunk_id = str(job.payload_json.get("chunk_id") or job.aggregate_id)
        async with self._container.uow_factory() as uow:
            chunk = await uow.chunks.get_by_id(chunk_id)
        if chunk is None or chunk.status != LifecycleStatus.ACTIVE:
            await self._container.vector_index.delete_chunks((chunk_id,))
            return
        if not _can_embed(chunk.classification):
            return
        capabilities = await self._container.vector_index.capabilities()
        if _capability_is_disabled(capabilities):
            return
        if not capabilities.enabled or not capabilities.healthy or not capabilities.supports_upsert:
            raise RuntimeError("vector adapter unavailable")

        embedding = await self._container.embedder.embed_texts((chunk.text,))
        if _is_disabled_projection(embedding.diagnostics):
            return
        _raise_if_degraded(embedding.status, "embeddings.embed_texts", embedding.diagnostics)
        if not embedding.vectors:
            raise RuntimeError("Embedding adapter returned no vectors")

        result = await self._container.vector_index.upsert_chunks(
            (
                VectorUpsertItem(
                    chunk_id=str(chunk.id),
                    space_id=str(chunk.space_id),
                    profile_id=str(chunk.profile_id),
                    thread_id=str(chunk.thread_id) if chunk.thread_id else None,
                    text=chunk.text,
                    vector=embedding.vectors[0],
                    projection_version="v1",
                    metadata={
                        "source_type": chunk.source_type,
                        "kind": chunk.kind.value,
                        "classification": chunk.classification,
                    },
                ),
            )
        )
        _raise_if_degraded(result.status, "vector.upsert_chunks", result.diagnostics)

    async def _handle_graph_upsert(self, job: ClaimedOutboxJob) -> None:
        async with self._container.uow_factory() as uow:
            fact = await uow.facts.get_by_id(job.aggregate_id)
        if fact is None or fact.status != FactStatus.ACTIVE:
            await self._container.graph_index.delete_fact(job.aggregate_id)
            return
        if job.aggregate_version and fact.version != job.aggregate_version:
            return
        result = await self._container.graph_index.upsert_fact(
            str(fact.id),
            fact.text,
            {
                "space_id": str(fact.space_id),
                "profile_id": str(fact.profile_id),
                "updated_at": fact.updated_at.isoformat(),
            },
        )
        _raise_if_degraded(result.status, "graph.upsert_fact", result.diagnostics)

    async def _mark_done(self, job_id: int) -> None:
        now = self._container.clock.now()
        async with AsyncSession(self._container.engine) as session:
            row = await session.get(MemoryOutboxRow, job_id)
            if row:
                row.status = "done"
                row.last_safe_error = None
                row.updated_at = now
            await session.commit()

    async def _mark_retry_or_dead(self, job_id: int, safe_error: str) -> None:
        now = self._container.clock.now()
        async with AsyncSession(self._container.engine) as session:
            row = await session.get(MemoryOutboxRow, job_id)
            if row:
                row.attempt_count += 1
                row.last_safe_error = safe_error[:400]
                row.updated_at = now
                if row.attempt_count >= MAX_ATTEMPTS:
                    row.status = "dead"
                else:
                    row.status = "retry_pending"
                    row.next_attempt_at = now + timedelta(seconds=2**row.attempt_count)
            await session.commit()


def _raise_if_degraded(
    status: PortStatus,
    operation: str,
    diagnostics: tuple[PortDiagnostic, ...] = (),
) -> None:
    if _is_disabled_projection(diagnostics):
        return
    if status != PortStatus.OK:
        raise RuntimeError(f"{operation} degraded")


def _is_disabled_projection(diagnostics: tuple[PortDiagnostic, ...]) -> bool:
    return any(diagnostic.code.endswith(".disabled") for diagnostic in diagnostics)


def _capability_is_disabled(capabilities: AdapterCapabilities) -> bool:
    return not capabilities.enabled and capabilities.degraded_reason == "disabled"


def _can_embed(classification: str) -> bool:
    return classification in {"public", "internal"}


def _safe_error(exc: Exception) -> str:
    return exc.__class__.__name__[:400]


async def _run(args: argparse.Namespace) -> None:
    worker = OutboxWorker(build_container(Settings()))
    while True:
        count = await worker.run_once(limit=args.limit)
        print({"processed": count})
        if args.once:
            return
        await asyncio.sleep(args.sleep_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Memory Platform outbox worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--sleep-seconds", type=float, default=2.0)
    args = parser.parse_args()
    if not args.once and not args.loop:
        args.once = True
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
