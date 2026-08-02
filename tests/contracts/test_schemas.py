"""Tests for the draft internal machine-readable contract schemas."""

from collections.abc import Mapping
from typing import Any

import pytest
from pydantic import ValidationError

from django_asklens import (
    CONTRACT_SCHEMA_NAMES,
    get_contract_schema,
    list_contract_schemas,
)
from django_asklens.catalog.capabilities import build_capabilities
from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.catalog.resources import Metric
from django_asklens.compiler import ResultColumn
from django_asklens.contracts._generation import (
    build_contract_schema,
    validate_contract_document,
)
from django_asklens.exceptions import PlanParseError, public_error_payload
from django_asklens.execution import QueryResult
from django_asklens.planning.schemas import parse_query_plan
from tests.test_project.models import CanonicalValueFixture

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"


def _property_names(value: object) -> set[str]:
    names: set[str] = set()
    if isinstance(value, Mapping):
        properties = value.get("properties")
        if isinstance(properties, Mapping):
            names.update(str(name) for name in properties)
        for child in value.values():
            names.update(_property_names(child))
    elif isinstance(value, list):
        for child in value:
            names.update(_property_names(child))
    return names


def _local_refs(value: object) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, Mapping):
        ref = value.get("$ref")
        if isinstance(ref, str):
            refs.add(ref)
        for child in value.values():
            refs.update(_local_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.update(_local_refs(child))
    return refs


def _assert_fixed_objects_are_closed(value: object) -> None:
    if isinstance(value, Mapping):
        if value.get("type") == "object" and "properties" in value:
            assert value.get("additionalProperties") is False
        for child in value.values():
            _assert_fixed_objects_are_closed(child)
    elif isinstance(value, list):
        for child in value:
            _assert_fixed_objects_are_closed(child)


def _runtime_documents() -> dict[str, dict[str, Any]]:
    registry = CatalogRegistry()
    registry.register(
        model=CanonicalValueFixture,
        name="canonical_values",
        label="Canonical values",
        description="Synthetic canonical values.",
        synonyms=("fixtures",),
        timezone="UTC",
        scope_mode="global",
        default_date_field="recorded_at",
        default_order=(("id", "asc"),),
        fields={
            "id": {
                "binding": "id",
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
                        {
                            "value": "draft",
                            "label": "Draft",
                            "aliases": ["DRAFT"],
                        }
                    ],
                },
            },
            "recorded_at": {
                "binding": "datetime_value",
                "type": "datetime",
                "nullable": True,
            },
        },
        metrics=(
            Metric(
                name="row_count",
                op="count",
                binding="id",
                result_type="integer",
            ),
        ),
    )
    plan = parse_query_plan(
        {
            "resource": "canonical_values",
            "intent": "list",
            "filters": [{"field": "state", "op": "eq", "value": "draft"}],
            "select": ["id", "state"],
            "order_by": [{"field": "id", "direction": "asc"}],
            "limit": 10,
        }
    )
    result = QueryResult(
        columns=(
            ResultColumn(
                key="id",
                label="Id",
                type="integer",
                nullable=False,
            ),
            ResultColumn(
                key="state",
                label="State",
                type="enum",
                nullable=False,
                enum_values=("draft",),
            ),
        ),
        rows=({"id": 1, "state": "draft"},),
        row_count=1,
        duration_ms=3,
        limit=10,
        limit_scope="rows",
        truncated=False,
    )
    error = public_error_payload(
        PlanParseError("internal diagnostic", pointer="/filters/0/value")
    )
    return {
        "catalog": registry.to_dict(),
        "query-plan": plan.model_dump(mode="json"),
        "capabilities": build_capabilities(),
        "result": result.to_dict(),
        "error": error,
    }


