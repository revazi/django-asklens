"""Security tests for the public trusted execution facade."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from django_asklens import Metric
from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.exceptions import PermissionDeniedError, PlanValidationError
from django_asklens.execution import execute_plan, run_query_plan
from django_asklens.planning import parse_query_plan
from tests.test_project.models import Customer, Order

pytestmark = pytest.mark.django_db


@dataclass(frozen=True, slots=True)
class RequestUser:
    """Minimal authenticated user with deterministic permission strings."""

    permissions: frozenset[str]
    is_authenticated: bool = True

    def get_all_permissions(self) -> frozenset[str]:
        """Return permissions used by the default AskLens resolver."""

        return self.permissions


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Minimal request-like object used by execution tests."""

    user: RequestUser
    visible_status: str = "paid"


def build_registry() -> CatalogRegistry:
    """Return a permissioned registry with request-aware row scope."""

    registry = CatalogRegistry()
    registry.register(
        model=Order,
        name="orders",
        fields={
            "id": {"label": "Order ID"},
            "status": {"label": "Status"},
            "customer.email": {
                "label": "Customer email",
                "sensitive": True,
                "result_visible": True,
                "requires_permission": "shop.view_customer_pii",
            },
        },
        metrics=[Metric("order_count", op="count", field="id")],
        requires_permission="shop.view_orders",
        base_queryset=lambda request: Order.objects.filter(
            status=request.visible_status
        ),
    )
    return registry


def request_with(*permissions: str, visible_status: str = "paid") -> RequestContext:
    """Return a request with explicit current permission and row context."""

    return RequestContext(
        user=RequestUser(frozenset(permissions)),
        visible_status=visible_status,
    )


def sensitive_plan():
    """Return a directly constructed shape-valid sensitive-field plan."""

    return parse_query_plan(
        {
            "resource": "orders",
            "intent": "list",
            "select": ["customer.email"],
            "limit": 10,
        }
    )


def status_plan(*, limit: int = 10):
    """Return a directly constructed shape-valid status plan."""

    return parse_query_plan(
        {
            "resource": "orders",
            "intent": "list",
            "select": ["status"],
            "order_by": [{"field": "status", "direction": "asc"}],
            "limit": limit,
        }
    )


def create_order(*, email: str, status: str, total: str) -> None:
    """Create one deterministic order row."""

    customer = Customer.objects.create(name=email, email=email)
    Order.objects.create(
        customer=customer,
        status=status,
        created_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
        total=Decimal(total),
    )


def test_execute_plan_revalidates_direct_query_plan_permissions(
    django_assert_num_queries,
) -> None:
    """A caller-constructed QueryPlan must not bypass current field policy."""

    with (
        django_assert_num_queries(0),
        pytest.raises(PermissionDeniedError, match="sensitive"),
    ):
        execute_plan(
            sensitive_plan(),
            request=request_with("shop.view_orders"),
            registry=build_registry(),
        )


def test_execute_plan_revalidates_current_limits(
    settings,
    django_assert_num_queries,
) -> None:
    """A caller-constructed QueryPlan must not bypass current plan limits."""

    settings.DJANGO_ASKLENS = {"MAX_ROWS": 1}

    with (
        django_assert_num_queries(0),
        pytest.raises(PlanValidationError, match="MAX_ROWS"),
    ):
        execute_plan(
            status_plan(limit=2),
            request=request_with("shop.view_orders"),
            registry=build_registry(),
        )


def test_execute_plan_resolves_current_request_scope() -> None:
    """Successful facade execution uses the current request-aware queryset."""

    create_order(email="paid@example.com", status="paid", total="10.00")
    create_order(email="pending@example.com", status="pending", total="20.00")

    result = execute_plan(
        status_plan(),
        request=request_with("shop.view_orders", visible_status="pending"),
        registry=build_registry(),
    )

    assert result.rows == ({"status": "pending"},)


def test_deprecated_runner_revalidates_instead_of_trusting_query_plan(
    django_assert_num_queries,
) -> None:
    """The compatibility runner must delegate to the safe facade behavior."""

    with (
        django_assert_num_queries(0),
        pytest.warns(DeprecationWarning, match="execute_plan"),
        pytest.raises(PermissionDeniedError, match="sensitive"),
    ):
        run_query_plan(
            sensitive_plan(),
            request=request_with("shop.view_orders"),
            registry=build_registry(),
        )
