"""Pure canonical parsing helpers for temporal QueryPlan values."""

import re
from datetime import date, datetime, time
from typing import Never

from django_asklens.exceptions import PlanValidationError

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RFC3339_DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)
_TIME_PATTERN = re.compile(r"^\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?$")


def normalize_date_string(value: object) -> str:
    """Return one strict ISO 8601 calendar date string."""

    if not isinstance(value, str) or _DATE_PATTERN.fullmatch(value) is None:
        _raise_invalid_date()
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        _raise_invalid_date()
    return parsed.isoformat()


def normalize_datetime_string(value: object) -> str:
    """Return one canonical offset-bearing RFC 3339 datetime string."""

    if (
        not isinstance(value, str)
        or _RFC3339_DATETIME_PATTERN.fullmatch(value) is None
        or value.endswith("-00:00")
    ):
        _raise_invalid_datetime()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        offset = parsed.utcoffset()
    except (OverflowError, ValueError):
        _raise_invalid_datetime()
    if offset is None:
        _raise_invalid_datetime()
    return parsed.isoformat()


def normalize_time_string(value: object) -> str:
    """Return one canonical offset-free ISO local-time string."""

    if not isinstance(value, str) or _TIME_PATTERN.fullmatch(value) is None:
        _raise_invalid_time()
    try:
        parsed = time.fromisoformat(value)
    except ValueError:
        _raise_invalid_time()
    if parsed.tzinfo is not None:
        _raise_invalid_time()
    return parsed.isoformat()


def parse_date_string(value: object) -> date:
    """Parse one already validated canonical date value."""

    return date.fromisoformat(normalize_date_string(value))


def parse_datetime_string(value: object) -> datetime:
    """Parse one already validated offset-bearing datetime value."""

    return datetime.fromisoformat(normalize_datetime_string(value))


def parse_time_string(value: object) -> time:
    """Parse one already validated offset-free local-time value."""

    return time.fromisoformat(normalize_time_string(value))


def _raise_invalid_date() -> Never:
    msg = "Date filters require a valid ISO 8601 date in YYYY-MM-DD form."
    raise PlanValidationError(msg)


def _raise_invalid_datetime() -> Never:
    msg = "Datetime filters require an offset-bearing RFC 3339 value."
    raise PlanValidationError(msg)


def _raise_invalid_time() -> Never:
    msg = "Time filters require an offset-free ISO time in HH:MM:SS form."
    raise PlanValidationError(msg)
