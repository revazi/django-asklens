"""Deterministic temporal helpers for ORM query compilation."""

import calendar
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db.models import F
from django.db.models.expressions import Expression
from django.db.models.functions import (
    TruncDay,
    TruncMonth,
    TruncQuarter,
    TruncWeek,
    TruncYear,
)
from django.utils import timezone

from django_asklens.exceptions import PlanValidationError
from django_asklens.planning.schemas import DateTrunc
from django_asklens.planning.temporal import (
    parse_date_string,
    parse_datetime_string,
    parse_time_string,
)


def get_now(value: datetime | None = None) -> datetime:
    """Return the explicitly injected timezone-aware request clock."""

    if value is None:
        msg = "AskLens temporal filters require an aware request clock."
        raise PlanValidationError(msg)
    current = value
    if timezone.is_naive(current):
        msg = "AskLens temporal filters require an aware request clock."
        raise PlanValidationError(msg)
    return current


def subtract_months(value: datetime, months: int) -> datetime:
    """Subtract calendar months while clamping an invalid day to month end."""

    month_index = value.month - months - 1
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def relative_datetime_bounds(
    *,
    operator: str,
    amount: int,
    now: datetime | None,
    resource_timezone: ZoneInfo,
) -> tuple[datetime, datetime]:
    """Return trusted half-open instant bounds for one relative-time filter."""

    current = get_now(now).astimezone(UTC)
    try:
        if operator == "last_n_days":
            return current - timedelta(days=amount), current
        if operator == "last_n_months":
            local_now = current.astimezone(resource_timezone)
            target_wall_time = subtract_months(
                local_now.replace(tzinfo=None),
                amount,
            )
            local_start = _resolve_local_wall_time(
                target_wall_time,
                resource_timezone=resource_timezone,
            )
            return local_start.astimezone(UTC), current
    except (OverflowError, ValueError) as exc:
        msg = "Relative temporal filter is outside the supported datetime range."
        raise PlanValidationError(msg) from exc

    msg = f"Unsupported relative date operator {operator!r}."
    raise PlanValidationError(msg)


def _resolve_local_wall_time(
    value: datetime, *, resource_timezone: ZoneInfo
) -> datetime:
    """Resolve a local wall time deterministically across DST transitions.

    Ambiguous times use the earlier occurrence (``fold=0``). Nonexistent times
    move forward by the transition gap through a UTC round trip.
    """

    candidate = value.replace(tzinfo=resource_timezone, fold=0)
    normalized = candidate.astimezone(UTC).astimezone(resource_timezone)
    if normalized.replace(tzinfo=None) != value:
        return normalized
    return candidate


def parse_temporal_value(value: object, *, field_type: str) -> object:
    """Parse one canonical date or offset-bearing datetime for ORM use."""

    if field_type == "date":
        return parse_date_string(value)
    if field_type == "datetime":
        return parse_datetime_string(value)
    if field_type == "time":
        return parse_time_string(value)
    msg = f"Unsupported temporal field type {field_type!r}."
    raise PlanValidationError(msg)


def build_date_trunc_expression(
    field_binding: str,
    date_trunc: DateTrunc | None,
    *,
    field_type: str,
    resource_timezone: ZoneInfo,
) -> Expression:
    """Return an ORM expression with explicit resource-timezone semantics."""

    if date_trunc is None:
        return F(field_binding)
    tzinfo = resource_timezone if field_type == "datetime" else None
    if date_trunc == "day":
        return TruncDay(field_binding, tzinfo=tzinfo)
    if date_trunc == "week":
        return TruncWeek(field_binding, tzinfo=tzinfo)
    if date_trunc == "month":
        return TruncMonth(field_binding, tzinfo=tzinfo)
    if date_trunc == "quarter":
        return TruncQuarter(field_binding, tzinfo=tzinfo)
    if date_trunc == "year":
        return TruncYear(field_binding, tzinfo=tzinfo)

    msg = f"Unsupported date truncation {date_trunc!r}."
    raise PlanValidationError(msg)
