"""Tests for the semantic catalog registry."""

from collections.abc import Iterator
from dataclasses import FrozenInstanceError

import pytest
from django.db.models import QuerySet

from django_asklens import Metric, get_resource, register, serialize_catalog
from django_asklens.catalog.registry import CatalogRegistry, default_registry
from django_asklens.catalog.resources import FieldSpec
from django_asklens.exceptions import (
    DuplicateResourceError,
    InvalidMetricError,
    InvalidResourceError,
    UnknownFieldError,
)
from tests.test_project.models import Order


@pytest.fixture(autouse=True)
def clear_default_registry() -> Iterator[None]:
    """Keep public default-registry tests isolated."""

    default_registry.clear()
    yield
    default_registry.clear()


def order_fields() -> dict[str, dict[str, object]]:
    """Return a representative field allowlist for Order resources."""

    return {
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
        "created_at": {
            "binding": "created_at",
            "type": "datetime",
            "nullable": False,
            "label": "Created date",
        },
        "customer.email": {
            "binding": "customer__email",
            "type": "string",
            "nullable": False,
            "label": "Customer email",
            "sensitive": True,
        },
        "total": {
            "binding": "total",
            "type": "decimal",
            "nullable": False,
            "label": "Order total",
            "metric": True,
        },
        "internal_notes": {
            "binding": "internal_notes",
            "type": "string",
            "nullable": False,
            "label": "Internal notes",
            "llm_visible": False,
        },
    }


def scoped_orders(_request: object) -> QuerySet:
    """Return a scoped queryset without executing a database query."""

    return Order.objects.none()


def test_public_register_api_registers_resource() -> None:
    resource = register(
        model=Order,
        label="Orders",
        description="Customer orders placed in the store",
        synonyms=["sales", "purchases", "transactions"],
        default_date_field="created_at",
        fields=order_fields(),
        metrics=[
            Metric("order_count", op="count", field="id", label="Number of orders"),
            Metric("revenue", op="sum", field="total", label="Revenue"),
        ],
        scope_mode="context_scoped",
        scope_provider=scoped_orders,
    )

    assert resource.name == "orders"
    assert resource.label == "Orders"
    assert resource.default_date_field == "created_at"
    assert resource.synonyms == ("sales", "purchases", "transactions")
    assert get_resource("orders") is resource
    assert get_resource("Orders") is resource
    assert resource.get_scope_queryset(object()).model is Order

    catalog = serialize_catalog()
    assert catalog["resources"][0]["name"] == "orders"
    assert "model" not in catalog["resources"][0]

    with pytest.raises(TypeError, match="include_internal"):
        serialize_catalog(include_internal=True)


def test_duplicate_resource_name_fails_loudly() -> None:
    registry = CatalogRegistry()
    registry.register(
        model=Order,
        name="orders",
        scope_mode="global",
        fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
    )

    with pytest.raises(DuplicateResourceError, match="orders"):
        registry.register(
            model=Order,
            name="orders",
            scope_mode="global",
            fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
        )


def test_field_allowlist_is_explicit_and_validated() -> None:
    registry = CatalogRegistry()
    resource = registry.register(
        model=Order,
        scope_mode="global",
        fields={
            "id": {"binding": "id", "type": "integer", "nullable": False},
            "status": {"binding": "status", "type": "string", "nullable": False},
        },
    )

    assert set(resource.fields) == {"id", "status"}
    assert "total" not in resource.fields

    with pytest.raises(UnknownFieldError, match="does_not_exist"):
        registry.register(
            model=Order,
            name="bad_field",
            scope_mode="global",
            fields={
                "does_not_exist": {
                    "binding": "does_not_exist",
                    "type": "string",
                    "nullable": False,
                }
            },
        )

    with pytest.raises(UnknownFieldError, match="non-relation"):
        registry.register(
            model=Order,
            name="bad_path",
            scope_mode="global",
            fields={
                "status.code": {
                    "binding": "status__code",
                    "type": "string",
                    "nullable": False,
                }
            },
        )


