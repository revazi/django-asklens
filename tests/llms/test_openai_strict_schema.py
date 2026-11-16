"""Offline strict-wire evidence; never provider acceptance or model evidence."""

import json
from copy import deepcopy
from datetime import UTC, datetime

import pytest
from jsonschema import Draft202012Validator

from django_asklens.exceptions import (
    LLMProviderError,
    PlanParseError,
    PlanValidationError,
    PublicAskLensError,
)
from django_asklens.execution import execute_plan
from django_asklens.llms import DummyProvider, OpenAICompatibleProvider
from django_asklens.llms._openai_schema import (
    normalize_wire_response,
    strict_wire_schema,
)
from django_asklens.planning.help import QueryHelp, get_query_help_json_schema
from django_asklens.planning.intents import QuestionIntent
from django_asklens.planning.planner import (
    PlannerProviderResponse,
    parse_planner_provider_response,
)
from django_asklens.planning.responses import (
    AskLensProviderResponse,
    get_asklens_provider_response_json_schema,
    parse_asklens_provider_response,
)
from django_asklens.planning.schemas import (
    SUPPORTED_DATE_TRUNCS,
    SUPPORTED_FILTER_OPERATORS,
    get_query_plan_json_schema,
    parse_query_plan,
)
from tests.execution.test_facade import build_registry, request_with
from tests.llms.test_openai_compatible import FakeResponse
from tests.test_project.models import Customer, Order

SCHEMAS = [
    PlannerProviderResponse.model_json_schema,
    get_asklens_provider_response_json_schema,
    get_query_help_json_schema,
    get_query_plan_json_schema,
    QuestionIntent.model_json_schema,
]


def schema_objects(node, path="$"):
    """Walk schema keywords, not examples, enums or arbitrary data."""

    if node.get("type") == "object":
        yield path, node
    for keyword in ("$defs", "properties"):
        for name, child in node.get(keyword, {}).items():
            yield from schema_objects(child, f"{path}/{keyword}/{name}")
    for index, child in enumerate(node.get("anyOf", [])):
        yield from schema_objects(child, f"{path}/anyOf/{index}")
    if "items" in node:
        yield from schema_objects(node["items"], f"{path}/items")


def assert_strict_schema(schema):
    Draft202012Validator.check_schema(schema)
    for path, node in schema_objects(schema):
        assert node.get("additionalProperties") is False, path
        assert set(node.get("required", [])) == set(node.get("properties", {})), path
        for prop in node.get("properties", {}).values():
            assert "default" not in prop, path


def fill_wire_properties(value, node, root):
    """Synthetic provider: fill omitted properties with null, without normalization."""

    if "$ref" in node:
        return fill_wire_properties(
            value, root["$defs"][node["$ref"].split("/")[-1]], root
        )
    if value is None:
        return None
    if "anyOf" in node:
        for branch in node["anyOf"]:
            if branch.get("type") != "null":
                # The application envelopes use object-or-null; scalar unions
                # need no property filling.
                if "$ref" in branch or branch.get("type") in ("object", "array"):
                    return fill_wire_properties(value, branch, root)
    if isinstance(value, dict) and "properties" in node:
        return {
            **value,
            **{
                name: fill_wire_properties(value.get(name), child, root)
                for name, child in node["properties"].items()
            },
        }
    if isinstance(value, list) and "items" in node:
        return [fill_wire_properties(item, node["items"], root) for item in value]
    return value


