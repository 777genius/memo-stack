"""Usage governance use cases."""

from __future__ import annotations

from memo_stack_core.application.dto import UsageSummaryQuery, UsageSummaryResult
from memo_stack_core.domain.usage import (
    ProductPlan,
    UsageResource,
    UsageSubjectType,
    UsageWindow,
    admit_usage,
)
from memo_stack_core.ports.clock import ClockPort
from memo_stack_core.ports.unit_of_work import UnitOfWorkFactoryPort


class GetUsageSummaryUseCase:
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactoryPort,
        clock: ClockPort,
        plan: ProductPlan,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._plan = plan

    async def execute(self, query: UsageSummaryQuery) -> UsageSummaryResult:
        window = UsageWindow.calendar_month_for(self._clock.now())
        async with self._uow_factory() as uow:
            used = await uow.usage.sum_quantity(
                subject_type=UsageSubjectType.SPACE.value,
                subject_id=str(query.space_id),
                resource=UsageResource.MEDIA_ANALYSIS_SECONDS.value,
                window_start=window.start,
                window_end=window.end,
            )
        decision = admit_usage(
            plan=self._plan,
            resource=UsageResource.MEDIA_ANALYSIS_SECONDS,
            used=used,
            requested=0,
            window=window,
        )
        return UsageSummaryResult.from_snapshots(
            plan=self._plan,
            snapshots=(decision.snapshot,),
        )
