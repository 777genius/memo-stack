"""Resolve relative event anchor time hints against observation time."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from infinity_context_core.application.anchor_extraction import ObservedAnchor
from infinity_context_core.domain.entities import MemoryAnchorKind

_WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def temporal_window_for_observed_anchor(
    observed: ObservedAnchor,
    *,
    observed_at: datetime,
) -> tuple[datetime | None, datetime | None]:
    if observed.kind != MemoryAnchorKind.EVENT:
        return None, None
    hint = _metadata_text(observed.metadata.get("event_temporal_hint_code"))
    if not hint:
        return None, None
    quantity = _metadata_int(observed.metadata.get("event_temporal_quantity"), default=1)
    unit = _metadata_text(observed.metadata.get("event_temporal_unit"))
    now = _aware_utc(observed_at)
    if hint == "today":
        return _day_window(now)
    if hint == "earlier_today":
        start, _ = _day_window(now)
        return start, now
    if hint == "today_morning":
        return _time_window(now, hour_from=6, hour_to=12)
    if hint == "today_afternoon":
        return _time_window(now, hour_from=12, hour_to=18)
    if hint == "today_evening":
        return _time_window(now, hour_from=18, hour_to=24)
    if hint == "this_month":
        start = _month_start(now)
        return start, _add_months(start, 1)
    if hint == "this_quarter":
        start = _quarter_start(now)
        return start, _add_months(start, 3)
    if hint == "this_year":
        start = _year_start(now.year)
        return start, _year_start(now.year + 1)
    if hint == "this_week":
        start = _week_start(now)
        return start, start + timedelta(days=7)
    if hint == "tomorrow":
        return _day_window(now + timedelta(days=quantity))
    if hint == "yesterday":
        return _day_window(now - timedelta(days=quantity))
    if hint.startswith("last_") and unit == "weekday":
        weekday = hint.removeprefix("last_")
        if weekday in _WEEKDAY_INDEX:
            return _previous_weekday_window(now, weekday=_WEEKDAY_INDEX[weekday])
    if hint == "hours_ago" and unit == "hour":
        start = now - timedelta(hours=max(1, quantity))
        return start, min(now, start + timedelta(hours=1))
    if hint == "days_ago" and unit == "day":
        return _day_window(now - timedelta(days=max(1, quantity)))
    if hint in {"last_week", "weeks_ago"} and unit == "week":
        target = now - timedelta(weeks=max(1, quantity))
        start = _week_start(target)
        return start, start + timedelta(days=7)
    if hint == "this_weekend" and unit == "weekend":
        return _weekend_window(now)
    if hint in {"last_weekend", "weekends_ago"} and unit == "weekend":
        target = now - timedelta(weeks=max(1, quantity))
        return _weekend_window(target)
    if hint in {"last_month", "months_ago"} and unit == "month":
        start = _month_start(_add_months(now, -max(1, quantity)))
        return start, _add_months(start, 1)
    if hint == "last_quarter" and unit == "quarter":
        start = _quarter_start(_add_months(now, -3))
        return start, _add_months(start, 3)
    if hint in {"last_year", "years_ago"} and unit == "year":
        start = _year_start(now.year - max(1, quantity))
        return start, _year_start(start.year + 1)
    return None, None


def temporal_window_metadata(
    valid_from: datetime | None,
    valid_to: datetime | None,
) -> dict[str, object]:
    if valid_from is None or valid_to is None:
        return {}
    return {
        "event_temporal_window_source": "relative_hint_v1",
        "event_valid_from": valid_from.isoformat(),
        "event_valid_to": valid_to.isoformat(),
    }


def _day_window(value: datetime) -> tuple[datetime, datetime]:
    start = datetime.combine(value.date(), time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


def _time_window(
    value: datetime,
    *,
    hour_from: int,
    hour_to: int,
) -> tuple[datetime, datetime]:
    start = datetime.combine(value.date(), time(hour_from), tzinfo=UTC)
    if hour_to >= 24:
        return start, datetime.combine(value.date(), time.min, tzinfo=UTC) + timedelta(days=1)
    return start, datetime.combine(value.date(), time(hour_to), tzinfo=UTC)


def _week_start(value: datetime) -> datetime:
    start_day = value.date() - timedelta(days=value.weekday())
    return datetime.combine(start_day, time.min, tzinfo=UTC)


def _weekend_window(value: datetime) -> tuple[datetime, datetime]:
    start = _week_start(value) + timedelta(days=5)
    return start, start + timedelta(days=2)


def _previous_weekday_window(value: datetime, *, weekday: int) -> tuple[datetime, datetime]:
    days_back = (value.weekday() - weekday) % 7
    if days_back == 0:
        days_back = 7
    return _day_window(value - timedelta(days=days_back))


def _month_start(value: datetime) -> datetime:
    return datetime(value.year, value.month, 1, tzinfo=UTC)


def _quarter_start(value: datetime) -> datetime:
    quarter_month = ((value.month - 1) // 3) * 3 + 1
    return datetime(value.year, quarter_month, 1, tzinfo=UTC)


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_offset = divmod(month_index, 12)
    return datetime(year, month_offset + 1, 1, tzinfo=UTC)


def _year_start(year: int) -> datetime:
    return datetime(year, 1, 1, tzinfo=UTC)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _metadata_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _metadata_int(value: object, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value >= 0:
        return value
    return default
