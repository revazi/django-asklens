"""Privacy and query-count tests for the trusted audit boundary."""

from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext

from django_asklens import Metric
from django_asklens.catalog.registry import default_registry
from django_asklens.exceptions import PublicAskLensError
from django_asklens.execution import execute_plan
from django_asklens.models import SemanticQueryRun
from django_asklens.querying import execute_asklens_query_request
from tests.execution.test_facade import build_registry, sensitive_plan, status_plan
from tests.test_project.models import Customer, Order

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_default_registry() -> None:
    """Keep audit orchestration tests isolated from global registrations."""

    default_registry.clear()
    yield
    default_registry.clear()


def build_request(*permissions: str):
    """Return a request with a real audit user and deterministic permissions."""

    user = get_user_model().objects.create_user(username="audit-user")
    return SimpleNamespace(
        user=user,
        asklens_permissions=frozenset(permissions),
        visible_status="paid",
    )


def configure_audit(settings, *, mode: str, sink=None, include_content=False) -> None:
    """Configure deterministic request permissions and one audit mode."""

    settings.DJANGO_ASKLENS = {
        "REQUEST_PERMISSIONS_GETTER": lambda request: request.asklens_permissions,
        "AUDIT_MODE": mode,
        "AUDIT_SINK": sink,
        "AUDIT_INCLUDE_CONTENT": include_content,
    }


def register_default_orders() -> None:
    """Register the audit Order resource in shared orchestration."""

    default_registry.register(
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
                "requires_permission": "shop.view_customer_pii",
            },
        },
        metrics=[Metric("order_count", op="count", field="id")],
        requires_permission="shop.view_orders",
        scope_mode="context_scoped",
        scope_provider=lambda request: Order.objects.filter(
            status=request.visible_status
        ),
    )


def create_paid_order() -> None:
    """Create one row for successful execution tests."""

    customer = Customer.objects.create(name="Audit", email="audit@example.test")
    Order.objects.create(
        customer=customer,
        status="paid",
        created_at="2026-01-01T00:00:00Z",
        total="10.00",
    )


def test_database_audit_default_writes_operational_metadata_only(
    settings,
    django_assert_num_queries,
) -> None:
    """Successful Python execution emits one metadata-only audit insert."""

    configure_audit(settings, mode="database")
    request = build_request("shop.view_orders")
    create_paid_order()

    with django_assert_num_queries(2):
        result = execute_plan(
            status_plan(),
            request=request,
            registry=build_registry(),
        )

    run = SemanticQueryRun.objects.get()
    assert result.row_count == 1
    assert run.user == request.user
    assert run.question == ""
    assert run.plan == {"resource": "orders", "intent": "list"}
    assert run.status == SemanticQueryRun.Status.SUCCESS
    assert run.row_count == 1
    assert run.error == ""


def test_database_audit_rejection_is_one_insert_and_no_application_query(
    settings,
) -> None:
    """A rejected plan may write one audit row but never query app data."""

    configure_audit(settings, mode="database")
    request = build_request("shop.view_orders")

    with CaptureQueriesContext(connection) as captured:
        with pytest.raises(PublicAskLensError) as caught:
            execute_plan(
                sensitive_plan(),
                request=request,
                registry=build_registry(),
            )

    assert caught.value.code == "asklens.member.unavailable"
    assert len(captured) == 1
    [query] = captured.captured_queries
    sql = query["sql"].upper()
    assert sql.startswith('INSERT INTO "ASKLENS_SEMANTICQUERYRUN"')
    assert "TEST_PROJECT_ORDER" not in sql
    run = SemanticQueryRun.objects.get()
    assert run.question == ""
    assert run.plan == {}
    assert run.error == (
        "asklens.member.unavailable: A requested query member is unavailable."
    )