def test_schema_accessors_return_exact_internal_draft_set() -> None:
    assert CONTRACT_SCHEMA_NAMES == (
        "catalog",
        "query-plan",
        "capabilities",
        "result",
        "error",
    )
    assert list_contract_schemas() == CONTRACT_SCHEMA_NAMES

    for name in CONTRACT_SCHEMA_NAMES:
        schema = get_contract_schema(name)
        assert schema == build_contract_schema(name)
        assert schema["$schema"] == DRAFT_2020_12
        assert schema["$id"] == f"{name}.schema.json"
        assert "version" not in _property_names(schema)
        assert "revision" not in _property_names(schema)
        assert all(
            ref.startswith("#/$defs/")
            and ref.removeprefix("#/$defs/") in schema.get("$defs", {})
            for ref in _local_refs(schema)
        )
        _assert_fixed_objects_are_closed(schema)

    first = get_contract_schema("catalog")
    first["title"] = "mutated by caller"
    assert get_contract_schema("catalog")["title"] != "mutated by caller"

    with pytest.raises(ValueError, match="Unknown AskLens contract schema"):
        get_contract_schema("unknown")  # type: ignore[arg-type]


def test_runtime_documents_validate_against_their_generated_schemas() -> None:
    documents = _runtime_documents()

    assert set(documents) == set(CONTRACT_SCHEMA_NAMES)
    assert "enum_text_value" not in str(documents["catalog"])
    assert "datetime_value" not in str(documents["catalog"])
    assert "internal diagnostic" not in str(documents["error"])
    for name, document in documents.items():
        validate_contract_document(name, document)


def test_contracts_reject_extra_or_private_shape() -> None:
    documents = _runtime_documents()

    with pytest.raises(ValidationError):
        validate_contract_document(
            "catalog",
            {
                **documents["catalog"],
                "binding": "private__orm_path",
            },
        )
    with pytest.raises(ValidationError):
        validate_contract_document(
            "query-plan",
            {
                **documents["query-plan"],
                "visualization": {"type": "bar"},
            },
        )
    with pytest.raises(ValidationError):
        validate_contract_document(
            "capabilities",
            {
                **documents["capabilities"],
                "summary": "Human prose does not belong here.",
            },
        )
    with pytest.raises(ValidationError):
        validate_contract_document(
            "result",
            {
                **documents["result"],
                "data": [{"id": ["not", "a", "cell"]}],
            },
        )
    with pytest.raises(ValidationError):
        validate_contract_document(
            "error",
            {
                "code": "asklens.internal.secret",
                "message": "unsafe",
            },
        )
    with pytest.raises(ValidationError):
        validate_contract_document(
            "error",
            {
                "code": "asklens.parse.invalid",
                "message": "The query plan could not be parsed.",
                "pointer": "/filters/0\ninternal",
            },
        )


def test_schemas_omit_private_backend_and_policy_properties() -> None:
    forbidden = {
        "binding",
        "cardinality_policy",
        "distinct_key",
        "expression",
        "permissions",
        "queryset",
        "requires_permission",
        "scope_provider",
        "tenant_id",
    }

    for name in CONTRACT_SCHEMA_NAMES:
        assert forbidden.isdisjoint(_property_names(get_contract_schema(name)))


def test_query_plan_schema_captures_structural_value_constraints() -> None:
    schema = get_contract_schema("query-plan")
    filter_schema = schema["$defs"]["FilterSpec"]
    order_schema = schema["$defs"]["OrderBySpec"]

    assert schema["properties"]["resource"]["minLength"] == 1
    assert schema["properties"]["select"]["items"]["minLength"] == 1
    assert schema["properties"]["limit"]["minimum"] == 1
    assert filter_schema["properties"]["field"]["minLength"] == 1
    assert len(filter_schema["allOf"]) == 5
    assert order_schema["oneOf"] == [
        {
            "properties": {
                "field": {"minLength": 1, "type": "string"},
                "metric": {"type": "null"},
            },
            "required": ["field"],
        },
        {
            "properties": {
                "field": {"type": "null"},
                "metric": {"minLength": 1, "type": "string"},
            },
            "required": ["metric"],
        },
    ]


def test_result_schema_has_one_typed_dynamic_row_map_exception() -> None:
    schema = get_contract_schema("result")
    row_schema = schema["properties"]["data"]["items"]

    assert row_schema["type"] == "object"
    assert row_schema["propertyNames"] == {"minLength": 1}
    assert row_schema["additionalProperties"] == {
        "anyOf": [
            {"type": "string"},
            {"type": "integer"},
            {"type": "number"},
            {"type": "boolean"},
            {"type": "null"},
        ]
    }
