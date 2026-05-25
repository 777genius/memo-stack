"""Internal event DTOs for outbox handoff."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OutboxEvent:
    event_type: str
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int | None = None
    payload: dict[str, object] = field(default_factory=dict)
