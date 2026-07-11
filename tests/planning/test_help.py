"""Tests for provider-backed query-help generation."""

from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from django_asklens import Metric
from django_asklens.catalog.registry import default_registry
from django_asklens.exceptions import PlanValidationError
from django_asklens.llms import LLMMessage
from django_asklens.planning.help import (
    MAX_HELP_SUGGESTIONS,
    build_deterministic_query_help,
    build_query_help,
    parse_query_help,
    requested_suggestion_count,
)
from tests.test_project.models import Order


@pytest.fixture(autouse=True)
def registered_orders() -> None:
    """Register the Order resource for executable help-plan validation."""

    default_registry.clear()
    default_registry.register(
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
    yield
    default_registry.clear()


class HelpProvider:
    """Provider double for query-help tests."""

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


def capabilities_payload() -> dict[str, Any]:
    """Return visible capabilities with one resource for query-help tests."""

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
            }
        ],
    }


def aggregate_help_plan_payload(**updates: Any) -> dict[str, Any]:
    """Return a valid aggregate plan for provider QueryHelp suggestions."""

    payload: dict[str, Any] = {
        "resource": "orders",
        "intent": "aggregate",
        "filters": [],
        "group_by": [{"field": "status"}],
        "metrics": [{"name": "order_count", "op": "count", "field": "status"}],
        "select": [],
        "order_by": [{"metric": "order_count", "direction": "desc"}],
        "limit": 50,
        "visualization": {"type": "bar", "x": "status", "y": "order_count"},
    }
    payload.update(updates)
    return payload


def trend_help_plan_payload() -> dict[str, Any]:
    """Return a valid date-trend plan for provider QueryHelp suggestions."""

    return aggregate_help_plan_payload(
        group_by=[{"field": "created_at", "date_trunc": "month"}],
        order_by=[{"field": "created_at", "direction": "asc"}],
        visualization={"type": "line", "x": "created_at", "y": "order_count"},
    )


def many_examples_capabilities_payload() -> dict[str, Any]:
    """Return capabilities with enough examples for count-limit tests."""

    payload = capabilities_payload()
    resources = []
    for index in range(1, 6):
        resource = dict(payload["resources"][0])
        resource["name"] = f"orders_{index}"
        resource["label"] = f"Orders {index}"
        resource["examples"] = [
            f"Show count of Orders {index} by Status",
            f"Trend Orders {index} by month using Created date",
        ]
        resources.append(resource)
    payload["resources"] = resources
    payload["examples"] = [
        example for resource in resources for example in resource["examples"]
    ]
    return payload


def test_requested_suggestion_count_parses_and_clamps_examples() -> None:
    """Help questions can request up to the supported example count."""

    assert requested_suggestion_count("What can I query?") == 5
    assert requested_suggestion_count("Give me 10 examples") == 10
    assert requested_suggestion_count("Can you suggest 7 query questions?") == 7
    assert requested_suggestion_count("Give me 99 examples") == MAX_HELP_SUGGESTIONS


def test_build_query_help_uses_provider_and_validates_references() -> None:
    """Provider-backed help returns validated suggestions from visible metadata."""

    provider = HelpProvider(
        {
            "answer": "You can ask order count and trend questions.",
            "suggestions": [
                {
                    "question": "Show order count by status",
                    "resource_name": "orders",
                    "fields": ["status"],
                    "metrics": ["order_count"],
                    "date_fields": [],
                    "plan": aggregate_help_plan_payload(),
                    "why": "Groups the registered order count metric by status.",
                },
                {
                    "question": "Trend order count by month using created date",
                    "resource_name": "orders",
                    "fields": [],
                    "metrics": ["order_count"],
                    "date_fields": ["created_at"],
                    "plan": trend_help_plan_payload(),
                },
            ],
            "notes": ["Only visible fields are used."],
        }
    )

    result = build_query_help(
        "Help me write order questions",
        provider=provider,
        capabilities=capabilities_payload(),
    )

    assert result.answer == "You can ask order count and trend questions."
    assert result.suggestions[0].resource_name == "orders"
    assert result.suggestions[0].fields == ("status",)
    assert result.suggestions[1].date_fields == ("created_at",)
    assert result.suggestions[0].plan is not None
    assert result.suggestions[1].plan is not None
    assert provider.schema is not None
    assert provider.schema["title"] == "QueryHelp"
    assert provider.messages is not None
    prompt_text = "\n".join(message["content"] for message in provider.messages)
    assert "Visible capabilities metadata" in prompt_text
    assert "Each suggestion.plan must match" not in prompt_text
    assert "orders" in prompt_text
    assert "facilities/accounts/tenants" not in prompt_text
    suggestion_schema = provider.schema["$defs"]["QueryHelpSuggestion"]
    assert "plan" not in suggestion_schema["properties"]


