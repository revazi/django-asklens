"""Deterministic PostgreSQL evidence for bounded host-control integration."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal

import pytest
from django.db import ConnectionHandler, DatabaseError, connection, transaction
from rest_framework.test import APIClient

from django_asklens import Metric
from django_asklens.catalog.registry import default_registry
from django_asklens.models import SemanticQueryRun
from tests.test_project.models import Customer, Order

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.postgresql,
]

READ_ROLE = "asklens_issue84_read_only"
QUERY_PERMISSION = "shop.view_orders"


@dataclass(frozen=True, slots=True)
class RequestUser:
    """Synthetic authenticated principal with server-owned permissions."""

    is_authenticated: bool = True

    def get_all_permissions(self) -> frozenset[str]:
        return frozenset({QUERY_PERMISSION})


@pytest.fixture(autouse=True)
def isolated_registry() -> Iterator[None]:
    """Keep API execution registration isolated from the shared registry."""

    default_registry.clear()
    yield
    default_registry.clear()


def _register_orders() -> None:
    default_registry.register(
        timezone="UTC",
        model=Order,
        name="orders",
        fields={
            "id": {
                "binding": "id",
                "type": "integer",
                "nullable": False,
            },
            "status": {
                "binding": "status",
                "type": "string",
                "nullable": False,
            },
            "customer.email": {
                "binding": "customer__email",
                "type": "string",
                "nullable": False,
                "sensitive": True,
                "requires_permission": "shop.view_customer_pii",
            },
        },
        metrics=[
            Metric("order_count", op="count", binding="id", result_type="integer")
        ],
        requires_permission=QUERY_PERMISSION,
        scope_mode="context_scoped",
        scope_provider=lambda _request: Order.objects.filter(status="paid"),
    )


def _create_order() -> Order:
    customer = Customer.objects.create(
        name="Synthetic role customer",
        email="role@example.test",
    )
    return Order.objects.create(
        customer=customer,
        status="paid",
        created_at="2026-01-01T00:00:00Z",
        total=Decimal("10.00"),
    )


def _query_payload(*, selected: str = "status") -> dict[str, object]:
    return {
        "question": "Show synthetic order status",
        "plan": {
            "resource": "orders",
            "intent": "list",
            "select": [selected],
            "limit": 10,
        },
    }


@pytest.fixture
def disposable_read_role() -> Iterator[str]:
    """Create one CI-only role that can select the synthetic query table."""

    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL role evidence requires the existing PostgreSQL harness")

    quoted_role = connection.ops.quote_name(READ_ROLE)
    quoted_order_table = connection.ops.quote_name(Order._meta.db_table)
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_schema()")
        [schema] = cursor.fetchone()
        quoted_schema = connection.ops.quote_name(schema)
        cursor.execute(f"DROP ROLE IF EXISTS {quoted_role}")
        cursor.execute(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT"
        )
        cursor.execute(f"GRANT USAGE ON SCHEMA {quoted_schema} TO {quoted_role}")
        cursor.execute(f"GRANT SELECT ON TABLE {quoted_order_table} TO {quoted_role}")

    try:
        yield READ_ROLE
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute(f"DROP OWNED BY {quoted_role}")
            cursor.execute(f"DROP ROLE {quoted_role}")


@contextmanager
def _using_role(role: str) -> Iterator[None]:
    quoted_role = connection.ops.quote_name(role)
    with connection.cursor() as cursor:
        cursor.execute(f"SET ROLE {quoted_role}")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")


def test_postgresql_connection_options_apply_statement_timeout() -> None:
    """A disposable connection observes a timeout supplied through OPTIONS."""

    if connection.vendor != "postgresql":
        pytest.skip(
            "PostgreSQL timeout evidence requires the existing PostgreSQL harness"
        )

    probe_settings = deepcopy(connection.settings_dict)
    probe_settings["CONN_MAX_AGE"] = 0
    probe_settings["OPTIONS"] = {
        **probe_settings.get("OPTIONS", {}),
        "options": "-c statement_timeout=1234",
    }
    probe_connections = ConnectionHandler({"default": probe_settings})
    probe = probe_connections["default"]
    try:
        with probe.cursor() as cursor:
            cursor.execute("SHOW statement_timeout")
            [observed] = cursor.fetchone()
        assert observed == "1234ms"
    finally:
        probe.close()


def test_disposable_read_role_allows_query_but_denies_application_writes(
    settings,
    disposable_read_role: str,
) -> None:
    """The facade can read through a role without application DML privileges."""

    settings.DJANGO_ASKLENS = {"AUDIT_MODE": "disabled"}
    _register_orders()
    order = _create_order()
    client = APIClient()
    client.force_authenticate(user=RequestUser())

    with _using_role(disposable_read_role):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT "
                "has_table_privilege(current_user, %s, 'SELECT'), "
                "has_table_privilege(current_user, %s, 'UPDATE')",
                [Order._meta.db_table, Order._meta.db_table],
            )
            assert cursor.fetchone() == (True, False)

        response = client.post("/asklens/query/", _query_payload(), format="json")

        assert response.status_code == 200
        assert response.data["result"]["data"] == [{"status": "paid"}]
        assert "run_id" not in response.data
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                Order.objects.filter(pk=order.pk).update(status="pending")

    order.refresh_from_db()
    assert order.status == "paid"


def test_database_audit_write_denial_preserves_safe_api_results_and_errors(
    settings,
    disposable_read_role: str,
) -> None:
    """A strict query role cannot make audit failure replace API outcomes."""

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "database",
        "AUDIT_INCLUDE_CONTENT": False,
    }
    _register_orders()
    _create_order()
    client = APIClient()
    client.force_authenticate(user=RequestUser())

    with _using_role(disposable_read_role):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT has_table_privilege(current_user, %s, 'INSERT')",
                [SemanticQueryRun._meta.db_table],
            )
            assert cursor.fetchone() == (False,)

        success = client.post("/asklens/query/", _query_payload(), format="json")
        rejection = client.post(
            "/asklens/query/",
            _query_payload(selected="customer.email"),
            format="json",
        )

    assert success.status_code == 200
    assert success.data["result"]["data"] == [{"status": "paid"}]
    assert "run_id" not in success.data
    assert rejection.status_code == 400
    assert rejection.json() == {
        "error": {
            "code": "asklens.member.unavailable",
            "message": "A requested query member is unavailable.",
        }
    }
    assert SemanticQueryRun.objects.count() == 0
