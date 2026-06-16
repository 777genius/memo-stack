"""Manual context-link CRUD use cases."""

from __future__ import annotations

from memo_stack_core.application.dto import (
    ContextLinkResult,
    CreateContextLinkCommand,
    DeleteContextLinkCommand,
    ListContextLinksQuery,
    UpdateContextLinkCommand,
)
from memo_stack_core.application.use_cases.context_link_visibility import (
    assert_context_link_endpoint_visible,
)
from memo_stack_core.domain.assets import MemoryContextLink, MemoryContextLinkId
from memo_stack_core.domain.errors import (
    MemoryConflictError,
    MemoryNotFoundError,
    MemoryValidationError,
)
from memo_stack_core.ports.clock import ClockPort
from memo_stack_core.ports.ids import IdGeneratorPort
from memo_stack_core.ports.unit_of_work import UnitOfWorkFactoryPort


class CreateContextLinkUseCase:
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactoryPort,
        clock: ClockPort,
        ids: IdGeneratorPort,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._ids = ids

    async def execute(self, command: CreateContextLinkCommand) -> ContextLinkResult:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            await assert_context_link_endpoint_visible(
                uow,
                endpoint_type=command.source_type,
                endpoint_id=command.source_id,
                space_id=str(command.space_id),
                memory_scope_id=str(command.memory_scope_id),
                role="source",
            )
            await assert_context_link_endpoint_visible(
                uow,
                endpoint_type=command.target_type,
                endpoint_id=command.target_id,
                space_id=str(command.space_id),
                memory_scope_id=str(command.memory_scope_id),
                role="target",
            )
            existing = await uow.context_links.find_active(
                space_id=str(command.space_id),
                memory_scope_id=str(command.memory_scope_id),
                source_type=command.source_type,
                source_id=command.source_id,
                target_type=command.target_type,
                target_id=command.target_id,
                relation_type=command.relation_type,
            )
            if existing is not None:
                return ContextLinkResult(link=existing, duplicate=True)
            link = MemoryContextLink.create(
                link_id=MemoryContextLinkId(self._ids.new_id("ctxlink")),
                space_id=command.space_id,
                memory_scope_id=command.memory_scope_id,
                source_type=command.source_type,
                source_id=command.source_id,
                target_type=command.target_type,
                target_id=command.target_id,
                relation_type=command.relation_type,
                confidence=command.confidence,
                reason=command.reason,
                metadata=command.metadata,
                now=now,
            )
            saved = await uow.context_links.create(link)
            await uow.commit()
        return ContextLinkResult(link=saved)


class ListContextLinksUseCase:
    def __init__(self, *, uow_factory: UnitOfWorkFactoryPort) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: ListContextLinksQuery) -> list[MemoryContextLink]:
        async with self._uow_factory() as uow:
            if query.source_type is None and query.source_id is None:
                return await uow.context_links.list_for_scope(
                    space_id=str(query.space_id),
                    memory_scope_id=str(query.memory_scope_id),
                    status=query.status,
                    limit=query.limit,
                    statuses=query.statuses,
                )
            if query.source_type is None or query.source_id is None:
                raise MemoryValidationError("Context link source requires type and id")
            return await uow.context_links.list_for_source(
                space_id=str(query.space_id),
                memory_scope_id=str(query.memory_scope_id),
                source_type=query.source_type,
                source_id=query.source_id,
                status=query.status,
                limit=query.limit,
                statuses=query.statuses,
            )


class DeleteContextLinkUseCase:
    def __init__(self, *, uow_factory: UnitOfWorkFactoryPort, clock: ClockPort) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, command: DeleteContextLinkCommand) -> ContextLinkResult:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            link = await uow.context_links.get_by_id(command.context_link_id)
            if link is None:
                raise MemoryNotFoundError("Context link not found")
            saved = await uow.context_links.save(link.delete(now=now))
            await uow.commit()
        return ContextLinkResult(link=saved)


class UpdateContextLinkUseCase:
    def __init__(self, *, uow_factory: UnitOfWorkFactoryPort, clock: ClockPort) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, command: UpdateContextLinkCommand) -> ContextLinkResult:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            link = await uow.context_links.get_by_id(command.context_link_id)
            if link is None:
                raise MemoryNotFoundError("Context link not found")
            source_type = command.source_type or link.source_type
            source_id = command.source_id or link.source_id
            target_type = command.target_type or link.target_type
            target_id = command.target_id or link.target_id
            relation_type = command.relation_type or link.relation_type
            await assert_context_link_endpoint_visible(
                uow,
                endpoint_type=source_type,
                endpoint_id=source_id,
                space_id=str(link.space_id),
                memory_scope_id=str(link.memory_scope_id),
                role="source",
            )
            await assert_context_link_endpoint_visible(
                uow,
                endpoint_type=target_type,
                endpoint_id=target_id,
                space_id=str(link.space_id),
                memory_scope_id=str(link.memory_scope_id),
                role="target",
            )
            existing = await uow.context_links.find_active(
                space_id=str(link.space_id),
                memory_scope_id=str(link.memory_scope_id),
                source_type=source_type,
                source_id=source_id,
                target_type=target_type,
                target_id=target_id,
                relation_type=relation_type,
            )
            if existing is not None and existing.id != link.id:
                raise MemoryConflictError("Context link conflicts with an existing active link")
            saved = await uow.context_links.save(
                link.update_details(
                    source_type=command.source_type,
                    source_id=command.source_id,
                    target_type=command.target_type,
                    target_id=command.target_id,
                    relation_type=command.relation_type,
                    confidence=command.confidence,
                    reason=command.reason,
                    metadata={
                        **dict(command.metadata or {}),
                        "last_edit_source": "manual",
                    },
                    now=now,
                )
            )
            await uow.commit()
        return ContextLinkResult(link=saved)
