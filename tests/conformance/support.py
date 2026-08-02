"""Trusted implementation setup for replaying language-neutral fixtures."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import QuerySet

from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.catalog.resources import Metric
from tests.test_project.models import Account, Customer, Order

RESOURCE_PERMISSION = "reports.view_orders"
CONFORMANCE_NOW = datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC"))
NORTH_ACCOUNT_ID = 9_101
SOUTH_ACCOUNT_ID = 9_102
EMPTY_ACCOUNT_ID = 9_103


@dataclass(frozen=True, slots=True)
class Scenario:
    """Server-owned identity, scope, and setting choices for one replay."""

    permissions: frozenset[str]
    account_id: int | None
    setting_overrides: tuple[tuple[str, object], ...] = ()


SCENARIOS = {
    "empty_visible": Scenario(
        permissions=frozenset({RESOURCE_PERMISSION}),
        account_id=EMPTY_ACCOUNT_ID,
    ),
    "missing_scope": Scenario(
        permissions=frozenset({RESOURCE_PERMISSION}),
        account_id=None,
    ),
    "north_no_permission": Scenario(
        permissions=frozenset(),
        account_id=NORTH_ACCOUNT_ID,
    ),
    "north_visible": Scenario(
        permissions=frozenset({RESOURCE_PERMISSION}),
        account_id=NORTH_ACCOUNT_ID,
    ),
    "tight_filter_budget": Scenario(
        permissions=frozenset({RESOURCE_PERMISSION}),
        account_id=NORTH_ACCOUNT_ID,
        setting_overrides=(("MAX_FILTERS", 1),),
    ),
}


class ConformanceUser:
    """Synthetic principal exposing only server-owned permission resolution."""

    is_authenticated = True
    pk = "conformance-user"

    def __init__(self, permissions: frozenset[str]) -> None:
        self._permissions = permissions

    def get_all_permissions(self) -> set[str]:
        """Return this trusted scenario's permission set."""

        return set(self._permissions)


def configure_settings(settings: Any, scenario: Scenario) -> None:
    """Apply trusted replay settings without reading them from fixture input."""

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "disabled",
        "MAX_ROWS": 50,
        **dict(scenario.setting_overrides),
    }


def create_synthetic_rows() -> dict[int, Account]:
    """Create deterministic synthetic rows for one isolated replay."""

    north = Account.objects.create(
        id=NORTH_ACCOUNT_ID,
        name="North Example",
        slug="conformance-north",
    )
    south = Account.objects.create(
        id=SOUTH_ACCOUNT_ID,
        name="South Example",
        slug="conformance-south",
    )
    empty = Account.objects.create(
        id=EMPTY_ACCOUNT_ID,
        name="Empty Example",
        slug="conformance-empty",
    )
    customer = Customer.objects.create(
        id=9_100,
        name="Synthetic Customer",
        email="synthetic@example.invalid",
    )
    utc = ZoneInfo("UTC")
    Order.objects.bulk_create(
        [
            Order(
                id=910_101,
                account=north,
                customer=customer,
                status="paid",
                created_at=datetime(2026, 1, 15, 10, 0, tzinfo=utc),
                total=Decimal("10.50"),
            ),
            Order(
                id=910_102,
                account=north,
                customer=customer,
                status="pending",
                created_at=datetime(2026, 1, 16, 11, 30, tzinfo=utc),
                total=Decimal("20.00"),
            ),
            Order(
                id=910_103,
                account=north,
                customer=customer,
                status="paid",
                created_at=datetime(2026, 1, 17, 12, 45, tzinfo=utc),
                total=Decimal("5.25"),
            ),
            Order(
                id=920_101,
                account=south,
                customer=customer,
                status="paid",
                created_at=datetime(2026, 1, 18, 9, 0, tzinfo=utc),
                total=Decimal("99.00"),
            ),
        ]
    )
    return {
        NORTH_ACCOUNT_ID: north,
        SOUTH_ACCOUNT_ID: south,
        EMPTY_ACCOUNT_ID: empty,
    }


def build_registry() -> CatalogRegistry:
    """Build trusted semantic registration independently of fixture metadata."""

    registry = CatalogRegistry()

    def scope_orders(request: object) -> QuerySet | None:
        account = getattr(request, "account", None)
        if account is None:
            return None
        return Order.objects.filter(account=account)

    registry.register(
        model=Order,
        name="orders",
        label="Orders",
        description="Synthetic scoped orders.",
        timezone="UTC",
        scope_mode="context_scoped",
        scope_provider=scope_orders,  # type: ignore[arg-type]
        requires_permission=RESOURCE_PERMISSION,
        default_date_field="created_at",
        default_order=(("id", "asc"),),
        fields={
            "id": {
                "binding": "id",
                "type": "integer",
                "nullable": False,
                "label": "Order ID",
            },
            "status": {
                "binding": "status",
                "type": "enum",
                "nullable": False,
                "label": "Status",
                "enum": {
                    "type": "string",
                    "values": [
                        {"value": "paid", "label": "Paid"},
                        {"value": "pending", "label": "Pending"},
                    ],
                },
            },
            "created_at": {
                "binding": "created_at",
                "type": "datetime",
                "nullable": False,
                "label": "Created at",
            },
            "total": {
                "binding": "total",
                "type": "decimal",
                "nullable": False,
                "label": "Total",
            },
        },
        metrics=(
            Metric(
                name="order_count",
                op="count",
                binding="id",
                result_type="integer",
                label="Order count",
            ),
            Metric(
                name="revenue",
                op="sum",
                binding="total",
                result_type="decimal",
                label="Revenue",
            ),
        ),
    )
    return registry


def build_request(
    scenario: Scenario,
    accounts: dict[int, Account],
) -> SimpleNamespace:
    """Build current request state solely from the trusted scenario mapping."""

    request = SimpleNamespace(user=ConformanceUser(scenario.permissions))
    if scenario.account_id is not None:
        request.account = accounts[scenario.account_id]
    return request
