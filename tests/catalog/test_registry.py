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
        "id": {"label": "Order ID"},
        "status": {"label": "Status"},
        "created_at": {"label": "Created date"},
        "customer.email": {"label": "Customer email", "sensitive": True},
        "total": {"label": "Order total", "metric": True},
        "internal_notes": {"label": "Internal notes", "llm_visible": False},
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
        base_queryset=scoped_orders,
    )

    assert resource.name == "orders"
    assert resource.label == "Orders"
    assert resource.default_date_field == "created_at"
    assert resource.synonyms == ("sales", "purchases", "transactions")
    assert get_resource("orders") is resource
    assert get_resource("Orders") is resource
    assert resource.get_base_queryset(object()).model is Order

    catalog = serialize_catalog()
    assert catalog["resources"][0]["name"] == "orders"
    assert "model" not in catalog["resources"][0]

    internal_catalog = serialize_catalog(include_internal=True)
    assert internal_catalog["resources"][0]["model"] == "test_project.Order"


def test_duplicate_resource_name_fails_loudly() -> None:
    registry = CatalogRegistry()
    registry.register(model=Order, name="orders", fields={"id": {}})

    with pytest.raises(DuplicateResourceError, match="orders"):
        registry.register(model=Order, name="orders", fields={"id": {}})


def test_field_allowlist_is_explicit_and_validated() -> None:
    registry = CatalogRegistry()
    resource = registry.register(model=Order, fields={"id": {}, "status": {}})

    assert set(resource.fields) == {"id", "status"}
    assert "total" not in resource.fields

    with pytest.raises(UnknownFieldError, match="does_not_exist"):
        registry.register(model=Order, name="bad_field", fields={"does_not_exist": {}})

    with pytest.raises(UnknownFieldError, match="non-relation"):
        registry.register(model=Order, name="bad_path", fields={"status.code": {}})


def test_registered_resource_metadata_is_effectively_immutable() -> None:
    registry = CatalogRegistry()
    resource = registry.register(model=Order, fields={"id": {}, "status": {}})

    with pytest.raises(FrozenInstanceError):
        resource.name = "other"

    with pytest.raises(TypeError):
        resource.fields["total"] = FieldSpec("total", "Total", "number", 0)


def test_sensitive_and_hidden_fields_are_excluded_from_default_catalog() -> None:
    registry = CatalogRegistry()
    registry.register(
        model=Order,
        label="Orders",
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
    resource = registry.register(model=Order, fields=order_fields())

    assert resource.fields["id"].relation_depth == 0
    assert resource.fields["customer.email"].relation_depth == 1


def test_field_config_validation_catches_typos_and_bad_types() -> None:
    registry = CatalogRegistry()

    with pytest.raises(InvalidResourceError, match="sensitve"):
        registry.register(
            model=Order,
            name="typo",
            fields={"customer.email": {"sensitve": True}},
        )

    with pytest.raises(InvalidResourceError, match="llm_visible"):
        registry.register(
            model=Order,
            name="bad_bool",
            fields={"customer.email": {"llm_visible": "no"}},
        )

    with pytest.raises(InvalidResourceError, match="requires_permission"):
        registry.register(
            model=Order,
            name="bad_permission",
            fields={"customer.email": {"requires_permission": object()}},
        )


def test_prebuilt_field_specs_are_still_validated_against_model_paths() -> None:
    registry = CatalogRegistry()
    field_spec = FieldSpec(
        name="status",
        label="Status",
        type="string",
        relation_depth=0,
    )

    resource = registry.register(model=Order, fields={"status": field_spec})

    assert resource.fields["status"] is field_spec

    with pytest.raises(InvalidResourceError, match="must match field path"):
        registry.register(
            model=Order,
            name="mismatch",
            fields={"status": FieldSpec("total", "Total", "number", 0)},
        )

    with pytest.raises(UnknownFieldError, match="missing"):
        registry.register(
            model=Order,
            name="missing_spec",
            fields={"missing": FieldSpec("missing", "Missing", "string", 0)},
        )


def test_resource_config_validation() -> None:
    registry = CatalogRegistry()

    with pytest.raises(InvalidResourceError, match="Django model class"):
        registry.register(model=object, name="bad_model", fields={"id": {}})

    with pytest.raises(InvalidResourceError, match="synonyms"):
        registry.register(
            model=Order,
            name="bad_synonyms",
            fields={"id": {}},
            synonyms="sales",
        )

    with pytest.raises(InvalidResourceError, match="base_queryset"):
        registry.register(
            model=Order,
            name="bad_queryset",
            fields={"id": {}},
            base_queryset=object(),
        )


def test_metric_registration_is_validated() -> None:
    registry = CatalogRegistry()
    resource = registry.register(
        model=Order,
        fields={"id": {}, "total": {}},
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
            fields={"id": {}},
            metrics=[Metric("bad", op="count", field="missing")],
        )

    with pytest.raises(InvalidMetricError, match="Unsupported metric"):
        Metric("median_total", op="median", field="total")


def test_default_date_field_must_be_allowlisted_and_date_like() -> None:
    registry = CatalogRegistry()

    with pytest.raises(UnknownFieldError, match="Default date field"):
        registry.register(
            model=Order,
            fields={"id": {}},
            default_date_field="created_at",
        )

    with pytest.raises(InvalidResourceError, match="date or datetime"):
        registry.register(
            model=Order,
            name="bad_default_date_type",
            fields={"id": {}, "status": {}},
            default_date_field="status",
        )

    with pytest.raises(InvalidResourceError, match="date or datetime"):
        registry.register(
            model=Order,
            name="bad_default_date_override",
            fields={"id": {}, "status": {"type": "date"}},
            default_date_field="status",
        )
