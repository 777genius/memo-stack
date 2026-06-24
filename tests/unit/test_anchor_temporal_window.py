from datetime import UTC, datetime

from infinity_context_core.application.anchor_extraction import extract_observed_anchors
from infinity_context_core.application.anchor_temporal_window import (
    temporal_window_for_observed_anchor,
    temporal_window_metadata,
)

NOW = datetime(2026, 6, 19, 15, 30, tzinfo=UTC)


def test_temporal_window_resolves_hours_ago_event_anchor() -> None:
    anchor = _event_anchor("Call with Alex about Project Atlas 2 hours ago.")

    valid_from, valid_to = temporal_window_for_observed_anchor(anchor, observed_at=NOW)

    assert valid_from == datetime(2026, 6, 19, 13, 30, tzinfo=UTC)
    assert valid_to == datetime(2026, 6, 19, 14, 30, tzinfo=UTC)
    assert temporal_window_metadata(valid_from, valid_to) == {
        "event_temporal_window_source": "relative_hint_v1",
        "event_valid_from": "2026-06-19T13:30:00+00:00",
        "event_valid_to": "2026-06-19T14:30:00+00:00",
    }


def test_temporal_window_resolves_day_and_week_event_anchors() -> None:
    yesterday = _event_anchor("Meeting with Dana yesterday.")
    this_week = _event_anchor("Call with Alex this week.")
    last_week = _event_anchor("Созвон с Алексом на прошлой неделе по Project Atlas.")
    last_friday = _event_anchor("Caroline had interviews last Friday.")
    last_weekend = _event_anchor("Caroline joined a mentorship program last weekend.")
    this_weekend = _event_anchor("Alex call this weekend covered Project Atlas.")
    two_weekends = _event_anchor("Melanie went camping two weekends ago.")

    yesterday_from, yesterday_to = temporal_window_for_observed_anchor(
        yesterday,
        observed_at=NOW,
    )
    this_week_from, this_week_to = temporal_window_for_observed_anchor(
        this_week,
        observed_at=NOW,
    )
    week_from, week_to = temporal_window_for_observed_anchor(last_week, observed_at=NOW)
    friday_from, friday_to = temporal_window_for_observed_anchor(
        last_friday,
        observed_at=NOW,
    )
    last_weekend_from, last_weekend_to = temporal_window_for_observed_anchor(
        last_weekend,
        observed_at=NOW,
    )
    this_weekend_from, this_weekend_to = temporal_window_for_observed_anchor(
        this_weekend,
        observed_at=NOW,
    )
    two_weekends_from, two_weekends_to = temporal_window_for_observed_anchor(
        two_weekends,
        observed_at=NOW,
    )

    assert yesterday_from == datetime(2026, 6, 18, tzinfo=UTC)
    assert yesterday_to == datetime(2026, 6, 19, tzinfo=UTC)
    assert this_week_from == datetime(2026, 6, 15, tzinfo=UTC)
    assert this_week_to == datetime(2026, 6, 22, tzinfo=UTC)
    assert week_from == datetime(2026, 6, 8, tzinfo=UTC)
    assert week_to == datetime(2026, 6, 15, tzinfo=UTC)
    assert friday_from == datetime(2026, 6, 12, tzinfo=UTC)
    assert friday_to == datetime(2026, 6, 13, tzinfo=UTC)
    assert last_weekend_from == datetime(2026, 6, 13, tzinfo=UTC)
    assert last_weekend_to == datetime(2026, 6, 15, tzinfo=UTC)
    assert this_weekend_from == datetime(2026, 6, 20, tzinfo=UTC)
    assert this_weekend_to == datetime(2026, 6, 22, tzinfo=UTC)
    assert two_weekends_from == datetime(2026, 6, 6, tzinfo=UTC)
    assert two_weekends_to == datetime(2026, 6, 8, tzinfo=UTC)


def test_temporal_window_resolves_month_event_anchors() -> None:
    last_month = _event_anchor("Meeting with Dana last month.")
    last_quarter = _event_anchor("Planning with Alex last quarter.")
    two_months = _event_anchor("Созвон с Алексом два месяца назад по Project Atlas.")

    last_month_from, last_month_to = temporal_window_for_observed_anchor(
        last_month,
        observed_at=NOW,
    )
    last_quarter_from, last_quarter_to = temporal_window_for_observed_anchor(
        last_quarter,
        observed_at=NOW,
    )
    two_months_from, two_months_to = temporal_window_for_observed_anchor(
        two_months,
        observed_at=NOW,
    )

    assert last_month_from == datetime(2026, 5, 1, tzinfo=UTC)
    assert last_month_to == datetime(2026, 6, 1, tzinfo=UTC)
    assert last_quarter_from == datetime(2026, 1, 1, tzinfo=UTC)
    assert last_quarter_to == datetime(2026, 4, 1, tzinfo=UTC)
    assert two_months_from == datetime(2026, 4, 1, tzinfo=UTC)
    assert two_months_to == datetime(2026, 5, 1, tzinfo=UTC)