def test_disabled_audit_rejection_performs_zero_total_sql(
    settings,
    django_assert_num_queries,
) -> None:
    """Disabled auditing adds no SQL to a rejected execution."""

    configure_audit(settings, mode="disabled")
    request = build_request("shop.view_orders")

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError),
    ):
        execute_plan(
            sensitive_plan(),
            request=request,
            registry=build_registry(),
        )

    assert SemanticQueryRun.objects.count() == 0


def test_disabled_audit_success_has_no_audit_sql_or_run_id(
    settings,
    django_assert_num_queries,
) -> None:
    """Question orchestration works without a database audit record."""

    configure_audit(settings, mode="disabled")
    request = build_request("shop.view_orders")
    register_default_orders()
    create_paid_order()

    with django_assert_num_queries(1):
        outcome = execute_asklens_query_request(
            request,
            question="Operational question",
            provided_plan=status_plan().model_dump(mode="json"),
        )

    assert outcome.response_type == "query"
    assert outcome.run is None
    assert "run_id" not in outcome.payload
    assert SemanticQueryRun.objects.count() == 0


def test_custom_non_database_sink_receives_safe_operational_event(
    settings,
    django_assert_num_queries,
) -> None:
    """A custom sink can audit rejection without SQL or raw plan content."""

    events = []
    configure_audit(settings, mode="custom", sink=events.append)
    request = build_request("shop.view_orders")

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError),
    ):
        execute_plan(
            sensitive_plan(),
            request=request,
            registry=build_registry(),
        )

    assert len(events) == 1
    [event] = events
    assert event == {
        "timestamp": event["timestamp"],
        "principal_id": request.user.pk,
        "resource": None,
        "intent": None,
        "status": SemanticQueryRun.Status.FAILED,
        "row_count": 0,
        "duration_ms": None,
        "error_code": "asklens.member.unavailable",
        "error_message": "A requested query member is unavailable.",
    }
    assert SemanticQueryRun.objects.count() == 0


def test_audit_sink_failure_does_not_trigger_execution(
    settings,
    monkeypatch,
    django_assert_num_queries,
) -> None:
    """Failure while auditing rejection preserves rejection and zero SQL."""

    sink_calls = []

    def failing_sink(event):
        sink_calls.append(event)
        raise RuntimeError("audit backend unavailable")

    configure_audit(settings, mode="custom", sink=failing_sink)
    request = build_request("shop.view_orders")
    monkeypatch.setattr(
        "django_asklens.execution.runner._compile_prepared_query",
        lambda _prepared: (_ for _ in ()).throw(
            AssertionError("rejected plan reached compilation")
        ),
    )

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError) as caught,
    ):
        execute_plan(
            sensitive_plan(),
            request=request,
            registry=build_registry(),
        )

    assert caught.value.code == "asklens.member.unavailable"
    assert len(sink_calls) == 1


def test_audit_sink_failure_after_success_does_not_hide_query_result(
    settings,
    django_assert_num_queries,
) -> None:
    """A post-execution audit failure does not replace a successful result."""

    sink_calls = []

    def failing_sink(event):
        sink_calls.append(event)
        raise RuntimeError("audit backend unavailable")

    configure_audit(settings, mode="custom", sink=failing_sink)
    request = build_request("shop.view_orders")
    create_paid_order()

    with django_assert_num_queries(1):
        result = execute_plan(
            status_plan(),
            request=request,
            registry=build_registry(),
        )

    assert result.rows == ({"status": "paid"},)
    assert len(sink_calls) == 1


def test_full_content_audit_requires_explicit_opt_in(settings) -> None:
    """Question and complete plan content are stored only when opted in."""

    configure_audit(settings, mode="database", include_content=True)
    request = build_request("shop.view_orders")
    register_default_orders()
    create_paid_order()
    plan = status_plan().model_dump(mode="json")
    question = "Private operational question"

    outcome = execute_asklens_query_request(
        request,
        question=question,
        provided_plan=plan,
    )

    assert outcome.response_type == "query"
    run = SemanticQueryRun.objects.get()
    assert run.question == question
    assert run.plan == outcome.payload["plan"]
