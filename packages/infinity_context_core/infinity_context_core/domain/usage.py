"""Usage governance domain objects."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NewType

from infinity_context_core.domain.entities import MemoryScopeId, SpaceId
from infinity_context_core.domain.errors import MemoryValidationError

UsageRecordId = NewType("UsageRecordId", str)

FREE_MEDIA_ANALYSIS_SECONDS_PER_MONTH = 10 * 60 * 60
MAX_USAGE_METADATA_KEYS = 80


class ProductPlanTier(StrEnum):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"
    SELF_HOSTED = "self_hosted"


class UsageResource(StrEnum):
    MEDIA_ANALYSIS_SECONDS = "media_analysis_seconds"


class UsageSubjectType(StrEnum):
    SPACE = "space"
    USER = "user"


class UsageRecordStatus(StrEnum):
    COMMITTED = "committed"
    RELEASED = "released"


USAGE_RECONCILIATION_SOURCE_TYPE = "usage_reconciliation"


@dataclass(frozen=True)
class UsageWindow:
    start: datetime
    end: datetime

    @classmethod
    def calendar_month_for(cls, now: datetime) -> UsageWindow:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return cls(start=start, end=end)


@dataclass(frozen=True)
class ProductPlan:
    tier: ProductPlanTier
    display_name: str
    media_analysis_seconds_per_month: int

    @classmethod
    def create(
        cls,
        *,
        tier: str,
        media_analysis_seconds_per_month: int,
    ) -> ProductPlan:
        safe_tier = ProductPlanTier(tier)
        if media_analysis_seconds_per_month < 0:
            raise MemoryValidationError("Plan media analysis quota cannot be negative")
        return cls(
            tier=safe_tier,
            display_name=safe_tier.value.replace("_", " ").title(),
            media_analysis_seconds_per_month=media_analysis_seconds_per_month,
        )

    def limit_for(self, resource: UsageResource) -> int:
        if resource == UsageResource.MEDIA_ANALYSIS_SECONDS:
            return self.media_analysis_seconds_per_month
        raise MemoryValidationError("Unknown usage resource")


@dataclass(frozen=True)
class UsageRecord:
    id: UsageRecordId
    subject_type: UsageSubjectType
    subject_id: str
    space_id: SpaceId
    memory_scope_id: MemoryScopeId | None
    resource: UsageResource
    quantity: int
    status: UsageRecordStatus
    source_type: str
    source_id: str
    idempotency_key: str
    window_start: datetime
    window_end: datetime
    metadata: Mapping[str, object]
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        record_id: UsageRecordId,
        subject_type: str,
        subject_id: str,
        space_id: SpaceId,
        resource: str,
        quantity: int,
        source_type: str,
        source_id: str,
        idempotency_key: str,
        window: UsageWindow,
        now: datetime,
        memory_scope_id: MemoryScopeId | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> UsageRecord:
        safe_subject_id = subject_id.strip()
        safe_source_type = source_type.strip()
        safe_source_id = source_id.strip()
        safe_idempotency_key = idempotency_key.strip()
        if not safe_subject_id:
            raise MemoryValidationError("Usage subject_id is required")
        if quantity == 0:
            raise MemoryValidationError("Usage quantity must be non-zero")
        if not safe_source_type or not safe_source_id:
            raise MemoryValidationError("Usage source is required")
        if quantity < 0 and safe_source_type != USAGE_RECONCILIATION_SOURCE_TYPE:
            raise MemoryValidationError("Negative usage is only allowed for reconciliation")
        if not safe_idempotency_key:
            raise MemoryValidationError("Usage idempotency_key is required")
        if window.end <= window.start:
            raise MemoryValidationError("Usage window is invalid")
        return cls(
            id=record_id,
            subject_type=UsageSubjectType(subject_type),
            subject_id=safe_subject_id,
            space_id=space_id,
            memory_scope_id=memory_scope_id,
            resource=UsageResource(resource),
            quantity=quantity,
            status=UsageRecordStatus.COMMITTED,
            source_type=safe_source_type[:80],
            source_id=safe_source_id[:120],
            idempotency_key=safe_idempotency_key[:240],
            window_start=window.start,
            window_end=window.end,
            metadata=_safe_metadata(metadata),
            created_at=now,
        )


@dataclass(frozen=True)
class UsageQuotaSnapshot:
    resource: UsageResource
    plan_tier: ProductPlanTier
    limit: int
    used: int
    remaining: int
    window: UsageWindow


@dataclass(frozen=True)
class UsageAdmissionDecision:
    allowed: bool
    requested: int
    snapshot: UsageQuotaSnapshot
    reason_code: str | None = None
    reason: str | None = None


def admit_usage(
    *,
    plan: ProductPlan,
    resource: UsageResource,
    used: int,
    requested: int,
    window: UsageWindow,
) -> UsageAdmissionDecision:
    limit = plan.limit_for(resource)
    remaining = max(limit - max(used, 0), 0)
    snapshot = UsageQuotaSnapshot(
        resource=resource,
        plan_tier=plan.tier,
        limit=limit,
        used=max(used, 0),
        remaining=remaining,
        window=window,
    )
    if requested <= 0:
        return UsageAdmissionDecision(allowed=True, requested=0, snapshot=snapshot)
    if requested > remaining:
        return UsageAdmissionDecision(
            allowed=False,
            requested=requested,
            snapshot=snapshot,
            reason_code="usage.media_analysis_quota_exceeded",
            reason="Media analysis monthly quota would be exceeded",
        )
    return UsageAdmissionDecision(allowed=True, requested=requested, snapshot=snapshot)


def _safe_metadata(metadata: Mapping[str, object] | None) -> dict[str, object]:
    safe: dict[str, object] = {}
    for key, value in dict(metadata or {}).items():
        if len(safe) >= MAX_USAGE_METADATA_KEYS:
            break
        key_text = str(key).strip()[:80]
        if not key_text:
            continue
        if isinstance(value, str):
            safe[key_text] = value[:500]
        elif isinstance(value, (int, float, bool)) or value is None:
            safe[key_text] = value
    return safe