def test_build_query_help_allows_ten_provider_examples_when_requested() -> None:
    """Provider-backed help can return ten validated example questions."""

    suggestions = [
        {
            "question": f"Show order count by status example {index}",
            "resource_name": "orders",
            "fields": ["status"],
            "metrics": ["order_count"],
            "plan": aggregate_help_plan_payload(),
        }
        for index in range(1, 11)
    ]
    provider = HelpProvider(
        {
            "answer": "Here are ten examples.",
            "suggestions": suggestions,
        }
    )

    result = build_query_help(
        "Give me 10 examples of what I can query",
        provider=provider,
        capabilities=capabilities_payload(),
    )

    assert len(result.suggestions) == 10
    assert provider.schema is not None
    assert provider.schema["properties"]["suggestions"]["maxItems"] == 10
    assert provider.messages is not None
    prompt_text = "\n".join(message["content"] for message in provider.messages)
    assert "Return up to 10 usable example questions" in prompt_text


def test_build_query_help_limits_provider_examples_to_default_count() -> None:
    """Provider help is capped to the requested/default suggestion count."""

    provider = HelpProvider(
        {
            "answer": "Here are many examples.",
            "suggestions": [
                {
                    "question": f"Show order count by status example {index}",
                    "resource_name": "orders",
                    "fields": ["status"],
                    "metrics": ["order_count"],
                    "plan": aggregate_help_plan_payload(),
                }
                for index in range(1, 11)
            ],
        }
    )

    result = build_query_help(
        "What can I query?",
        provider=provider,
        capabilities=capabilities_payload(),
    )

    assert len(result.suggestions) == 5


def test_build_query_help_canonicalizes_provider_labels() -> None:
    """Provider references may use visible labels and still validate."""

    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "Show order count by status",
                    "resource_name": "orders",
                    "fields": ["Status"],
                    "metrics": ["Order count"],
                    "date_fields": ["Created date"],
                    "plan": aggregate_help_plan_payload(),
                }
            ],
        }
    )

    result = build_query_help(
        "What can I query?",
        provider=provider,
        capabilities=capabilities_payload(),
    )

    [suggestion] = result.suggestions
    assert suggestion.fields == ("status",)
    assert suggestion.metrics == ("order_count",)
    assert suggestion.date_fields == ("created_at",)


def test_build_query_help_keeps_valid_provider_suggestions() -> None:
    """One bad provider suggestion should not discard other valid suggestions."""

    provider = HelpProvider(
        {
            "answer": "Try these.",
            "suggestions": [
                {
                    "question": "Show order count by status",
                    "resource_name": "orders",
                    "fields": ["status"],
                    "metrics": ["order_count"],
                    "plan": aggregate_help_plan_payload(),
                },
                {
                    "question": "List orders with private notes",
                    "resource_name": "orders",
                    "fields": ["private_notes"],
                },
            ],
        }
    )

    result = build_query_help(
        "What can I query?",
        provider=provider,
        capabilities=capabilities_payload(),
    )

    assert [suggestion.question for suggestion in result.suggestions] == [
        "Show order count by status"
    ]


def test_build_query_help_synthesizes_missing_executable_plan() -> None:
    """Provider suggestions get locally validated plans without extra LLM calls."""

    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "Show order count by status",
                    "resource_name": "orders",
                    "fields": ["status"],
                    "metrics": ["order_count"],
                }
            ],
        }
    )

    result = build_query_help(
        "Help me write order questions",
        provider=provider,
        capabilities=capabilities_payload(),
    )

    [suggestion] = result.suggestions
    assert suggestion.plan is not None
    assert suggestion.plan["resource"] == "orders"
    assert suggestion.plan["intent"] == "aggregate"
    assert suggestion.plan["group_by"] == [{"field": "status", "date_trunc": None}]
    assert suggestion.plan["metrics"][0]["name"] == "order_count"


