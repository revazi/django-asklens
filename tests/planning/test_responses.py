"""Tests for unified provider query/help responses."""

from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from django_asklens import Metric
from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.exceptions import PlanValidationError
from django_asklens.llms import LLMMessage
from django_asklens.planning.responses import (
    get_asklens_provider_response_json_schema,
    parse_asklens_provider_response,
    plan_asklens_response,
)
from tests.test_project.models import Order

QUESTION = "Show orders by status"


class UnifiedProvider:
    """Provider double for unified response tests."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = payload
        self.messages: Sequence[LLMMessage] | None = None
        self.schema: Mapping[str, Any] | None = None

    def complete_json(
        self,
        *,
        messages: Sequence[LLMMessage],
        schema: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        self.messages = messages
        self.schema = schema
        return self.payload


def build_registry() -> CatalogRegistry:
    """Return a registry with one order resource."""

    registry = CatalogRegistry()
    registry.register(
        timezone="UTC",
        model=Order,
        name="orders",
        label="Orders",
        default_date_field="created_at",
        scope_mode="global",
        fields={
            "status": {
                "binding": "status",
                "type": "enum",
                "nullable": False,
                "label": "Status",
                "enum": {
                    "type": "string",
                    "values": [
                        {"value": "paid", "label": "Paid", "aliases": ["settled"]},
                        {"value": "pending", "label": "Pending"},
                    ],
                },
            },
            "created_at": {
                "binding": "created_at",
                "type": "datetime",
                "nullable": False,
                "label": "Created date",
            },
        },
        metrics=[
            Metric("order_count", op="count", binding="status", result_type="integer")
        ],
    )
    return registry


def capabilities_payload() -> dict[str, Any]:
    """Return visible query guidance for unified response tests."""

    return {
        "summary": "You can query Orders.",
        "query_patterns": [],
        "limitations": [],
        "examples": ["Show Order count by Status"],
        "resources": [
            {
                "name": "orders",
                "label": "Orders",
                "description": "Orders.",
                "synonyms": [],
                "default_date_field": "created_at",
                "fields": [
                    {
                        "name": "status",
                        "label": "Status",
                        "type": "enum",
                        "nullable": False,
                        "relation_depth": 0,
                        "operators": ["eq", "neq", "in", "isnull"],
                        "enum": {
                            "type": "string",
                            "values": [
                                {
                                    "value": "paid",
                                    "label": "Paid",
                                    "aliases": ["settled"],
                                },
                                {"value": "pending", "label": "Pending"},
                            ],
                        },
                        "can_filter": True,
                        "can_select": True,
                        "can_group": True,
                        "can_order": True,
                        "can_date_bucket": False,
                    },
                    {
                        "name": "created_at",
                        "label": "Created date",
                        "type": "datetime",
                        "relation_depth": 0,
                        "can_filter": True,
                        "can_select": True,
                        "can_group": True,
                        "can_order": True,
                        "can_date_bucket": True,
                    },
                ],
                "metrics": [
                    {
                        "name": "order_count",
                        "label": "Order count",
                        "result_type": "integer",
                    }
                ],
                "date_fields": [
                    {
                        "name": "created_at",
                        "label": "Created date",
                        "type": "datetime",
                        "relation_depth": 0,
                        "can_filter": True,
                        "can_select": True,
                        "can_group": True,
                        "can_order": True,
                        "can_date_bucket": True,
                    }
                ],
                "examples": ["Show Order count by Status"],
                "guidance": [],
                "scope": {"level": "unknown", "guidance": "Use visible rows."},
            }
        ],
    }


def valid_query_plan_payload() -> dict[str, Any]:
    """Return one valid query plan payload."""

    return {
        "resource": "orders",
        "intent": "aggregate",
        "filters": [],
        "group_by": [{"field": "status"}],
        "metrics": [{"metric": "order_count"}],
        "select": [],
        "order_by": [{"metric": "order_count", "direction": "desc"}],
        "limit": 10,
    }


def test_provider_response_schema_hides_local_suggestion_plans() -> None:
    """The provider should not be asked to emit clicked-suggestion plans."""

    schema = get_asklens_provider_response_json_schema()

    assert schema["title"] == "AskLensProviderResponse"
    assert "$defs" not in schema
    assert "query_plan" in schema["properties"]
    assert "presentation" in schema["properties"]
    query_plan_schema = schema["properties"]["query_plan"]
    assert "visualization" not in query_plan_schema["properties"]
    assert query_plan_schema["required"] == ["resource", "intent"]
    metric_schema = query_plan_schema["properties"]["metrics"]["items"]
    assert metric_schema["required"] == ["metric"]
    assert metric_schema["properties"] == {"metric": {"type": "string"}}
    filter_item_schema = query_plan_schema["properties"]["filters"]["items"]
    assert filter_item_schema["required"] == ["field", "op", "value"]
    filter_value_schema = filter_item_schema["properties"]["value"]
    assert "null" not in filter_value_schema["type"]
    assert "null" not in filter_value_schema["items"]["type"]
    suggestion_schema = schema["properties"]["query_help"]["properties"]["suggestions"][
        "items"
    ]
    assert "plan" not in suggestion_schema["properties"]
    assert "QueryPlan" not in str(schema)


def test_parse_provider_response_requires_matching_branch() -> None:
    """Unified provider output must match the selected response branch."""

    with pytest.raises(PlanValidationError, match="query_plan"):
        parse_asklens_provider_response({"response_type": "query"})

    with pytest.raises(PlanValidationError, match="query_help"):
        parse_asklens_provider_response({"response_type": "capabilities"})

    with pytest.raises(PlanValidationError, match="must not include presentation"):
        parse_asklens_provider_response(
            {
                "response_type": "capabilities",
                "query_help": {"answer": "Help"},
                "presentation": {"kind": "table"},
            }
        )


def test_plan_asklens_response_validates_query_branch() -> None:
    """Query responses keep presentation outside the validated QueryPlan."""

    provider = UnifiedProvider(
        {
            "response_type": "query",
            "query_plan": valid_query_plan_payload(),
            "presentation": {
                "kind": "bar",
                "x": "status",
                "y": "order_count",
            },
        }
    )

    result = plan_asklens_response(
        QUESTION,
        provider=provider,
        registry=build_registry(),
        capabilities=capabilities_payload(),
    )

    assert result.response_type == "query"
    assert result.query_plan is not None
    assert result.query_plan.resource == "orders"
    assert result.presentation is not None
    assert result.presentation.kind == "bar"
    assert provider.schema is not None
    assert provider.schema["title"] == "AskLensProviderResponse"
    assert provider.messages is not None
    prompt_text = "\n".join(message["content"] for message in provider.messages)
    assert "Visible query guidance metadata" in prompt_text
    assert "Aggregate plans must put dimensions in" in prompt_text
    assert "must not include select" in prompt_text
    assert "operators listed for each field" in prompt_text
    assert "enum canonical values or aliases" in prompt_text
    assert '"operators": [' in prompt_text
    assert '"settled"' in prompt_text
    assert "Catalog metadata" not in prompt_text


def test_plan_asklens_response_drops_duplicate_aggregate_select() -> None:
    """Live compact provider plans may repeat group_by fields in select."""

    plan_payload = valid_query_plan_payload()
    plan_payload["select"] = ["status"]
    provider = UnifiedProvider({"response_type": "query", "query_plan": plan_payload})

    result = plan_asklens_response(
        "Show order count by status",
        provider=provider,
        registry=build_registry(),
        capabilities=capabilities_payload(),
    )

    assert result.query_plan is not None
    assert result.query_plan.intent == "aggregate"
    assert result.query_plan.select == ()
    assert result.query_plan.group_by[0].field == "status"


def test_plan_asklens_response_rejects_non_duplicate_aggregate_select() -> None:
    """Aggregate select remains invalid when it is not just group_by noise."""

    plan_payload = valid_query_plan_payload()
    plan_payload["select"] = ["created_at"]
    provider = UnifiedProvider({"response_type": "query", "query_plan": plan_payload})

    with pytest.raises(PlanValidationError, match="must not include select"):
        plan_asklens_response(
            "Show order count by status",
            provider=provider,
            registry=build_registry(),
            capabilities=capabilities_payload(),
        )


def test_plan_asklens_response_synthesizes_help_suggestion_plans() -> None:
    """Capabilities responses get locally validated clicked-suggestion plans."""

    provider = UnifiedProvider(
        {
            "response_type": "capabilities",
            "query_help": {
                "answer": "Try these examples.",
                "suggestions": [
                    {
                        "question": "Show order count by status",
                        "resource_name": "orders",
                        "fields": ["status"],
                        "metrics": ["order_count"],
                    }
                ],
            },
        }
    )

    result = plan_asklens_response(
        "show me example queries",
        provider=provider,
        registry=build_registry(),
        capabilities=capabilities_payload(),
    )

    assert result.response_type == "capabilities"
    assert result.query_help is not None
    [suggestion] = result.query_help.suggestions
    assert suggestion.plan is not None
    assert suggestion.plan["resource"] == "orders"
    assert suggestion.plan["intent"] == "aggregate"


def multi_resource_capabilities_payload() -> dict[str, Any]:
    """Return capabilities with more than one visible resource."""

    capabilities = capabilities_payload()
    capabilities["summary"] = "You can query Orders and Payment attempts."
    capabilities["resources"] = [
        *capabilities["resources"],
        {
            "name": "payment_attempts",
            "label": "Payment attempts",
            "description": "Payment collection attempts.",
            "synonyms": ["payments"],
            "default_date_field": "created_at",
            "fields": [
                {
                    "name": "status",
                    "label": "Status",
                    "type": "string",
                    "relation_depth": 0,
                    "can_filter": True,
                    "can_select": True,
                    "can_group": True,
                    "can_order": True,
                    "can_date_bucket": False,
                },
                {
                    "name": "created_at",
                    "label": "Created date",
                    "type": "datetime",
                    "relation_depth": 0,
                    "can_filter": True,
                    "can_select": True,
                    "can_group": True,
                    "can_order": True,
                    "can_date_bucket": True,
                },
            ],
            "metrics": [
                {
                    "name": "payment_amount",
                    "label": "Payment amount",
                    "result_type": "decimal",
                }
            ],
            "date_fields": [
                {
                    "name": "created_at",
                    "label": "Created date",
                    "type": "datetime",
                    "relation_depth": 0,
                    "can_filter": True,
                    "can_select": True,
                    "can_group": True,
                    "can_order": True,
                    "can_date_bucket": True,
                }
            ],
            "examples": ["Show payment amount by Status"],
            "guidance": [],
            "scope": {"level": "unknown", "guidance": "Use visible rows."},
        },
    ]
    capabilities["examples"] = [
        "Show Order count by Status",
        "Show payment amount by Status",
    ]
    return capabilities


def test_plan_asklens_response_default_prompt_keeps_all_resources() -> None:
    """Alpha default should not rely on heuristic resource shortlisting."""

    provider = UnifiedProvider(
        {"response_type": "query", "query_plan": valid_query_plan_payload()}
    )

    plan_asklens_response(
        "Show orders by status",
        provider=provider,
        registry=build_registry(),
        capabilities=multi_resource_capabilities_payload(),
    )

    assert provider.messages is not None
    prompt_text = "\n".join(message["content"] for message in provider.messages)
    assert '"name": "orders"' in prompt_text
    assert "payment_attempts" in prompt_text
    assert '"date_fields"' not in prompt_text
    assert '"examples"' not in prompt_text


def test_plan_asklens_response_shortlists_data_question_prompt(settings) -> None:
    """Likely data questions should send only likely visible resources."""

    settings.DJANGO_ASKLENS = {"PROMPT_RESOURCE_SHORTLIST_LIMIT": 1}
    provider = UnifiedProvider(
        {"response_type": "query", "query_plan": valid_query_plan_payload()}
    )

    plan_asklens_response(
        "Show orders by status",
        provider=provider,
        registry=build_registry(),
        capabilities=multi_resource_capabilities_payload(),
    )

    assert provider.messages is not None
    prompt_text = "\n".join(message["content"] for message in provider.messages)
    assert '"name": "orders"' in prompt_text
    assert "payment_attempts" not in prompt_text
    assert '"date_fields"' not in prompt_text
    assert '"examples"' not in prompt_text


def test_plan_asklens_response_keeps_full_prompt_for_explicit_help(settings) -> None:
    """Explicit help questions should keep full visible query guidance metadata."""

    settings.DJANGO_ASKLENS = {"PROMPT_RESOURCE_SHORTLIST_LIMIT": 1}
    provider = UnifiedProvider(
        {
            "response_type": "capabilities",
            "query_help": {
                "answer": "Try these examples.",
                "suggestions": [
                    {
                        "question": "Show order count by status",
                        "resource_name": "orders",
                        "fields": ["status"],
                        "metrics": ["order_count"],
                    }
                ],
            },
        }
    )

    plan_asklens_response(
        "show me example queries",
        provider=provider,
        registry=build_registry(),
        capabilities=multi_resource_capabilities_payload(),
    )

    assert provider.messages is not None
    prompt_text = "\n".join(message["content"] for message in provider.messages)
    assert '"name": "orders"' in prompt_text
    assert "payment_attempts" in prompt_text
    assert '"date_fields"' in prompt_text
    assert '"examples"' in prompt_text


def test_plan_asklens_response_filters_invalid_help_suggestions() -> None:
    """Provider help suggestions still fail closed against capabilities."""

    provider = UnifiedProvider(
        {
            "response_type": "capabilities",
            "query_help": {
                "answer": "Try this.",
                "suggestions": [
                    {
                        "question": "Show private orders",
                        "resource_name": "orders",
                        "fields": ["private_notes"],
                    }
                ],
            },
        }
    )

    with pytest.raises(PlanValidationError, match="private_notes"):
        plan_asklens_response(
            "show me example queries",
            provider=provider,
            registry=build_registry(),
            capabilities=capabilities_payload(),
        )
