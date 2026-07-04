"""Date helpers for ORM query compilation."""

import calendar
from datetime import datetime, timedelta

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
from django.utils.dateparse import parse_date, parse_datetime

from django_asklens.exceptions import PlanValidationError
from django_asklens.planning.schemas import DateTrunc


def get_now(value: datetime | None = None) -> datetime:
    """Return an explicit or current timezone-aware datetime."""

    if value is not None:
        return value
    return timezone.now()


def subtract_months(value: datetime, months: int) -> datetime:
    """Subtract calendar months from a datetime without extra dependencies."""

    month_index = value.month - months - 1
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def relative_datetime(
    *, operator: str, amount: int, now: datetime | None = None
) -> datetime:
    """Return the lower-bound datetime for a relative date filter."""

    current = get_now(now)
    if operator == "last_n_days":
        return current - timedelta(days=amount)
    if operator == "last_n_months":
        return subtract_months(current, amount)

    msg = f"Unsupported relative date operator {operator!r}."
    raise PlanValidationError(msg)


def parse_temporal_value(value: object) -> object:
    """Parse an ISO date/datetime string for Django ORM filters."""

    if not isinstance(value, str):
        return value

    parsed_datetime = parse_datetime(value)
    if parsed_datetime is not None:
        return parsed_datetime

    parsed_date = parse_date(value)
    if parsed_date is not None:
        return parsed_date

    msg = f"Invalid date/datetime filter value {value!r}."
    raise PlanValidationError(msg)


def build_date_trunc_expression(
    field_path: str, date_trunc: DateTrunc | None
) -> Expression:
    """Return an ORM expression for a plain or truncated grouping field."""

    orm_path = to_orm_path(field_path)
    if date_trunc is None:
        return F(orm_path)
    if date_trunc == "day":
        return TruncDay(orm_path)
    if date_trunc == "week":
        return TruncWeek(orm_path)
    if date_trunc == "month":
        return TruncMonth(orm_path)
    if date_trunc == "quarter":
        return TruncQuarter(orm_path)
    if date_trunc == "year":
        return TruncYear(orm_path)

    msg = f"Unsupported date truncation {date_trunc!r}."
    raise PlanValidationError(msg)


def to_orm_path(field_path: str) -> str:
    """Convert a catalog dot path to a Django ORM lookup path."""

    return field_path.replace(".", "__")
