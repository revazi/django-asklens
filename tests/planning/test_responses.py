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
        model=Order,
        name="orders",
        label="Orders",
        default_date_field="created_at",
        fields={
            "status": {"label": "Status"},
            "created_at": {"label": "Created date"},
        },
        metrics=[Metric("order_count", op="count", field="status")],
    )
    return registry


def capabilities_payload() -> dict[str, Any]:
    """Return visible capabilities for unified response tests."""

    return {
        "summary": "You can query Orders.",
        "query_patterns": [],
        "limitations": [],
        "examples": ["Show count of Orders by Status"],
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
                        "name": "order_count",
                        "label": "Order count",
                        "op": "count",
                        "field": "status",
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
                "examples": ["Show count of Orders by Status"],
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
        "metrics": [{"name": "order_count", "op": "count", "field": "status"}],
        "select": [],
        "order_by": [{"metric": "order_count", "direction": "desc"}],
        "limit": 10,
        "visualization": {"type": "bar", "x": "status", "y": "order_count"},
    }


def test_provider_response_schema_hides_local_suggestion_plans() -> None:
    """The provider should not be asked to emit clicked-suggestion plans."""

    schema = get_asklens_provider_response_json_schema()

    assert schema["title"] == "AskLensProviderResponse"
    assert "$defs" not in schema
    assert "query_plan" in schema["properties"]
    assert schema["properties"]["query_plan"]["required"] == ["resource", "intent"]
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


def test_plan_asklens_response_validates_query_branch() -> None:
    """Query responses produce a normal validated QueryPlan."""

    provider = UnifiedProvider(
        {"response_type": "query", "query_plan": valid_query_plan_payload()}
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
    assert provider.schema is not None
    assert provider.schema["title"] == "AskLensProviderResponse"
    assert provider.messages is not None
    prompt_text = "\n".join(message["content"] for message in provider.messages)
    assert "Visible capabilities metadata" in prompt_text
    assert "Catalog metadata" not in prompt_text


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
