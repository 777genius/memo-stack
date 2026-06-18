"""Load one capture through the application boundary."""

from __future__ import annotations

from infinity_context_core.application.dto import GetCaptureQuery
from infinity_context_core.domain.capture import CanonicalCapture
from infinity_context_core.ports.unit_of_work import UnitOfWorkFactoryPort


class GetCaptureUseCase:
    def __init__(self, *, uow_factory: UnitOfWorkFactoryPort) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: GetCaptureQuery) -> CanonicalCapture | None:
        async with self._uow_factory() as uow:
            return await uow.captures.get_by_id(query.capture_id)
