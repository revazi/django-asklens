"""Current identity, policy, catalog, and request revalidation tests."""

import pytest

from django_asklens import Metric
from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.exceptions import PublicAskLensError, public_error_payload
from django_asklens.execution import execute_plan
from django_asklens.planning import parse_and_validate_query_plan, parse_query_plan
from tests.execution.test_facade import (
    build_registry,
    create_order,
    request_with,
    sensitive_plan,
    status_plan,
)
from tests.test_project.models import Order

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def disable_audit(settings) -> None:
    """Assert current-context rejection in zero-total-SQL audit mode."""

    settings.DJANGO_ASKLENS = {"AUDIT_MODE": "disabled"}


MEMBER_ERROR = {
    "code": "asklens.member.unavailable",
    "message": "A requested query member is unavailable.",
}


def test_preview_validation_does_not_authorize_later_execution(
    django_assert_num_queries,
) -> None:
    """A permissioned preview remains untrusted under a later request."""

    registry = build_registry()
    previewed = parse_and_validate_query_plan(
        sensitive_plan().model_dump(mode="json"),
        registry=registry,
        permissions={"shop.view_orders", "shop.view_customer_pii"},
    )

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError) as caught,
    ):
        execute_plan(
            previewed,
            request=request_with("shop.view_orders"),
            registry=registry,
        )

    assert public_error_payload(caught.value) == MEMBER_ERROR


def test_previewed_plan_is_revalidated_against_current_catalog(
    django_assert_num_queries,
) -> None:
    """A plan validated in one catalog cannot authorize another catalog."""

    preview_registry = build_registry()
    previewed = parse_and_validate_query_plan(
        status_plan().model_dump(mode="json"),
        registry=preview_registry,
        permissions={"shop.view_orders"},
    )
    current_registry = CatalogRegistry()
    current_registry.register(
        model=Order,
        name="orders",
        fields={
            "id": {
                "binding": "id",
                "type": "integer",
                "nullable": False,
                "label": "Order ID",
            }
        },
        metrics=[
            Metric("order_count", op="count", binding="id", result_type="integer")
        ],
        scope_mode="context_scoped",
        scope_provider=lambda _request: Order.objects.all(),
    )

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError) as caught,
    ):
        execute_plan(
            previewed,
            request=request_with(),
            registry=current_registry,
        )

    assert public_error_payload(caught.value) == MEMBER_ERROR


def test_same_plan_uses_each_current_request_scope() -> None:
    """Reusing ordinary plan data never reuses a prior request queryset."""

    create_order(email="paid@example.com", status="paid", total="10.00")
    create_order(email="pending@example.com", status="pending", total="20.00")
    plan = status_plan()
    registry = build_registry()

    paid = execute_plan(
        plan,
        request=request_with("shop.view_orders", visible_status="paid"),
        registry=registry,
    )
    pending = execute_plan(
        plan,
        request=request_with("shop.view_orders", visible_status="pending"),
        registry=registry,
    )

    assert paid.rows == ({"status": "paid"},)
    assert pending.rows == ({"status": "pending"},)


def test_resource_and_metric_permissions_are_rechecked_before_sql(
    django_assert_num_queries,
) -> None:
    """Direct plans cannot bypass resource or metric-source permissions."""

    resource_registry = build_registry()
    resource_plan = status_plan()

    metric_registry = CatalogRegistry()
    metric_registry.register(
        model=Order,
        name="orders",
        fields={
            "id": {
                "binding": "id",
                "type": "integer",
                "nullable": False,
                "label": "Order ID",
            },
            "total": {
                "binding": "total",
                "type": "decimal",
                "nullable": False,
                "label": "Order total",
                "requires_permission": "shop.view_financials",
            },
        },
        metrics=[
            Metric(
                "revenue",
                op="sum",
                binding="total",
                result_type="decimal",
                requires_permission="shop.view_financials",
            )
        ],
        scope_mode="context_scoped",
        scope_provider=lambda _request: Order.objects.all(),
    )
    metric_plan = parse_query_plan(
        {
            "resource": "orders",
            "intent": "aggregate",
            "metrics": [{"metric": "revenue"}],
            "limit": 1,
        }
    )

    with django_assert_num_queries(0):
        with pytest.raises(PublicAskLensError) as resource_error:
            execute_plan(
                resource_plan,
                request=request_with(),
                registry=resource_registry,
            )
        with pytest.raises(PublicAskLensError) as metric_error:
            execute_plan(
                metric_plan,
                request=request_with(),
                registry=metric_registry,
            )

    assert public_error_payload(resource_error.value) == MEMBER_ERROR
    assert public_error_payload(metric_error.value) == MEMBER_ERROR
