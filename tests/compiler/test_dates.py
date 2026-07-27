"""Deterministic temporal helper contract tests."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from django_asklens.compiler.dates import relative_datetime_bounds
from django_asklens.exceptions import PlanValidationError
from django_asklens.planning.temporal import (
    normalize_date_string,
    normalize_datetime_string,
    normalize_time_string,
)


def test_date_strings_are_strict_iso_calendar_dates() -> None:
    assert normalize_date_string("2026-02-28") == "2026-02-28"

    for value in ("2026-02-29", "2026-2-28", "2026-02-28T00:00:00Z"):
        with pytest.raises(PlanValidationError, match="valid ISO 8601 date"):
            normalize_date_string(value)


def test_datetime_strings_require_offset_bearing_rfc3339() -> None:
    assert normalize_datetime_string("2026-07-27T10:15:30Z") == (
        "2026-07-27T10:15:30+00:00"
    )
    assert normalize_datetime_string("2026-07-27T12:15:30+02:00") == (
        "2026-07-27T12:15:30+02:00"
    )

    for value in (
        "2026-07-27T10:15:30",
        "2026-07-27 10:15:30Z",
        "2026-07-27",
        "2026-07-27T10:15:30.1234567Z",
        "not-a-datetime",
    ):
        with pytest.raises(PlanValidationError, match="offset-bearing RFC 3339"):
            normalize_datetime_string(value)


def test_time_strings_are_offset_free_iso_local_times() -> None:
    assert normalize_time_string("12:30:45.123456") == "12:30:45.123456"

    for value in ("12:30", "25:00:00", "12:30:00+02:00"):
        with pytest.raises(PlanValidationError, match="offset-free ISO time"):
            normalize_time_string(value)


def test_last_n_days_is_exact_rolling_duration_across_dst() -> None:
    new_york = ZoneInfo("America/New_York")
    now = datetime(2026, 3, 9, 1, 30, tzinfo=new_york)

    start, end = relative_datetime_bounds(
        operator="last_n_days",
        amount=1,
        now=now,
        resource_timezone=new_york,
    )

    assert end == now.astimezone(UTC)
    assert end - start == timedelta(hours=24)
    assert start.astimezone(new_york) == datetime(
        2026,
        3,
        8,
        0,
        30,
        tzinfo=new_york,
    )


def test_last_n_months_clamps_month_end_at_same_local_wall_time() -> None:
    timezone = ZoneInfo("Europe/Berlin")
    now = datetime(2026, 3, 31, 10, 15, tzinfo=timezone)

    start, end = relative_datetime_bounds(
        operator="last_n_months",
        amount=1,
        now=now,
        resource_timezone=timezone,
    )

    assert start.astimezone(timezone) == datetime(
        2026,
        2,
        28,
        10,
        15,
        tzinfo=timezone,
    )
    assert end == now.astimezone(UTC)


def test_last_n_months_resolves_nonexistent_wall_time_forward() -> None:
    new_york = ZoneInfo("America/New_York")
    start, _end = relative_datetime_bounds(
        operator="last_n_months",
        amount=1,
        now=datetime(2026, 4, 8, 2, 30, tzinfo=new_york),
        resource_timezone=new_york,
    )

    assert start.astimezone(new_york) == datetime(
        2026,
        3,
        8,
        3,
        30,
        tzinfo=new_york,
    )


def test_last_n_months_uses_earlier_ambiguous_wall_time() -> None:
    new_york = ZoneInfo("America/New_York")
    start, _end = relative_datetime_bounds(
        operator="last_n_months",
        amount=1,
        now=datetime(2026, 12, 1, 1, 30, tzinfo=new_york),
        resource_timezone=new_york,
    )

    local_start = start.astimezone(new_york)
    assert local_start.replace(tzinfo=None) == datetime(2026, 11, 1, 1, 30)
    assert local_start.fold == 0
    assert local_start.utcoffset() == timedelta(hours=-4)


@pytest.mark.parametrize("operator", ["last_n_days", "last_n_months"])
def test_relative_datetime_bounds_reject_overflow(operator: str) -> None:
    with pytest.raises(PlanValidationError, match="supported datetime range"):
        relative_datetime_bounds(
            operator=operator,
            amount=999_999_999,
            now=datetime(2026, 7, 27, 10, 0, tzinfo=UTC),
            resource_timezone=ZoneInfo("UTC"),
        )


@pytest.mark.parametrize("now", [None, datetime(2026, 7, 27, 10, 0)])
def test_relative_datetime_bounds_require_injected_aware_clock(
    now: datetime | None,
) -> None:
    with pytest.raises(PlanValidationError, match="aware request clock"):
        relative_datetime_bounds(
            operator="last_n_days",
            amount=1,
            now=now,
            resource_timezone=ZoneInfo("UTC"),
        )
