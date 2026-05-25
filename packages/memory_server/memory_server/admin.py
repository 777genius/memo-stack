"""Production-safe admin and repair commands."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from memory_adapters.postgres.models import (
    Base,
    MemoryChunkRow,
    MemoryDocumentRow,
    MemoryEpisodeRow,
    MemoryFactRow,
    MemoryIdempotencyRecordRow,
    MemoryOutboxRow,
    MemoryProfileRow,
    MemorySourceRefRow,
    MemorySpaceRow,
    MemorySuggestionRow,
)
from memory_core.application import EnsureScopeCommand
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from memory_server.auth_tokens import (
    create_service_token,
    list_service_tokens,
    revoke_service_token,
)
from memory_server.composition import build_container
from memory_server.config import DeployProfile, Settings
from memory_server.profile_transfer import export_profile, import_profile


async def seed_defaults() -> dict[str, object]:
    container = build_container(Settings())
    try:
        scope = await container.ensure_scope.execute(
            EnsureScopeCommand(
                space_slug=container.settings.default_space_slug,
                profile_external_ref=container.settings.default_profile_external_ref,
            )
        )
        return {
            "status": "ok",
            "space_id": str(scope.space_id),
            "profile_id": str(scope.profile_id),
            "thread_id": str(scope.thread_id) if scope.thread_id else None,
        }
    finally:
        await container.engine.dispose()


async def doctor() -> dict[str, object]:
    container = build_container(Settings())
    try:
        capabilities = await container.get_capabilities.execute()
        async with AsyncSession(container.engine) as session:
            pending = await _count_outbox(session, "pending")
            dead = await _count_outbox(session, "dead")
        return {
            "status": "degraded" if dead else "ok",
            "adapters": {
                adapter.name: {
                    "enabled": adapter.enabled,
                    "healthy": adapter.healthy,
                    "degraded_reason": adapter.degraded_reason,
                }
                for adapter in capabilities.adapters
            },
            "outbox": {"pending": pending, "dead": dead},
        }
    finally:
        await container.engine.dispose()


async def invariant_check(
    *,
    space: str | None = None,
    profile: str | None = None,
) -> dict[str, object]:
    container = build_container(Settings())
    try:
        async with AsyncSession(container.engine) as session:
            scope = await _resolve_scope(session, space=space, profile=profile)
            if (space or profile) and scope is None:
                return {
                    "status": "not_found",
                    "checks": [],
                    "space": space,
                    "profile": profile,
                }
            scope_filters = _scope_filters(scope)
            active_facts = await session.scalar(
                select(func.count())
                .select_from(MemoryFactRow)
                .where(MemoryFactRow.status == "active", *scope_filters.for_model(MemoryFactRow))
            )
            active_chunks = await session.scalar(
                select(func.count())
                .select_from(MemoryChunkRow)
                .where(MemoryChunkRow.status == "active", *scope_filters.for_model(MemoryChunkRow))
            )
            dead = await _count_outbox(session, "dead")
            checks = [
                await _check_active_fact_source_refs(session, scope_filters),
                await _check_active_chunk_parent_exists(session, scope_filters),
                await _check_profile_rows_match_scope(session, scope_filters),
                await _check_deleted_document_has_no_active_chunks(session, scope_filters),
                await _check_idempotency_results_exist(session, scope_filters),
                _check_dead_outbox(dead),
            ]
        failed = [check for check in checks if check["status"] != "ok"]
        active_facts_without_source_refs = next(
            check["count"] for check in checks if check["name"] == "active_fact_source_refs"
        )
        return {
            "status": "ok" if not failed else "failed",
            "space": space,
            "profile": profile,
            "checks": checks,
            "active_facts": int(active_facts or 0),
            "active_facts_without_source_refs": int(active_facts_without_source_refs),
            "active_chunks": int(active_chunks or 0),
            "dead_outbox_jobs": dead,
        }
    finally:
        await container.engine.dispose()


async def _check_active_fact_source_refs(
    session: AsyncSession,
    scope_filters: ScopeFilters,
) -> dict[str, object]:
    rows = list(
        (
            await session.execute(
                select(MemoryFactRow.id)
                .outerjoin(
                    MemorySourceRefRow,
                    (MemorySourceRefRow.fact_id == MemoryFactRow.id)
                    & (MemorySourceRefRow.fact_version == MemoryFactRow.version),
                )
                .where(
                    MemoryFactRow.status == "active",
                    MemorySourceRefRow.id.is_(None),
                    *scope_filters.for_model(MemoryFactRow),
                )
                .order_by(MemoryFactRow.id)
                .limit(50)
            )
        ).scalars()
    )
    return _check("active_fact_source_refs", rows)


async def _check_active_chunk_parent_exists(
    session: AsyncSession,
    scope_filters: ScopeFilters,
) -> dict[str, object]:
    document_exists = exists(
        select(MemoryDocumentRow.id).where(MemoryDocumentRow.id == MemoryChunkRow.document_id)
    )
    episode_exists = exists(
        select(MemoryEpisodeRow.id).where(MemoryEpisodeRow.id == MemoryChunkRow.episode_id)
    )
    rows = list(
        (
            await session.execute(
                select(MemoryChunkRow.id)
                .where(
                    MemoryChunkRow.status == "active",
                    or_(
                        and_(
                            MemoryChunkRow.document_id.is_(None),
                            MemoryChunkRow.episode_id.is_(None),
                        ),
                        and_(
                            MemoryChunkRow.document_id.is_not(None),
                            ~document_exists,
                        ),
                        and_(
                            MemoryChunkRow.episode_id.is_not(None),
                            ~episode_exists,
                        ),
                    ),
                    *scope_filters.for_model(MemoryChunkRow),
                )
                .order_by(MemoryChunkRow.id)
                .limit(50)
            )
        ).scalars()
    )
    return _check("active_chunk_parent_exists", rows)


async def _check_profile_rows_match_scope(
    session: AsyncSession,
    scope_filters: ScopeFilters,
) -> dict[str, object]:
    ids: list[str] = []
    for model, prefix in (
        (MemoryFactRow, "fact"),
        (MemoryDocumentRow, "doc"),
        (MemoryChunkRow, "chunk"),
        (MemorySuggestionRow, "suggestion"),
    ):
        ids.extend(
            f"{prefix}:{row_id}"
            for row_id in (
                await session.execute(
                    select(model.id)
                    .outerjoin(
                        MemoryProfileRow,
                        (MemoryProfileRow.id == model.profile_id)
                        & (MemoryProfileRow.space_id == model.space_id),
                    )
                    .where(
                        MemoryProfileRow.id.is_(None),
                        *scope_filters.for_model(model),
                    )
                    .order_by(model.id)
                    .limit(50)
                )
            ).scalars()
        )
    return _check("profile_scoped_rows_match_profile", ids[:50])


async def _check_deleted_document_has_no_active_chunks(
    session: AsyncSession,
    scope_filters: ScopeFilters,
) -> dict[str, object]:
    rows = list(
        (
            await session.execute(
                select(MemoryChunkRow.id)
                .join(MemoryDocumentRow, MemoryDocumentRow.id == MemoryChunkRow.document_id)
                .where(
                    MemoryChunkRow.status == "active",
                    MemoryDocumentRow.status == "deleted",
                    *scope_filters.for_model(MemoryChunkRow),
                )
                .order_by(MemoryChunkRow.id)
                .limit(50)
            )
        ).scalars()
    )
    return _check("deleted_document_active_chunks", rows)


async def _check_idempotency_results_exist(
    session: AsyncSession,
    scope_filters: ScopeFilters,
) -> dict[str, object]:
    rows = list(
        (
            await session.execute(
                select(MemoryIdempotencyRecordRow).where(*scope_filters.for_idempotency())
            )
        ).scalars()
    )
    broken: list[str] = []
    for row in rows:
        model = {
            "fact": MemoryFactRow,
            "document": MemoryDocumentRow,
            "episode": MemoryEpisodeRow,
        }.get(row.result_type)
        if model is None:
            broken.append(str(row.id))
            continue
        exists_result = await session.scalar(
            select(func.count()).select_from(model).where(model.id == row.result_id)
        )
        if int(exists_result or 0) == 0:
            broken.append(str(row.id))
    return _check("idempotency_results_exist", broken[:50])


def _check_dead_outbox(dead: int) -> dict[str, object]:
    return {
        "name": "dead_outbox_jobs",
        "status": "ok" if dead == 0 else "failed",
        "count": dead,
        "ids": [],
    }


def _check(name: str, ids: list[str]) -> dict[str, object]:
    return {
        "name": name,
        "status": "ok" if not ids else "failed",
        "count": len(ids),
        "ids": ids[:20],
    }


class ScopeFilters:
    def __init__(self, *, space_id: str | None, profile_id: str | None) -> None:
        self.space_id = space_id
        self.profile_id = profile_id

    def for_model(self, model) -> list[object]:
        filters = []
        if self.space_id is not None:
            filters.append(model.space_id == self.space_id)
        if self.profile_id is not None:
            filters.append(model.profile_id == self.profile_id)
        return filters

    def for_idempotency(self) -> list[object]:
        if self.space_id is None:
            return []
        return [MemoryIdempotencyRecordRow.space_id == self.space_id]


async def _resolve_scope(
    session: AsyncSession,
    *,
    space: str | None,
    profile: str | None,
) -> tuple[str | None, str | None] | None:
    if space is None and profile is None:
        return (None, None)
    if space is None or profile is None:
        return None
    space_row = (
        await session.execute(select(MemorySpaceRow).where(MemorySpaceRow.slug == space))
    ).scalar_one_or_none()
    if space_row is None:
        return None
    profile_row = (
        await session.execute(
            select(MemoryProfileRow).where(
                MemoryProfileRow.space_id == space_row.id,
                MemoryProfileRow.external_ref == profile,
            )
        )
    ).scalar_one_or_none()
    if profile_row is None:
        return None
    return (space_row.id, profile_row.id)


def _scope_filters(scope: tuple[str | None, str | None] | None) -> ScopeFilters:
    space_id, profile_id = scope or (None, None)
    return ScopeFilters(space_id=space_id, profile_id=profile_id)


async def repair_projections(
    *,
    space: str | None,
    profile: str | None,
    dry_run: bool,
) -> dict[str, object]:
    if not space or not profile:
        return {
            "status": "refused",
            "reason": "repair requires --space and --profile",
            "dry_run": dry_run,
        }
    if not dry_run:
        return {
            "status": "refused",
            "reason": "repair requires --dry-run in Core Lite",
            "dry_run": dry_run,
        }
    container = build_container(Settings())
    try:
        async with AsyncSession(container.engine) as session:
            scope = await _resolve_scope(session, space=space, profile=profile)
            if scope is None:
                return {
                    "status": "not_found",
                    "space": space,
                    "profile": profile,
                    "dry_run": dry_run,
                }
            scope_filters = _scope_filters(scope)
            active_chunks = int(
                (
                    await session.scalar(
                        select(func.count())
                        .select_from(MemoryChunkRow)
                        .where(
                            MemoryChunkRow.status == "active",
                            *scope_filters.for_model(MemoryChunkRow),
                        )
                    )
                )
                or 0
            )
            active_facts = int(
                (
                    await session.scalar(
                        select(func.count())
                        .select_from(MemoryFactRow)
                        .where(
                            MemoryFactRow.status == "active",
                            *scope_filters.for_model(MemoryFactRow),
                        )
                    )
                )
                or 0
            )
        return {
            "status": "ok",
            "space": space,
            "profile": profile,
            "dry_run": dry_run,
            "qdrant": {
                "would_upsert": active_chunks,
                "would_delete": 0,
            },
            "graphiti": {
                "would_upsert": active_facts,
                "would_delete": 0,
            },
        }
    finally:
        await container.engine.dispose()


async def replay_outbox(*, status: str, limit: int) -> dict[str, object]:
    container = build_container(Settings())
    try:
        async with AsyncSession(container.engine) as session:
            rows = list(
                (
                    await session.execute(
                        select(MemoryOutboxRow)
                        .where(MemoryOutboxRow.status == status)
                        .order_by(MemoryOutboxRow.created_at)
                        .limit(limit)
                    )
                ).scalars()
            )
            now = container.clock.now()
            for row in rows:
                row.status = "pending"
                row.next_attempt_at = now
                row.updated_at = now
            await session.commit()
        return {"replayed": len(rows), "from_status": status}
    finally:
        await container.engine.dispose()


async def token_create(
    *,
    space_id: str | None,
    profile_ids: tuple[str, ...] | None = None,
    description: str,
    expires_at: str | None = None,
    permissions: tuple[str, ...] | None = None,
) -> dict[str, object]:
    container = build_container(Settings())
    try:
        parsed_expires_at = _parse_optional_datetime(expires_at)
        token = await create_service_token(
            engine=container.engine,
            now=container.clock.now(),
            token_id=container.ids.new_id("tok"),
            description=description,
            space_id=space_id,
            profile_ids=profile_ids,
            expires_at=parsed_expires_at,
            permissions=permissions,
        )
        return {
            "status": "created",
            "token_id": token.token_id,
            "token": token.token,
            "space_id": token.space_id,
            "profile_ids": list(token.profile_ids) if token.profile_ids is not None else None,
            "description": token.description,
            "permissions": list(token.permissions),
            "expires_at": parsed_expires_at.isoformat() if parsed_expires_at else None,
        }
    finally:
        await container.engine.dispose()


async def token_list(*, space_id: str | None) -> dict[str, object]:
    container = build_container(Settings())
    try:
        return {
            "status": "ok",
            "tokens": await list_service_tokens(engine=container.engine, space_id=space_id),
        }
    finally:
        await container.engine.dispose()


async def token_revoke(*, token_id: str) -> dict[str, object]:
    container = build_container(Settings())
    try:
        return await revoke_service_token(
            engine=container.engine,
            now=container.clock.now(),
            token_id=token_id,
        )
    finally:
        await container.engine.dispose()


async def reset_local(*, confirmed: bool) -> dict[str, object]:
    settings = Settings()
    if settings.deploy_profile == DeployProfile.SERVER:
        return {"status": "refused", "reason": "reset-local is forbidden in server profile"}
    if not confirmed:
        return {
            "status": "refused",
            "reason": "pass --i-understand-this-deletes-local-memory to reset local memory",
        }
    container = build_container(settings)
    try:
        async with container.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
        return {"status": "ok", "operation": "reset-local"}
    finally:
        await container.engine.dispose()


async def export_profile_command(
    *,
    space: str,
    profile: str,
    out: str,
    redacted: bool,
) -> dict[str, object]:
    container = build_container(Settings())
    try:
        return await export_profile(
            engine=container.engine,
            space_slug=space,
            profile_external_ref=profile,
            out_path=Path(out),
            redacted=redacted,
        )
    finally:
        await container.engine.dispose()


async def import_profile_command(
    *,
    space: str,
    profile: str,
    file: str,
    dry_run: bool,
    merge_strategy: str,
    confirmed: bool = False,
) -> dict[str, object]:
    if not dry_run and not confirmed:
        return {
            "status": "refused",
            "reason": "import-profile requires --i-understand-this-writes-canonical-memory",
        }
    container = build_container(Settings())
    try:
        if dry_run:
            space_id = ""
            profile_id = ""
        else:
            scope = await container.ensure_scope.execute(
                EnsureScopeCommand(space_slug=space, profile_external_ref=profile)
            )
            space_id = str(scope.space_id)
            profile_id = str(scope.profile_id)
        return await import_profile(
            engine=container.engine,
            now=container.clock.now(),
            space_id=space_id,
            profile_id=profile_id,
            in_path=Path(file),
            dry_run=dry_run,
            merge_strategy=merge_strategy,
        )
    finally:
        await container.engine.dispose()


async def _count_outbox(session: AsyncSession, status: str) -> int:
    return int(
        (
            await session.scalar(
                select(func.count())
                .select_from(MemoryOutboxRow)
                .where(MemoryOutboxRow.status == status)
            )
        )
        or 0
    )


async def _run(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "seed-defaults":
        return await seed_defaults()
    if args.command == "doctor":
        return await doctor()
    if args.command in {"invariant-check", "check-invariants"}:
        return await invariant_check(space=args.space, profile=args.profile)
    if args.command in {"repair-projections", "reindex-qdrant", "reindex-graphiti"}:
        return await repair_projections(
            space=args.space,
            profile=args.profile,
            dry_run=args.dry_run,
        )
    if args.command == "replay-outbox":
        return await replay_outbox(status=args.status, limit=args.limit)
    if args.command == "token":
        if args.token_command == "create":
            return await token_create(
                space_id=args.space,
                profile_ids=tuple(args.profile) if args.profile else None,
                description=args.description,
                expires_at=args.expires_at,
                permissions=tuple(args.permission) if args.permission else None,
            )
        if args.token_command == "list":
            return await token_list(space_id=args.space)
        if args.token_command == "revoke":
            return await token_revoke(token_id=args.token_id)
    if args.command == "reset-local":
        return await reset_local(confirmed=args.i_understand_this_deletes_local_memory)
    if args.command == "export-profile":
        return await export_profile_command(
            space=args.space,
            profile=args.profile,
            out=args.out,
            redacted=args.redacted,
        )
    if args.command == "import-profile":
        return await import_profile_command(
            space=args.space,
            profile=args.profile,
            file=args.file,
            dry_run=args.dry_run,
            merge_strategy=args.merge_strategy,
            confirmed=args.i_understand_this_writes_canonical_memory,
        )
    raise ValueError(f"Unknown command: {args.command}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Memory Platform admin commands")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed-defaults")
    sub.add_parser("doctor")
    invariant = sub.add_parser("invariant-check")
    invariant.add_argument("--space", default=None)
    invariant.add_argument("--profile", default=None)
    check_invariants = sub.add_parser("check-invariants")
    check_invariants.add_argument("--space", default=None)
    check_invariants.add_argument("--profile", default=None)
    for command in ("repair-projections", "reindex-qdrant", "reindex-graphiti"):
        repair = sub.add_parser(command)
        repair.add_argument("--space", default=None)
        repair.add_argument("--profile", default=None)
        repair.add_argument("--dry-run", action="store_true")
    replay = sub.add_parser("replay-outbox")
    replay.add_argument("--status", default="dead")
    replay.add_argument("--limit", type=int, default=50)
    token = sub.add_parser("token")
    token_sub = token.add_subparsers(dest="token_command", required=True)
    token_create_parser = token_sub.add_parser("create")
    token_create_parser.add_argument("--space", default=None)
    token_create_parser.add_argument(
        "--profile",
        action="append",
        default=[],
        help="Repeatable profile id or external ref for profile-scoped tokens",
    )
    token_create_parser.add_argument("--description", required=True)
    token_create_parser.add_argument("--expires-at", default=None)
    token_create_parser.add_argument(
        "--permission",
        action="append",
        default=[],
        help="Repeatable permission, for example memory:read or memory:write",
    )
    token_list_parser = token_sub.add_parser("list")
    token_list_parser.add_argument("--space", default=None)
    token_revoke_parser = token_sub.add_parser("revoke")
    token_revoke_parser.add_argument("--token-id", required=True)
    reset = sub.add_parser("reset-local")
    reset.add_argument("--i-understand-this-deletes-local-memory", action="store_true")
    export = sub.add_parser("export-profile")
    export.add_argument("--space", required=True)
    export.add_argument("--profile", required=True)
    export.add_argument("--out", required=True)
    export.add_argument("--redacted", action="store_true")
    import_parser = sub.add_parser("import-profile")
    import_parser.add_argument("--space", required=True)
    import_parser.add_argument("--profile", required=True)
    import_parser.add_argument("--file", required=True)
    import_parser.add_argument("--dry-run", action="store_true")
    import_parser.add_argument("--i-understand-this-writes-canonical-memory", action="store_true")
    import_parser.add_argument(
        "--merge-strategy",
        default="fail_on_conflict",
        choices=("fail_on_conflict", "skip_existing"),
    )
    result = asyncio.run(_run(parser.parse_args()))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result.get("status") in {"failed", "refused", "conflict"}:
        sys.exit(1)


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


if __name__ == "__main__":
    main()