def test_temporal_window_resolves_year_event_anchors() -> None:
    last_year = _event_anchor("Meeting with Dana last year.")
    four_years = _event_anchor("Созвон с Алексом четыре года назад по Project Atlas.")

    last_year_from, last_year_to = temporal_window_for_observed_anchor(
        last_year,
        observed_at=NOW,
    )
    four_years_from, four_years_to = temporal_window_for_observed_anchor(
        four_years,
        observed_at=NOW,
    )

    assert last_year_from == datetime(2025, 1, 1, tzinfo=UTC)
    assert last_year_to == datetime(2026, 1, 1, tzinfo=UTC)
    assert four_years_from == datetime(2022, 1, 1, tzinfo=UTC)
    assert four_years_to == datetime(2023, 1, 1, tzinfo=UTC)


def test_temporal_window_resolves_current_month_and_year_event_anchors() -> None:
    this_month = _event_anchor("Meeting with Dana this month.")
    this_quarter = _event_anchor("Planning with Dana this quarter.")
    this_year = _event_anchor("Созвон с Алексом в этом году по Project Atlas.")

    this_month_from, this_month_to = temporal_window_for_observed_anchor(
        this_month,
        observed_at=NOW,
    )
    this_quarter_from, this_quarter_to = temporal_window_for_observed_anchor(
        this_quarter,
        observed_at=NOW,
    )
    this_year_from, this_year_to = temporal_window_for_observed_anchor(
        this_year,
        observed_at=NOW,
    )

    assert this_month_from == datetime(2026, 6, 1, tzinfo=UTC)
    assert this_month_to == datetime(2026, 7, 1, tzinfo=UTC)
    assert this_quarter_from == datetime(2026, 4, 1, tzinfo=UTC)
    assert this_quarter_to == datetime(2026, 7, 1, tzinfo=UTC)
    assert this_year_from == datetime(2026, 1, 1, tzinfo=UTC)
    assert this_year_to == datetime(2027, 1, 1, tzinfo=UTC)


def test_temporal_window_resolves_partial_day_event_anchors() -> None:
    earlier_today = _event_anchor("Alex wrote about Project Atlas earlier today.")
    morning = _event_anchor("Meeting with Dana this morning.")
    afternoon = _event_anchor("Review with Alex this afternoon.")
    evening = _event_anchor("Созвон с Марией по Project Atlas сегодня вечером.")

    earlier_from, earlier_to = temporal_window_for_observed_anchor(
        earlier_today,
        observed_at=NOW,
    )
    morning_from, morning_to = temporal_window_for_observed_anchor(morning, observed_at=NOW)
    afternoon_from, afternoon_to = temporal_window_for_observed_anchor(
        afternoon,
        observed_at=NOW,
    )
    evening_from, evening_to = temporal_window_for_observed_anchor(evening, observed_at=NOW)

    assert earlier_from == datetime(2026, 6, 19, tzinfo=UTC)
    assert earlier_to == NOW
    assert morning_from == datetime(2026, 6, 19, 6, tzinfo=UTC)
    assert morning_to == datetime(2026, 6, 19, 12, tzinfo=UTC)
    assert afternoon_from == datetime(2026, 6, 19, 12, tzinfo=UTC)
    assert afternoon_to == datetime(2026, 6, 19, 18, tzinfo=UTC)
    assert evening_from == datetime(2026, 6, 19, 18, tzinfo=UTC)
    assert evening_to == datetime(2026, 6, 20, tzinfo=UTC)


def test_temporal_window_ignores_non_event_and_unknown_relative_time() -> None:
    project = next(
        anchor
        for anchor in extract_observed_anchors("Project Atlas reviewed yesterday.")
        if anchor.kind.value == "project"
    )
    unknown_event = _event_anchor("Meeting with Alex someday.")

    assert temporal_window_for_observed_anchor(project, observed_at=NOW) == (None, None)
    assert temporal_window_for_observed_anchor(unknown_event, observed_at=NOW) == (
        None,
        None,
    )


def _event_anchor(text: str):
    return next(anchor for anchor in extract_observed_anchors(text) if anchor.kind.value == "event")