def test_semantic_field_keys_are_separate_from_private_django_bindings() -> None:
    """Catalog keys stay public while trusted Django paths remain private."""

    registry = CatalogRegistry()
    resource = registry.register(
        model=Order,
        name="orders",
        scope_mode="global",
        fields={
            "order.number": {
                "binding": "id",
                "type": "integer",
                "nullable": False,
                "label": "Order number",
            },
            "customer_contact": {
                "binding": "customer__email",
                "type": "string",
                "nullable": False,
                "label": "Customer contact",
                "requires_permission": "customers.view_pii",
            },
        },
    )

    assert resource.fields["order.number"].binding == "id"
    assert resource.fields["customer_contact"].binding == "customer__email"
    assert resource.fields["customer_contact"].relation_depth == 1
    assert resource.fields["customer_contact"].relationship_edges == ("customer",)
    catalog = registry.to_dict(permissions={"customers.view_pii"})
    serialized = str(catalog)
    assert {field["name"] for field in catalog["resources"][0]["fields"]} == {
        "order.number",
        "customer_contact",
    }
    assert "binding" not in serialized
    assert "customer__email" not in serialized
    assert "customers.view_pii" not in serialized
    assert "test_project.Order" not in serialized
    assert all(
        field["nullable"] is False for field in catalog["resources"][0]["fields"]
    )


def test_missing_private_field_binding_is_a_migration_error() -> None:
    """A 0.1 field name must never be converted into an ORM path implicitly."""

    registry = CatalogRegistry()

    with pytest.raises(InvalidResourceError, match="binding.*required"):
        registry.register(
            model=Order,
            name="orders",
            scope_mode="global",
            fields={"id": {}},
        )

    assert registry.all() == ()


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ({"binding": "id", "nullable": False}, "Canonical type is required"),
        ({"binding": "id", "type": "integer"}, "nullable must be a boolean"),
    ],
)
def test_field_type_and_nullability_are_required(
    config: dict[str, object],
    message: str,
) -> None:
    """Public field metadata must not be inferred from a private binding."""

    registry = CatalogRegistry()

    with pytest.raises(InvalidResourceError, match=message):
        registry.register(
            model=Order,
            name="orders",
            scope_mode="global",
            fields={"order_id": config},
        )


def test_unsupported_canonical_field_type_fails_registration() -> None:
    """Legacy or backend-specific type labels cannot enter public metadata."""

    registry = CatalogRegistry()

    with pytest.raises(InvalidResourceError, match="Unsupported canonical type"):
        registry.register(
            model=Order,
            name="orders",
            scope_mode="global",
            fields={
                "amount": {
                    "binding": "total",
                    "type": "number",
                    "nullable": False,
                }
            },
        )


def test_non_null_semantics_reject_a_nullable_private_binding() -> None:
    """Registration cannot promise non-null values for a nullable traversal."""

    registry = CatalogRegistry()

    with pytest.raises(InvalidResourceError, match="cannot be non-null"):
        registry.register(
            model=Order,
            name="orders",
            scope_mode="global",
            fields={
                "account_name": {
                    "binding": "account__name",
                    "type": "string",
                    "nullable": False,
                }
            },
        )


def test_unknown_private_field_binding_fails_registration() -> None:
    """Invalid trusted bindings fail while the semantic key stays independent."""

    registry = CatalogRegistry()

    with pytest.raises(UnknownFieldError, match="missing_field"):
        registry.register(
            model=Order,
            name="orders",
            scope_mode="global",
            fields={
                "order_id": {
                    "binding": "missing_field",
                    "type": "integer",
                    "nullable": False,
                }
            },
        )

    assert registry.all() == ()


def test_registered_resource_metadata_is_effectively_immutable() -> None:
    registry = CatalogRegistry()
    resource = registry.register(
        model=Order,
        scope_mode="global",
        fields={
            "id": {"binding": "id", "type": "integer", "nullable": False},
            "status": {"binding": "status", "type": "string", "nullable": False},
        },
    )

    with pytest.raises(FrozenInstanceError):
        resource.name = "other"

    with pytest.raises(TypeError):
        resource.fields["total"] = FieldSpec(
            name="total",
            label="Total",
            type="decimal",
            nullable=False,
            binding="total",
            relation_depth=0,
        )


