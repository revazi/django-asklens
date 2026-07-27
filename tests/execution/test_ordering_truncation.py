"""Deterministic ordering and accurate truncation execution tests."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from django_asklens import Metric
from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.exceptions import InvalidResourceError
from django_asklens.execution import execute_plan
from tests.test_project.models import Account, Customer, Order

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def disable_audit(settings) -> None:
    """Keep result-semantics query counts independent from audit SQL."""

    settings.DJANGO_ASKLENS = {"AUDIT_MODE": "disabled"}


def request_context() -> SimpleNamespace:
    """Return a minimal current request."""

    return SimpleNamespace(user=None)


def build_registry(
    *,
    default_order: tuple[tuple[str, str], ...] = (),
    row_identity: str | None = None,
) -> CatalogRegistry:
    """Return an Order registry with configurable deterministic metadata."""

    registry = CatalogRegistry()
    registration: dict[str, Any] = {
        "model": Order,
        "name": "orders",
        "scope_mode": "global",
        "fields": {
            "id": {"binding": "id", "type": "integer", "nullable": False},
            "status": {
                "binding": "status",
                "type": "string",
                "nullable": False,
            },
            "created_at": {
                "binding": "created_at",
                "type": "datetime",
                "nullable": False,
            },
            "total": {
                "binding": "total",
                "type": "decimal",
                "nullable": False,
            },
            "account.name": {
                "binding": "account__name",
                "type": "string",
                "nullable": True,
            },
        },
        "metrics": [
            Metric("order_count", op="count", binding="id", result_type="integer"),
            Metric("revenue", op="sum", binding="total", result_type="decimal"),
        ],
        "default_order": default_order,
    }
    if row_identity is not None:
        registration["row_identity"] = row_identity
    registry.register(**registration)
    return registry


def create_order(
    *,
    status: str,
    total: str,
    account: Account | None = None,
) -> Order:
    """Create one deterministic row and return it."""

    customer = Customer.objects.create(
        name=f"{status}-{total}",
        email=f"{status}-{total}@example.com",
    )
    return Order.objects.create(
        customer=customer,
        account=account,
        status=status,
        created_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
        total=Decimal(total),
    )


def list_plan(**updates: object) -> dict[str, Any]:
    """Return a list plan that deliberately omits order by default."""

    payload: dict[str, Any] = {
        "resource": "orders",
        "intent": "list",
        "select": ["id", "status"],
        "limit": 2,
    }
    payload.update(updates)
    return payload


def grouped_plan(**updates: object) -> dict[str, Any]:
    """Return a grouped aggregate plan with optional ordering."""

    payload: dict[str, Any] = {
        "resource": "orders",
        "intent": "aggregate",
        "group_by": [{"field": "status"}],
        "metrics": [{"metric": "order_count"}],
        "limit": 2,
    }
    payload.update(updates)
    return payload


def test_list_without_order_uses_private_identity_and_is_repeatable() -> None:
    """Identity ordering makes repeated limited list queries deterministic."""

    first = create_order(status="same", total="10.00")
    second = create_order(status="same", total="20.00")
    create_order(status="same", total="30.00")
    registry = build_registry()

    first_result = execute_plan(
        list_plan(),
        request=request_context(),
        registry=registry,
    )
    second_result = execute_plan(
        list_plan(),
        request=request_context(),
        registry=registry,
    )

    assert first.pk < second.pk
    assert (
        first_result.rows
        == second_result.rows
        == (
            {"id": first.pk, "status": "same"},
            {"id": second.pk, "status": "same"},
        )
    )
    assert first_result.truncated is True


def test_semantic_default_order_then_identity_is_deterministic() -> None:
    """An omitted plan order uses semantic defaults plus identity tie-breaker."""

    pending = create_order(status="pending", total="10.00")
    first_paid = create_order(status="paid", total="20.00")
    second_paid = create_order(status="paid", total="30.00")
    registry = build_registry(default_order=(("status", "asc"),))
    resource = registry.get("orders")
    catalog_resource = registry.to_dict()["resources"][0]

    assert resource.row_identity == "id"
    assert catalog_resource["default_order"] == [
        {"field": "status", "direction": "asc"}
    ]
    assert "row_identity" not in catalog_resource

    result = execute_plan(
        list_plan(limit=3),
        request=request_context(),
        registry=registry,
    )

    assert first_paid.pk < second_paid.pk
    assert result.rows == (
        {"id": first_paid.pk, "status": "paid"},
        {"id": second_paid.pk, "status": "paid"},
        {"id": pending.pk, "status": "pending"},
    )
    assert result.truncated is False


def test_explicit_order_appends_identity_for_ties() -> None:
    """Caller ordering remains primary while identity stabilizes equal values."""

    first = create_order(status="paid", total="10.00")
    second = create_order(status="paid", total="20.00")
    registry = build_registry(default_order=(("created_at", "desc"),))

    result = execute_plan(
        list_plan(
            order_by=[{"field": "status", "direction": "asc"}],
            limit=2,
        ),
        request=request_context(),
        registry=registry,
    )

    assert result.rows == (
        {"id": first.pk, "status": "paid"},
        {"id": second.pk, "status": "paid"},
    )


def test_nulls_sort_last_for_ascending_and_descending_order() -> None:
    """Null placement does not inherit backend-specific defaults."""

    account = Account.objects.create(name="Alpha", slug="alpha")
    with_account = create_order(status="paid", total="10.00", account=account)
    without_account = create_order(status="paid", total="20.00")
    registry = build_registry(default_order=(("account.name", "asc"),))
    plan = list_plan(select=["id", "account.name"], limit=2)

    ascending = execute_plan(plan, request=request_context(), registry=registry)
    descending = execute_plan(
        {
            **plan,
            "order_by": [{"field": "account.name", "direction": "desc"}],
        },
        request=request_context(),
        registry=registry,
    )

    expected = (
        {"id": with_account.pk, "account.name": "Alpha"},
        {"id": without_account.pk, "account.name": None},
    )
    assert ascending.rows == expected
    assert descending.rows == expected


@pytest.mark.parametrize("row_count", [1, 2, 3])
def test_list_truncated_is_true_only_when_another_row_exists(
    row_count: int,
    django_assert_num_queries,
) -> None:
    """List execution fetches one extra row without returning it."""

    for index in range(row_count):
        create_order(status="paid", total=f"{index + 1}.00")

    with django_assert_num_queries(1):
        result = execute_plan(
            list_plan(limit=2),
            request=request_context(),
            registry=build_registry(),
        )

    assert result.row_count == min(row_count, 2)
    assert result.limit == 2
    assert result.limit_scope == "rows"
    assert result.truncated is (row_count > 2)
    assert result.to_dict()["result_metadata"] == {
        "limit": 2,
        "limit_scope": "rows",
        "truncated": row_count > 2,
    }


def test_grouped_order_appends_group_key_and_reports_truncation() -> None:
    """Metric ties use group keys and grouped execution detects another group."""

    create_order(status="pending", total="10.00")
    create_order(status="failed", total="20.00")
    create_order(status="paid", total="30.00")

    result = execute_plan(
        grouped_plan(
            order_by=[{"metric": "order_count", "direction": "desc"}],
            limit=2,
        ),
        request=request_context(),
        registry=build_registry(),
    )

    assert result.rows == (
        {"status": "failed", "order_count": 1},
        {"status": "paid", "order_count": 1},
    )
    assert result.limit == 2
    assert result.limit_scope == "groups"
    assert result.truncated is True


def test_grouped_exact_limit_is_not_truncated() -> None:
    """Returning exactly the requested number of groups is not truncation."""

    create_order(status="pending", total="10.00")
    create_order(status="paid", total="20.00")

    result = execute_plan(
        grouped_plan(limit=2),
        request=request_context(),
        registry=build_registry(),
    )

    assert result.row_count == 2
    assert result.truncated is False


def test_ungrouped_aggregate_has_effective_limit_one_and_never_truncates() -> None:
    """A scalar aggregate returns exactly one non-truncated result row."""

    create_order(status="paid", total="10.00")
    create_order(status="pending", total="20.00")

    result = execute_plan(
        {
            "resource": "orders",
            "intent": "aggregate",
            "metrics": [{"metric": "order_count"}],
            "limit": 10,
        },
        request=request_context(),
        registry=build_registry(),
    )

    assert result.rows == ({"order_count": 2},)
    assert result.limit == 1
    assert result.limit_scope == "groups"
    assert result.truncated is False


def test_default_order_registration_is_validated() -> None:
    """Default ordering must use unique registered semantic fields."""

    registry = CatalogRegistry()

    with pytest.raises(InvalidResourceError, match="sequence.*pairs"):
        registry.register(
            model=Order,
            fields={
                "id": {"binding": "id", "type": "integer", "nullable": False},
                "status": {"binding": "status", "type": "string", "nullable": False},
            },
            scope_mode="global",
            default_order="status",
        )

    with pytest.raises(InvalidResourceError, match="default_order.*registered"):
        registry.register(
            model=Order,
            fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
            scope_mode="global",
            default_order=(("missing", "asc"),),
        )

    with pytest.raises(InvalidResourceError, match="Duplicate default_order"):
        registry.register(
            model=Order,
            fields={
                "id": {"binding": "id", "type": "integer", "nullable": False},
                "status": {"binding": "status", "type": "string", "nullable": False},
            },
            scope_mode="global",
            default_order=(("status", "asc"), ("status", "desc")),
        )

    with pytest.raises(InvalidResourceError, match="asc.*desc"):
        registry.register(
            model=Order,
            fields={
                "id": {"binding": "id", "type": "integer", "nullable": False},
                "status": {"binding": "status", "type": "string", "nullable": False},
            },
            scope_mode="global",
            default_order=(("status", "sideways"),),
        )

    with pytest.raises(InvalidResourceError, match="unrestricted result-visible"):
        registry.register(
            model=Order,
            fields={
                "id": {"binding": "id", "type": "integer", "nullable": False},
                "status": {
                    "binding": "status",
                    "type": "string",
                    "nullable": False,
                    "requires_permission": "shop.private",
                },
            },
            scope_mode="global",
            default_order=(("status", "asc"),),
        )


def test_alternate_row_identity_requires_non_null_unique_field() -> None:
    """Unsafe identity guesses fail registration without an escape hatch."""

    registry = CatalogRegistry()
    with pytest.raises(InvalidResourceError, match="one concrete field"):
        registry.register(
            model=Order,
            fields={
                "id": {"binding": "id", "type": "integer", "nullable": False},
                "status": {"binding": "status", "type": "string", "nullable": False},
            },
            scope_mode="global",
            row_identity="",
        )

    with pytest.raises(InvalidResourceError, match="non-null.*unique"):
        registry.register(
            model=Order,
            fields={
                "id": {"binding": "id", "type": "integer", "nullable": False},
                "status": {"binding": "status", "type": "string", "nullable": False},
            },
            scope_mode="global",
            row_identity="status",
        )

    account_registry = CatalogRegistry()
    resource = account_registry.register(
        model=Account,
        fields={"name": {"binding": "name", "type": "string", "nullable": False}},
        scope_mode="global",
        row_identity="slug",
    )

    assert resource.row_identity == "slug"