def test_build_query_help_rejects_unknown_references() -> None:
    """Provider suggestions cannot mention fields outside capabilities."""

    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "List orders with private notes",
                    "resource_name": "orders",
                    "fields": ["private_notes"],
                }
            ],
        }
    )

    with pytest.raises(PlanValidationError, match="private_notes"):
        build_query_help(
            "Help me write order questions",
            provider=provider,
            capabilities=capabilities_payload(),
        )


def test_build_query_help_rejects_quoted_sample_value_suggestions() -> None:
    """Provider suggestions must not invent row/sample values."""

    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "Show order count for 'Premium Plan Product'",
                    "resource_name": "orders",
                    "fields": ["status"],
                    "metrics": ["order_count"],
                    "plan": aggregate_help_plan_payload(),
                }
            ],
        }
    )

    with pytest.raises(PlanValidationError, match="sample values"):
        build_query_help(
            "Help me write order questions",
            provider=provider,
            capabilities=capabilities_payload(),
        )


def test_build_query_help_rejects_sql_or_mutation_suggestions() -> None:
    """Query help must remain read-only and natural-language only."""

    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "Delete orders by status",
                    "resource_name": "orders",
                    "fields": ["status"],
                }
            ],
        }
    )

    with pytest.raises(PlanValidationError, match="read-only"):
        build_query_help(
            "Help me write order questions",
            provider=provider,
            capabilities=capabilities_payload(),
        )


def test_build_query_help_rejects_single_scope_resource_suggestions() -> None:
    """Live help should not suggest plural scoped-entity questions."""

    payload = capabilities_payload()
    payload["resources"] = [
        {
            "name": "facilities",
            "label": "Facilities",
            "description": "Visible facilities.",
            "synonyms": [],
            "default_date_field": None,
            "scope": {
                "level": "single",
                "kind": "facility",
                "guidance": "Visible rows are scoped to one facility.",
            },
            "fields": [
                {
                    "name": "name",
                    "label": "Facility name",
                    "type": "string",
                    "relation_depth": 0,
                    "can_filter": True,
                    "can_select": True,
                    "can_group": True,
                    "can_order": True,
                    "can_date_bucket": False,
                }
            ],
            "metrics": [],
            "date_fields": [],
            "examples": [],
            "guidance": [],
        }
    ]
    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "List Facilities with Facility name",
                    "resource_name": "facilities",
                    "fields": ["name"],
                }
            ],
        }
    )

    with pytest.raises(PlanValidationError, match="single visible facility"):
        build_query_help(
            "Help me write facility questions",
            provider=provider,
            capabilities=payload,
        )


def test_build_query_help_rejects_arbitrarily_named_scope_resource() -> None:
    """Scope-resource validation should not depend on resource naming."""

    payload = capabilities_payload()
    payload["resources"] = [
        {
            "name": "locations",
            "label": "Studios",
            "description": "Visible studios.",
            "synonyms": [],
            "default_date_field": None,
            "scope": {
                "level": "single",
                "kind": "gym",
                "guidance": "Visible rows are scoped to one gym.",
            },
            "scope_resource": True,
            "fields": [
                {
                    "name": "display_name",
                    "label": "Display name",
                    "type": "string",
                    "relation_depth": 0,
                    "can_filter": True,
                    "can_select": True,
                    "can_group": True,
                    "can_order": True,
                    "can_date_bucket": False,
                }
            ],
            "metrics": [],
            "date_fields": [],
            "examples": [],
            "guidance": [],
        }
    ]
    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "List Studios with Display name",
                    "resource_name": "locations",
                    "fields": ["display_name"],
                }
            ],
        }
    )

    with pytest.raises(PlanValidationError, match="single visible gym"):
        build_query_help(
            "Help me write studio questions",
            provider=provider,
            capabilities=payload,
        )


