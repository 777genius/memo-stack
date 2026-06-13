"""Space and memory_scope management use cases."""

from __future__ import annotations

from memo_stack_core.application.dto import (
    CreateMemoryScopeCommand,
    CreateSpaceCommand,
    DeleteMemoryScopeCommand,
    MemoryScopeResult,
    SpaceResult,
    UpdateMemoryScopeCommand,
)
from memo_stack_core.domain.entities import MemoryScope, MemoryScopeId, MemorySpace, SpaceId
from memo_stack_core.domain.errors import MemoryNotFoundError
from memo_stack_core.ports.clock import ClockPort
from memo_stack_core.ports.ids import IdGeneratorPort
from memo_stack_core.ports.unit_of_work import UnitOfWorkFactoryPort


class CreateSpaceUseCase:
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

    async def execute(self, command: CreateSpaceCommand) -> SpaceResult:
        now = self._clock.now()
        space = MemorySpace.create(
            space_id=SpaceId(self._ids.new_id("space")),
            slug=command.slug,
            name=command.name,
            now=now,
        )
        async with self._uow_factory() as uow:
            saved = await uow.scope.create_space(space)
            await uow.commit()
        return SpaceResult(space=saved, created=saved.id == space.id)


class ListSpacesUseCase:
    def __init__(self, *, uow_factory: UnitOfWorkFactoryPort) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, limit: int = 100) -> list[MemorySpace]:
        async with self._uow_factory() as uow:
            return await uow.scope.list_spaces(limit=limit)


class CreateMemoryScopeUseCase:
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

    async def execute(self, command: CreateMemoryScopeCommand) -> MemoryScopeResult:
        now = self._clock.now()
        memory_scope = MemoryScope.create(
            memory_scope_id=MemoryScopeId(self._ids.new_id("memory_scope")),
            space_id=command.space_id,
            external_ref=command.external_ref,
            name=command.name,
            now=now,
        )
        async with self._uow_factory() as uow:
            saved = await uow.scope.create_memory_scope(memory_scope)
            await uow.commit()
        return MemoryScopeResult(memory_scope=saved, created=saved.id == memory_scope.id)


class ListMemoryScopesUseCase:
    def __init__(self, *, uow_factory: UnitOfWorkFactoryPort) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, space_id: SpaceId, limit: int = 100) -> list[MemoryScope]:
        async with self._uow_factory() as uow:
            return await uow.scope.list_memory_scopes(space_id=str(space_id), limit=limit)


class UpdateMemoryScopeUseCase:
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactoryPort,
        clock: ClockPort,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, command: UpdateMemoryScopeCommand) -> MemoryScopeResult:
        async with self._uow_factory() as uow:
            memory_scope = await uow.scope.get_memory_scope(str(command.memory_scope_id))
            if memory_scope is None:
                raise MemoryNotFoundError("MemoryScope not found")
            updated = memory_scope.update_details(
                external_ref=command.external_ref,
                name=command.name,
                now=self._clock.now(),
            )
            saved = await uow.scope.save_memory_scope(updated)
            await uow.commit()
        return MemoryScopeResult(memory_scope=saved, created=False)


class DeleteMemoryScopeUseCase:
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactoryPort,
        clock: ClockPort,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, command: DeleteMemoryScopeCommand) -> MemoryScopeResult:
        async with self._uow_factory() as uow:
            memory_scope = await uow.scope.get_memory_scope(str(command.memory_scope_id))
            if memory_scope is None:
                raise MemoryNotFoundError("MemoryScope not found")
            deleted = memory_scope.delete(now=self._clock.now())
            saved = await uow.scope.save_memory_scope(deleted)
            await uow.commit()
        return MemoryScopeResult(memory_scope=saved, created=False)
