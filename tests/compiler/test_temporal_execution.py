"""Database evidence for deterministic temporal query semantics."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from django_asklens import Metric
from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.execution import execute_plan, run_query_plan
from tests.test_project.models import CanonicalValueFixture

pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def build_registry(*, resource_timezone: str = "UTC") -> CatalogRegistry:
    """Return a canonical temporal resource with an explicit timezone."""

    registry = CatalogRegistry()
    registry.register(
        model=CanonicalValueFixture,
        name="temporal_values",
        timezone=resource_timezone,
        scope_mode="global",
        fields={
            "id": {"binding": "id", "type": "integer", "nullable": False},
            "day": {
                "binding": "date_value",
                "type": "date",
                "nullable": False,
            },
            "instant": {
                "binding": "datetime_value",
                "type": "datetime",
                "nullable": False,
            },
            "clock": {
                "binding": "time_value",
                "type": "time",
                "nullable": False,
            },
        },
        metrics=[Metric("row_count", op="count", binding="id", result_type="integer")],
        default_order=(("instant", "asc"),),
    )
    return registry


def create_value(*, day: date, instant: datetime, clock: time = time(12, 0)) -> None:
    """Create one fully populated canonical fixture row."""

    CanonicalValueFixture.objects.create(
        text_value="value",
        boolean_value=False,
        integer_value=1,
        decimal_value=Decimal("1.0000"),
        float_value=1.0,
        date_value=day,
        datetime_value=instant,
        time_value=clock,
        enum_text_value="draft",
    )


def execute(plan: dict[str, object], *, registry: CatalogRegistry):
    """Execute one temporal plan through the trusted public facade."""

    return execute_plan(
        plan,
        request=SimpleNamespace(user=None),
        registry=registry,
    )


def test_canonical_database_scalars_round_trip_through_serialization() -> None:
    """Canonical scalar values survive the database and result boundary."""

    identifier = UUID("01234567-89ab-cdef-0123-456789abcdef")
    instant = datetime(2026, 3, 8, 7, 30, 15, 123456, tzinfo=UTC)
    clock = time(9, 30, 15, 123456)
    CanonicalValueFixture.objects.create(
        text_value="café",
        nullable_text=None,
        boolean_value=True,
        integer_value=-123456,
        decimal_value=Decimal("-1234.5678"),
        float_value=1.25,
        date_value=date(2026, 3, 8),
        datetime_value=instant,
        time_value=clock,
        uuid_value=identifier,
        enum_text_value="active",
        enum_integer_value=2,
    )
    registry = CatalogRegistry()
    registry.register(
        model=CanonicalValueFixture,
        name="canonical_values",
        timezone="UTC",
        scope_mode="global",
        fields={
            "text": {"binding": "text_value", "type": "string", "nullable": False},
            "optional_text": {
                "binding": "nullable_text",
                "type": "string",
                "nullable": True,
            },
            "flag": {
                "binding": "boolean_value",
                "type": "boolean",
                "nullable": False,
            },
            "count": {
                "binding": "integer_value",
                "type": "integer",
                "nullable": False,
            },
            "amount": {
                "binding": "decimal_value",
                "type": "decimal",
                "nullable": False,
            },
            "ratio": {
                "binding": "float_value",
                "type": "float",
                "nullable": False,
            },
            "day": {"binding": "date_value", "type": "date", "nullable": False},
            "instant": {
                "binding": "datetime_value",
                "type": "datetime",
                "nullable": False,
            },
            "clock": {
                "binding": "time_value",
                "type": "time",
                "nullable": False,
            },
            "identifier": {
                "binding": "uuid_value",
                "type": "uuid",
                "nullable": False,
            },
            "state": {
                "binding": "enum_text_value",
                "type": "enum",
                "nullable": False,
                "enum": {
                    "type": "string",
                    "values": [{"value": "draft"}, {"value": "active"}],
                },
            },
            "state_code": {
                "binding": "enum_integer_value",
                "type": "enum",
                "nullable": False,
                "enum": {
                    "type": "integer",
                    "values": [{"value": 1}, {"value": 2}],
                },
            },
        },
    )
    selected = [
        "text",
        "optional_text",
        "flag",
        "count",
        "amount",
        "ratio",
        "day",
        "instant",
        "clock",
        "identifier",
        "state",
        "state_code",
    ]

    result = execute(
        {
            "resource": "canonical_values",
            "intent": "list",
            "select": selected,
            "limit": 1,
        },
        registry=registry,
    )

    assert result.rows == (
        {
            "text": "café",
            "optional_text": None,
            "flag": True,
            "count": -123456,
            "amount": Decimal("-1234.5678"),
            "ratio": 1.25,
            "day": date(2026, 3, 8),
            "instant": instant,
            "clock": clock,
            "identifier": identifier,
            "state": "active",
            "state_code": 2,
        },
    )
    assert result.to_dict()["data"] == [
        {
            "text": "café",
            "optional_text": None,
            "flag": True,
            "count": -123456,
            "amount": "-1234.5678",
            "ratio": 1.25,
            "day": "2026-03-08",
            "instant": "2026-03-08T07:30:15.123456+00:00",
            "clock": "09:30:15.123456",
            "identifier": "01234567-89ab-cdef-0123-456789abcdef",
            "state": "active",
            "state_code": 2,
        }
    ]


def test_date_range_is_inclusive_of_both_calendar_dates() -> None:
    create_value(day=date(2026, 1, 1), instant=datetime(2026, 1, 1, tzinfo=UTC))
    create_value(day=date(2026, 1, 31), instant=datetime(2026, 1, 31, tzinfo=UTC))
    create_value(day=date(2026, 2, 1), instant=datetime(2026, 2, 1, tzinfo=UTC))

    result = execute(
        {
            "resource": "temporal_values",
            "intent": "list",
            "filters": [
                {
                    "field": "day",
                    "op": "date_range",
                    "value": ["2026-01-01", "2026-01-31"],
                }
            ],
            "select": ["day"],
            "order_by": [{"field": "day"}],
        },
        registry=build_registry(),
    )

    assert result.rows == ({"day": date(2026, 1, 1)}, {"day": date(2026, 1, 31)})


def test_time_filters_use_canonical_python_time_values() -> None:
    create_value(
        day=date(2026, 1, 1),
        instant=datetime(2026, 1, 1, tzinfo=UTC),
        clock=time(9, 30),
    )
    create_value(
        day=date(2026, 1, 2),
        instant=datetime(2026, 1, 2, tzinfo=UTC),
        clock=time(10, 30),
    )

    result = execute(
        {
            "resource": "temporal_values",
            "intent": "list",
            "filters": [{"field": "clock", "op": "gte", "value": "10:00:00"}],
            "select": ["clock"],
        },
        registry=build_registry(),
    )

    assert result.rows == ({"clock": time(10, 30)},)


def test_datetime_range_is_half_open() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 2, 1, tzinfo=UTC)
    create_value(day=start.date(), instant=start)
    create_value(day=date(2026, 1, 31), instant=end - timedelta(microseconds=1))
    create_value(day=end.date(), instant=end)

    result = execute(
        {
            "resource": "temporal_values",
            "intent": "list",
            "filters": [
                {
                    "field": "instant",
                    "op": "date_range",
                    "value": ["2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z"],
                }
            ],
            "select": ["instant"],
        },
        registry=build_registry(),
    )

    assert tuple(row["instant"] for row in result.rows) == (
        start,
        end - timedelta(microseconds=1),
    )


def test_last_n_days_includes_start_and_excludes_now_and_future() -> None:
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    start = now - timedelta(days=1)
    for instant in (
        start - timedelta(microseconds=1),
        start,
        now - timedelta(microseconds=1),
        now,
        now + timedelta(hours=1),
    ):
        create_value(day=instant.date(), instant=instant)

    with pytest.warns(DeprecationWarning, match="execute_plan"):
        result = run_query_plan(
            {
                "resource": "temporal_values",
                "intent": "list",
                "filters": [{"field": "instant", "op": "last_n_days", "value": 1}],
                "select": ["instant"],
            },
            registry=build_registry(),
            request=SimpleNamespace(user=None),
            now=now,
        )

    assert tuple(row["instant"] for row in result.rows) == (
        start,
        now - timedelta(microseconds=1),
    )


def test_relative_date_filter_projects_bounds_to_resource_calendar_dates() -> None:
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    for day in (
        date(2026, 7, 25),
        date(2026, 7, 26),
        date(2026, 7, 27),
        date(2026, 7, 28),
    ):
        create_value(day=day, instant=datetime.combine(day, time(12), tzinfo=UTC))

    with pytest.warns(DeprecationWarning, match="execute_plan"):
        result = run_query_plan(
            {
                "resource": "temporal_values",
                "intent": "list",
                "filters": [{"field": "day", "op": "last_n_days", "value": 1}],
                "select": ["day"],
                "order_by": [{"field": "day"}],
            },
            registry=build_registry(),
            request=SimpleNamespace(user=None),
            now=now,
        )

    assert result.rows == ({"day": date(2026, 7, 26)}, {"day": date(2026, 7, 27)})


def test_relative_date_projection_preserves_exclusive_midnight_upper_bound() -> None:
    now = datetime(2026, 7, 27, 0, 0, tzinfo=UTC)
    for day in (date(2026, 7, 26), date(2026, 7, 27)):
        create_value(day=day, instant=datetime.combine(day, time(12), tzinfo=UTC))

    with pytest.warns(DeprecationWarning, match="execute_plan"):
        result = run_query_plan(
            {
                "resource": "temporal_values",
                "intent": "list",
                "filters": [{"field": "day", "op": "last_n_days", "value": 1}],
                "select": ["day"],
                "order_by": [{"field": "day"}],
            },
            registry=build_registry(),
            request=SimpleNamespace(user=None),
            now=now,
        )

    assert result.rows == ({"day": date(2026, 7, 26)},)


@pytest.mark.parametrize(
    ("now", "expected_start"),
    [
        (
            datetime(2026, 4, 8, 2, 30, tzinfo=ZoneInfo("America/New_York")),
            datetime(2026, 3, 8, 7, 30, tzinfo=UTC),
        ),
        (
            datetime(2026, 12, 1, 1, 30, tzinfo=ZoneInfo("America/New_York")),
            datetime(2026, 11, 1, 5, 30, tzinfo=UTC),
        ),
    ],
    ids=["dst-gap-moves-forward", "dst-fold-uses-earlier-occurrence"],
)
def test_last_n_months_executes_at_dst_gap_and_fold_boundaries(
    now: datetime,
    expected_start: datetime,
) -> None:
    expected_end = now.astimezone(UTC)
    for instant in (
        expected_start - timedelta(microseconds=1),
        expected_start,
        expected_end - timedelta(microseconds=1),
        expected_end,
    ):
        create_value(day=instant.date(), instant=instant)

    with pytest.warns(DeprecationWarning, match="execute_plan"):
        result = run_query_plan(
            {
                "resource": "temporal_values",
                "intent": "list",
                "filters": [{"field": "instant", "op": "last_n_months", "value": 1}],
                "select": ["instant"],
            },
            registry=build_registry(resource_timezone="America/New_York"),
            request=SimpleNamespace(user=None),
            now=now,
        )

    assert tuple(row["instant"] for row in result.rows) == (
        expected_start,
        expected_end - timedelta(microseconds=1),
    )


def test_day_grouping_uses_explicit_resource_timezone() -> None:
    timezone = ZoneInfo("America/New_York")
    create_value(
        day=date(2026, 3, 7),
        instant=datetime(2026, 3, 8, 4, 30, tzinfo=UTC),
    )
    create_value(
        day=date(2026, 3, 8),
        instant=datetime(2026, 3, 8, 5, 30, tzinfo=UTC),
    )

    result = execute(
        {
            "resource": "temporal_values",
            "intent": "aggregate",
            "group_by": [{"field": "instant", "date_trunc": "day"}],
            "metrics": [{"metric": "row_count"}],
        },
        registry=build_registry(resource_timezone=timezone.key),
    )

    assert result.rows == (
        {
            "instant": datetime(2026, 3, 7, tzinfo=timezone),
            "row_count": 1,
        },
        {
            "instant": datetime(2026, 3, 8, tzinfo=timezone),
            "row_count": 1,
        },
    )


def test_week_grouping_begins_monday() -> None:
    create_value(
        day=date(2026, 1, 4),
        instant=datetime(2026, 1, 4, 12, tzinfo=UTC),
    )
    create_value(
        day=date(2026, 1, 5),
        instant=datetime(2026, 1, 5, 12, tzinfo=UTC),
    )

    result = execute(
        {
            "resource": "temporal_values",
            "intent": "aggregate",
            "group_by": [{"field": "instant", "date_trunc": "week"}],
            "metrics": [{"metric": "row_count"}],
        },
        registry=build_registry(),
    )

    assert result.rows == (
        {"instant": datetime(2025, 12, 29, tzinfo=UTC), "row_count": 1},
        {"instant": datetime(2026, 1, 5, tzinfo=UTC), "row_count": 1},
    )
