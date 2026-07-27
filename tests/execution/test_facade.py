"""Security tests for the public trusted execution facade."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal

import pytest

from django_asklens import Metric
from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.exceptions import PublicAskLensError
from django_asklens.execution import execute_plan, run_query_plan
from django_asklens.planning import parse_query_plan
from tests.test_project.models import CanonicalValueFixture, Customer, Facility, Order

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def disable_audit(settings) -> None:
    """Keep facade authorization tests in accepted zero-total-SQL mode."""

    settings.DJANGO_ASKLENS = {"AUDIT_MODE": "disabled"}


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
            "id": {
                "binding": "id",
                "type": "integer",
                "nullable": False,
                "label": "Order ID",
            },
            "status": {
                "binding": "status",
                "type": "string",
                "nullable": False,
                "label": "Status",
            },
            "customer.email": {
                "binding": "customer__email",
                "type": "string",
                "nullable": False,
                "label": "Customer email",
                "sensitive": True,
                "result_visible": True,
                "requires_permission": "shop.view_customer_pii",
            },
        },
        metrics=[
            Metric("order_count", op="count", binding="id", result_type="integer")
        ],
        requires_permission="shop.view_orders",
        scope_mode="context_scoped",
        scope_provider=lambda request: Order.objects.filter(
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


def build_independent_fanout_registry() -> CatalogRegistry:
    """Return two independently safe metrics that are unsafe together."""

    registry = CatalogRegistry()
    registry.register(
        model=Facility,
        name="facilities",
        scope_mode="global",
        fields={
            "name": {
                "binding": "name",
                "type": "string",
                "nullable": False,
            }
        },
        metrics=[
            Metric(
                "member_count",
                op="count",
                binding="members__member_id",
                result_type="integer",
                cardinality_policy="count_rows",
            ),
            Metric(
                "staff_count",
                op="count",
                binding="staff_assignments__id",
                result_type="integer",
                cardinality_policy="count_rows",
            ),
        ],
    )
    return registry


def build_canonical_registry() -> CatalogRegistry:
    """Return canonical fields for pre-query semantic rejection tests."""

    registry = CatalogRegistry()
    registry.register(
        model=CanonicalValueFixture,
        name="canonical_values",
        scope_mode="global",
        fields={
            "count": {
                "binding": "integer_value",
                "type": "integer",
                "nullable": False,
            },
            "state": {
                "binding": "enum_text_value",
                "type": "enum",
                "nullable": False,
                "enum": {
                    "type": "string",
                    "values": [
                        {"value": "draft", "aliases": ["pending"]},
                        {"value": "active"},
                    ],
                },
            },
        },
    )
    return registry


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


def test_execute_plan_rejects_client_metric_redefinition_before_sql(
    django_assert_num_queries,
) -> None:
    plan = {
        "resource": "orders",
        "intent": "aggregate",
        "metrics": [
            {
                "metric": "order_count",
                "op": "count",
                "field": "customer__email",
                "distinct": True,
            }
        ],
    }

    with django_assert_num_queries(0):
        with pytest.raises(PublicAskLensError) as exc_info:
            execute_plan(
                plan,
                request=request_with("shop.view_orders"),
                registry=build_registry(),
            )

    assert exc_info.value.code == "asklens.parse.invalid"


def test_execute_plan_rejects_independent_metric_fanout_before_sql(
    django_assert_num_queries,
) -> None:
    plan = {
        "resource": "facilities",
        "intent": "aggregate",
        "metrics": [
            {"metric": "member_count"},
            {"metric": "staff_count"},
        ],
    }

    with django_assert_num_queries(0):
        with pytest.raises(PublicAskLensError) as exc_info:
            execute_plan(
                plan,
                request=request_with(),
                registry=build_independent_fanout_registry(),
            )

    assert exc_info.value.code == "asklens.plan.invalid"


@pytest.mark.parametrize(
    "filter_spec",
    [
        {"field": "count", "op": "contains", "value": "1"},
        {"field": "state", "op": "eq", "value": "unknown"},
        {"field": "count", "op": "eq", "value": "1"},
    ],
)
def test_invalid_canonical_filters_reject_before_application_sql(
    filter_spec: dict[str, object],
    django_assert_num_queries,
) -> None:
    """Type/operator/enum failures must not reach registered application data."""

    with django_assert_num_queries(0):
        with pytest.raises(PublicAskLensError) as exc_info:
            execute_plan(
                {
                    "resource": "canonical_values",
                    "intent": "list",
                    "filters": [filter_spec],
                    "select": ["count"],
                    "limit": 10,
                },
                request=request_with(),
                registry=build_canonical_registry(),
            )

    assert exc_info.value.code == "asklens.plan.invalid"


def test_invalid_enum_value_does_not_reveal_unavailable_field(
    django_assert_num_queries,
) -> None:
    """Value normalization runs only after current field authorization."""

    registry = build_canonical_registry()
    state = registry.get("canonical_values").fields["state"]
    hidden_registry = CatalogRegistry()
    hidden_registry.register(
        model=CanonicalValueFixture,
        name="canonical_values",
        scope_mode="global",
        fields={
            "count": {
                "binding": "integer_value",
                "type": "integer",
                "nullable": False,
            },
            "state": {
                "binding": state.binding,
                "type": "enum",
                "nullable": False,
                "requires_permission": "reports.view_state",
                "enum": state.enum.to_dict() if state.enum is not None else None,
            },
        },
    )

    with django_assert_num_queries(0):
        with pytest.raises(PublicAskLensError) as exc_info:
            execute_plan(
                {
                    "resource": "canonical_values",
                    "intent": "list",
                    "filters": [{"field": "state", "op": "eq", "value": "unknown"}],
                    "select": ["count"],
                },
                request=request_with(),
                registry=hidden_registry,
            )

    assert exc_info.value.code == "asklens.member.unavailable"


def test_unregistered_enum_result_fails_inside_trusted_execution(
    django_assert_num_queries,
) -> None:
    """Unexpected stored enum values cannot become successful public results."""

    CanonicalValueFixture.objects.create(
        text_value="value",
        boolean_value=False,
        integer_value=1,
        decimal_value=Decimal("1.0000"),
        float_value=1.0,
        date_value=date(2026, 1, 1),
        datetime_value=datetime(2026, 1, 1, tzinfo=UTC),
        time_value=time(12, 0),
        enum_text_value="retired",
    )

    with django_assert_num_queries(1):
        with pytest.raises(PublicAskLensError) as exc_info:
            execute_plan(
                {
                    "resource": "canonical_values",
                    "intent": "list",
                    "select": ["state"],
                    "limit": 10,
                },
                request=request_with(),
                registry=build_canonical_registry(),
            )

    assert exc_info.value.code == "asklens.execute.failed"


def test_execute_plan_revalidates_direct_query_plan_permissions(
    django_assert_num_queries,
) -> None:
    """A caller-constructed QueryPlan must not bypass current field policy."""

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError, match="requested query member") as caught,
    ):
        execute_plan(
            sensitive_plan(),
            request=request_with("shop.view_orders"),
            registry=build_registry(),
        )

    assert caught.value.code == "asklens.member.unavailable"


def test_execute_plan_revalidates_current_limits(
    settings,
    django_assert_num_queries,
) -> None:
    """A caller-constructed QueryPlan must not bypass current plan limits."""

    settings.DJANGO_ASKLENS = {"MAX_ROWS": 1, "AUDIT_MODE": "disabled"}

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError, match="execution limit") as caught,
    ):
        execute_plan(
            status_plan(limit=2),
            request=request_with("shop.view_orders"),
            registry=build_registry(),
        )

    assert caught.value.code == "asklens.budget.exceeded"


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
        pytest.raises(PublicAskLensError, match="requested query member") as caught,
    ):
        run_query_plan(
            sensitive_plan(),
            request=request_with("shop.view_orders"),
            registry=build_registry(),
        )

    assert caught.value.code == "asklens.member.unavailable"