class StrictTransport:
    """Assert the actual request schema and return one validated synthetic object."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def __call__(self, request, *, timeout):
        self.calls += 1
        body = json.loads(request.data)
        response_format = body["response_format"]["json_schema"]
        assert response_format["strict"] is True
        schema = response_format["schema"]
        assert_strict_schema(schema)
        self.wire = fill_wire_properties(self.payload, schema, schema)
        Draft202012Validator(schema).validate(self.wire)
        return FakeResponse(
            {"choices": [{"message": {"content": json.dumps(self.wire)}}]}
        )


def round_trip(payload, schema):
    transport = StrictTransport(payload)
    provider = OpenAICompatibleProvider(
        base_url="https://provider.invalid/v1",
        api_key="synthetic-offline-key",
        model="synthetic-model",
        urlopen_func=transport,
    )
    original_schema = deepcopy(schema)
    original_payload = deepcopy(payload)
    result = provider.complete_json(messages=(), schema=schema)
    assert transport.calls == 1
    assert schema == original_schema
    assert payload == original_payload
    return result


@pytest.mark.parametrize("schema_factory", SCHEMAS)
def test_reproduces_missing_required_but_not_open_objects(schema_factory):
    schema = schema_factory()
    objects = list(schema_objects(schema))
    assert any(
        set(node.get("required", [])) != set(node["properties"]) for _, node in objects
    )
    assert all(node.get("additionalProperties") is False for _, node in objects)
    wire = strict_wire_schema(schema)
    assert_strict_schema(wire)
    assert wire["type"] == "object" and "anyOf" not in wire
    # The actual emitted schemas use only this documented base-model subset;
    # this assertion is not a generic schema-compiler or live-acceptance claim.
    supported = {
        "$defs",
        "$ref",
        "title",
        "description",
        "type",
        "properties",
        "required",
        "additionalProperties",
        "anyOf",
        "enum",
        "items",
        "maxItems",
        "minimum",
        "maximum",
    }

    def check_keywords(node):
        assert set(node) <= supported
        for keyword in ("$defs", "properties"):
            for child in node.get(keyword, {}).values():
                check_keywords(child)
        for child in node.get("anyOf", []):
            check_keywords(child)
        if "items" in node:
            check_keywords(node["items"])

    check_keywords(wire)


def test_exact_planner_and_unified_mismatch_locations():
    def missing(schema):
        return {
            path: set(node["properties"]) - set(node.get("required", []))
            for path, node in schema_objects(schema)
            if set(node["properties"]) - set(node.get("required", []))
        }

    assert missing(PlannerProviderResponse.model_json_schema()) == {
        "$": {"presentation"},
        "$/$defs/QueryPlan": {
            "filters",
            "group_by",
            "metrics",
            "select",
            "order_by",
            "limit",
        },
        "$/$defs/GroupBySpec": {"date_trunc"},
        "$/$defs/OrderBySpec": {"field", "metric", "direction"},
        "$/$defs/PresentationSpec": {"kind", "x", "y"},
    }
    assert missing(get_asklens_provider_response_json_schema()) == {
        "$": {"query_plan", "presentation", "query_help"},
        "$/properties/query_plan": {
            "filters",
            "group_by",
            "metrics",
            "select",
            "order_by",
            "limit",
        },
        "$/properties/query_plan/properties/group_by/items": {"date_trunc"},
        "$/properties/query_plan/properties/order_by/items": {
            "field",
            "metric",
            "direction",
        },
        "$/properties/presentation": {"x", "y"},
        "$/properties/query_help": {"suggestions", "notes"},
        "$/properties/query_help/properties/suggestions/items": {
            "fields",
            "metrics",
            "date_fields",
            "why",
        },
    }


def test_unused_raw_unified_model_open_maps_fail_before_transport():
    schema = AskLensProviderResponse.model_json_schema()
    assert any(
        node.get("additionalProperties") is not False
        for _, node in schema_objects(schema)
    )
    transport = StrictTransport({})
    provider = OpenAICompatibleProvider(
        base_url="https://provider.invalid/v1",
        api_key="synthetic",
        model="synthetic",
        urlopen_func=transport,
    )
    with pytest.raises(LLMProviderError, match="closed objects"):
        provider.complete_json(messages=(), schema=schema)
    assert transport.calls == 0


@pytest.mark.parametrize("unified", [False, True])
@pytest.mark.parametrize("limit", [None, 1, 37, 100])
def test_list_omission_and_explicit_limits_preserve_fields_set(unified, limit):
    plan = {
        "resource": "orders",
        "intent": "list",
        "select": ["status"],
        "order_by": [{"field": "status"}],
    }
    if limit is not None:
        plan["limit"] = limit
    payload = {"query_plan": plan}
    schema = PlannerProviderResponse.model_json_schema()
    if unified:
        payload["response_type"] = "query"
        schema = get_asklens_provider_response_json_schema()
    result = round_trip(payload, schema)
    parsed = parse_query_plan(result["query_plan"])
    expected = parse_query_plan(plan)
    assert parsed == expected
    assert parsed.model_fields_set == expected.model_fields_set
    assert ("limit" in result["query_plan"]) is (limit is not None)
    assert "metrics" not in result["query_plan"]
    assert "group_by" not in result["query_plan"]
    assert parsed.order_by[0].direction == "asc"
    if unified:
        assert "query_help" not in result
        parse_asklens_provider_response(result)
    else:
        parse_planner_provider_response(result)


FILTER_VALUES = [
    "paid",
    "",
    "a",
    "A",
    0,
    1.25,
    -1,
    10,
    [False, 0, "paid"],
    False,
    ["2025-01-01", "2025-02-01"],
    3,
    2,
]


@pytest.mark.parametrize(
    "op,value", list(zip(SUPPORTED_FILTER_OPERATORS, FILTER_VALUES, strict=True))
)
@pytest.mark.parametrize("schema_factory", SCHEMAS[:2])
def test_all_filter_operators_retain_meaningful_values(schema_factory, op, value):
    plan = {
        "resource": "orders",
        "intent": "list",
        "select": ["status"],
        "filters": [{"field": "status", "op": op, "value": value}],
    }
    payload = {"query_plan": plan}
    schema = schema_factory()
    if schema["title"] == "AskLensProviderResponse":
        payload["response_type"] = "query"
    result = round_trip(payload, schema)
    assert result["query_plan"]["filters"] == plan["filters"]
    assert json.dumps(result["query_plan"]["filters"][0]["value"]) == json.dumps(value)
    assert parse_query_plan(result["query_plan"]) == parse_query_plan(plan)


@pytest.mark.parametrize("date_trunc", [None, *SUPPORTED_DATE_TRUNCS])
@pytest.mark.parametrize("kind", ["table", "metric", "bar", "line", "pie"])
@pytest.mark.parametrize("unified", [False, True])
def test_aggregate_grouping_ordering_and_presentation(date_trunc, kind, unified):
    group = {"field": "created_at"}
    if date_trunc:
        group["date_trunc"] = date_trunc
    presentation = {"kind": kind}
    if kind != "table":
        presentation["y"] = "order_count"
    if kind not in {"table", "metric"}:
        presentation["x"] = "created_at"
    payload = {
        "response_type": "query",
        "query_plan": {
            "resource": "orders",
            "intent": "aggregate",
            "group_by": [group],
            "metrics": [{"metric": "order_count"}],
            "filters": [],
            "order_by": [
                {"field": "created_at", "direction": "asc"},
                {"metric": "order_count", "direction": "desc"},
            ],
        },
        "presentation": presentation,
    }
    if unified:
        result = round_trip(payload, get_asklens_provider_response_json_schema())
        assert result == payload
        assert parse_asklens_provider_response(
            result
        ) == parse_asklens_provider_response(payload)
    else:
        payload.pop("response_type")
        result = round_trip(payload, PlannerProviderResponse.model_json_schema())
        assert parse_planner_provider_response(
            result
        ) == parse_planner_provider_response(payload)
    assert "select" not in result["query_plan"]


@pytest.mark.parametrize("standalone", [False, True])
def test_help_references_notes_and_empty_values_are_preserved(standalone):
    help_payload = {
        "answer": "Available questions",
        "notes": ["Synthetic guidance"],
        "suggestions": [
            {
                "question": "Orders by status",
                "resource_name": "orders",
                "fields": ["status"],
                "metrics": ["order_count"],
                "date_fields": ["created_at"],
                "why": "",
            },
            {
                "question": "List orders",
                "resource_name": "orders",
                "fields": [],
                "metrics": [],
                "date_fields": [],
            },
        ],
    }
    payload = (
        help_payload
        if standalone
        else {"response_type": "capabilities", "query_help": help_payload}
    )
    schema = (
        get_query_help_json_schema()
        if standalone
        else get_asklens_provider_response_json_schema()
    )
    result = round_trip(payload, schema)
    assert result == payload
    if standalone:
        assert QueryHelp.model_validate(result) == QueryHelp.model_validate(payload)
    else:
        assert parse_asklens_provider_response(
            result
        ) == parse_asklens_provider_response(payload)


def test_original_nullable_values_are_not_omission_sentinels():
    payload = {
        "query_plan": {
            "resource": "orders",
            "intent": "list",
            "select": ["status"],
            "group_by": [],
            "order_by": [{"field": "status", "metric": None}],
        },
        "presentation": None,
    }
    result = round_trip(payload, PlannerProviderResponse.model_json_schema())
    assert result == payload
    assert "presentation" in result
    assert result["query_plan"]["group_by"] == []


@pytest.mark.parametrize("value", [False, 0, "", [], [False, 0, ""]])
def test_non_null_values_are_never_treated_as_omission(value):
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "value": {
                "type": ["boolean", "integer", "string", "array"],
                "items": {"type": ["boolean", "integer", "string"]},
            }
        },
    }
    result = round_trip({"value": value}, schema)
    assert result == {"value": value}
    assert json.dumps(result["value"]) == json.dumps(value)


@pytest.mark.parametrize(
    "plan",
    [
        {"resource": "orders", "intent": "list", "select": ["status"], "limit": False},
        {"resource": "orders", "intent": "list", "select": ["status"], "limit": 0},
        {
            "resource": "orders",
            "intent": "list",
            "select": ["status"],
            "filters": [{"field": "status", "op": "eq", "value": None}],
        },
        {
            "resource": "orders",
            "intent": "list",
            "select": ["status"],
            "unknown": "retain-and-reject",
        },
    ],
)
def test_normalization_does_not_hide_invalid_application_values(plan):
    normalized = normalize_wire_response(plan, get_query_plan_json_schema())
    assert normalized == plan
    with pytest.raises(PlanParseError):
        parse_query_plan(normalized)


def test_inactive_meaningful_branch_is_retained_and_rejected():
    payload = {
        "response_type": "query",
        "query_plan": {"resource": "orders", "intent": "list", "select": ["status"]},
        "query_help": {"answer": "Not inactive"},
    }
    result = round_trip(payload, get_asklens_provider_response_json_schema())
    assert result == payload
    with pytest.raises(PlanValidationError):
        parse_asklens_provider_response(result)


def test_required_null_is_not_removed():
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["query_plan"],
        "properties": {
            "query_plan": {
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            }
        },
    }
    assert normalize_wire_response({"query_plan": None}, schema) == {"query_plan": None}


@pytest.mark.django_db
@pytest.mark.postgresql
@pytest.mark.parametrize("unified", [False, True])
def test_wire_omission_respects_current_limits_permissions_and_scope(
    settings, django_assert_num_queries, unified
):
    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "disabled",
        "DEFAULT_LIMIT": 7,
        "MAX_ROWS": 10,
    }
    plan = {
        "resource": "orders",
        "intent": "aggregate",
        "group_by": [{"field": "status"}],
        "metrics": [{"metric": "order_count"}],
    }
    payload = {"query_plan": plan}
    schema = PlannerProviderResponse.model_json_schema()
    if unified:
        payload["response_type"] = "query"
        schema = get_asklens_provider_response_json_schema()
    result = round_trip(payload, schema)
    registry = build_registry()
    customer = Customer.objects.create(
        name="Synthetic", email="synthetic@example.invalid"
    )
    for status in ("paid", "pending"):
        Order.objects.create(
            customer=customer,
            status=status,
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            total="1.00",
        )
    with django_assert_num_queries(0), pytest.raises(PublicAskLensError) as denied:
        execute_plan(result["query_plan"], request=request_with(), registry=registry)
    assert denied.value.code == "asklens.member.unavailable"
    with django_assert_num_queries(1):
        executed = execute_plan(
            result["query_plan"],
            request=request_with("shop.view_orders"),
            registry=registry,
        )
    assert executed.rows == ({"status": "paid", "order_count": 1},)
    assert executed.limit == 7
    # A meaningful explicit limit must not be discarded to obtain the default.
    payload["query_plan"]["limit"] = 100
    explicit = round_trip(payload, schema)
    with django_assert_num_queries(0), pytest.raises(PublicAskLensError) as budget:
        execute_plan(
            explicit["query_plan"],
            request=request_with("shop.view_orders"),
            registry=registry,
        )
    assert budget.value.code == "asklens.budget.exceeded"


@pytest.mark.parametrize(
    "nullable", [{"type": ["string", "null"]}, {"enum": [None, "x"]}, {"const": None}]
)
def test_original_nullable_null_remains_a_value(nullable):
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"value": nullable},
    }
    assert round_trip({"value": None}, schema) == {"value": None}


@pytest.mark.parametrize("ref", ["https://schema.invalid/private", "#/$defs/missing"])
def test_invalid_optional_references_fail_safely_before_transport(ref):
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"value": {"$ref": ref}},
    }
    with pytest.raises(LLMProviderError) as error:
        strict_wire_schema(schema)
    assert ref not in str(error.value)


def test_ambiguous_object_union_never_chooses_a_lossy_normalization():
    optional = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"value": {"type": "string"}},
    }
    required = {**optional, "required": ["value"]}
    schema = {"anyOf": [optional, required]}
    with pytest.raises(LLMProviderError, match="ambiguous normalization"):
        normalize_wire_response({"value": None}, schema)


def test_intent_zero_confidence_and_empty_sections_remain_explicit():
    payload = {"intent": "query", "confidence": 0, "resource_names": [], "sections": []}
    result = round_trip(payload, QuestionIntent.model_json_schema())
    assert result == payload
    assert QuestionIntent.model_validate(result) == QuestionIntent.model_validate(
        payload
    )


def test_planner_presentation_default_is_applied_only_by_application_parser():
    payload = {
        "query_plan": {"resource": "orders", "intent": "list", "select": ["status"]},
        "presentation": {},
    }
    result = round_trip(payload, PlannerProviderResponse.model_json_schema())
    assert "kind" not in result["presentation"]
    assert parse_planner_provider_response(result).presentation.kind == "table"


def test_null_limit_remains_invalid_outside_openai_wire_boundary():
    plan = {"resource": "orders", "intent": "list", "select": ["status"], "limit": None}
    dummy = DummyProvider(default_plan={"query_plan": plan})
    result = dummy.complete_json(
        messages=({"role": "user", "content": "Synthetic"},),
        schema=PlannerProviderResponse.model_json_schema(),
    )
    assert result["query_plan"]["limit"] is None
    with pytest.raises(PlanParseError):
        parse_query_plan(result["query_plan"])