def test_scope_metadata_is_explicit_and_schema_agnostic() -> None:
    """Registrations can mark arbitrary resources/fields as scope metadata."""

    registry = CatalogRegistry()
    registry.register(
        model=Order,
        name="locations",
        label="Locations",
        scope_mode="global",
        fields={
            "id": {"binding": "id", "type": "integer", "nullable": False},
            "customer.email": {
                "binding": "customer__email",
                "type": "string",
                "nullable": False,
                "scope_dimension": True,
            },
        },
        scope_resource=True,
        examples_enabled=False,
    )

    resource = registry.to_dict()["resources"][0]
    fields = {field["name"]: field for field in resource["fields"]}
    assert resource["scope_resource"] is True
    assert resource["examples_enabled"] is False
    assert fields["customer.email"]["scope_dimension"] is True


def test_resource_permission_scopes_catalog_visibility() -> None:
    registry = CatalogRegistry()
    registry.register(
        model=Order,
        name="orders",
        scope_mode="global",
        fields={
            "id": {"binding": "id", "type": "integer", "nullable": False},
            "status": {"binding": "status", "type": "string", "nullable": False},
        },
        requires_permission="shop.view_orders",
    )

    assert registry.to_dict()["resources"] == []
    assert (
        registry.to_dict(permissions={"shop.view_orders"})["resources"][0]["name"]
        == "orders"
    )
    assert (
        registry.to_dict(permissions={"facility:1:shop.view_orders"})["resources"][0][
            "name"
        ]
        == "orders"
    )


def test_sensitive_and_hidden_fields_are_excluded_from_default_catalog() -> None:
    registry = CatalogRegistry()
    registry.register(
        model=Order,
        label="Orders",
        scope_mode="global",
        fields=order_fields(),
        metrics=[
            Metric("revenue", op="sum", field="total"),
            Metric("email_count", op="count", field="customer.email"),
        ],
    )

    resource = registry.to_dict()["resources"][0]
    field_names = {field["name"] for field in resource["fields"]}
    metric_names = {metric["name"] for metric in resource["metrics"]}

    assert "customer.email" not in field_names
    assert "internal_notes" not in field_names
    assert "total" in field_names
    assert metric_names == {"revenue"}

    full_resource = registry.to_dict(
        include_sensitive=True,
        include_hidden=True,
    )["resources"][0]
    full_field_names = {field["name"] for field in full_resource["fields"]}
    full_metric_names = {metric["name"] for metric in full_resource["metrics"]}

    assert "customer.email" in full_field_names
    assert "internal_notes" in full_field_names
    assert full_metric_names == {"email_count", "revenue"}


def test_relation_depth_is_tracked_for_relation_paths() -> None:
    registry = CatalogRegistry()
    resource = registry.register(
        model=Order, scope_mode="global", fields=order_fields()
    )

    assert resource.fields["id"].relation_depth == 0
    assert resource.fields["customer.email"].relation_depth == 1


def test_field_config_validation_catches_typos_and_bad_types() -> None:
    registry = CatalogRegistry()

    with pytest.raises(InvalidResourceError, match="sensitve"):
        registry.register(
            model=Order,
            name="typo",
            scope_mode="global",
            fields={
                "customer.email": {
                    "binding": "customer__email",
                    "type": "string",
                    "nullable": False,
                    "sensitve": True,
                }
            },
        )

    with pytest.raises(InvalidResourceError, match="llm_visible"):
        registry.register(
            model=Order,
            name="bad_bool",
            scope_mode="global",
            fields={
                "customer.email": {
                    "binding": "customer__email",
                    "type": "string",
                    "nullable": False,
                    "llm_visible": "no",
                }
            },
        )

    with pytest.raises(InvalidResourceError, match="requires_permission"):
        registry.register(
            model=Order,
            name="bad_permission",
            scope_mode="global",
            fields={
                "customer.email": {
                    "binding": "customer__email",
                    "type": "string",
                    "nullable": False,
                    "requires_permission": object(),
                }
            },
        )

    with pytest.raises(InvalidResourceError, match="scope_dimension"):
        registry.register(
            model=Order,
            name="bad_scope_dimension",
            scope_mode="global",
            fields={
                "customer.email": {
                    "binding": "customer__email",
                    "type": "string",
                    "nullable": False,
                    "scope_dimension": "yes",
                }
            },
        )