def test_build_query_help_rejects_single_scope_comparison_wording() -> None:
    """Help suggestions must not imply multi-scope access for single scopes."""

    payload = capabilities_payload()
    resource = payload["resources"][0]
    resource["scope"] = {
        "level": "single",
        "kind": "facility",
        "guidance": "Visible rows are scoped to one facility.",
    }
    resource["fields"].append(
        {
            "name": "facility.name",
            "label": "Facility",
            "type": "string",
            "relation_depth": 1,
            "can_filter": True,
            "can_select": True,
            "can_group": True,
            "can_order": True,
            "can_date_bucket": False,
        }
    )
    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "Compare order count across facilities",
                    "resource_name": "orders",
                    "fields": [],
                    "metrics": ["order_count"],
                }
            ],
        }
    )

    with pytest.raises(PlanValidationError, match="single visible facility"):
        build_query_help(
            "Help me write order questions",
            provider=provider,
            capabilities=payload,
        )


def test_build_query_help_rejects_explicit_scope_dimension_fields() -> None:
    """Scope fields do not need facility/account/tenant naming to be blocked."""

    payload = capabilities_payload()
    resource = payload["resources"][0]
    resource["scope"] = {
        "level": "single",
        "kind": "gym",
        "guidance": "Visible rows are scoped to one gym.",
    }
    resource["fields"].append(
        {
            "name": "home_box.label",
            "label": "Home box",
            "type": "string",
            "relation_depth": 1,
            "can_filter": True,
            "can_select": True,
            "can_group": True,
            "can_order": True,
            "can_date_bucket": False,
            "scope_dimension": True,
        }
    )
    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "Show order count by home box",
                    "resource_name": "orders",
                    "fields": ["home_box.label"],
                    "metrics": ["order_count"],
                }
            ],
        }
    )

    with pytest.raises(PlanValidationError, match="scope fields"):
        build_query_help(
            "Help me write order questions",
            provider=provider,
            capabilities=payload,
        )


def test_build_query_help_rejects_single_scope_dimension_fields() -> None:
    """Provider suggestions cannot use facility dimensions for one facility."""

    payload = capabilities_payload()
    resource = payload["resources"][0]
    resource["scope"] = {
        "level": "single",
        "kind": "facility",
        "guidance": "Visible rows are scoped to one facility.",
    }
    resource["fields"].append(
        {
            "name": "facility.name",
            "label": "Facility",
            "type": "string",
            "relation_depth": 1,
            "can_filter": True,
            "can_select": True,
            "can_group": True,
            "can_order": True,
            "can_date_bucket": False,
        }
    )
    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "Show order count by facility",
                    "resource_name": "orders",
                    "fields": ["facility.name"],
                    "metrics": ["order_count"],
                }
            ],
        }
    )

    with pytest.raises(PlanValidationError, match="scope fields"):
        build_query_help(
            "Help me write order questions",
            provider=provider,
            capabilities=payload,
        )


def test_build_query_help_rejects_generated_date_bucket_aliases() -> None:
    """Help suggestions should not teach users invalid result-key aliases."""

    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "Trend order count by created_at_month",
                    "resource_name": "orders",
                    "metrics": ["order_count"],
                    "date_fields": ["created_at"],
                }
            ],
        }
    )

    with pytest.raises(PlanValidationError, match="date-bucket aliases"):
        build_query_help(
            "Help me write order questions",
            provider=provider,
            capabilities=capabilities_payload(),
        )


def test_parse_query_help_rejects_extra_keys() -> None:
    """QueryHelp provider output is strict."""

    with pytest.raises(PlanValidationError, match="raw_sql"):
        parse_query_help({"answer": "Try this.", "raw_sql": "select 1"})


def test_deterministic_query_help_uses_capabilities_examples() -> None:
    """Offline help falls back to deterministic examples from capabilities."""

    result = build_deterministic_query_help(capabilities=capabilities_payload())

    assert result.answer == "You can query Orders."
    assert result.suggestions[0].question == "Show count of Orders by Status"
    assert result.suggestions[0].resource_name == "orders"


def test_deterministic_query_help_honors_requested_example_count() -> None:
    """Offline fallback can return up to ten examples when requested."""

    result = build_deterministic_query_help(
        capabilities=many_examples_capabilities_payload(),
        question="Give me 10 examples",
    )

    assert len(result.suggestions) == 10
    assert result.suggestions[0].question == "Show count of Orders 1 by Status"
    assert result.suggestions[-1].question == (
        "Trend Orders 5 by month using Created date"
    )