def test_prebuilt_field_specs_are_validated_against_private_bindings() -> None:
    registry = CatalogRegistry()
    field_spec = FieldSpec(
        name="status",
        label="Status",
        type="string",
        nullable=False,
        binding="status",
        relation_depth=0,
    )

    resource = registry.register(
        model=Order, scope_mode="global", fields={"status": field_spec}
    )

    assert resource.fields["status"] == field_spec
    assert resource.fields["status"].binding == "status"

    with pytest.raises(InvalidResourceError, match="must match semantic key"):
        registry.register(
            model=Order,
            name="mismatch",
            scope_mode="global",
            fields={
                "status": FieldSpec(
                    name="total",
                    label="Total",
                    type="decimal",
                    nullable=False,
                    binding="total",
                    relation_depth=0,
                )
            },
        )

    with pytest.raises(UnknownFieldError, match="missing"):
        registry.register(
            model=Order,
            name="missing_spec",
            scope_mode="global",
            fields={
                "missing": FieldSpec(
                    name="missing",
                    label="Missing",
                    type="string",
                    nullable=False,
                    binding="missing",
                    relation_depth=0,
                )
            },
        )


def test_resource_config_validation() -> None:
    registry = CatalogRegistry()

    with pytest.raises(InvalidResourceError, match="Django model class"):
        registry.register(
            model=object,
            name="bad_model",
            scope_mode="global",
            fields={"id": {"binding": "id", "type": "string", "nullable": False}},
        )

    with pytest.raises(InvalidResourceError, match="synonyms"):
        registry.register(
            model=Order,
            name="bad_synonyms",
            scope_mode="global",
            fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
            synonyms="sales",
        )

    with pytest.raises(InvalidResourceError, match="scope_provider"):
        registry.register(
            model=Order,
            name="bad_scope_provider",
            fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
            scope_mode="context_scoped",
            scope_provider=object(),
        )

    with pytest.raises(InvalidResourceError, match="requires_permission"):
        registry.register(
            model=Order,
            name="bad_resource_permission",
            scope_mode="global",
            fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
            requires_permission=object(),
        )

    with pytest.raises(InvalidResourceError, match="scope_resource"):
        registry.register(
            model=Order,
            name="bad_scope_resource",
            scope_mode="global",
            fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
            scope_resource=object(),
        )

    with pytest.raises(InvalidResourceError, match="examples_enabled"):
        registry.register(
            model=Order,
            name="bad_examples_enabled",
            scope_mode="global",
            fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
            examples_enabled=object(),
        )


def test_metric_registration_is_validated() -> None:
    registry = CatalogRegistry()
    resource = registry.register(
        model=Order,
        scope_mode="global",
        fields={
            "id": {"binding": "id", "type": "integer", "nullable": False},
            "total": {"binding": "total", "type": "decimal", "nullable": False},
        },
        metrics=[Metric("revenue", op="sum", field="total")],
    )

    assert resource.metrics["revenue"].to_dict() == {
        "name": "revenue",
        "label": "Revenue",
        "op": "sum",
        "field": "total",
    }

    with pytest.raises(UnknownFieldError, match="missing"):
        registry.register(
            model=Order,
            name="bad_metric_field",
            scope_mode="global",
            fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
            metrics=[Metric("bad", op="count", field="missing")],
        )

    with pytest.raises(InvalidMetricError, match="Unsupported metric"):
        Metric("median_total", op="median", field="total")


def test_default_date_field_must_be_allowlisted_and_date_like() -> None:
    registry = CatalogRegistry()

    with pytest.raises(UnknownFieldError, match="Default date field"):
        registry.register(
            model=Order,
            scope_mode="global",
            fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
            default_date_field="created_at",
        )

    with pytest.raises(InvalidResourceError, match="date or datetime"):
        registry.register(
            model=Order,
            name="bad_default_date_type",
            scope_mode="global",
            fields={
                "id": {"binding": "id", "type": "integer", "nullable": False},
                "status": {"binding": "status", "type": "string", "nullable": False},
            },
            default_date_field="status",
        )

    with pytest.raises(InvalidResourceError, match="does not match"):
        registry.register(
            model=Order,
            name="bad_default_date_override",
            scope_mode="global",
            fields={
                "id": {"binding": "id", "type": "integer", "nullable": False},
                "status": {"binding": "status", "nullable": False, "type": "date"},
            },
            default_date_field="status",
        )

    with pytest.raises(InvalidResourceError, match="does not match"):
        registry.register(
            model=Order,
            name="bad_default_date_semantics",
            scope_mode="global",
            fields={
                "placed_at": {
                    "binding": "created_at",
                    "type": "string",
                    "nullable": False,
                }
            },
            default_date_field="placed_at",
        )
